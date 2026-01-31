"""
Order Repository Interface - Domain Repository

This is an abstract interface for order persistence.
Implementation is in Infrastructure layer.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from ..entities.order import Order, OrderStatus
from ..value_objects.symbol import Symbol


class OrderRepository(ABC):
    """Abstract repository for Order entities"""
    
    @abstractmethod
    async def save(self, order: Order) -> Order:
        """Save an order"""
        pass
    
    @abstractmethod
    async def get_by_id(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        pass
    
    @abstractmethod
    async def get_pending_orders(self) -> List[Order]:
        """Get all pending orders"""
        pass
    
    @abstractmethod
    async def get_by_symbol(
        self, 
        symbol: Symbol, 
        status: Optional[OrderStatus] = None,
        limit: int = 10
    ) -> List[Order]:
        """Get orders by symbol"""
        pass
    
    @abstractmethod
    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Order]:
        """Get orders by date range"""
        pass

