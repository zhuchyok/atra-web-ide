"""
Единая политика keep_alive для всех вызовов Ollama.
Учитывает: fallback-мозг (v3.5 при падении MLX), бессмертные модели, env, резерв MLX в RAM, размер модели.
См. docs/MODEL_UNLOADING_AND_MEMORY.md, docs/plans/*-ollama-unload-policy-design.md.
"""

import logging
import os
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

# Бессмертные модели (держать в памяти всегда) — дублируем список, чтобы не импортировать local_router
IMMORTAL_MODELS = {
    "nomic-embed-text",
    "nomic-embed-text:latest",
    "moondream",
    "moondream:latest",
}

# Модели эмбеддингов — выгружать сразу после ответа
EMBEDDING_MODELS = {"nomic-embed-text", "nomic-embed-text:latest"}

# Fallback-мозг: имена моделей Victoria v3.5 в Ollama (при падении MLX не выгружать)
FALLBACK_BRAIN_MODELS = ("victoria-wisdom-v3.5",)

# Модели для явной выгрузки при восстановлении MLX
OLLAMA_FALLBACK_UNLOAD_MODELS = ["victoria-wisdom-v3.5", "victoria-wisdom-v3.5:latest"]

DEFAULT_KEEP_ALIVE = 300

# Резерв RAM под MLX (модели всегда в памяти). В GB или в процентах — один из двух.
MLX_RAM_RESERVE_GB = float(os.getenv("MLX_RAM_RESERVE_GB", "0"))
MLX_RAM_RESERVE_PERCENT = float(os.getenv("MLX_RAM_RESERVE_PERCENT", "15"))
# Порог «низкая память» для агрессивной выгрузки: используемая RAM выше этого (с учётом резерва MLX)
RAM_CRITICAL_PERCENT = float(os.getenv("OLLAMA_RAM_CRITICAL_PERCENT", "85"))


def _effective_ram_percent() -> Optional[float]:
    """Используемая доля RAM с учётом резерва под MLX. None если psutil недоступен."""
    try:
        import psutil

        v = psutil.virtual_memory()
        used_percent = v.percent
        if MLX_RAM_RESERVE_PERCENT > 0:
            # Эффективная занятость для Ollama: считаем, что MLX резервирует X%
            used_percent = min(100.0, used_percent + MLX_RAM_RESERVE_PERCENT)
        if MLX_RAM_RESERVE_GB > 0:
            total_gb = v.total / (1024**3)
            available_gb = v.available / (1024**3)
            reserve_gb = min(MLX_RAM_RESERVE_GB, total_gb)
            # Доступно для Ollama после вычета резерва MLX
            available_for_ollama = max(0, available_gb - reserve_gb)
            used_percent = (
                100.0 - (100.0 * available_for_ollama / total_gb) if total_gb else used_percent
            )
        return used_percent
    except ImportError:
        return None
    except Exception:
        return None


def _model_size_gb(model_name: Optional[str]) -> Optional[float]:
    """Размер модели в GB из кэша сканера. None если неизвестно."""
    if not model_name:
        return None
    try:
        from available_models_scanner import _scan_cache

        if _scan_cache and "ollama_sizes" in _scan_cache:
            size_bytes = _scan_cache["ollama_sizes"].get(model_name, 0)
            if size_bytes > 0:
                return size_bytes / (1024**3)
    except Exception:
        pass
    return None


def _is_heavy_model(model_name: Optional[str], size_gb: Optional[float]) -> bool:
    """Тяжёлая модель для агрессивной выгрузки при нехватке RAM."""
    if size_gb is not None:
        return size_gb >= 5.0
    if not model_name:
        return False
    key = model_name.lower()
    return any(x in key for x in ("32b", "30b", "35b", "70b", "104b", "qwq", "deepseek-r1"))


def get_keep_alive(
    model_name: Optional[str] = None,
    category: Optional[str] = None,
    mlx_alive: bool = True,
    ram_percent: Optional[float] = None,
) -> Union[int, str]:
    """
    Единая политика keep_alive для запросов к Ollama.

    Порядок проверок:
    1. Fallback-мозг: mlx_alive=False и модель v3.5 → -1
    2. Бессмертные по имени (nomic, moondream) → -1
    3. Эмбеддинги → 0
    4. Env VICTORIA_OLLAMA_KEEP_ALIVE / OLLAMA_KEEP_ALIVE
    5. Адаптация по RAM (с учётом резерва MLX): при высокой занятости → 0 или 60 для тяжёлых
    6. Smart Keep-Alive по размеру модели
    7. Дефолт 300
    """
    # 1. Fallback-мозг: пока MLX недоступен, v3.5 в Ollama не выгружается
    if not mlx_alive and model_name and any(m in model_name for m in FALLBACK_BRAIN_MODELS):
        logger.info("🧠 [FALLBACK IMMORTALITY] MLX is down, making v3.5 immortal in Ollama")
        return -1

    # 2. Эмбеддинги — выгрузить сразу (до бессмертных, чтобы nomic возвращал 0)
    if category == "embedding" or (model_name and any(m in model_name for m in EMBEDDING_MODELS)):
        return 0

    # 3. Бессмертные по имени (moondream и т.д., но не nomic — он уже 0 выше)
    if model_name and any(m in model_name for m in IMMORTAL_MODELS):
        return -1

    # 4. Env
    raw = os.getenv("VICTORIA_OLLAMA_KEEP_ALIVE") or os.getenv("OLLAMA_KEEP_ALIVE")
    if raw is not None and str(raw).strip() != "":
        if str(raw).strip() == "-1":
            return -1
        try:
            return int(raw) if str(raw).strip().lstrip("-").isdigit() else raw
        except (ValueError, AttributeError):
            pass

    # 5. Адаптация по RAM (с учётом резерва MLX)
    effective_ram = ram_percent if ram_percent is not None else _effective_ram_percent()
    size_gb = _model_size_gb(model_name)
    if effective_ram is not None and effective_ram >= RAM_CRITICAL_PERCENT:
        if _is_heavy_model(model_name, size_gb):
            return 60
        if size_gb is not None and size_gb >= 5.0:
            return 300

    # 6. Smart Keep-Alive по размеру
    if model_name:
        if size_gb is not None and size_gb > 0:
            if size_gb > 30:
                return 60
            if size_gb > 15:
                return 300
            if size_gb > 5:
                return 600
            return 3600
        # Эвристика по имени
        key = model_name.lower()
        if "70b" in key or "104b" in key or "next" in key:
            return 60
        if "32b" in key or "30b" in key or "qwq" in key:
            return 300
        if "7b" in key or "8b" in key or "14b" in key:
            return 600
        if "3b" in key or "1b" in key or "tiny" in key or "embedding" in key:
            return 3600

    return DEFAULT_KEEP_ALIVE


async def unload_ollama_fallback_models(
    ollama_url: str, model_names: Optional[List[str]] = None
) -> None:
    """
    Явная выгрузка fallback-моделей в Ollama (best effort).
    Вызывать при переходе «MLX снова жив», чтобы освободить память от v3.5 в Ollama.
    """
    models = model_names or OLLAMA_FALLBACK_UNLOAD_MODELS
    try:
        import httpx
    except ImportError:
        logger.debug("httpx not available for unload_ollama_fallback_models")
        return
    url = ollama_url.rstrip("/")
    for name in models:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{url}/api/generate",
                    json={"model": name, "prompt": " ", "stream": False, "keep_alive": 0},
                )
            logger.info("Unloaded fallback model %s from Ollama (keep_alive=0)", name)
        except Exception as e:
            logger.debug("unload_ollama_fallback_models %s: %s", name, e)
