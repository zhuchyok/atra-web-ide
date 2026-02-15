#!/usr/bin/env python3
"""
Замер времени ответа каждой модели Ollama и MLX.
Учитывается: (1) время развёртывания модели (холодный старт, загрузка в RAM) + (2) время ответа.
Для каждой модели: первый запрос = развёртывание + ответ (cold_total_sec), второй запрос = только ответ (warm_response_sec).
Оценка времени развёртывания = cold_total - warm_response. Рекомендованный таймаут = cold_total + буфер.
Таймаут на запрос по размеру: small 90 с, medium 120 с, large 180 с (MEASURE_TIMEOUT_*).

Запуск:
  OLLAMA_BASE_URL=http://localhost:11434 MLX_BASE_URL=http://localhost:11435 python scripts/measure_all_models_ollama_mlx.py

Выход: tmp/model_timings_ollama_mlx.json, tmp/model_timings_ollama_mlx.txt
"""

import json
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "tmp"
OUT_DIR.mkdir(exist_ok=True)

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
MLX_URL = os.getenv("MLX_BASE_URL", "http://localhost:11435").rstrip("/")
PROMPT = "Ответь одним словом: сколько будет 2+2?"

# Таймаут на один запрос по размеру (сек). Если модель даёт TimeoutError — не хватило времени (холодный старт/нагрузка), увеличьте через env.
REQUEST_TIMEOUT_SMALL = int(os.getenv("MEASURE_TIMEOUT_SMALL", "90"))   # 1.5 мин (маленькие могут грузиться 60+ с)
REQUEST_TIMEOUT_MEDIUM = int(os.getenv("MEASURE_TIMEOUT_MEDIUM", "120")) # 2 мин
REQUEST_TIMEOUT_LARGE = int(os.getenv("MEASURE_TIMEOUT_LARGE", "180"))   # 3 мин

# Буфер на запуск/развёртывание модели (холодный старт), сек
STARTUP_BUFFER_SMALL = int(os.getenv("MEASURE_STARTUP_BUFFER_SMALL", "30"))
STARTUP_BUFFER_MEDIUM = int(os.getenv("MEASURE_STARTUP_BUFFER_MEDIUM", "60"))
STARTUP_BUFFER_LARGE = int(os.getenv("MEASURE_STARTUP_BUFFER_LARGE", "90"))

EMBED_SKIP = {"nomic-embed-text", "nomic-embed", "mxbai-embed", "all-minilm"}


def size_category(model_name: str) -> str:
    """По имени модели: small (1–7B), medium (11–32B), large (70B+)."""
    name = (model_name or "").lower()
    # 104b, 70b, 33b, 32b, 11b, 7b, 3.8b, 3b, 1.1b
    if re.search(r"104b|70b|66b", name):
        return "large"
    if re.search(r"32b|33b|30b", name):
        return "medium"
    if re.search(r"11b", name):
        return "medium"
    if re.search(r"7b|8b", name):
        return "small"
    if re.search(r"3\.8b|3b|4b|1\.1b|1b|mini", name):
        return "small"
    return "medium"


def request_timeout_and_buffer(category: str) -> tuple[int, int]:
    if category == "small":
        return REQUEST_TIMEOUT_SMALL, STARTUP_BUFFER_SMALL
    if category == "large":
        return REQUEST_TIMEOUT_LARGE, STARTUP_BUFFER_LARGE
    return REQUEST_TIMEOUT_MEDIUM, STARTUP_BUFFER_MEDIUM


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
    """Один запрос к MLX /api/generate. Возвращает (elapsed_sec, status). MLX может возвращать category (reasoning, coding, default) — тогда в запросе передаём category."""
    try:
        import urllib.request
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
        return round(elapsed, 2), f"error:{type(e).__name__}"


