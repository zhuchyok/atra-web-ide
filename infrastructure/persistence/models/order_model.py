"""
Order Model - ORM Model

Infrastructure layer model for database persistence.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.domain.entities.order import Order, OrderSide, OrderType, OrderStatus
from src.domain.value_objects.price import Price
from src.domain.value_objects.symbol import Symbol


class OrderModel:
    """
    ORM Model for Order
    
    This is an infrastructure concern for database persistence.
    """
    
    def __init__(
        self,
        id: str,
        symbol_base: str,
        symbol_quote: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal],
        status: str,
        filled_quantity: Decimal,
        created_at: datetime,
        filled_at: Optional[datetime] = None,
    ):
        self.id = id
        self.symbol_base = symbol_base
        self.symbol_quote = symbol_quote
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.status = status
        self.filled_quantity = filled_quantity
        self.created_at = created_at
        self.filled_at = filled_at
    
    @classmethod
    def from_entity(cls, order: Order) -> 'OrderModel':
        """Create model from domain entity"""
        return cls(
            id=order.id,
            symbol_base=order.symbol.base,
            symbol_quote=order.symbol.quote,
            side=order.side.value,
            order_type=order.order_type.value,
            quantity=order.quantity,
            price=order.price.value if order.price else None,
            status=order.status.value,
            filled_quantity=order.filled_quantity,
            created_at=order.created_at,
            filled_at=order.filled_at,
        )
    
    def to_entity(self) -> Order:
        """Convert model to domain entity"""
        symbol = Symbol(base=self.symbol_base, quote=self.symbol_quote)
        price = Price(self.price, "USDT") if self.price else None
        
        return Order(
            id=self.id,
            symbol=symbol,
            side=OrderSide(self.side),
            order_type=OrderType(self.order_type),
            quantity=self.quantity,
            price=price,
            status=OrderStatus(self.status),
            filled_quantity=self.filled_quantity,
            created_at=self.created_at,
            filled_at=self.filled_at,
        )

