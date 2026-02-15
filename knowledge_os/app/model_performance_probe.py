"""
Probe для измерения времени загрузки, выгрузки, развёртывания и ответа по каждой модели.
При появлении новой модели (при скане, MODEL_PROBE_ON_SCAN) запускается тест:

  1. Время выгрузки (unload) — если модель загружена: keep_alive=0, ждём исчезновения из /api/ps.
  2. Время загрузки (load) — холодный запрос /api/generate: модель поднимается с нуля.
  3. Время развёртывания (deploy) — то же, что load (момент готовности к запросам).
  4. Время ответа (processing) — тёплый запрос (модель уже в памяти): чистый инференс, сек на 1k токенов.

Результаты сохраняются с запасом (margin, свой у каждой модели) в model_performance_metrics.
Используется сканером и таймаутами (local_router, mlx_api_server).
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
DEFAULT_MARGIN_FACTOR = float(os.getenv("MODEL_METRICS_MARGIN_FACTOR", "1.2"))
PROBE_TIMEOUT_LOAD_SEC = float(os.getenv("MODEL_PROBE_LOAD_TIMEOUT", "180"))
PROBE_TIMEOUT_UNLOAD_SEC = float(os.getenv("MODEL_PROBE_UNLOAD_TIMEOUT", "60"))


def _margin_factor_for_model(model_name: str) -> float:
    """Свой коэффициент запаса для каждой модели: тяжёлые — больший запас, лёгкие — меньший."""
    key = (model_name or "").lower()
    if "70b" in key or "104b" in key or "70" in key:
        return 1.4
    if "32b" in key or "32" in key:
        return 1.3
    if "7b" in key or "8b" in key:
        return 1.25
    if "3b" in key or "3.8" in key or "4k" in key:
        return 1.2
    if "1b" in key or "1.1" in key or "tiny" in key:
        return 1.15
    return DEFAULT_MARGIN_FACTOR


@dataclass
class ModelMetrics:
    """Метрики модели: измеренные и с запасом."""
    model_name: str
    source: str  # 'ollama' | 'mlx'
    base_url: Optional[str] = None
    load_time_sec: Optional[float] = None
    unload_time_sec: Optional[float] = None
    deploy_time_sec: Optional[float] = None
    processing_sec_per_1k_tokens: Optional[float] = None
    load_time_sec_with_margin: Optional[float] = None
    unload_time_sec_with_margin: Optional[float] = None
    deploy_time_sec_with_margin: Optional[float] = None
    processing_sec_per_1k_with_margin: Optional[float] = None
    margin_factor: float = DEFAULT_MARGIN_FACTOR
    last_probed_at: Optional[str] = None


def _apply_margin(value: Optional[float], margin: float) -> Optional[float]:
    if value is None:
        return None
    return round(value * margin, 2)


async def _ollama_loaded_models(base_url: str) -> List[str]:
    """Список загруженных моделей в Ollama (/api/ps)."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base_url.rstrip('/')}/api/ps")
            if r.status_code != 200:
                return []
            data = r.json()
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception as e:
        logger.debug("Ollama /api/ps: %s", e)
        return []