def main():
    results = []
    print("=== Замер времени ответа каждой модели (Ollama + MLX) ===")
    print(f"   Ollama: {OLLAMA_URL}")
    print(f"   MLX:    {MLX_URL}")
    print(f"   Таймауты: small {REQUEST_TIMEOUT_SMALL} с, medium {REQUEST_TIMEOUT_MEDIUM} с, large {REQUEST_TIMEOUT_LARGE} с")
    print(f"   Буфер запуска: small +{STARTUP_BUFFER_SMALL} с, medium +{STARTUP_BUFFER_MEDIUM} с, large +{STARTUP_BUFFER_LARGE} с")
    print()

    total_models = 0
    for source, fetch_fn, measure_fn in [
        ("ollama", fetch_ollama_models, measure_ollama),
        ("mlx", fetch_mlx_models, measure_mlx),
    ]:
        models = fetch_fn()
        if not models:
            print(f"   [{source}] Нет моделей или сервис недоступен.")
            continue
        n = len(models)
        total_models += n
        print(f"   [{source}] Моделей: {n}. Замер: 1-й запрос = развёртывание + ответ, 2-й = только ответ.")
        for idx, model in enumerate(models, 1):
            cat = size_category(model)
            req_to, startup_buf = request_timeout_and_buffer(cat)
            print(f"      Замер {idx}/{n}: {model} (категория {cat})...", end=" ", flush=True)
            cold_total, status = measure_fn(model, req_to)
            warm_response: float = 0.0
            deploy_estimate: float = 0.0
            if status == "ok":
                warm_response, _ = measure_fn(model, req_to)
                deploy_estimate = round(max(0, cold_total - warm_response), 2)
            recommended = round(cold_total + startup_buf, 1)
            rec = {
                "model": model,
                "source": source,
                "size_category": cat,
                "cold_total_sec": cold_total,
                "warm_response_sec": warm_response,
                "deploy_estimate_sec": deploy_estimate,
                "measured_sec": cold_total,
                "request_timeout_sec": req_to,
                "startup_buffer_sec": startup_buf,
                "recommended_timeout_sec": recommended,
                "status": status,
            }
            results.append(rec)
            st = "✓" if status == "ok" else status
            if status == "ok":
                print(f"развёртывание ~{deploy_estimate} с, ответ (тёплый) {warm_response} с, холодный итого {cold_total} с → рекоменд. таймаут {recommended} с {st}", flush=True)
            else:
                print(f"холодный запрос {cold_total} с → рекоменд. таймаут {recommended} с {st}", flush=True)
        print()

    if not results:
        print("Нет результатов (Ollama и MLX недоступны или нет моделей).")
        return 0

    out_json = OUT_DIR / "model_timings_ollama_mlx.json"
    out_txt = OUT_DIR / "model_timings_ollama_mlx.txt"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("model\tsource\tsize_category\tdeploy_estimate_sec\twarm_response_sec\tcold_total_sec\trequest_timeout_sec\tstartup_buffer_sec\trecommended_timeout_sec\tstatus\n")
        for r in results:
            f.write(f"{r['model']}\t{r['source']}\t{r['size_category']}\t{r.get('deploy_estimate_sec', '')}\t{r.get('warm_response_sec', '')}\t{r['cold_total_sec']}\t{r['request_timeout_sec']}\t{r['startup_buffer_sec']}\t{r['recommended_timeout_sec']}\t{r['status']}\n")

    print("=== Итоговая таблица: развёртывание + ответ, рекомендуемый таймаут ===")
    print("-" * 115)
    print(f"{'Модель':<32} {'Источник':<8} {'Разверт.(с)':<12} {'Ответ(с)':<10} {'Холодный(с)':<12} {'Буфер(с)':<8} {'Рекоменд.(с)':<12} {'Статус':<12}")
    print("-" * 115)
    for r in results:
        dep = r.get("deploy_estimate_sec", "—") if r["status"] == "ok" else "—"
        warm = r.get("warm_response_sec", "—") if r["status"] == "ok" else "—"
        cold = r["cold_total_sec"] if r["cold_total_sec"] else "—"
        print(f"{r['model']:<32} {r['source']:<8} {str(dep):<12} {str(warm):<10} {str(cold):<12} {r['startup_buffer_sec']:<8} {r['recommended_timeout_sec']:<12} {r['status']:<12}")
    print("-" * 115)
    print(f"   Файлы: {out_json}, {out_txt}")
    print("   Рекомендованный таймаут = холодный запрос (развёртывание + ответ) + буфер; если ответа нет после него — «модель не отвечает».")
    if any(r["status"] != "ok" for r in results):
        print("   При TimeoutError/HTTPError возможно не хватило времени (холодный старт, нагрузка). Увеличьте: MEASURE_TIMEOUT_SMALL=120 MEASURE_TIMEOUT_MEDIUM=180 MEASURE_TIMEOUT_LARGE=300")
    return 0


if __name__ == "__main__":
    sys.exit(main())
