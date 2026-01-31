"""
Signal Repository Interface - Domain Repository

This is an abstract interface for signal persistence.
Implementation is in Infrastructure layer.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from ..entities.signal import Signal


class SignalRepository(ABC):
    """Abstract repository for Signal entities"""
    
    @abstractmethod
    async def save(self, signal: Signal) -> Signal:
        """Save a signal"""
        pass
    
    @abstractmethod
    async def get_by_id(self, signal_id: str) -> Optional[Signal]:
        """Get signal by ID"""
        pass
    
    @abstractmethod
    async def get_pending(self, since: Optional[datetime] = None) -> List[Signal]:
        """Get pending signals"""
        pass
    
    @abstractmethod
    async def get_by_symbol(
        self, 
        symbol: str, 
        limit: int = 10
    ) -> List[Signal]:
        """Get signals by symbol"""
        pass