async def _ollama_probe(
    model_name: str,
    base_url: str,
    margin_factor: Optional[float] = None,
) -> Optional[ModelMetrics]:
    """
    Измеряет для Ollama-модели: load (cold), unload, один generate для processing.
    deploy_time_sec = load_time_sec (время до готовности).
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx не установлен, probe пропущен")
        return None

    base_url = base_url.rstrip("/")
    # У каждой модели свой коэффициент запаса (тяжёлые — больше, лёгкие — меньше)
    margin = margin_factor if margin_factor is not None else _margin_factor_for_model(model_name)
    metrics = ModelMetrics(model_name=model_name, source="ollama", base_url=base_url, margin_factor=margin)

    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_LOAD_SEC + 30) as client:
        # 1) Выгрузить модель если загружена (keep_alive=0)
        loaded = await _ollama_loaded_models(base_url)
        if model_name in loaded:
            t0 = time.perf_counter()
            await client.post(
                f"{base_url}/api/generate",
                json={"model": model_name, "prompt": "x", "stream": False, "keep_alive": 0, "num_predict": 1},
            )
            # Ждём выгрузки (poll /api/ps)
            for _ in range(int(PROBE_TIMEOUT_UNLOAD_SEC)):
                await asyncio.sleep(1)
                loaded = await _ollama_loaded_models(base_url)
                if model_name not in loaded:
                    break
            metrics.unload_time_sec = round(time.perf_counter() - t0, 2)
            metrics.unload_time_sec_with_margin = _apply_margin(metrics.unload_time_sec, margin)
            await asyncio.sleep(1)

        # 2) Холодный запрос = загрузка + первый инференс (время загрузки и развёртывания)
        t0 = time.perf_counter()
        r = await client.post(
            f"{base_url}/api/generate",
            json={
                "model": model_name,
                "prompt": "Say one word: ok",
                "stream": False,
                "num_predict": 10,
            },
            timeout=PROBE_TIMEOUT_LOAD_SEC,
        )
        load_elapsed = time.perf_counter() - t0
        if r.status_code != 200:
            logger.warning("Probe load/generate failed for %s: %s", model_name, r.status_code)
            return None

        metrics.load_time_sec = round(load_elapsed, 2)
        metrics.deploy_time_sec = metrics.load_time_sec
        metrics.load_time_sec_with_margin = _apply_margin(metrics.load_time_sec, margin)
        metrics.deploy_time_sec_with_margin = metrics.load_time_sec_with_margin

        # 3) Тёплый запрос (модель уже в памяти) — время ответа (чистый инференс)
        t1 = time.perf_counter()
        r2 = await client.post(
            f"{base_url}/api/generate",
            json={
                "model": model_name,
                "prompt": "Count from 1 to 5, one number per line.",
                "stream": False,
                "num_predict": 80,
            },
            timeout=120.0,
        )
        response_elapsed = time.perf_counter() - t1
        if r2.status_code == 200:
            data = r2.json()
            eval_count = data.get("eval_count") or 0
            if eval_count and response_elapsed > 0:
                metrics.processing_sec_per_1k_tokens = round(
                    (response_elapsed / (eval_count / 1000.0)), 2
                )
                metrics.processing_sec_per_1k_with_margin = _apply_margin(
                    metrics.processing_sec_per_1k_tokens, margin
                )
            else:
                metrics.processing_sec_per_1k_tokens = 15.0
                metrics.processing_sec_per_1k_with_margin = _apply_margin(15.0, margin)
        else:
            data = r.json()
            eval_count = data.get("eval_count") or 0
            if eval_count and load_elapsed > 0:
                metrics.processing_sec_per_1k_tokens = round(
                    (load_elapsed / (eval_count / 1000.0)), 2
                )
                metrics.processing_sec_per_1k_with_margin = _apply_margin(
                    metrics.processing_sec_per_1k_tokens, margin
                )
            else:
                metrics.processing_sec_per_1k_tokens = 15.0
                metrics.processing_sec_per_1k_with_margin = _apply_margin(15.0, margin)

        return metrics
    except Exception as e:
        logger.warning("Probe failed for %s (%s): %s", model_name, base_url, e)
        return None


async def save_metrics(metrics: ModelMetrics, db_url: str = DB_URL) -> bool:
    """Сохранить метрики в model_performance_metrics (UPSERT)."""
    if not ASYNCPG_AVAILABLE:
        return False
    try:
        conn = await asyncpg.connect(db_url)
        try:
            await conn.execute("""
                INSERT INTO model_performance_metrics (
                    model_name, source, base_url,
                    load_time_sec, unload_time_sec, deploy_time_sec, processing_sec_per_1k_tokens,
                    load_time_sec_with_margin, unload_time_sec_with_margin,
                    deploy_time_sec_with_margin, processing_sec_per_1k_with_margin,
                    margin_factor, probe_count, last_probed_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 1, NOW(), NOW())
                ON CONFLICT (model_name, source) DO UPDATE SET
                    base_url = EXCLUDED.base_url,
                    load_time_sec = EXCLUDED.load_time_sec,
                    unload_time_sec = EXCLUDED.unload_time_sec,
                    deploy_time_sec = EXCLUDED.deploy_time_sec,
                    processing_sec_per_1k_tokens = EXCLUDED.processing_sec_per_1k_tokens,
                    load_time_sec_with_margin = EXCLUDED.load_time_sec_with_margin,
                    unload_time_sec_with_margin = EXCLUDED.unload_time_sec_with_margin,
                    deploy_time_sec_with_margin = EXCLUDED.deploy_time_sec_with_margin,
                    processing_sec_per_1k_with_margin = EXCLUDED.processing_sec_per_1k_with_margin,
                    margin_factor = EXCLUDED.margin_factor,
                    probe_count = model_performance_metrics.probe_count + 1,
                    last_probed_at = NOW(),
                    updated_at = NOW()
            """,
                metrics.model_name,
                metrics.source,
                metrics.base_url,
                metrics.load_time_sec,
                metrics.unload_time_sec,
                metrics.deploy_time_sec,
                metrics.processing_sec_per_1k_tokens,
                metrics.load_time_sec_with_margin,
                metrics.unload_time_sec_with_margin,
                metrics.deploy_time_sec_with_margin,
                metrics.processing_sec_per_1k_with_margin,
                metrics.margin_factor,
            )
            return True
        finally:
            await conn.close()
    except Exception as e:
        logger.warning("Save model_performance_metrics failed: %s", e)
        return False
    return False


async def get_metrics_for_models(
    model_names: List[str],
    source: str,
    db_url: str = DB_URL,
) -> Dict[str, ModelMetrics]:
    """Загрузить из БД метрики по списку моделей. Возвращает dict[model_name] -> ModelMetrics."""
    result: Dict[str, ModelMetrics] = {}
    if not ASYNCPG_AVAILABLE or not model_names:
        return result
    try:
        conn = await asyncpg.connect(db_url)
        try:
            for name in model_names:
                row = await conn.fetchrow(
                    """
                    SELECT model_name, source, base_url,
                           load_time_sec, unload_time_sec, deploy_time_sec, processing_sec_per_1k_tokens,
                           load_time_sec_with_margin, unload_time_sec_with_margin,
                           deploy_time_sec_with_margin, processing_sec_per_1k_with_margin,
                           margin_factor, last_probed_at
                    FROM model_performance_metrics
                    WHERE model_name = $1 AND source = $2
                    """,
                    name,
                    source,
                )
                if row:
                    result[name] = ModelMetrics(
                        model_name=row["model_name"],
                        source=row["source"],
                        base_url=row["base_url"],
                        load_time_sec=float(row["load_time_sec"]) if row["load_time_sec"] is not None else None,
                        unload_time_sec=float(row["unload_time_sec"]) if row["unload_time_sec"] is not None else None,
                        deploy_time_sec=float(row["deploy_time_sec"]) if row["deploy_time_sec"] is not None else None,
                        processing_sec_per_1k_tokens=float(row["processing_sec_per_1k_tokens"]) if row["processing_sec_per_1k_tokens"] is not None else None,
                        load_time_sec_with_margin=float(row["load_time_sec_with_margin"]) if row["load_time_sec_with_margin"] is not None else None,
                        unload_time_sec_with_margin=float(row["unload_time_sec_with_margin"]) if row["unload_time_sec_with_margin"] is not None else None,
                        deploy_time_sec_with_margin=float(row["deploy_time_sec_with_margin"]) if row["deploy_time_sec_with_margin"] is not None else None,
                        processing_sec_per_1k_with_margin=float(row["processing_sec_per_1k_with_margin"]) if row["processing_sec_per_1k_with_margin"] is not None else None,
                        margin_factor=float(row["margin_factor"] or DEFAULT_MARGIN_FACTOR),
                        last_probed_at=row["last_probed_at"].isoformat() if row.get("last_probed_at") else None,
                    )
        finally:
            await conn.close()
    except Exception as e:
        logger.debug("get_metrics_for_models: %s", e)
    return result


async def probe_new_models_if_needed(
    ollama_models: List[str],
    mlx_models: List[str],
    ollama_url: str,
    mlx_url: str,
    db_url: str = DB_URL,
    margin_factor: float = DEFAULT_MARGIN_FACTOR,
    max_probes_per_run: int = 2,
) -> Dict[str, ModelMetrics]:
    """
    Для моделей, по которым ещё нет записей в model_performance_metrics (или они старые),
    запускает probe и сохраняет результат с запасом.
    Ограничение: max_probes_per_run моделей за один вызов (чтобы не блокировать сканер).
    """
    results: Dict[str, ModelMetrics] = {}
    # Пока probe только для Ollama (MLX сложнее — свой API)
    existing = await get_metrics_for_models(ollama_models, "ollama", db_url)
    to_probe = [m for m in ollama_models if m not in existing][:max_probes_per_run]
    for model_name in to_probe:
        m = await _ollama_probe(model_name, ollama_url, margin_factor)
        if m:
            await save_metrics(m, db_url)
            results[model_name] = m
            logger.info(
                "Probe %s: load=%.1fs unload=%.1fs deploy=%.1fs processing_1k=%.1fs (margin=%.2f)",
                model_name,
                m.load_time_sec or 0,
                m.unload_time_sec or 0,
                m.deploy_time_sec or 0,
                m.processing_sec_per_1k_tokens or 0,
                m.margin_factor,
            )
    return results


def get_timeout_estimate_with_metrics(
    model_name: str,
    source: str,
    max_tokens: int,
    metrics: Optional[ModelMetrics] = None,
    fallback_load_sec: float = 60.0,
    fallback_inference_sec_per_1k: float = 30.0,
    margin_sec: float = 30.0,
) -> float:
    """
    Оценка таймаута запроса с учётом метрик этой модели (с запасом).
    Если metrics передан — используем load_time_sec_with_margin и processing_sec_per_1k_with_margin.
    """
    if metrics and metrics.load_time_sec_with_margin is not None:
        load_sec = metrics.load_time_sec_with_margin
    else:
        load_sec = fallback_load_sec
    if metrics and metrics.processing_sec_per_1k_with_margin is not None:
        inf_sec_per_1k = metrics.processing_sec_per_1k_with_margin
    else:
        inf_sec_per_1k = fallback_inference_sec_per_1k
    inference_sec = (max_tokens / 1000.0) * inf_sec_per_1k
    return max(60.0, load_sec + inference_sec + margin_sec)


def get_timeout_estimate_from_metrics_dict(
    max_tokens: int,
    metrics_dict: Optional[Dict[str, Any]] = None,
    fallback_load_sec: float = 60.0,
    fallback_inference_sec_per_1k: float = 30.0,
    margin_sec: float = 30.0,
) -> float:
    """
    Таймаут по словарю метрик (результат get_model_metrics). У каждой модели свои значения.
    """
    if not metrics_dict:
        return max(60.0, fallback_load_sec + (max_tokens / 1000.0) * fallback_inference_sec_per_1k + margin_sec)
    load_sec = metrics_dict.get("load_time_sec_with_margin")
    if load_sec is None:
        load_sec = fallback_load_sec
    inf_sec_per_1k = metrics_dict.get("processing_sec_per_1k_with_margin")
    if inf_sec_per_1k is None:
        inf_sec_per_1k = fallback_inference_sec_per_1k
    inference_sec = (max_tokens / 1000.0) * inf_sec_per_1k
    return max(60.0, load_sec + inference_sec + margin_sec)
