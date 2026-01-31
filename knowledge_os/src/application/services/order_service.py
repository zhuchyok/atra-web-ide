"""
Order Service - Application Service

Orchestrates order-related use cases.
"""

from typing import List
from decimal import Decimal
from typing import Optional

from src.domain.entities.order import Order, OrderSide, OrderType
from src.domain.repositories.order_repository import OrderRepository
from src.domain.value_objects.price import Price
from src.domain.value_objects.symbol import Symbol
from src.application.use_cases.orders.place_order import PlaceOrderUseCase


class OrderService:
    """
    Application Service for order operations
    
    This service orchestrates multiple use cases and provides
    a higher-level interface for order management.
    """
    
    def __init__(
        self,
        order_repository: OrderRepository,
        place_order_use_case: PlaceOrderUseCase,
    ):
        self._order_repository = order_repository
        self._place_order = place_order_use_case
    
    async def place_limit_order(
        self,
        symbol: Symbol,
        side: OrderSide,
        quantity: Decimal,
        price: Price,
    ) -> Order:
        """
        Place a limit order
        
        Returns:
            Created Order entity
        """
        return await self._place_order.execute(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=price,
        )
    
    async def place_market_order(
        self,
        symbol: Symbol,
        side: OrderSide,
        quantity: Decimal,
    ) -> Order:
        """
        Place a market order
        
        Returns:
            Created Order entity
        """
        return await self._place_order.execute(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            price=None,
        )
    
    async def get_pending_orders(self) -> List[Order]:
        """Get all pending orders"""
        return await self._order_repository.get_pending_orders()
    
    async def get_order_by_id(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        return await self._order_repository.get_by_id(order_id)

