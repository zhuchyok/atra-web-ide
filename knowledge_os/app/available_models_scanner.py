"""
Сканирование доступных моделей в MLX API Server и Ollama.
При запуске чата и по запросу — актуальный список моделей (могут меняться).
Кэш с TTL, чтобы не дергать /api/tags на каждый запрос.

ВАЖНО: Модели Ollama и MLX хранятся РАЗДЕЛЬНО, не смешиваются!
- Ollama: локальные модели на порту 11434
- MLX: Apple Silicon оптимизированные модели на порту 11435
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Кэш: {"mlx": [...], "ollama": [...], "scanned_at": float, "metrics": {"ollama": {...}, "mlx": {...}}}
_scan_cache: Optional[Dict] = None
_SCAN_TTL_SEC = 120  # 2 минуты
# Включить probe новых моделей при сканировании (замер load/unload/deploy/processing с запасом)
_PROBE_NEW_MODELS = os.getenv("MODEL_PROBE_ON_SCAN", "true").lower() in ("true", "1", "yes")

# ==============================================================================
# ПРИОРИТЕТЫ МОДЕЛЕЙ (от самой мощной к менее мощной)
# ВАЖНО: Списки для Ollama и MLX РАЗНЫЕ, не путать!
# ==============================================================================

# Приоритет для OLLAMA (порт 11434) - по мощности
OLLAMA_BEST_FIRST: List[str] = [
    "deepseek-r1:32b",          # 32B Reasoning (Board/VIP)
    "qwen2.5-coder:32b",        # 32B Main Engineer
    "qwq:32b",                  # 32B Logic
    "deepseek-r1:14b",          # 14B Fast Reasoning
    "glm-4.7-flash:q8_0",       # 31B Fast Reasoning
    "qwen3-coder:30b",          # 30B Previous Gen
    "llava:7b",                 # Vision 7B
    "moondream:latest",         # Vision small
    "tinyllama:1.1b-chat",      # Tiny fallback
]

# Приоритет для MLX (порт 11435)
MLX_BEST_FIRST: List[str] = [
    "qwen2.5:3b",                    # 3B light
    "phi3:mini-4k",                  # Mini
    "tinyllama:1.1b-chat",           # Tiny fallback
]

# Приоритеты моделей Ollama по категории (первый доступный из списка будет выбран)
OLLAMA_PRIORITY_BY_CATEGORY: Dict[str, List[str]] = {
    "fast": ["deepseek-r1:14b", "qwen2.5-coder:32b", "tinyllama:1.1b-chat"],
    "default": ["qwen2.5-coder:32b", "deepseek-r1:32b", "qwq:32b"],
    "general": ["qwen2.5-coder:32b", "glm-4.7-flash:q8_0", "deepseek-r1:14b"],
    "coding": ["qwen2.5-coder:32b", "qwq:32b", "qwen3-coder:30b"],
    "reasoning": ["deepseek-r1:32b", "qwq:32b", "glm-4.7-flash:q8_0"],
    "complex": ["deepseek-r1:32b", "qwen2.5-coder:32b", "qwq:32b"],
    "vision": ["moondream:latest", "llava:7b"],
    "vip": ["deepseek-r1:32b", "qwen2.5-coder:32b"],
}

# Приоритеты моделей MLX — только лёгкие (32b убран: ~35 ГБ процесс, Metal/память)
MLX_PRIORITY_BY_CATEGORY: Dict[str, List[str]] = {
    "fast": ["phi3.5:3.8b", "qwen2.5:3b", "tinyllama:1.1b-chat"],
    "default": ["phi3.5:3.8b", "qwen2.5:3b", "tinyllama:1.1b-chat"],
    "general": ["phi3.5:3.8b", "qwen2.5:3b", "tinyllama:1.1b-chat"],
    "coding": ["phi3.5:3.8b", "qwen2.5:3b", "tinyllama:1.1b-chat"],
    "reasoning": ["phi3.5:3.8b", "qwen2.5:3b", "tinyllama:1.1b-chat"],
    "complex": ["phi3.5:3.8b", "qwen2.5:3b", "tinyllama:1.1b-chat"],
}


@dataclass
class ModelSelection:
    """Результат выбора моделей - Ollama и MLX раздельно"""
    ollama_best: Optional[str] = None
    ollama_models: List[str] = None
    mlx_best: Optional[str] = None
    mlx_models: List[str] = None
    ollama_sizes: Dict[str, int] = None  # В байтах
    
    def __post_init__(self):
        if self.ollama_models is None:
            self.ollama_models = []
        if self.mlx_models is None:
            self.mlx_models = []
        if self.ollama_sizes is None:
            self.ollama_sizes = {}


def _mlx_scan_timeout() -> float:
    """Таймаут сканирования MLX (сек). Из Docker до host.docker.internal:11435 часто дольше — задать MLX_SCAN_TIMEOUT=12."""
    return float(os.getenv("MLX_SCAN_TIMEOUT", "5"))


def _ollama_scan_timeout() -> float:
    """Таймаут сканирования Ollama (сек). Из Docker до host.docker.internal:11434 часто дольше — по умолчанию 15 в Docker."""
    default = 15.0 if (os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() == "true") else 5.0
    return float(os.getenv("OLLAMA_SCAN_TIMEOUT", str(int(default))))


async def _fetch_mlx_models(mlx_url: str, timeout: Optional[float] = None) -> List[str]:
    """Сканирует MLX API Server (/api/tags или /), возвращает список имён моделей/категорий. При пустом/отключённом URL возвращает [] без запроса."""
    if not mlx_url or (mlx_url.strip().lower() in ("", "none", "disabled", "off")):
        return []
    if timeout is None:
        timeout = _mlx_scan_timeout()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            # MLX API Server: /api/tags возвращает {"models": [{"name": "fast", ...}, ...]}
            r = await client.get(f"{mlx_url}/api/tags")
            if r.status_code != 200:
                try:
                    r2 = await client.get(f"{mlx_url}/")
                    if r2.status_code == 200:
                        data = r2.json()
                        return list(data.get("available_models", []))
                except Exception:
                    pass
                return []
            data = r.json()
            models = data.get("models", [])
            return [m.get("name", "") for m in models if m.get("name")]
    except Exception as e:
        logger.debug("MLX scan: %s", e)
        return []


async def _fetch_ollama_models_with_details(ollama_url: str, timeout: Optional[float] = None) -> Tuple[List[str], Dict[str, int]]:
    """Сканирует Ollama /api/tags, возвращает список имён моделей и их размеры в байтах."""
    if timeout is None:
        timeout = _ollama_scan_timeout()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            if r.status_code != 200:
                return [], {}
            data = r.json()
            models_data = data.get("models", [])
            names = [m.get("name", "") for m in models_data if m.get("name")]
            sizes = {m.get("name"): m.get("size", 0) for m in models_data if m.get("name")}
            return names, sizes
    except Exception as e:
        logger.debug("Ollama scan: %s", e)
        return [], {}


async def _check_model_health(model_name: str, ollama_url: str) -> bool:
    """Проверяет здоровье модели через /api/show (Singularity 10.0)."""
    if not model_name or "embedding" in model_name: return True
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{ollama_url}/api/show", json={"name": model_name})
            return r.status_code == 200
    except Exception:
        return False

async def get_available_models(
    mlx_url: str,
    ollama_url: str,
    ttl_sec: int = _SCAN_TTL_SEC,
    force_refresh: bool = False,
) -> Tuple[List[str], List[str]]:
    """
    Возвращает (mlx_models, ollama_models) — списки доступных имён моделей.
    Использует кэш с TTL; при force_refresh или истечении TTL сканирует заново.
    При включённом MODEL_PROBE_ON_SCAN для новых моделей запускается probe (load/unload/deploy/processing с запасом).
    """
    global _scan_cache
    now = time.time()
    if not force_refresh and _scan_cache is not None and (now - _scan_cache.get("scanned_at", 0)) < ttl_sec:
        return (_scan_cache.get("mlx") or [], _scan_cache.get("ollama") or [])

    # Сканируем MLX и Ollama (теперь с размерами)
    mlx_task = asyncio.create_task(_fetch_mlx_models(mlx_url))
    ollama_task = asyncio.create_task(_fetch_ollama_models_with_details(ollama_url))
    
    mlx_list = await mlx_task
    ollama_list, ollama_sizes = await ollama_task

    # Фильтруем только рабочие модели (Singularity 10.0: Anti-Corruption)
    working_ollama = []
    working_sizes = {}
    for m in ollama_list:
        if await _check_model_health(m, ollama_url):
            working_ollama.append(m)
            working_sizes[m] = ollama_sizes.get(m, 0)
        else:
            logger.error(f"🚨 [CORRUPTION] Модель {m} повреждена или недоступна. Исключаем из роутинга.")
    
    ollama_list = working_ollama

    _scan_cache = {
        "mlx": mlx_list,
        "ollama": ollama_list,
        "ollama_sizes": working_sizes,
        "scanned_at": now,
        "mlx_url": mlx_url,
        "ollama_url": ollama_url,
    }

    # Проверка целостности модели (Singularity 10.0: Anti-Corruption)
    async def check_model_integrity(model_name: str) -> bool:
        """Проверяет, не повреждена ли модель (Ollama Tensor Check)."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Пытаемся получить информацию о модели
                r = await client.post(f"{ollama_url}/api/show", json={"name": model_name})
                if r.status_code != 200:
                    return False
                # Если Ollama может показать детали, модель скорее всего жива
                return True
        except Exception:
            return False

    # Probe новых моделей в фоне
    if _PROBE_NEW_MODELS and ollama_list:
        try:
            from app.model_performance_probe import probe_new_models_if_needed
            asyncio.create_task(
                probe_new_models_if_needed(
                    ollama_models=ollama_list,
                    mlx_models=mlx_list or [],
                    ollama_url=ollama_url,
                    mlx_url=mlx_url or "",
                )
            )
        except Exception as e:
            logger.debug("Probe new models (background): %s", e)

    # Подгрузить метрики из БД в кэш (для get_model_metrics)
    try:
        from app.model_performance_probe import get_metrics_for_models
        ollama_metrics = await get_metrics_for_models(ollama_list, "ollama")
        mlx_metrics = await get_metrics_for_models(mlx_list or [], "mlx")
        _scan_cache["metrics"] = {"ollama": ollama_metrics, "mlx": mlx_metrics}
    except Exception as e:
        logger.debug("Load model metrics: %s", e)
        _scan_cache["metrics"] = {"ollama": {}, "mlx": {}}

    logger.info("Сканирование моделей: MLX=%s, Ollama=%s", len(mlx_list), len(ollama_list))
    if mlx_list:
        logger.debug("MLX модели: %s", mlx_list[:10])
    if ollama_list:
        logger.debug("Ollama модели: %s", ollama_list[:10])
    return (mlx_list, ollama_list)


