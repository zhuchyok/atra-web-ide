"""
Configuration Validation - Валидация конфигурации системы

Принцип: Self-Validating Code - Configuration Validation
Цель: Валидация конфигурации при старте системы и предотвращение ошибок конфигурации
"""

import functools
import inspect
import logging
from typing import Callable, Any, Optional, Dict, List, Type, Union, get_type_hints, get_origin, get_args
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


class ConfigValidationError(ValueError):
    """Исключение при нарушении валидации конфигурации"""
    pass


@dataclass
class ValidationRule:
    """Правило валидации"""
    field_name: str
    rule_type: str  # "required", "range", "type", "custom"
    message: str
    validator: Optional[Callable] = None


@dataclass
class ConfigValidationResult:
    """Результат валидации конфигурации"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ConfigValidator:
    """
    Валидатор конфигурации
    
    Обеспечивает:
    - Валидацию обязательных полей
    - Проверку типов
    - Проверку диапазонов значений
    - Валидацию зависимостей между полями
    """
    
    def __init__(self):
        """Инициализация валидатора"""
        self._rules: Dict[str, List[ValidationRule]] = {}
        self._custom_validators: Dict[str, Callable] = {}
    
    def add_rule(
        self,
        config_class: Type,
        field_name: str,
        rule_type: str,
        message: str = "",
        validator: Optional[Callable] = None
    ) -> None:
        """
        Добавить правило валидации
        
        Args:
            config_class: Класс конфигурации
            field_name: Имя поля
            rule_type: Тип правила ("required", "range", "type", "custom")
            message: Сообщение об ошибке
            validator: Функция валидации (для custom правил)
        """
        class_name = config_class.__name__
        if class_name not in self._rules:
            self._rules[class_name] = []
        
        rule = ValidationRule(
            field_name=field_name,
            rule_type=rule_type,
            message=message,
            validator=validator
        )
        self._rules[class_name].append(rule)
    
    def validate(self, config: Any) -> ConfigValidationResult:
        """
        Валидировать конфигурацию
        
        Args:
            config: Объект конфигурации
            
        Returns:
            Результат валидации
        """
        errors = []
        warnings = []
        
        config_class = type(config)
        class_name = config_class.__name__
        
        # Получаем правила для этого класса
        rules = self._rules.get(class_name, [])
        
        # Получаем type hints
        try:
            hints = get_type_hints(config_class)
        except Exception:
            hints = {}
        
        # Проверяем каждое правило
        for rule in rules:
            field_name = rule.field_name
            
            # Проверка наличия поля
            if not hasattr(config, field_name):
                if rule.rule_type == "required":
                    errors.append(f"{field_name}: {rule.message or 'Field is required'}")
                continue
            
            value = getattr(config, field_name)
            
            # Проверка типа
            if rule.rule_type == "type" and field_name in hints:
                expected_type = hints[field_name]
                if not self._check_type(value, expected_type):
                    errors.append(
                        f"{field_name}: {rule.message or f'Expected {expected_type}, got {type(value)}'}"
                    )
            
            # Проверка диапазона
            elif rule.rule_type == "range" and rule.validator:
                if not rule.validator(value):
                    errors.append(
                        f"{field_name}: {rule.message or 'Value out of range'}"
                    )
            
            # Кастомная валидация
            elif rule.rule_type == "custom" and rule.validator:
                try:
                    if not rule.validator(value, config):
                        errors.append(
                            f"{field_name}: {rule.message or 'Validation failed'}"
                        )
                except Exception as e:
                    errors.append(
                        f"{field_name}: Validation error: {str(e)}"
                    )
        
        # Автоматическая валидация на основе type hints
        for field_name, expected_type in hints.items():
            if hasattr(config, field_name):
                value = getattr(config, field_name)
                
                # Проверка типа
                if not self._check_type(value, expected_type):
                    # Пропускаем если уже есть ошибка для этого поля
                    if not any(e.startswith(f"{field_name}:") for e in errors):
                        errors.append(
                            f"{field_name}: Expected {expected_type.__name__}, got {type(value).__name__}"
                        )
        
        return ConfigValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _check_type(self, value: Any, expected_type: Type) -> bool:
        """Проверка типа значения"""
        # Обработка Optional
        if get_origin(expected_type) is Optional or (hasattr(expected_type, '__origin__') and expected_type.__origin__ is type(None)):
            args = get_args(expected_type)
            if args:
                # Optional[T] -> Union[T, None]
                return any(self._check_type(value, arg) for arg in args if arg is not type(None))
        
        # Обработка Union
        if get_origin(expected_type) is type(Union):
            args = get_args(expected_type)
            return any(self._check_type(value, arg) for arg in args)
        
        # Базовые типы
        if expected_type == Any:
            return True
        
        # Проверка через isinstance
        try:
            return isinstance(value, expected_type)
        except TypeError:
            # Для сложных типов (List, Dict и т.д.) упрощённая проверка
            return True
    
    def validate_and_raise(self, config: Any) -> None:
        """
        Валидировать конфигурацию и выбросить исключение при ошибках
        
        Args:
            config: Объект конфигурации
            
        Raises:
            ConfigValidationError: При ошибках валидации
        """
        result = self.validate(config)
        if not result.is_valid:
            error_msg = "Configuration validation failed:\n" + "\n".join(result.errors)
            logger.error(error_msg)
            raise ConfigValidationError(error_msg)


# Глобальный экземпляр для удобства использования
_global_validator: Optional[ConfigValidator] = None


def get_config_validator() -> ConfigValidator:
    """
    Получить глобальный экземпляр ConfigValidator
    
    Returns:
        Глобальный экземпляр валидатора
    """
    global _global_validator
    if _global_validator is None:
        _global_validator = ConfigValidator()
    return _global_validator


def validate_config(
    required_fields: Optional[List[str]] = None,
    range_validators: Optional[Dict[str, Callable]] = None,
    custom_validators: Optional[Dict[str, Callable]] = None
):
    """
    Декоратор для валидации конфигурации
    
    Args:
        required_fields: Список обязательных полей
        range_validators: Словарь валидаторов диапазонов {field_name: validator}
        custom_validators: Словарь кастомных валидаторов {field_name: validator}
        
    Example:
        @validate_config(
            required_fields=["risk_pct", "leverage"],
            range_validators={
                "risk_pct": lambda x: 0.1 <= x <= 10.0,
                "leverage": lambda x: 1.0 <= x <= 20.0
            }
        )
        class TradingConfig:
            risk_pct: float
            leverage: float
    """
    def decorator(cls: Type) -> Type:
        validator = get_config_validator()
        
        # Добавляем правила для обязательных полей
        if required_fields:
            for field_name in required_fields:
                validator.add_rule(
                    cls,
                    field_name,
                    "required",
                    f"Field '{field_name}' is required"
                )
        
        # Добавляем правила для диапазонов
        if range_validators:
            for field_name, range_validator in range_validators.items():
                validator.add_rule(
                    cls,
                    field_name,
                    "range",
                    f"Field '{field_name}' is out of valid range",
                    validator=range_validator
                )
        
        # Добавляем кастомные валидаторы
        if custom_validators:
            for field_name, custom_validator in custom_validators.items():
                validator.add_rule(
                    cls,
                    field_name,
                    "custom",
                    f"Field '{field_name}' validation failed",
                    validator=custom_validator
                )
        
        # Добавляем валидацию в __post_init__ для dataclass
        if hasattr(cls, '__dataclass_fields__'):
            original_post_init = getattr(cls, '__post_init__', None)
            
            def new_post_init(self):
                if original_post_init:
                    original_post_init(self)
                validator.validate_and_raise(self)
            
            cls.__post_init__ = new_post_init
        
        return cls
    return decorator

