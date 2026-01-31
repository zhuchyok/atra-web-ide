"""
Base Exchange Adapter

Abstract base class for exchange adapters.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

from src.domain.value_objects.price import Price
from src.domain.value_objects.symbol import Symbol
from src.domain.entities.position import PositionSide
from src.shared.types.types import OrderRequest, OrderResponse


class ExchangeAdapter(ABC):
    """Abstract exchange adapter"""
    
    @abstractmethod
    async def get_current_price(self, symbol: Symbol) -> Price:
        """Get current market price"""
        pass
    
    @abstractmethod
    async def place_order(
        self,
        symbol: Symbol,
        side: PositionSide,
        quantity: Decimal,
        price: Optional[Price] = None,
    ) -> str:
        """
        Place order on exchange
        
        Args:
            symbol: Trading symbol
            side: Position side (LONG/SHORT)
            quantity: Order quantity
            price: Order price (None for market orders)
            
        Returns:
            Order ID
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get order status"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        pass
    
    @abstractmethod
    async def get_balance(self, currency: str) -> Decimal:
        """Get account balance for currency"""
        pass