# ==============================================================================
# ФУНКЦИИ ВЫБОРА МОДЕЛЕЙ (Ollama и MLX РАЗДЕЛЬНО!)
# ==============================================================================

def pick_best_ollama(ollama_models: List[str]) -> Optional[str]:
    """
    Выбирает самую мощную модель из ТОЛЬКО Ollama списка.
    Не смешивает с MLX - это важно для executor/planner которые ходят в Ollama API.
    """
    if not ollama_models:
        return None
    lower_to_exact = {m.strip().lower(): m.strip() for m in ollama_models if m}
    for name in OLLAMA_BEST_FIRST:
        key = name.strip().lower()
        if key in lower_to_exact:
            return lower_to_exact[key]
    return ollama_models[0].strip() if ollama_models else None


def pick_best_mlx(mlx_models: List[str]) -> Optional[str]:
    """
    Выбирает самую мощную модель из ТОЛЬКО MLX списка.
    Не смешивает с Ollama - MLX модели запускаются через MLX API Server.
    """
    if not mlx_models:
        return None
    lower_to_exact = {m.strip().lower(): m.strip() for m in mlx_models if m}
    for name in MLX_BEST_FIRST:
        key = name.strip().lower()
        if key in lower_to_exact:
            return lower_to_exact[key]
    return mlx_models[0].strip() if mlx_models else None


