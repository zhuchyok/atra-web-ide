"""
Order Entity - Domain Entity

An Order represents a trading order with identity and business rules.
"""

from dataclasses import dataclass
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
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


class OrderSide(Enum):
    """Order direction"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order type"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(Enum):
    """Order status"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Order:
    """
    Order Entity
    
    This is a domain entity representing a trading order.
    It contains business logic and validation rules.
    """
    
    id: str
    symbol: Symbol
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Price]
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: Decimal = Decimal("0")
    created_at: datetime = None
    filled_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate business rules"""
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("Limit order must have a price")
        
        if self.order_type == OrderType.MARKET and self.price is not None:
            raise ValueError("Market order cannot have a price")
        
        if self.filled_quantity < 0:
            raise ValueError("Filled quantity cannot be negative")
        
        if self.filled_quantity > self.quantity:
            raise ValueError("Filled quantity cannot exceed order quantity")
        
        if self.created_at is None:
            object.__setattr__(self, 'created_at', get_utc_now())
    
    def fill(self, filled_quantity: Decimal, filled_at: datetime) -> 'Order':
        """Fill the order"""
        # Валидация перехода состояния
        from ...core.state_machine import get_state_validator, StateTransitionError
        validator = get_state_validator()
        
        try:
            validator.validate_transition(
                self,
                self.status,
                OrderStatus.FILLED if (self.filled_quantity + filled_quantity) >= self.quantity else OrderStatus.PARTIALLY_FILLED,
                context={"function": "fill", "filled_quantity": str(filled_quantity)}
            )
        except StateTransitionError:
            # Если нет правил для этого класса, продолжаем с обычной валидацией
            pass
        
        if self.status not in [OrderStatus.PENDING, OrderStatus.OPEN]:
            raise ValueError(f"Cannot fill order in status {self.status}")
        
        if filled_quantity <= 0:
            raise ValueError("Filled quantity must be positive")
        
        if filled_quantity > self.quantity:
            raise ValueError("Filled quantity cannot exceed order quantity")
        
        new_filled = self.filled_quantity + filled_quantity
        
        if new_filled >= self.quantity:
            # Fully filled
            new_status = OrderStatus.FILLED
        else:
            # Partially filled
            new_status = OrderStatus.PARTIALLY_FILLED
        
        return Order(
            id=self.id,
            symbol=self.symbol,
            side=self.side,
            order_type=self.order_type,
            quantity=self.quantity,
            price=self.price,
            status=new_status,
            filled_quantity=new_filled,
            created_at=self.created_at,
            filled_at=filled_at if new_status == OrderStatus.FILLED else None,
        )
    
    def cancel(self) -> 'Order':
        """Cancel the order"""
        # Валидация перехода состояния
        from ...core.state_machine import get_state_validator, StateTransitionError
        validator = get_state_validator()
        
        try:
            validator.validate_transition(
                self,
                self.status,
                OrderStatus.CANCELLED,
                context={"function": "cancel"}
            )
        except StateTransitionError:
            # Если нет правил для этого класса, продолжаем с обычной валидацией
            pass
        
        if self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            raise ValueError(f"Cannot cancel order in status {self.status}")
        
        return Order(
            id=self.id,
            symbol=self.symbol,
            side=self.side,
            order_type=self.order_type,
            quantity=self.quantity,
            price=self.price,
            status=OrderStatus.CANCELLED,
            filled_quantity=self.filled_quantity,
            created_at=self.created_at,
            filled_at=self.filled_at,
        )
    
    def is_fully_filled(self) -> bool:
        """Check if order is fully filled"""
        return self.status == OrderStatus.FILLED
    
    def remaining_quantity(self) -> Decimal:
        """Get remaining quantity to fill"""
        return self.quantity - self.filled_quantity

