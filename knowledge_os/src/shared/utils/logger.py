"""
Structured Logging Utility

Shared logging utility for the application.
"""

import logging
import sys
import os
from typing import Optional

try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False


def setup_logging(
    level: str = "INFO",
    use_structlog: bool = True,
    use_elk: bool = False,
    elk_url: Optional[str] = None
) -> logging.Logger:
    """
    Setup structured logging with optional ELK integration
    
    Args:
        level: Logging level
        use_structlog: Use structlog if available
        use_elk: Enable ELK handler for Elasticsearch
        elk_url: Elasticsearch URL (defaults to ELASTICSEARCH_URL env var)
        
    Returns:
        Configured logger
    """
    # Проверяем переменную окружения если use_elk не указан явно
    if not use_elk:
        use_elk = os.getenv("USE_ELK", "false").lower() in ("true", "1", "yes")
    
    if use_structlog and STRUCTLOG_AVAILABLE:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        logger = structlog.get_logger()
    else:
        # Fallback to standard logging
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            stream=sys.stdout,
        )
        logger = logging.getLogger(__name__)
    
    # Добавляем ELK handler если включен
    if use_elk:
        try:
            # Импортируем ELK handler
            import sys
            import os
            # Добавляем путь к app если нужно (для контейнера)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            app_path = os.path.join(current_dir, "../../../app")
            app_path_abs = os.path.abspath(app_path)
            if os.path.exists(os.path.join(app_path_abs, "elk_handler.py")):
                if app_path_abs not in sys.path:
                    sys.path.insert(0, app_path_abs)
            
            from elk_handler import create_elk_handler
            
            elk_handler = create_elk_handler(
                elasticsearch_url=elk_url,
                log_level=getattr(logging, level.upper())
            )
            
            if elk_handler:
                root_logger = logging.getLogger()
                root_logger.addHandler(elk_handler)
                logger.info("✅ ELK handler enabled")
        except ImportError as e:
            logger.warning(f"ELK handler not available: {e}")
        except Exception as e:
            logger.warning(f"Failed to setup ELK handler: {e}")
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get logger instance
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    else:
        return logging.getLogger(name or __name__)