def pick_ollama_for_category(category: str, ollama_models: List[str]) -> Optional[str]:
    """
    Выбирает модель Ollama для категории задачи.
    Возвращает первую доступную из приоритетного списка для этой категории.
    """
    if not ollama_models:
        return None
    priorities = OLLAMA_PRIORITY_BY_CATEGORY.get(category, OLLAMA_PRIORITY_BY_CATEGORY["default"])
    lower_to_exact = {m.strip().lower(): m.strip() for m in ollama_models if m}
    for name in priorities:
        key = name.strip().lower()
        if key in lower_to_exact:
            return lower_to_exact[key]
    return ollama_models[0].strip() if ollama_models else None


def pick_mlx_for_category(category: str, mlx_models: List[str]) -> Optional[str]:
    """
    Выбирает модель MLX для категории задачи.
    Возвращает первую доступную из приоритетного списка для этой категории.
    """
    if not mlx_models:
        return None
    priorities = MLX_PRIORITY_BY_CATEGORY.get(category, MLX_PRIORITY_BY_CATEGORY.get("default", []))
    lower_to_exact = {m.strip().lower(): m.strip() for m in mlx_models if m}
    for name in priorities:
        key = name.strip().lower()
        if key in lower_to_exact:
            return lower_to_exact[key]
    return mlx_models[0].strip() if mlx_models else None


