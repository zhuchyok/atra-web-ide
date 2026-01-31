"""
Position Model - ORM Model

Infrastructure layer model for database persistence.
This is separate from Domain entities.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.domain.entities.position import Position, PositionSide, PositionStatus
from src.domain.value_objects.price import Price
from src.domain.value_objects.symbol import Symbol


class PositionModel:
    """
    ORM Model for Position
    
    This is an infrastructure concern for database persistence.
    It converts between database representation and domain entities.
    """
    
    def __init__(
        self,
        id: str,
        symbol_base: str,
        symbol_quote: str,
        side: str,
        entry_price: Decimal,
        quantity: Decimal,
        opened_at: datetime,
        status: str = "open",
        current_price: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
        closed_at: Optional[datetime] = None,
        closed_price: Optional[Decimal] = None,
        pnl: Optional[Decimal] = None,
        pnl_percentage: Optional[Decimal] = None,
    ):
        self.id = id
        self.symbol_base = symbol_base
        self.symbol_quote = symbol_quote
        self.side = side
        self.entry_price = entry_price
        self.quantity = quantity
        self.opened_at = opened_at
        self.status = status
        self.current_price = current_price
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.closed_at = closed_at
        self.closed_price = closed_price
        self.pnl = pnl
        self.pnl_percentage = pnl_percentage
    
    @classmethod
    def from_entity(cls, position: Position) -> 'PositionModel':
        """Create model from domain entity"""
        return cls(
            id=position.id,
            symbol_base=position.symbol.base,
            symbol_quote=position.symbol.quote,
            side=position.side.value,
            entry_price=position.entry_price.value,
            quantity=position.quantity,
            opened_at=position.opened_at,
            status=position.status.value,
            current_price=position.current_price.value if position.current_price else None,
            take_profit=position.take_profit.value if position.take_profit else None,
            stop_loss=position.stop_loss.value if position.stop_loss else None,
            closed_at=position.closed_at,
            closed_price=position.closed_price.value if position.closed_price else None,
            pnl=position.pnl,
            pnl_percentage=position.pnl_percentage,
        )
    
    def to_entity(self) -> Position:
        """Convert model to domain entity"""
        symbol = Symbol(base=self.symbol_base, quote=self.symbol_quote)
        entry_price = Price(self.entry_price, "USDT")
        
        return Position(
            id=self.id,
            symbol=symbol,
            side=PositionSide(self.side),
            entry_price=entry_price,
            quantity=self.quantity,
            opened_at=self.opened_at,
            status=PositionStatus(self.status),
            current_price=Price(self.current_price, "USDT") if self.current_price else None,
            take_profit=Price(self.take_profit, "USDT") if self.take_profit else None,
            stop_loss=Price(self.stop_loss, "USDT") if self.stop_loss else None,
            closed_at=self.closed_at,
            closed_price=Price(self.closed_price, "USDT") if self.closed_price else None,
            pnl=self.pnl,
            pnl_percentage=self.pnl_percentage,
        )

