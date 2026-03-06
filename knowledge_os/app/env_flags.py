"""
Централизованная проверка флагов окружения для Knowledge OS.

Используется во всех модулях, где нужна проверка режима работы (STRICT_LOCAL и др.).
Единый источник истины для конфигурации (12-Factor App).
"""

import os


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
    return {
        "enabled": enabled,
        "mode": "strict_local" if enabled else "normal"
    }
