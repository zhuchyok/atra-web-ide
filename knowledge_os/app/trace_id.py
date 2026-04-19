"""
[SINGULARITY 26.10] Trace ID - Full Observability Across Agents

Мировая практика:
- Trace ID следует через всю цепочку агентов
- Каждый агент логирует свой вход/выход с trace_id
- OpenTelemetry совместимый формат
"""

import os
import uuid
import logging
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger(__name__)

# Context variable для trace_id - автоматически передаётся между async функциями
_trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def generate_trace_id() -> str:
    """Генерирует уникальный trace_id"""
    return f"trace_{uuid.uuid4().hex[:16]}"


def get_trace_id() -> Optional[str]:
    """Получить текущий trace_id из контекста"""
    return _trace_id_var.get()


def set_trace_id(trace_id: str) -> None:
    """Установить trace_id в контекст"""
    _trace_id_var.set(trace_id)


class TraceContext:
    """Контекстный менеджер для trace_id"""

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or generate_trace_id()
        self._token = None

    def __enter__(self):
        self._token = _trace_id_var.set(self.trace_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _trace_id_var.reset(self._token)
        return False

    async def __aenter__(self):
        self._token = _trace_id_var.set(self.trace_id)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        _trace_id_var.reset(self._token)
        return False


def log_with_trace(level: int, message: str, **kwargs):
    """Логирование с trace_id"""
    trace_id = get_trace_id()
    trace_str = f"[{trace_id}] " if trace_id else ""

    extra = ""
    if kwargs:
        extra = " | " + " | ".join([f"{k}={v}" for k, v in kwargs.items()])

    logger.log(level, f"{trace_str}{message}{extra}")


# Декоратор для автоматического trace_id
def traced(agent_name: str):
    """Декоратор для добавления trace_id в функцию агента"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            trace_id = get_trace_id() or generate_trace_id()
            set_trace_id(trace_id)

            logger.info(f"[{agent_name}] START trace_id={trace_id}")
            try:
                result = await func(*args, **kwargs)
                logger.info(f"[{agent_name}] END trace_id={trace_id} success")
                return result
            except Exception as e:
                logger.error(f"[{agent_name}] ERROR trace_id={trace_id} error={e}")
                raise

        return wrapper

    return decorator
