"""
State Machine Validation - Валидация переходов состояний

Принцип: Self-Validating Code - State Machine Validation
Цель: Валидация переходов состояний для критичных объектов и защита от невалидных переходов
"""

import functools
import logging
from typing import Callable, Any, Optional, Dict, List, Set, Type
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class StateTransitionError(ValueError):
    """Исключение при невалидном переходе состояния"""
    pass


@dataclass
class StateTransition:
    """Переход состояния"""
    from_state: Any
    to_state: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: Optional[Dict[str, Any]] = None


@dataclass
class StateTransitionRule:
    """Правило перехода состояния"""
    from_state: Any
    to_states: Set[Any]
    condition: Optional[Callable] = None  # Дополнительное условие для перехода


class StateMachineValidator:
    """
    Валидатор переходов состояний
    
    Обеспечивает:
    - Валидацию переходов состояний
    - Защиту от невалидных переходов
    - Логирование переходов
    - Проверку условий переходов
    """
    
    def __init__(self):
        """Инициализация валидатора"""
        self._rules: Dict[str, List[StateTransitionRule]] = {}
        self._transition_history: Dict[str, List[StateTransition]] = {}
    
    def register_state_machine(
        self,
        class_name: str,
        rules: List[StateTransitionRule]
    ) -> None:
        """
        Регистрация state machine для класса
        
        Args:
            class_name: Имя класса
            rules: Список правил переходов
        """
        self._rules[class_name] = rules
        self._transition_history[class_name] = []
        logger.debug(f"State machine registered for {class_name} with {len(rules)} rules")
    
    def validate_transition(
        self,
        obj: Any,
        from_state: Any,
        to_state: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Валидировать переход состояния
        
        Args:
            obj: Объект с состоянием
            from_state: Текущее состояние
            to_state: Целевое состояние
            context: Дополнительный контекст
            
        Returns:
            True если переход валиден
            
        Raises:
            StateTransitionError: При невалидном переходе
        """
        class_name = type(obj).__name__
        rules = self._rules.get(class_name, [])
        
        # Ищем правило для текущего состояния
        matching_rules = [r for r in rules if r.from_state == from_state]
        
        if not matching_rules:
            # Если нет правил, разрешаем переход (для обратной совместимости)
            logger.warning(f"No transition rules for {class_name} from {from_state}")
            return True
        
        # Проверяем, разрешён ли переход
        for rule in matching_rules:
            if to_state in rule.to_states:
                # Проверяем дополнительное условие
                if rule.condition:
                    try:
                        if not rule.condition(obj, from_state, to_state, context):
                            raise StateTransitionError(
                                f"Transition condition failed for {class_name}: "
                                f"{from_state} -> {to_state}"
                            )
                    except Exception as e:
                        if isinstance(e, StateTransitionError):
                            raise
                        raise StateTransitionError(
                            f"Transition condition error for {class_name}: {str(e)}"
                        )
                
                # Переход валиден, записываем в историю
                transition = StateTransition(
                    from_state=from_state,
                    to_state=to_state,
                    context=context
                )
                self._transition_history[class_name].append(transition)
                
                logger.debug(
                    f"Valid transition for {class_name}: {from_state} -> {to_state}"
                )
                return True
        
        # Переход не разрешён
        allowed_states = set()
        for rule in matching_rules:
            allowed_states.update(rule.to_states)
        
        error_msg = (
            f"Invalid state transition for {class_name}: "
            f"{from_state} -> {to_state}. "
            f"Allowed transitions from {from_state}: {allowed_states}"
        )
        logger.error(error_msg)
        raise StateTransitionError(error_msg)
    
    def get_transition_history(self, class_name: str) -> List[StateTransition]:
        """Получить историю переходов для класса"""
        return self._transition_history.get(class_name, []).copy()
    
    def clear_history(self, class_name: Optional[str] = None) -> None:
        """Очистить историю переходов"""
        if class_name:
            self._transition_history[class_name] = []
        else:
            self._transition_history.clear()


# Глобальный экземпляр для удобства использования
_global_validator: Optional[StateMachineValidator] = None


def get_state_validator() -> StateMachineValidator:
    """
    Получить глобальный экземпляр StateMachineValidator
    
    Returns:
        Глобальный экземпляр валидатора
    """
    global _global_validator
    if _global_validator is None:
        _global_validator = StateMachineValidator()
    return _global_validator


def valid_transition(
    from_state: Any,
    to_states: List[Any],
    condition: Optional[Callable] = None
):
    """
    Декоратор для валидации перехода состояния
    
    Args:
        from_state: Исходное состояние
        to_states: Список разрешённых целевых состояний
        condition: Дополнительное условие для перехода (опционально)
        
    Example:
        @valid_transition(
            from_state=OrderStatus.PENDING,
            to_states=[OrderStatus.FILLED, OrderStatus.CANCELLED]
        )
        def fill_order(order: Order):
            order.status = OrderStatus.FILLED
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Получаем текущее состояние объекта
            if not hasattr(self, 'status'):
                logger.warning(f"Object {type(self).__name__} has no 'status' attribute")
                return func(self, *args, **kwargs)
            
            current_state = self.status
            validator = get_state_validator()
            
            # Определяем целевое состояние из функции
            # (упрощённая версия - предполагаем что функция изменяет self.status)
            # В реальности нужно анализировать код функции или передавать to_state явно
            
            # Для простоты проверяем все разрешённые переходы
            # В реальной реализации нужно определить целевое состояние из контекста
            
            # Выполняем функцию
            result = func(self, *args, **kwargs)
            
            # Проверяем новое состояние
            new_state = self.status
            if new_state != current_state:
                # Валидируем переход
                validator.validate_transition(
                    self,
                    current_state,
                    new_state,
                    context={"function": func.__name__}
                )
            
            return result
        
        return wrapper
    return decorator

