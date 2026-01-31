"""
Signal Model - ORM Model

Infrastructure layer model for database persistence.
This is separate from Domain entities.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.domain.entities.signal import Signal, SignalSide, SignalStatus


class SignalModel:
    """
    ORM Model for Signal
    
    This is an infrastructure concern for database persistence.
    It converts between database representation and domain entities.
    """
    
    def __init__(
        self,
        id: str,
        symbol: str,
        side: str,
        entry_price: Decimal,
        take_profit: Decimal,
        stop_loss: Decimal,
        timestamp: datetime,
        status: str = "pending",
        confidence: Optional[Decimal] = None,
        risk_percentage: Optional[Decimal] = None,
    ):
        self.id = id
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.timestamp = timestamp
        self.status = status
        self.confidence = confidence
        self.risk_percentage = risk_percentage
    
    @classmethod
    def from_entity(cls, signal: Signal) -> 'SignalModel':
        """Create model from domain entity"""
        return cls(
            id=signal.id,
            symbol=signal.symbol,
            side=signal.side.value,
            entry_price=signal.entry_price,
            take_profit=signal.take_profit,
            stop_loss=signal.stop_loss,
            timestamp=signal.timestamp,
            status=signal.status.value,
            confidence=signal.confidence,
            risk_percentage=signal.risk_percentage,
        )
    
    def to_entity(self) -> Signal:
        """Convert model to domain entity"""
        return Signal(
            id=self.id,
            symbol=self.symbol,
            side=SignalSide(self.side),
            entry_price=self.entry_price,
            take_profit=self.take_profit,
            stop_loss=self.stop_loss,
            timestamp=self.timestamp,
            status=SignalStatus(self.status),
            confidence=self.confidence,
            risk_percentage=self.risk_percentage,
        )