def _default_ollama_url() -> str:
    import os
    if os.getenv("OLLAMA_API_URL"):
        return os.getenv("OLLAMA_API_URL", "").rstrip("/")
    if os.getenv("OLLAMA_BASE_URL"):
        return os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
    is_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() in ("true", "1")
    return "http://host.docker.internal:11434" if is_docker else "http://localhost:11434"


def _default_mlx_url() -> str:
    import os
    raw = os.getenv("MLX_API_URL", "").strip()
    if raw.lower() in ("none", "disabled", "off", "false"):
        return ""
    if raw:
        return raw.rstrip("/")
    is_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() in ("true", "1")
    return "http://host.docker.internal:11435" if is_docker else "http://localhost:11435"


async def scan_and_select_models(
    mlx_url: Optional[str] = None,
    ollama_url: Optional[str] = None,
    force_refresh: bool = False,
) -> ModelSelection:
    """
    Сканирует модели и выбирает лучшие из каждого источника РАЗДЕЛЬНО.
    
    Returns:
        ModelSelection с раздельными списками и лучшими моделями для Ollama и MLX
    """
    mlx_url = mlx_url or _default_mlx_url()
    ollama_url = ollama_url or _default_ollama_url()
    mlx_models, ollama_models = await get_available_models(mlx_url, ollama_url, force_refresh=force_refresh)
    
    # Фильтруем только рабочие модели (Singularity 10.0: Anti-Corruption)
    working_ollama = []
    for m in ollama_models:
        # Используем синхронную проверку или обертку, так как scan_and_select_models асинхронная
        # Но _check_model_health уже асинхронная, так что просто await
        try:
            # Небольшой хак: если мы внутри асинхронной функции, можем использовать await
            import httpx
            async def check_inner(name):
                if not name or "embedding" in name: return True
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        r = await client.post(f"{ollama_url}/api/show", json={"name": name})
                        return r.status_code == 200
                except Exception: return False
            
            # Для скорости проверяем только топ-5 моделей
            is_ok = True
            if m in OLLAMA_BEST_FIRST[:5]:
                is_ok = await check_inner(m)
            
            if is_ok:
                working_ollama.append(m)
            else:
                logger.error(f"🚨 [CORRUPTION] Модель {m} повреждена. Исключаем.")
        except Exception:
            working_ollama.append(m)
    
    ollama_models = working_ollama

    result = ModelSelection(
        ollama_models=ollama_models,
        ollama_best=pick_best_ollama(ollama_models),
        mlx_models=mlx_models,
        mlx_best=pick_best_mlx(mlx_models),
        ollama_sizes=_scan_cache.get("ollama_sizes", {})
    )
    
    logger.info("=" * 60)
    logger.info("📊 СКАНИРОВАНИЕ МОДЕЛЕЙ (Ollama и MLX РАЗДЕЛЬНО)")
    logger.info("=" * 60)
    logger.info("🔵 OLLAMA (порт 11434):")
    logger.info("   Найдено: %d моделей", len(ollama_models))
    logger.info("   Модели: %s", ollama_models[:10] if ollama_models else [])
    logger.info("   ✅ Лучшая: %s", result.ollama_best or "(нет)")
    logger.info("-" * 60)
    logger.info("🟢 MLX (порт 11435):")
    logger.info("   Найдено: %d моделей", len(mlx_models))
    logger.info("   Модели: %s", mlx_models[:10] if mlx_models else [])
    logger.info("   ✅ Лучшая: %s", result.mlx_best or "(нет)")
    logger.info("=" * 60)
    
    return result


