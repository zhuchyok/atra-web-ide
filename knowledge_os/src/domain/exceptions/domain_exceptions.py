"""
Domain Exceptions

Domain-specific exceptions for business logic errors.
"""


class DomainException(Exception):
    """Base domain exception"""
    pass


class InvalidSignalException(DomainException):
    """Raised when signal validation fails"""
    pass


class InvalidPositionException(DomainException):
    """Raised when position validation fails"""
    pass


class InvalidOrderException(DomainException):
    """Raised when order validation fails"""
    pass


class RiskLimitExceededException(DomainException):
    """Raised when risk limits are exceeded"""
    pass


class PositionNotFoundException(DomainException):
    """Raised when position is not found"""
    pass


class SignalNotFoundException(DomainException):
    """Raised when signal is not found"""
    pass


class OrderNotFoundException(DomainException):
    """Raised when order is not found"""
    pass

