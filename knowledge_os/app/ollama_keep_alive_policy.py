"""
Единая политика keep_alive для всех вызовов Ollama.
Учитывает: fallback-мозг (v3.5 при падении MLX), бессмертные модели, env, резерв MLX в RAM, размер модели.
См. docs/MODEL_UNLOADING_AND_MEMORY.md, docs/plans/*-ollama-unload-policy-design.md.
"""

import logging
import os
import time
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Track last MLX failure time for recovery cooldown
_last_mlx_failure_time: float = 0

# Бессмертные модели (держать в памяти всегда) — дублируем список, чтобы не импортировать local_router
# Финальный состав по §53 (2026-03-08 Singularity 24.7 Immortal Models Alignment):
# nomic, moondream, tinyllama, phi3.5 — всегда в памяти.
# victoria-wisdom-v3.5:latest НЕ здесь: при живом MLX → 60с (Wisdom Era §825), immortal только при падении MLX.
IMMORTAL_MODELS = {
    "nomic-embed-text",
    "moondream",
    "tinyllama",
    # Keep phi3.5 immortal for stable fast fallback path in tests/runtime.
    "phi3.5:3.8b",
}

# Cooldown constant for recovery
RECOVERY_COOLDOWN_SECONDS = 300  # 5 minutes

# Модели эмбеддингов — выгружать сразу после ответа
EMBEDDING_MODELS = {"nomic-embed-text", "nomic-embed-text:latest"}

# Fallback-мозг: имена моделей Victoria v3.5 в Ollama (при падении MLX не выгружать)
FALLBACK_BRAIN_MODELS = ("victoria-wisdom-v3.5",)

# Модели для явной выгрузки при восстановлении MLX
OLLAMA_FALLBACK_UNLOAD_MODELS = ["victoria-wisdom-v3.5", "victoria-wisdom-v3.5:latest"]

DEFAULT_KEEP_ALIVE = 300

# Burst/heavy workers (coding + vision): short idle so they do not starve Victoria/MLX.
# Override: OLLAMA_HEAVY_KEEP_ALIVE_SEC (seconds, default 180).
HEAVY_IDLE_KEEP_ALIVE = max(60, int(os.getenv("OLLAMA_HEAVY_KEEP_ALIVE_SEC", "180")))
HEAVY_NAME_MARKERS = (
    "qwen2.5-coder",
    "qwen2.5-coder:",
    "minicpm",
    "deepseek-coder",
    "coder-v2",
    "codellama",
)

# Резерв RAM под MLX (модели всегда в памяти). В GB или в процентах — один из двух.
MLX_RAM_RESERVE_GB = float(os.getenv("MLX_RAM_RESERVE_GB", "0"))
MLX_RAM_RESERVE_PERCENT = float(os.getenv("MLX_RAM_RESERVE_PERCENT", "15"))
# Порог «низкая память» для агрессивной выгрузки: используемая RAM выше этого (с учётом резерва MLX)
RAM_CRITICAL_PERCENT = float(os.getenv("OLLAMA_RAM_CRITICAL_PERCENT", "75"))


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


def _is_named_burst_heavy(model_name: Optional[str]) -> bool:
    """Coding/vision burst models that must not stay resident after idle."""
    if not model_name:
        return False
    key = model_name.lower()
    if any(m in key for m in HEAVY_NAME_MARKERS):
        return True
    # Generic large-coder tags (avoid matching victoria-wisdom etc.)
    if "14b" in key and ("coder" in key or "code" in key):
        return True
    return False


def _is_heavy_model(model_name: Optional[str], size_gb: Optional[float]) -> bool:
    """Тяжёлая модель для агрессивной выгрузки при нехватке RAM."""
    if _is_named_burst_heavy(model_name):
        return True
    if size_gb is not None:
        return size_gb >= 5.0
    if not model_name:
        return False
    key = model_name.lower()
    return any(x in key for x in ("32b", "30b", "35b", "70b", "104b", "qwq", "deepseek-r1", "14b"))


