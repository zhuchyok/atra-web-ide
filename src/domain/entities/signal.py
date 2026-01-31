"""
Signal Entity - Domain Entity

A Signal represents a trading signal with identity and business rules.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from decimal import Decimal


class SignalSide(Enum):
    """Signal direction"""
    LONG = "long"
    SHORT = "short"


class SignalStatus(Enum):
    """Signal status"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class Signal:
    """
    Signal Entity
    
    This is a domain entity representing a trading signal.
    It contains business logic and validation rules.
    """
    
    id: str
    symbol: str
    side: SignalSide
    entry_price: Decimal
    take_profit: Decimal
    stop_loss: Decimal
    timestamp: datetime
    status: SignalStatus = SignalStatus.PENDING
    confidence: Optional[Decimal] = None
    risk_percentage: Optional[Decimal] = None
    
    def __post_init__(self):
        """Validate business rules"""
        if self.entry_price <= 0:
            raise ValueError("Entry price must be positive")
        
        if self.side == SignalSide.LONG:
            if self.take_profit <= self.entry_price:
                raise ValueError("Take profit must be above entry for LONG")
            if self.stop_loss >= self.entry_price:
                raise ValueError("Stop loss must be below entry for LONG")
        else:  # SHORT
            if self.take_profit >= self.entry_price:
                raise ValueError("Take profit must be below entry for SHORT")
            if self.stop_loss <= self.entry_price:
                raise ValueError("Stop loss must be above entry for SHORT")
    
    def accept(self) -> 'Signal':
        """Accept the signal"""
        if self.status != SignalStatus.PENDING:
            raise ValueError(f"Cannot accept signal in status {self.status}")
        
        # Create new instance with updated status (immutable)
        return Signal(
            id=self.id,
            symbol=self.symbol,
            side=self.side,
            entry_price=self.entry_price,
            take_profit=self.take_profit,
            stop_loss=self.stop_loss,
            timestamp=self.timestamp,
            status=SignalStatus.ACCEPTED,
            confidence=self.confidence,
            risk_percentage=self.risk_percentage,
        )
    
    def reject(self) -> 'Signal':
        """Reject the signal"""
        if self.status != SignalStatus.PENDING:
            raise ValueError(f"Cannot reject signal in status {self.status}")
        
        return Signal(
            id=self.id,
            symbol=self.symbol,
            side=self.side,
            entry_price=self.entry_price,
            take_profit=self.take_profit,
            stop_loss=self.stop_loss,
            timestamp=self.timestamp,
            status=SignalStatus.REJECTED,
            confidence=self.confidence,
            risk_percentage=self.risk_percentage,
        )
    
    def is_expired(self, current_time: datetime, expiry_minutes: int = 60) -> bool:
        """Check if signal is expired"""
        age_minutes = (current_time - self.timestamp).total_seconds() / 60
        return age_minutes > expiry_minutes

