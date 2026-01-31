"""
Position Entity - Domain Entity

A Position represents an open trading position with identity and business rules.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from decimal import Decimal

from ..value_objects.price import Price
from ..value_objects.symbol import Symbol

# Регистрируем state machine при импорте
try:
    from ...core.state_machine_rules import register_state_machines
    register_state_machines()
except Exception:
    pass  # Если регистрация не удалась, продолжаем без неё


class PositionSide(Enum):
    """Position direction"""
    LONG = "long"
    SHORT = "short"


class PositionStatus(Enum):
    """Position status"""
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"


@dataclass(frozen=True)
class Position:
    """
    Position Entity
    
    This is a domain entity representing a trading position.
    It contains business logic and validation rules.
    """
    
    id: str
    symbol: Symbol
    side: PositionSide
    entry_price: Price
    quantity: Decimal
    opened_at: datetime
    status: PositionStatus = PositionStatus.OPEN
    current_price: Optional[Price] = None
    take_profit: Optional[Price] = None
    stop_loss: Optional[Price] = None
    closed_at: Optional[datetime] = None
    closed_price: Optional[Price] = None
    pnl: Optional[Decimal] = None
    pnl_percentage: Optional[Decimal] = None
    
    def __post_init__(self):
        """Validate business rules"""
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if self.status == PositionStatus.OPEN:
            if self.closed_at is not None:
                raise ValueError("Open position cannot have closed_at")
            if self.closed_price is not None:
                raise ValueError("Open position cannot have closed_price")
        
        if self.status == PositionStatus.CLOSED:
            if self.closed_at is None:
                raise ValueError("Closed position must have closed_at")
            if self.closed_price is None:
                raise ValueError("Closed position must have closed_price")
    
    def update_price(self, new_price: Price) -> 'Position':
        """Update current price and recalculate PnL"""
        if self.status != PositionStatus.OPEN:
            raise ValueError("Can only update price for open positions")
        
        if new_price.currency != self.entry_price.currency:
            raise ValueError("Price currency must match entry price currency")
        
        # Calculate PnL
        if self.side == PositionSide.LONG:
            pnl = (new_price.value - self.entry_price.value) * self.quantity
        else:  # SHORT
            pnl = (self.entry_price.value - new_price.value) * self.quantity
        
        pnl_percentage = (pnl / (self.entry_price.value * self.quantity)) * Decimal("100")
        
        return Position(
            id=self.id,
            symbol=self.symbol,
            side=self.side,
            entry_price=self.entry_price,
            quantity=self.quantity,
            opened_at=self.opened_at,
            status=self.status,
            current_price=new_price,
            take_profit=self.take_profit,
            stop_loss=self.stop_loss,
            closed_at=self.closed_at,
            closed_price=self.closed_price,
            pnl=pnl,
            pnl_percentage=pnl_percentage,
        )
    
    def close(self, close_price: Price, closed_at: datetime) -> 'Position':
        """Close the position"""
        # Валидация перехода состояния
        from ...core.state_machine import get_state_validator, StateTransitionError
        validator = get_state_validator()
        
        try:
            validator.validate_transition(
                self,
                self.status,
                PositionStatus.CLOSED,
                context={"function": "close", "close_price": str(close_price.value)}
            )
        except StateTransitionError:
            # Если нет правил для этого класса, продолжаем с обычной валидацией
            pass
        
        if self.status != PositionStatus.OPEN:
            raise ValueError(f"Cannot close position in status {self.status}")
        
        if close_price.currency != self.entry_price.currency:
            raise ValueError("Close price currency must match entry price currency")
        
        # Calculate final PnL
        if self.side == PositionSide.LONG:
            pnl = (close_price.value - self.entry_price.value) * self.quantity
        else:  # SHORT
            pnl = (self.entry_price.value - close_price.value) * self.quantity
        
        pnl_percentage = (pnl / (self.entry_price.value * self.quantity)) * Decimal("100")
        
        return Position(
            id=self.id,
            symbol=self.symbol,
            side=self.side,
            entry_price=self.entry_price,
            quantity=self.quantity,
            opened_at=self.opened_at,
            status=PositionStatus.CLOSED,
            current_price=None,
            take_profit=self.take_profit,
            stop_loss=self.stop_loss,
            closed_at=closed_at,
            closed_price=close_price,
            pnl=pnl,
            pnl_percentage=pnl_percentage,
        )
    
    def is_profitable(self) -> bool:
        """Check if position is profitable"""
        if self.pnl is None:
            return False
        return self.pnl > 0
    
    def is_at_take_profit(self) -> bool:
        """Check if position reached take profit"""
        if self.take_profit is None or self.current_price is None:
            return False
        
        if self.side == PositionSide.LONG:
            return self.current_price.value >= self.take_profit.value
        else:  # SHORT
            return self.current_price.value <= self.take_profit.value
    
    def is_at_stop_loss(self) -> bool:
        """Check if position hit stop loss"""
        if self.stop_loss is None or self.current_price is None:
            return False
        
        if self.side == PositionSide.LONG:
            return self.current_price.value <= self.stop_loss.value
        else:  # SHORT
            return self.current_price.value >= self.stop_loss.value

