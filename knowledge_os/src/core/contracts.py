"""
Contract-Based Programming - Preconditions, Postconditions, Invariants

Принцип: Self-Validating Code - Contract-Based Programming
Цель: Обеспечить явные контракты для функций с автоматической проверкой preconditions/postconditions
"""

import functools
import inspect
import logging
import asyncio
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class ContractViolation:
    """Нарушение контракта"""
    contract_type: str  # "precondition", "postcondition", "invariant"
    function_name: str
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


class ContractViolationError(ValueError):
    """Исключение при нарушении контракта"""
    def __init__(self, violation: ContractViolation):
        self.violation = violation
        super().__init__(f"{violation.contract_type} violation in {violation.function_name}: {violation.message}")


def precondition(check: Callable[[Any], bool], message: str = ""):
    """
    Декоратор для проверки preconditions (условий перед выполнением функции)
    
    Args:
        check: Функция проверки (принимает те же аргументы, что и декорируемая функция)
        message: Сообщение при нарушении
        
    Example:
        @precondition(lambda x, y: x > 0 and y > 0, "x and y must be positive")
        def divide(x, y):
            return x / y
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Выполняем проверку precondition
            try:
                if not check(*args, **kwargs):
                    violation = ContractViolation(
                        contract_type="precondition",
                        function_name=func.__name__,
                        message=message or f"Precondition failed for {func.__name__}",
                        timestamp=datetime.now(timezone.utc),
                        details={"args": args, "kwargs": kwargs}
                    )
                    logger.error(f"Precondition violation: {violation.message}")
                    raise ContractViolationError(violation)
            except Exception as e:
                if isinstance(e, ContractViolationError):
                    raise
                # Если проверка сама упала, это тоже нарушение
                violation = ContractViolation(
                    contract_type="precondition",
                    function_name=func.__name__,
                    message=f"Precondition check failed: {str(e)}",
                    timestamp=datetime.now(timezone.utc),
                    details={"error": str(e)}
                )
                raise ContractViolationError(violation)
            
            # Выполняем оригинальную функцию
            return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Выполняем проверку precondition
            try:
                # Для async функций проверка может быть async или sync
                if inspect.iscoroutinefunction(check):
                    result = await check(*args, **kwargs)
                else:
                    result = check(*args, **kwargs)
                
                if not result:
                    violation = ContractViolation(
                        contract_type="precondition",
                        function_name=func.__name__,
                        message=message or f"Precondition failed for {func.__name__}",
                        timestamp=datetime.now(timezone.utc),
                        details={"args": args, "kwargs": kwargs}
                    )
                    logger.error(f"Precondition violation: {violation.message}")
                    raise ContractViolationError(violation)
            except Exception as e:
                if isinstance(e, ContractViolationError):
                    raise
                violation = ContractViolation(
                    contract_type="precondition",
                    function_name=func.__name__,
                    message=f"Precondition check failed: {str(e)}",
                    timestamp=datetime.now(timezone.utc),
                    details={"error": str(e)}
                )
                raise ContractViolationError(violation)
            
            # Выполняем оригинальную функцию
            return await func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


def postcondition(check: Callable[[Any], bool], message: str = ""):
    """
    Декоратор для проверки postconditions (условий после выполнения функции)
    
    Args:
        check: Функция проверки (принимает результат функции и те же аргументы)
        message: Сообщение при нарушении
        
    Example:
        @postcondition(lambda result, x, y: result > 0, "Result must be positive")
        def multiply(x, y):
            return x * y
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Выполняем оригинальную функцию
            result = func(*args, **kwargs)
            
            # Выполняем проверку postcondition
            try:
                if not check(result, *args, **kwargs):
                    violation = ContractViolation(
                        contract_type="postcondition",
                        function_name=func.__name__,
                        message=message or f"Postcondition failed for {func.__name__}",
                        timestamp=datetime.now(timezone.utc),
                        details={"result": result, "args": args, "kwargs": kwargs}
                    )
                    logger.error(f"Postcondition violation: {violation.message}")
                    raise ContractViolationError(violation)
            except Exception as e:
                if isinstance(e, ContractViolationError):
                    raise
                violation = ContractViolation(
                    contract_type="postcondition",
                    function_name=func.__name__,
                    message=f"Postcondition check failed: {str(e)}",
                    timestamp=datetime.now(timezone.utc),
                    details={"error": str(e), "result": result}
                )
                raise ContractViolationError(violation)
            
            return result
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Выполняем оригинальную функцию
            result = await func(*args, **kwargs)
            
            # Выполняем проверку postcondition
            try:
                if inspect.iscoroutinefunction(check):
                    check_result = await check(result, *args, **kwargs)
                else:
                    check_result = check(result, *args, **kwargs)
                
                if not check_result:
                    violation = ContractViolation(
                        contract_type="postcondition",
                        function_name=func.__name__,
                        message=message or f"Postcondition failed for {func.__name__}",
                        timestamp=datetime.now(timezone.utc),
                        details={"result": result, "args": args, "kwargs": kwargs}
                    )
                    logger.error(f"Postcondition violation: {violation.message}")
                    raise ContractViolationError(violation)
            except Exception as e:
                if isinstance(e, ContractViolationError):
                    raise
                violation = ContractViolation(
                    contract_type="postcondition",
                    function_name=func.__name__,
                    message=f"Postcondition check failed: {str(e)}",
                    timestamp=datetime.now(timezone.utc),
                    details={"error": str(e), "result": result}
                )
                raise ContractViolationError(violation)
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


