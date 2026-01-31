"""
Система специфичных исключений для ATRA

Принцип: Self-Validating Code - Обработка ошибок
Цель: Заменить общие исключения на специфичные для лучшей диагностики
"""

from typing import Optional, Dict, Any


class ATRAException(Exception):
    """Базовое исключение ATRA"""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
    
    def __str__(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({ctx_str})"
        return self.message


class ValidationError(ATRAException):
    """Ошибка валидации данных"""
    pass


class DatabaseError(ATRAException):
    """Ошибка базы данных"""
    pass


class DatabaseConnectionError(DatabaseError):
    """Ошибка подключения к базе данных"""
    pass


class DatabaseQueryError(DatabaseError):
    """Ошибка выполнения запроса к базе данных"""
    pass


class DatabaseTransactionError(DatabaseError):
    """Ошибка транзакции базы данных"""
    pass


class APIError(ATRAException):
    """Ошибка API"""
    pass


class ExchangeAPIError(APIError):
    """Ошибка биржевого API"""
    pass


class TelegramAPIError(APIError):
    """Ошибка Telegram API"""
    pass


class NetworkError(APIError):
    """Ошибка сети (timeout, connection refused, etc.)"""
    pass


class RateLimitError(APIError):
    """Превышен лимит запросов к API"""
    pass


class AuthenticationError(APIError):
    """Ошибка аутентификации"""
    pass


class FinancialError(ATRAException):
    """Ошибка финансовых расчетов"""
    pass


class InsufficientFundsError(FinancialError):
    """Недостаточно средств"""
    pass


class InvalidPriceError(FinancialError):
    """Невалидная цена"""
    pass


class InvalidQuantityError(FinancialError):
    """Невалидное количество"""
    pass


class RiskManagementError(ATRAException):
    """Ошибка управления рисками"""
    pass


class PositionError(ATRAException):
    """Ошибка работы с позицией"""
    pass


class OrderError(ATRAException):
    """Ошибка работы с ордером"""
    pass


class OrderNotFoundError(OrderError):
    """Ордер не найден"""
    pass


class OrderExecutionError(OrderError):
    """Ошибка исполнения ордера"""
    pass


class OrderCancellationError(OrderError):
    """Ошибка отмены ордера"""
    pass


class SignalError(ATRAException):
    """Ошибка генерации или обработки сигнала"""
    pass


class ConfigurationError(ATRAException):
    """Ошибка конфигурации"""
    pass


class MissingConfigError(ConfigurationError):
    """Отсутствует обязательная конфигурация"""
    pass


class InvalidConfigError(ConfigurationError):
    """Невалидная конфигурация"""
    pass

