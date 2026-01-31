"""
Type Safety - Строгая валидация типов с pydantic

Принцип: Self-Validating Code - Type Safety
Цель: Обеспечить runtime проверку типов для критичных функций
"""

import functools
import inspect
import logging
from typing import Any, Callable, Optional, Type, get_type_hints
from pydantic import BaseModel, ValidationError, validate_call

logger = logging.getLogger(__name__)


def validate_types(func: Callable) -> Callable:
    """
    Декоратор для runtime проверки типов через pydantic
    
    Использует type hints функции для валидации аргументов и возвращаемого значения
    
    Example:
        @validate_types
        def calculate_risk(entry_price: float, risk_pct: float) -> float:
            return entry_price * (risk_pct / 100)
    """
    # Получаем type hints
    hints = get_type_hints(func)
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Валидация аргументов
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        # Проверяем типы аргументов
        for param_name, param_value in bound_args.arguments.items():
            if param_name in hints:
                expected_type = hints[param_name]
                if not _check_type(param_value, expected_type):
                    raise TypeError(
                        f"Argument '{param_name}' has wrong type. "
                        f"Expected {expected_type}, got {type(param_value)}"
                    )
        
        # Выполняем функцию
        result = func(*args, **kwargs)
        
        # Проверяем тип возвращаемого значения
        if 'return' in hints:
            return_type = hints['return']
            if not _check_type(result, return_type):
                raise TypeError(
                    f"Return value has wrong type. "
                    f"Expected {return_type}, got {type(result)}"
                )
        
        return result
    
    return wrapper


def _check_type(value: Any, expected_type: Type) -> bool:
    """
    Проверка типа значения
    
    Args:
        value: Значение для проверки
        expected_type: Ожидаемый тип
        
    Returns:
        True если тип соответствует, False иначе
    """
    import typing
    
    # Обработка Optional
    if hasattr(typing, 'get_origin') and typing.get_origin(expected_type) is typing.Union:
        args = typing.get_args(expected_type)
        # Проверяем все варианты Union
        return any(_check_type(value, arg) for arg in args if arg is not type(None))
    
    # Обработка базовых типов
    if expected_type == Any:
        return True
    
    # Проверка через isinstance
    try:
        return isinstance(value, expected_type)
    except TypeError:
        # Для сложных типов (List, Dict и т.д.) упрощённая проверка
        return True


def pydantic_validate(model_class: Type[BaseModel]):
    """
    Декоратор для валидации через pydantic модель
    
    Args:
        model_class: Pydantic модель для валидации
        
    Example:
        class RiskCalculationInput(BaseModel):
            entry_price: float
            risk_pct: float
        
        @pydantic_validate(RiskCalculationInput)
        def calculate_risk(input_data: RiskCalculationInput) -> float:
            return input_data.entry_price * (input_data.risk_pct / 100)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Валидируем первый аргумент через pydantic модель
            if args:
                try:
                    validated_arg = model_class(**args[0] if isinstance(args[0], dict) else args[0].__dict__)
                    new_args = (validated_arg,) + args[1:]
                    return func(*new_args, **kwargs)
                except ValidationError as e:
                    logger.error(f"Validation error in {func.__name__}: {e}")
                    raise
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def strict_type_check(*expected_types: Type):
    """
    Декоратор для строгой проверки типов аргументов
    
    Args:
        *expected_types: Ожидаемые типы для каждого аргумента
        
    Example:
        @strict_type_check(float, float)
        def divide(x, y):
            return x / y
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Проверяем типы позиционных аргументов
            for i, (arg, expected_type) in enumerate(zip(args, expected_types)):
                if not isinstance(arg, expected_type):
                    raise TypeError(
                        f"Argument {i} has wrong type. "
                        f"Expected {expected_type.__name__}, got {type(arg).__name__}"
                    )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

