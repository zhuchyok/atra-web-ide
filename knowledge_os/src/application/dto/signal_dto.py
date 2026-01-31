"""
Signal DTO - Data Transfer Object

DTOs are used for data transfer between layers.
They don't contain business logic.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class SignalDTO:
    """Data Transfer Object for Signal"""
    
    id: str
    symbol: str
    side: str  # "long" or "short"
    entry_price: Decimal
    take_profit: Decimal
    stop_loss: Decimal
    timestamp: datetime
    status: str
    confidence: Optional[Decimal] = None
    risk_percentage: Optional[Decimal] = None
    
    @classmethod
    def from_entity(cls, signal) -> 'SignalDTO':
        """Create DTO from Signal entity"""
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
    
    def to_dict(self) -> dict:
        """Convert DTO to dictionary"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': str(self.entry_price),
            'take_profit': str(self.take_profit),
            'stop_loss': str(self.stop_loss),
            'timestamp': self.timestamp.isoformat(),
            'status': self.status,
            'confidence': str(self.confidence) if self.confidence else None,
            'risk_percentage': str(self.risk_percentage) if self.risk_percentage else None,
        }

