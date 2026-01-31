"""
Position Repository Interface - Domain Repository

This is an abstract interface for position persistence.
Implementation is in Infrastructure layer.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from ..entities.position import Position, PositionStatus
from ..value_objects.symbol import Symbol


class PositionRepository(ABC):
    """Abstract repository for Position entities"""
    
    @abstractmethod
    async def save(self, position: Position) -> Position:
        """Save a position"""
        pass
    
    @abstractmethod
    async def get_by_id(self, position_id: str) -> Optional[Position]:
        """Get position by ID"""
        pass
    
    @abstractmethod
    async def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        pass
    
    @abstractmethod
    async def get_by_symbol(
        self, 
        symbol: Symbol, 
        status: Optional[PositionStatus] = None,
        limit: int = 10
    ) -> List[Position]:
        """Get positions by symbol"""
        pass
    
    @abstractmethod
    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Position]:
        """Get positions by date range"""
        pass

