#!/usr/bin/env python3
"""
Замер холодного запуска и времени ответа по каждой модели (Ollama + MLX).
Перед холодным замером модель выгружается (Ollama: API keep_alive=0; MLX: выгрузка через API не поддерживается).
Таймаут на ответ: 30 минут по умолчанию (MEASURE_REQUEST_TIMEOUT=1800).

Запуск:
  OLLAMA_BASE_URL=http://localhost:11434 MLX_BASE_URL=http://localhost:11435 python scripts/measure_cold_start_all_models.py
  # Только указанные модели: MEASURE_MODELS=glm-4.7-flash:q8_0,llava:7b python ...
  # Только MLX: MEASURE_SOURCE=mlx MLX_BASE_URL=http://localhost:11435 python ...
  # Только Ollama: MEASURE_SOURCE=ollama python ...

Выход: tmp/cold_start_timings.json, tmp/cold_start_timings.txt, таблица в консоль.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "tmp"
OUT_DIR.mkdir(exist_ok=True)

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
MLX_URL = os.getenv("MLX_BASE_URL", "http://localhost:11435").rstrip("/")
PROMPT = "Ответь одним словом: сколько будет 2+2?"

# Таймаут на один запрос: 30 минут по умолчанию (тяжёлые/vision-модели могут грузиться дольше)
REQUEST_TIMEOUT = int(os.getenv("MEASURE_REQUEST_TIMEOUT", str(30 * 60)))  # 1800 сек

# Пауза после выгрузки модели перед холодным запросом (сек)
UNLOAD_WAIT_SEC = int(os.getenv("MEASURE_UNLOAD_WAIT_SEC", "5"))
# Таймаут на запрос выгрузки (Ollama: generate с keep_alive=0 выполняет один короткий ответ, затем выгружает)
UNLOAD_REQUEST_TIMEOUT = int(os.getenv("MEASURE_UNLOAD_REQUEST_TIMEOUT", "120"))

# Только эти модели (через запятую); пусто = все модели. Пример: MEASURE_MODELS=glm-4.7-flash:q8_0,llava:7b
MEASURE_MODELS_FILTER = os.getenv("MEASURE_MODELS", "").strip()
if MEASURE_MODELS_FILTER:
    MEASURE_MODELS_SET = {m.strip() for m in MEASURE_MODELS_FILTER.split(",") if m.strip()}
else:
    MEASURE_MODELS_SET = None

# Какой источник замерять: all | ollama | mlx
MEASURE_SOURCE = (os.getenv("MEASURE_SOURCE", "all") or "all").strip().lower()

# Пауза между моделями MLX (сек), чтобы не упираться в rate limit (150 запросов / 90 с)
MEASURE_MLX_DELAY_BETWEEN_MODELS_SEC = int(os.getenv("MEASURE_MLX_DELAY_BETWEEN_MODELS_SEC", "5"))

# По умолчанию не замерять тяжёлые MLX-модели (70B/104B) — они роняют Python (Metal OOM). 0 = замерять все.
MEASURE_MLX_SKIP_HEAVY = os.getenv("MEASURE_MLX_SKIP_HEAVY", "1").strip().lower() in ("1", "true", "yes")
MLX_HEAVY_SKIP = {"deepseek-r1-distill-llama:70b", "llama3.3:70b", "command-r-plus:104b", "reasoning"}  # reasoning = 70B

EMBED_SKIP = {"nomic-embed-text", "nomic-embed", "mxbai-embed", "all-minilm"}


def _urlopen_post(url: str, data: bytes, timeout: int):
    import urllib.request
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        r.read()


def unload_ollama(model: str) -> bool:
    """Выгрузить модель из памяти Ollama (keep_alive=0: один короткий ответ, затем выгрузка). Возвращает True при успехе."""
    try:
        payload = json.dumps({
            "model": model,
            "prompt": ".",
            "stream": False,
            "keep_alive": 0,
        }).encode()
        _urlopen_post(f"{OLLAMA_URL}/api/generate", payload, timeout=UNLOAD_REQUEST_TIMEOUT)
        return True
    except Exception:
        return False


def fetch_ollama_models() -> list[str]:
    try:
        import urllib.request
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
    except Exception:
        return []
    models = []
    for m in data.get("models") or []:
        name = (m.get("name") or "").strip()
        if not name:
            continue
        base = name.split(":")[0].lower()
        if base in EMBED_SKIP:
            continue
        models.append(name)
    return models


def fetch_mlx_models() -> list[str]:
    try:
        import urllib.request
        req = urllib.request.Request(f"{MLX_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
    except Exception:
        try:
            req = urllib.request.Request(MLX_URL + "/")
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            return list(data.get("available_models", []) or [])
        except Exception:
            return []
    models = []
    for m in data.get("models") or []:
        name = (m.get("name") or "").strip()
        if name:
            models.append(name)
    return models


def measure_ollama(model: str, timeout_sec: int) -> tuple[float, str]:
    """Один запрос к Ollama /api/generate. Возвращает (elapsed_sec, status)."""
    try:
        import urllib.request
        payload = json.dumps({"model": model, "prompt": PROMPT, "stream": False}).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=timeout_sec) as r:
            r.read()
        elapsed = time.perf_counter() - t0
        return round(elapsed, 2), "ok"
    except Exception as e:
        elapsed = timeout_sec if "timeout" in str(e).lower() else 0
        return round(elapsed, 2), f"error:{type(e).__name__}"


def measure_mlx(model: str, timeout_sec: int) -> tuple[float, str]:
    """Один запрос к MLX /api/generate. Совместимость с knowledge_os (model или category). Возвращает (elapsed_sec, status)."""
    try:
        import urllib.request
        import urllib.error
        body: dict = {"prompt": PROMPT, "stream": False, "max_tokens": 50}
        if model in ("reasoning", "coding", "fast", "tiny", "default"):
            body["category"] = model
        else:
            body["model"] = model
        payload = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{MLX_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=timeout_sec) as r:
            r.read()
        elapsed = time.perf_counter() - t0
        return round(elapsed, 2), "ok"
    except Exception as e:
        elapsed = timeout_sec if "timeout" in str(e).lower() else 0
        detail = str(e)
        if hasattr(e, "code"):
            detail = f"HTTP {e.code}"
        if hasattr(e, "read") and callable(getattr(e, "read", None)):
            try:
                body_err = e.read().decode()[:200]
                detail += f" {body_err}"
            except Exception:
                pass
        return round(elapsed, 2), f"error:{type(e).__name__}({detail})"


def main():
    results = []
    print("=== Замер холодного запуска и ответа по каждой модели (Ollama + MLX) ===")
    print(f"   Ollama: {OLLAMA_URL}")
    print(f"   MLX:    {MLX_URL}")
    print(f"   Таймаут на ответ: {REQUEST_TIMEOUT} с ({REQUEST_TIMEOUT // 60} мин)")
    print(f"   Перед холодным замером: выгрузка модели (Ollama), пауза {UNLOAD_WAIT_SEC} с")
    print()

    sources = []
    if MEASURE_SOURCE in ("all", "ollama"):
        sources.append(("ollama", fetch_ollama_models, measure_ollama, unload_ollama))
    if MEASURE_SOURCE in ("all", "mlx"):
        sources.append(("mlx", fetch_mlx_models, measure_mlx, lambda m: False))  # MLX: выгрузка через API не поддерживается

    for source, fetch_fn, measure_fn, unload_fn in sources:
        models = fetch_fn()
        if not models:
            print(f"   [{source}] Нет моделей или сервис недоступен.")
            continue
        if MEASURE_MODELS_SET is not None:
            models = [m for m in models if m in MEASURE_MODELS_SET]
            if not models:
                print(f"   [{source}] После фильтра MEASURE_MODELS ни одной модели не осталось.")
                continue
        if source == "mlx" and MEASURE_MLX_SKIP_HEAVY:
            skipped = [m for m in models if m in MLX_HEAVY_SKIP]
            models = [m for m in models if m not in MLX_HEAVY_SKIP]
            if skipped:
                print(f"   [{source}] Пропуск тяжёлых (70B/104B), чтобы не ронять MLX: {skipped}")
        n = len(models)
        print(f"   [{source}] Моделей: {n}. Выгрузка → холодный запрос → тёплый запрос (таймаут {REQUEST_TIMEOUT} с).")
        for idx, model in enumerate(models, 1):
            if source == "mlx" and idx > 1:
                time.sleep(MEASURE_MLX_DELAY_BETWEEN_MODELS_SEC)
            print(f"      {idx}/{n}: {model} ...", end=" ", flush=True)
            # 1) Выгрузить модель (Ollama — через API; MLX — нет API)
            if unload_fn(model):
                time.sleep(UNLOAD_WAIT_SEC)
            # 2) Холодный запрос = развёртывание + ответ
            cold_total, status = measure_fn(model, REQUEST_TIMEOUT)
            warm_response: float = 0.0
            deploy_estimate: float = 0.0
            if status == "ok":
                warm_response, _ = measure_fn(model, REQUEST_TIMEOUT)
                deploy_estimate = round(max(0, cold_total - warm_response), 2)
            rec = {
                "model": model,
                "source": source,
                "cold_total_sec": cold_total,
                "warm_response_sec": warm_response,
                "deploy_estimate_sec": deploy_estimate,
                "request_timeout_sec": REQUEST_TIMEOUT,
                "status": status,
            }
            results.append(rec)
            st = "✓" if status == "ok" else status
            if status == "ok":
                print(f"холодный: {cold_total} с (развёртывание ~{deploy_estimate} с, ответ ~{warm_response} с) {st}", flush=True)
            else:
                print(f"холодный: {cold_total} с {st}", flush=True)
        print()

    if not results:
        print("Нет результатов (Ollama и MLX недоступны или нет моделей).")
        return 0

    out_json = OUT_DIR / "cold_start_timings.json"
    out_txt = OUT_DIR / "cold_start_timings.txt"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("model\tsource\tdeploy_estimate_sec\twarm_response_sec\tcold_total_sec\trequest_timeout_sec\tstatus\n")
        for r in results:
            f.write(f"{r['model']}\t{r['source']}\t{r.get('deploy_estimate_sec', '')}\t{r.get('warm_response_sec', '')}\t{r['cold_total_sec']}\t{r['request_timeout_sec']}\t{r['status']}\n")

    # Обновить справочники в configs/ по источнику (ollama / mlx)
    config_dir = REPO_ROOT / "configs"
    for src in ("ollama", "mlx"):
        subset = [r for r in results if r["source"] == src]
        if not subset:
            continue
        payload = {
            "_comment": "Замеры холодного запуска и ответа. Использовать для таймаутов. Обновляется скриптом measure_cold_start_all_models.py.",
            "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": src,
            "models": [
                {
                    "model": r["model"],
                    "source": r["source"],
                    "deploy_estimate_sec": r.get("deploy_estimate_sec", 0),
                    "warm_response_sec": r.get("warm_response_sec", 0),
                    "cold_total_sec": r["cold_total_sec"],
                    "recommended_timeout_sec": round(r["cold_total_sec"] + 60) if r["status"] == "ok" else None,
                }
                for r in subset
            ],
        }
        config_file = config_dir / f"{src}_model_timings.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"   Справочник обновлён: {config_file}")

    print("=== Итоговая таблица: холодный запуск и ответ ===")
    print("-" * 90)
    print(f"{'Модель':<32} {'Источник':<8} {'Развёртывание (с)':<18} {'Ответ (с)':<12} {'Холодный итого (с)':<18} {'Статус':<10}")
    print("-" * 90)
    for r in results:
        dep = r.get("deploy_estimate_sec", "—") if r["status"] == "ok" else "—"
        warm = r.get("warm_response_sec", "—") if r["status"] == "ok" else "—"
        cold = r["cold_total_sec"] if r["cold_total_sec"] else "—"
        print(f"{r['model']:<32} {r['source']:<8} {str(dep):<18} {str(warm):<12} {str(cold):<18} {r['status']:<10}")
    print("-" * 90)
    print(f"   Файлы: {out_json}, {out_txt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
