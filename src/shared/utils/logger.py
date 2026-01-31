"""
Centralized Structured Logging

Централизованная система логирования на базе structlog для всех модулей ATRA.
Обеспечивает структурированные логи с контекстом (user_id, symbol, request_id).
"""

import logging
import sys
from typing import Any, Dict, Optional
import structlog
from structlog.stdlib import LoggerFactory

# Конфигурация structlog
def configure_structured_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    use_json: bool = False
) -> None:
    """
    Настройка структурированного логирования для всей системы.
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Путь к файлу для записи логов (опционально)
        use_json: Использовать JSON формат для логов (для production)
    """
    # Настройка процессоров structlog
    processors = [
        structlog.contextvars.merge_contextvars,  # Добавляет contextvars
        structlog.stdlib.add_log_level,           # Добавляет уровень лога
        structlog.stdlib.add_logger_name,         # Добавляет имя логгера
        structlog.processors.TimeStamper(fmt="iso"),  # ISO timestamp
        structlog.processors.StackInfoRenderer(),     # Stack trace
        structlog.processors.format_exc_info,         # Exception info
    ]
    
    if use_json:
        # JSON формат для production
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Человекочитаемый формат для разработки
        processors.extend([
            structlog.dev.set_exc_info,  # Exception formatting
            structlog.dev.ConsoleRenderer(colors=True)  # Colored console
        ])
    
    # Настройка structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Настройка стандартного logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout if not log_file else open(log_file, 'a'),
        level=getattr(logging, log_level.upper()),
    )


def get_logger(name: str = __name__, **context: Any) -> structlog.BoundLogger:
    """
    Получить структурированный логгер для модуля.
    
    Args:
        name: Имя логгера (обычно __name__ модуля)
        **context: Контекст для всех логов этого логгера (user_id, symbol, request_id и т.д.)
    
    Returns:
        structlog.BoundLogger с привязанным контекстом
    
    Examples:
        # Базовое использование
        logger = get_logger(__name__)
        logger.info("Signal generated", symbol="BTCUSDT", direction="LONG")
        
        # С контекстом
        logger = get_logger(__name__, user_id=123, symbol="BTCUSDT")
        logger.info("Position opened", entry_price=50000.0)
        # Все логи автоматически включат user_id и symbol
    """
    logger = structlog.get_logger(name)
    
    # Привязываем контекст, если передан
    if context:
        logger = logger.bind(**context)
    
    return logger


def set_log_context(**context: Any) -> None:
    """
    Установить глобальный контекст для всех последующих логов в текущем потоке.
    
    Args:
        **context: Ключ-значение пары для контекста
    
    Examples:
        set_log_context(user_id=123, request_id="abc-123")
        logger.info("Processing request")  # Автоматически включит user_id и request_id
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(**context)


def clear_log_context() -> None:
    """Очистить глобальный контекст логирования."""
    structlog.contextvars.clear_contextvars()


def add_log_context(**context: Any) -> None:
    """
    Добавить к существующему глобальному контексту (не перезаписывает).
    
    Args:
        **context: Ключ-значение пары для добавления в контекст
    """
    structlog.contextvars.bind_contextvars(**context)


# Автоматическая инициализация при импорте (если не настроена)
_initialized = False

def ensure_initialized() -> None:
    """Убедиться, что логирование инициализировано."""
    global _initialized
    if not _initialized:
        # Проверяем, настроен ли structlog
        try:
            structlog.get_logger()
        except Exception:
            # Если не настроен, настраиваем по умолчанию
            configure_structured_logging()
        _initialized = True

# Инициализация при импорте модуля
ensure_initialized()

# Экспорт удобных функций
__all__ = [
    'configure_structured_logging',
    'get_logger',
    'set_log_context',
    'clear_log_context',
    'add_log_context',
    'ensure_initialized',
]