def _cap_heavy_keep_alive(
    model_name: Optional[str], value: Union[int, str]
) -> Union[int, str]:
    """Never let burst-heavy models stay warmer than HEAVY_IDLE_KEEP_ALIVE (except unload=0)."""
    if not _is_named_burst_heavy(model_name):
        return value
    if value == -1:
        return HEAVY_IDLE_KEEP_ALIVE
    if isinstance(value, int) and value > HEAVY_IDLE_KEEP_ALIVE:
        return HEAVY_IDLE_KEEP_ALIVE
    return value


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
    if model_name and any(m in model_name for m in FALLBACK_BRAIN_MODELS):
        if not mlx_alive:
            global _last_mlx_failure_time
            _last_mlx_failure_time = time.time()
            logger.info("🧠 [FALLBACK IMMORTALITY] MLX is down, making v3.5 immortal in Ollama")
            return -1
        else:
            # Если MLX жив, но мы в периоде кулдауна после сбоя — держим v3.5 живой
            if _last_mlx_failure_time > 0:
                elapsed = time.time() - _last_mlx_failure_time
                if elapsed < RECOVERY_COOLDOWN_SECONDS:
                    logger.info(
                        "🛡️ [RECOVERY COOLDOWN] MLX recovered %.1fs ago, keeping v3.5 alive for cooldown",
                        elapsed,
                    )
                    return -1
            # Если MLX жив и кулдаун прошёл, выгружаем v3.5 в Ollama быстрее (через 1 мин), так как мозг в MLX
            return 60

    # 1.5. Recovery cooldown: if MLX just recovered, keep Ollama models alive
    if mlx_alive and _last_mlx_failure_time > 0:
        elapsed = time.time() - _last_mlx_failure_time
        if elapsed < RECOVERY_COOLDOWN_SECONDS:
            # Для не-brain моделей тоже держим в памяти во время кулдауна
            # НО: Эмбеддинги всё равно выгружаем (проверка ниже)
            if not (
                category == "embedding"
                or (model_name and any(m in model_name for m in EMBEDDING_MODELS))
                or (category and "embedding" in str(category).lower())
            ):
                # Burst-heavy (coder/vision) must not become immortal during cooldown.
                return _cap_heavy_keep_alive(model_name, -1)
        else:
            # Кулдаун прошёл, сбрасываем время сбоя
            _last_mlx_failure_time = 0

    # 2. Бессмертные по имени (moondream и т.д.)
    if model_name and any(m in model_name for m in IMMORTAL_MODELS):
        return -1

    # 3. Эмбеддинги — адаптивная политика keep_alive
    if (
        category == "embedding"
        or (model_name and any(m in model_name for m in EMBEDDING_MODELS))
        or (category and "embedding" in str(category).lower())
    ):
        # [SINGULARITY 24.3] В Blitz Mode при высокой нагрузке держим эмбеддинги 5 минут
        # Это предотвращает постоянную выгрузку/загрузку при пачках задач
        # [SINGULARITY 24.7] Adaptive Resource Steering: Если RAM критична, выгружаем мгновенно
        try:
            effective_ram = ram_percent if ram_percent is not None else _effective_ram_percent()
            if effective_ram is not None and effective_ram >= RAM_CRITICAL_PERCENT:
                return 0
            if effective_ram is not None and effective_ram < RAM_CRITICAL_PERCENT:
                return 300
        except:
            pass
        return 0

    # 4. Env (global) — still capped for burst-heavy models
    raw = os.getenv("VICTORIA_OLLAMA_KEEP_ALIVE") or os.getenv("OLLAMA_KEEP_ALIVE")
    if raw is not None and str(raw).strip() != "":
        if str(raw).strip() == "-1":
            return _cap_heavy_keep_alive(model_name, -1)
        try:
            val: Union[int, str] = (
                int(raw) if str(raw).strip().lstrip("-").isdigit() else raw
            )
            return _cap_heavy_keep_alive(model_name, val)
        except (ValueError, AttributeError):
            pass

    if not model_name:
        return DEFAULT_KEEP_ALIVE

    # 4.5 Named burst-heavy (coder / minicpm): short idle by default
    if _is_named_burst_heavy(model_name):
        effective_ram = ram_percent if ram_percent is not None else _effective_ram_percent()
        if effective_ram is not None and effective_ram >= RAM_CRITICAL_PERCENT:
            return 60
        return HEAVY_IDLE_KEEP_ALIVE

    # 5. Адаптация по RAM (с учётом резерва MLX)
    effective_ram = ram_percent if ram_percent is not None else _effective_ram_percent()
    size_gb = _model_size_gb(model_name)
    if effective_ram is not None and effective_ram >= RAM_CRITICAL_PERCENT:
        # [SINGULARITY 24.7] Aggressive Resource Steering: Unload most models immediately if RAM is critical
        if model_name and any(m in model_name for m in IMMORTAL_MODELS):
            return -1
        if _is_heavy_model(model_name, size_gb):
            return 60
        return 60  # Keep light models for only 1 minute

    # 6. Smart Keep-Alive по размеру
    if model_name:
        if size_gb is not None and size_gb > 0:
            if size_gb > 30:
                return 60
            if size_gb > 15:
                return 300
            if size_gb > 5:
                return HEAVY_IDLE_KEEP_ALIVE
            return 3600
        # Эвристика по имени
        key = model_name.lower()
        if "70b" in key or "104b" in key or "next" in key:
            return 60
        if "32b" in key or "30b" in key or "qwq" in key:
            return 300
        if "7b" in key or "8b" in key or "14b" in key:
            return HEAVY_IDLE_KEEP_ALIVE
        if "3b" in key or "1b" in key or "tiny" in key or "embedding" in key:
            return 3600

    return DEFAULT_KEEP_ALIVE


async def unload_ollama_fallback_models(
    ollama_url: str, model_names: Optional[list[str]] = None
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
