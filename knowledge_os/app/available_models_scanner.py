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
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Кэш: {"mlx": [...], "ollama": [...], "scanned_at": float}
_scan_cache: Optional[Dict] = None
_SCAN_TTL_SEC = 120  # 2 минуты

# ==============================================================================
# ПРИОРИТЕТЫ МОДЕЛЕЙ (от самой мощной к менее мощной)
# ВАЖНО: Списки для Ollama и MLX РАЗНЫЕ, не путать!
# ==============================================================================

# Приоритет для OLLAMA (порт 11434) - по мощности
OLLAMA_BEST_FIRST: List[str] = [
    "qwq:32b",              # 32B reasoning
    "qwen2.5-coder:32b",    # 32B coding
    "glm-4.7-flash:q8_0",   # Fast reasoning
    "llava:7b",             # Vision 7B
    "phi3.5:3.8b",          # Fast general
    "moondream:latest",     # Vision small
    "tinyllama:1.1b-chat",  # Tiny fallback
]

# Приоритет для MLX (порт 11435) - по мощности  
MLX_BEST_FIRST: List[str] = [
    "command-r-plus:104b",           # 104B - самая мощная
    "deepseek-r1-distill-llama:70b", # 70B reasoning
    "llama3.3:70b",                  # 70B general
    "qwen2.5-coder:32b",             # 32B coding
    "phi3.5:3.8b",                   # Fast general
    "qwen2.5:3b",                    # 3B light
    "phi3:mini-4k",                  # Mini
    "tinyllama:1.1b-chat",           # Tiny fallback
]

# Приоритеты моделей Ollama по категории (первый доступный из списка будет выбран)
OLLAMA_PRIORITY_BY_CATEGORY: Dict[str, List[str]] = {
    "fast": ["phi3.5:3.8b", "tinyllama:1.1b-chat", "moondream:latest"],
    "default": ["qwen2.5-coder:32b", "phi3.5:3.8b", "tinyllama:1.1b-chat"],
    "general": ["qwen2.5-coder:32b", "qwq:32b", "glm-4.7-flash:q8_0", "phi3.5:3.8b"],
    "coding": ["qwen2.5-coder:32b", "qwq:32b", "phi3.5:3.8b"],
    "reasoning": ["qwq:32b", "glm-4.7-flash:q8_0", "qwen2.5-coder:32b"],
    "complex": ["qwq:32b", "qwen2.5-coder:32b", "glm-4.7-flash:q8_0"],
    "vision": ["llava:7b", "moondream:latest"],
}

# Приоритеты моделей MLX по категории
MLX_PRIORITY_BY_CATEGORY: Dict[str, List[str]] = {
    "fast": ["phi3.5:3.8b", "qwen2.5:3b", "tinyllama:1.1b-chat"],
    "default": ["qwen2.5-coder:32b", "deepseek-r1-distill-llama:70b", "phi3.5:3.8b"],
    "general": ["command-r-plus:104b", "llama3.3:70b", "qwen2.5-coder:32b"],
    "coding": ["qwen2.5-coder:32b", "deepseek-r1-distill-llama:70b", "phi3.5:3.8b"],
    "reasoning": ["deepseek-r1-distill-llama:70b", "command-r-plus:104b", "llama3.3:70b"],
    "complex": ["command-r-plus:104b", "deepseek-r1-distill-llama:70b", "llama3.3:70b"],
}


@dataclass
class ModelSelection:
    """Результат выбора моделей - Ollama и MLX раздельно"""
    ollama_best: Optional[str] = None
    ollama_models: List[str] = None
    mlx_best: Optional[str] = None
    mlx_models: List[str] = None
    
    def __post_init__(self):
        if self.ollama_models is None:
            self.ollama_models = []
        if self.mlx_models is None:
            self.mlx_models = []


async def _fetch_mlx_models(mlx_url: str, timeout: float = 5.0) -> List[str]:
    """Сканирует MLX API Server (/api/tags или /), возвращает список имён моделей/категорий."""
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


async def _fetch_ollama_models(ollama_url: str, timeout: float = 5.0) -> List[str]:
    """Сканирует Ollama /api/tags, возвращает список имён моделей."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            if r.status_code != 200:
                return []
            data = r.json()
            models = data.get("models", [])
            return [m.get("name", "") for m in models if m.get("name")]
    except Exception as e:
        logger.debug("Ollama scan: %s", e)
        return []


async def get_available_models(
    mlx_url: str,
    ollama_url: str,
    ttl_sec: int = _SCAN_TTL_SEC,
    force_refresh: bool = False,
) -> Tuple[List[str], List[str]]:
    """
    Возвращает (mlx_models, ollama_models) — списки доступных имён моделей.
    Использует кэш с TTL; при force_refresh или истечении TTL сканирует заново.
    """
    global _scan_cache
    now = time.time()
    if not force_refresh and _scan_cache is not None and (now - _scan_cache.get("scanned_at", 0)) < ttl_sec:
        return (_scan_cache.get("mlx") or [], _scan_cache.get("ollama") or [])

    mlx_list, ollama_list = await asyncio.gather(
        _fetch_mlx_models(mlx_url),
        _fetch_ollama_models(ollama_url),
    )
    _scan_cache = {
        "mlx": mlx_list,
        "ollama": ollama_list,
        "scanned_at": now,
    }
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


async def scan_and_select_models(
    mlx_url: str = "http://localhost:11435",
    ollama_url: str = "http://localhost:11434",
    force_refresh: bool = False,
) -> ModelSelection:
    """
    Сканирует модели и выбирает лучшие из каждого источника РАЗДЕЛЬНО.
    
    Returns:
        ModelSelection с раздельными списками и лучшими моделями для Ollama и MLX
    """
    mlx_models, ollama_models = await get_available_models(mlx_url, ollama_url, force_refresh=force_refresh)
    
    result = ModelSelection(
        ollama_models=ollama_models,
        ollama_best=pick_best_ollama(ollama_models),
        mlx_models=mlx_models,
        mlx_best=pick_best_mlx(mlx_models),
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
