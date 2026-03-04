"""
Состояние восстановления MLX: отслеживание перехода «MLX был мёртв → MLX снова жив»
для событийной выгрузки fallback-моделей в Ollama.
"""

import logging
import time
from typing import List

logger = logging.getLogger(__name__)

_mlx_was_dead = False
_last_unload_on_recovery_time = 0.0
UNLOAD_DEBOUNCE_SEC = float(
    __import__("os").environ.get("OLLAMA_UNLOAD_ON_RECOVERY_DEBOUNCE_SEC", "300")
)  # 5 min


def is_mlx_recovery_event(healthy_nodes: List[dict]) -> bool:
    """
    Возвращает True если сейчас MLX есть в healthy_nodes и ранее его не было (переход «MLX снова жив»).
    Обновляет внутреннее состояние. Вызывать после каждого check_health.
    """
    global _mlx_was_dead
    has_mlx = any(
        "mlx" in (n.get("url") or "").lower() or "11435" in (n.get("url") or "")
        for n in (healthy_nodes or [])
    )
    if has_mlx:
        was_recovery = _mlx_was_dead
        _mlx_was_dead = False
        return was_recovery
    _mlx_was_dead = True
    return False


def should_run_unload_on_recovery() -> bool:
    """Проверка дебаунса: можно ли вызывать unload (не чаще раза в UNLOAD_DEBOUNCE_SEC)."""
    global _last_unload_on_recovery_time
    now = time.time()
    if now - _last_unload_on_recovery_time >= UNLOAD_DEBOUNCE_SEC:
        _last_unload_on_recovery_time = now
        return True
    return False
