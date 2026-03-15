"""
Централизованная проверка флагов окружения для Knowledge OS.

Используется во всех модулях, где нужна проверка режима работы (STRICT_LOCAL и др.).
Единый источник истины для конфигурации (12-Factor App).
"""

import os
from typing import Any, Dict

# Счётчики для метрик Prometheus (STRICT_LOCAL)
_strict_local_qa_skip_count: int = 0
_strict_local_safety_skip_count: int = 0


def is_strict_local() -> bool:
    """
    Проверяет, включён ли строго локальный режим (STRICT_LOCAL).

    При STRICT_LOCAL=true:
    - Все запросы обслуживаются только локальными моделями (MLX + Ollama)
    - При недоступности локальных моделей возвращается явная ошибка
    - Нет fallback на cursor-agent или облачные API
    - Safety/QA не выполняют reroute_to_cloud

    Returns:
        bool: True если STRICT_LOCAL включён, иначе False
    """
    return os.getenv("STRICT_LOCAL", "").lower() in ("1", "true", "yes")


def get_strict_local_status() -> dict:
    """
    Возвращает текущий статус STRICT_LOCAL для логирования и метрик.

    Returns:
        dict: {"enabled": bool, "mode": str}
    """
    enabled = is_strict_local()
    return {"enabled": enabled, "mode": "strict_local" if enabled else "normal"}


def increment_strict_local_qa_skip() -> None:
    """Увеличивает счётчик QA reroute_to_cloud, пропущенных из-за STRICT_LOCAL."""
    global _strict_local_qa_skip_count
    _strict_local_qa_skip_count += 1


def increment_strict_local_safety_skip() -> None:
    """Увеличивает счётчик safety reroute, пропущенных из-за STRICT_LOCAL."""
    global _strict_local_safety_skip_count
    _strict_local_safety_skip_count += 1


def get_strict_local_metrics() -> Dict[str, Any]:
    """
    Возвращает метрики STRICT_LOCAL для экспорта в Prometheus.

    Returns:
        dict: enabled (bool), qa_skip_count (int), safety_skip_count (int)
    """
    return {
        "enabled": is_strict_local(),
        "qa_skip_count": _strict_local_qa_skip_count,
        "safety_skip_count": _strict_local_safety_skip_count,
    }
