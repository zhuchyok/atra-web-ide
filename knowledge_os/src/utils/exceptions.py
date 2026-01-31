"""
Кастомные исключения для торгового бота ATRA
"""

class ATRAException(Exception):
    """Базовое исключение для торгового бота"""

class SignalValidationError(ATRAException):
    """Ошибка валидации торгового сигнала"""

class DataQualityError(ATRAException):
    """Ошибка качества данных"""

class DatabaseConnectionError(ATRAException):
    """Ошибка подключения к базе данных"""

class APIError(ATRAException):
    """Ошибка API (Binance, Telegram и др.)"""

class ConfigurationError(ATRAException):
    """Ошибка конфигурации"""

class TradingHoursError(ATRAException):
    """Ошибка торговых часов"""

class RiskManagementError(ATRAException):
    """Ошибка управления рисками"""
