"""
Правила переходов состояний для критичных объектов

Регистрация state machines для Order, Position, Signal
"""

import logging
from src.core.state_machine import (
    StateMachineValidator,
    StateTransitionRule,
    get_state_validator
)
from src.domain.entities.order import OrderStatus
from src.domain.entities.position import PositionStatus

logger = logging.getLogger(__name__)


def register_state_machines():
    """Регистрация state machines для всех критичных объектов"""
    validator = get_state_validator()
    
    # ========================================================================
    # Order State Machine
    # ========================================================================
    
    order_rules = [
        StateTransitionRule(
            from_state=OrderStatus.PENDING,
            to_states={OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}
        ),
        StateTransitionRule(
            from_state=OrderStatus.OPEN,
            to_states={OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED, OrderStatus.CANCELLED}
        ),
        StateTransitionRule(
            from_state=OrderStatus.PARTIALLY_FILLED,
            to_states={OrderStatus.FILLED, OrderStatus.CANCELLED}
        ),
        # Финальные состояния - переходы не разрешены
        StateTransitionRule(
            from_state=OrderStatus.FILLED,
            to_states=set()
        ),
        StateTransitionRule(
            from_state=OrderStatus.CANCELLED,
            to_states=set()
        ),
        StateTransitionRule(
            from_state=OrderStatus.REJECTED,
            to_states=set()
        )
    ]
    
    validator.register_state_machine("Order", order_rules)
    
    # ========================================================================
    # Position State Machine
    # ========================================================================
    
    position_rules = [
        StateTransitionRule(
            from_state=PositionStatus.OPEN,
            to_states={PositionStatus.CLOSED, PositionStatus.PARTIALLY_CLOSED}
        ),
        StateTransitionRule(
            from_state=PositionStatus.PARTIALLY_CLOSED,
            to_states={PositionStatus.CLOSED}
        ),
        # Финальное состояние - переходы не разрешены
        StateTransitionRule(
            from_state=PositionStatus.CLOSED,
            to_states=set()
        )
    ]
    
    validator.register_state_machine("Position", position_rules)
    
    logger.info("State machines registered for Order and Position")


# Автоматическая регистрация при импорте
try:
    register_state_machines()
except Exception as e:
    logger.warning(f"Failed to register state machines: {e}")

