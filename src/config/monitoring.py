"""
Конфигурация мониторинга для торгового бота ATRA
"""

# Метрики производительности
PERFORMANCE_METRICS = {
    "max_latency_ms": 5000,  # Максимальная задержка сигнала
    "max_memory_mb": 1024,   # Максимальное потребление памяти
    "max_cpu_percent": 80,   # Максимальная загрузка CPU
}

# Health checks
HEALTH_CHECKS = {
    "database_timeout": 5,      # Таймаут проверки БД
    "api_timeout": 10,          # Таймаут проверки API
    "queue_timeout": 30,        # Таймаут проверки очереди
    "ai_response_timeout": 15,  # Таймаут ответа ИИ
}

# Алерты
ALERT_THRESHOLDS = {
    "error_rate_percent": 5,    # Порог ошибок для алерта
    "latency_threshold_ms": 3000,  # Порог задержки для алерта
    "memory_threshold_mb": 800,    # Порог памяти для алерта
    "queue_size_threshold": 100,   # Порог размера очереди
}

# Логирование
LOGGING_CONFIG = {
    "structured": True,         # Использовать structured logging
    "trace_id": True,          # Включать trace ID
    "performance_logging": True, # Логировать производительность
    "error_tracking": True,     # Отслеживать ошибки
}

# Мониторинг компонентов
COMPONENT_MONITORING = {
    "telegram_bot": True,
    "signal_generator": True,
    "ai_integration": True,
    "database": True,
    "external_apis": True,
    "pattern_cleaner": True,
}