# Обратная совместимость со старым API
def pick_best_available_victoria(
    ollama_models: List[str],
    mlx_models: Optional[List[str]] = None,
) -> Optional[str]:
    """
    DEPRECATED: Используйте pick_best_ollama() или pick_best_mlx() отдельно.
    
    Оставлено для обратной совместимости.
    Теперь возвращает лучшую модель ТОЛЬКО из Ollama (executor/planner ходят в Ollama API).
    """
    logger.warning("⚠️ pick_best_available_victoria() deprecated - используйте pick_best_ollama()")
    return pick_best_ollama(ollama_models)


def pick_ollama_model_for_category(category: str, ollama_models: List[str]) -> Optional[str]:
    """DEPRECATED: Используйте pick_ollama_for_category()"""
    return pick_ollama_for_category(category, ollama_models)


def invalidate_cache() -> None:
    """Сбросить кэш (например, при смене окружения)."""
    global _scan_cache
    _scan_cache = None


def get_model_metrics(
    model_name: str,
    source: str,
) -> Optional[Dict[str, Any]]:
    """
    Возвращает метрики модели (время загрузки, выгрузки, развёртывания, обработки с запасом)
    из кэша сканера. Кэш заполняется при get_available_models() из БД model_performance_metrics.
    
    Args:
        model_name: Имя модели (например phi3.5:3.8b)
        source: 'ollama' | 'mlx'
    
    Returns:
        Dict с ключами: load_time_sec, unload_time_sec, deploy_time_sec, processing_sec_per_1k_tokens,
        load_time_sec_with_margin, unload_time_sec_with_margin, deploy_time_sec_with_margin,
        processing_sec_per_1k_with_margin, margin_factor (свой у каждой модели), last_probed_at; или None если метрик нет.
    """
    if _scan_cache is None:
        return None
    metrics = (_scan_cache.get("metrics") or {}).get(source) or {}
    m = metrics.get(model_name)
    if m is None:
        return None
    # ModelMetrics dataclass -> dict для удобства (у каждой модели свои значения)
    return {
        "load_time_sec": m.load_time_sec,
        "unload_time_sec": m.unload_time_sec,
        "deploy_time_sec": m.deploy_time_sec,
        "processing_sec_per_1k_tokens": m.processing_sec_per_1k_tokens,
        "load_time_sec_with_margin": m.load_time_sec_with_margin,
        "unload_time_sec_with_margin": m.unload_time_sec_with_margin,
        "deploy_time_sec_with_margin": m.deploy_time_sec_with_margin,
        "processing_sec_per_1k_with_margin": m.processing_sec_per_1k_with_margin,
        "margin_factor": m.margin_factor,
        "last_probed_at": m.last_probed_at,
    }


async def get_available_models_with_metrics(
    mlx_url: str,
    ollama_url: str,
    ttl_sec: int = _SCAN_TTL_SEC,
    force_refresh: bool = False,
) -> Tuple[List[str], List[str], Dict[str, Dict[str, Dict[str, Any]]]]:
    """
    То же что get_available_models(), плюс третий элемент — метрики по моделям:
    {"ollama": {model_name: {...}}, "mlx": {model_name: {...}}}.
    Каждая запись содержит load_time_sec, unload_time_sec, deploy_time_sec, processing_sec_per_1k_tokens
    и варианты с запасом (_with_margin).
    """
    mlx_list, ollama_list = await get_available_models(mlx_url, ollama_url, ttl_sec=ttl_sec, force_refresh=force_refresh)
    metrics = (_scan_cache or {}).get("metrics") or {"ollama": {}, "mlx": {}}
    # Преобразуем ModelMetrics в dict
    out_metrics: Dict[str, Dict[str, Dict[str, Any]]] = {"ollama": {}, "mlx": {}}
    for src in ("ollama", "mlx"):
        for name, m in (metrics.get(src) or {}).items():
            out_metrics[src][name] = {
                "load_time_sec": m.load_time_sec,
                "unload_time_sec": m.unload_time_sec,
                "deploy_time_sec": m.deploy_time_sec,
                "processing_sec_per_1k_tokens": m.processing_sec_per_1k_tokens,
                "load_time_sec_with_margin": m.load_time_sec_with_margin,
                "unload_time_sec_with_margin": m.unload_time_sec_with_margin,
                "deploy_time_sec_with_margin": m.deploy_time_sec_with_margin,
                "processing_sec_per_1k_with_margin": m.processing_sec_per_1k_with_margin,
                "margin_factor": m.margin_factor,
                "last_probed_at": m.last_probed_at,
            }
    return (mlx_list, ollama_list, out_metrics)