def invariant(check: Callable[[Any], bool], message: str = ""):
    """
    Декоратор для проверки инвариантов состояния объекта
    
    Args:
        check: Функция проверки (принимает self и возвращает bool)
        message: Сообщение при нарушении
        
    Example:
        class Account:
            @invariant(lambda self: self.balance >= 0, "Balance must be non-negative")
            def withdraw(self, amount):
                self.balance -= amount
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Проверяем инвариант до выполнения
            try:
                if not check(self):
                    violation = ContractViolation(
                        contract_type="invariant",
                        function_name=f"{type(self).__name__}.{func.__name__}",
                        message=message or f"Invariant violated before {func.__name__}",
                        timestamp=datetime.now(timezone.utc),
                        details={"object": str(self)[:100]}
                    )
                    logger.error(f"Invariant violation: {violation.message}")
                    raise ContractViolationError(violation)
            except Exception as e:
                if isinstance(e, ContractViolationError):
                    raise
                violation = ContractViolation(
                    contract_type="invariant",
                    function_name=f"{type(self).__name__}.{func.__name__}",
                    message=f"Invariant check failed: {str(e)}",
                    timestamp=datetime.now(timezone.utc),
                    details={"error": str(e)}
                )
                raise ContractViolationError(violation)
            
            # Выполняем оригинальную функцию
            result = func(self, *args, **kwargs)
            
            # Проверяем инвариант после выполнения
            try:
                if not check(self):
                    violation = ContractViolation(
                        contract_type="invariant",
                        function_name=f"{type(self).__name__}.{func.__name__}",
                        message=message or f"Invariant violated after {func.__name__}",
                        timestamp=datetime.now(timezone.utc),
                        details={"object": str(self)[:100]}
                    )
                    logger.error(f"Invariant violation: {violation.message}")
                    raise ContractViolationError(violation)
            except Exception as e:
                if isinstance(e, ContractViolationError):
                    raise
                violation = ContractViolation(
                    contract_type="invariant",
                    function_name=f"{type(self).__name__}.{func.__name__}",
                    message=f"Invariant check failed: {str(e)}",
                    timestamp=datetime.now(timezone.utc),
                    details={"error": str(e)}
                )
                raise ContractViolationError(violation)
            
            return result
        
        return wrapper
    return decorator


def contract(precondition_check: Optional[Callable] = None,
             postcondition_check: Optional[Callable] = None,
             precondition_msg: str = "",
             postcondition_msg: str = ""):
    """
    Комбинированный декоратор для preconditions и postconditions
    
    Args:
        precondition_check: Функция проверки precondition
        postcondition_check: Функция проверки postcondition
        precondition_msg: Сообщение при нарушении precondition
        postcondition_msg: Сообщение при нарушении postcondition
        
    Example:
        @contract(
            precondition_check=lambda x, y: x > 0 and y > 0,
            postcondition_check=lambda result, x, y: result > 0
        )
        def divide(x, y):
            return x / y
    """
    def decorator(func: Callable) -> Callable:
        if precondition_check:
            func = precondition(precondition_check, precondition_msg)(func)
        if postcondition_check:
            func = postcondition(postcondition_check, postcondition_msg)(func)
        return func
    return decorator

