"""
Place Order Use Case

This use case handles placing a new trading order.
"""

from decimal import Decimal
from typing import Optional

from src.shared.utils.datetime_utils import get_utc_now
from src.domain.entities.order import Order, OrderSide, OrderType, OrderStatus
from src.domain.entities.position import PositionSide
from src.domain.repositories.order_repository import OrderRepository
from src.domain.value_objects.price import Price
from src.domain.value_objects.symbol import Symbol
from src.infrastructure.external.exchanges.base import ExchangeAdapter


class PlaceOrderUseCase:
    """Use case for placing a trading order"""

    def __init__(
        self,
        order_repository: OrderRepository,
        exchange_adapter: ExchangeAdapter,
    ):
        self._order_repository = order_repository
        self._exchange = exchange_adapter

    async def execute(
        self,
        symbol: Symbol,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Price] = None,
    ) -> Order:
        """
        Place a new order

        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            order_type: Order type (MARKET/LIMIT)
            quantity: Order quantity
            price: Order price (required for LIMIT, None for MARKET)

        Returns:
            Created Order entity
        """
        # Validate
        if order_type == OrderType.LIMIT and price is None:
            raise ValueError("Limit order requires a price")

        if order_type == OrderType.MARKET:
            price = None  # Market orders don't have price

        # Place order on exchange
        exchange_order_id = await self._exchange.place_order(
            symbol=symbol,
            side=PositionSide.LONG if side == OrderSide.BUY else PositionSide.SHORT,
            quantity=quantity,
            price=price,
        )

        # Create order entity
        order = Order(
            id=exchange_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.PENDING,
            filled_quantity=Decimal("0"),
            created_at=get_utc_now(),
        )

        # Save to repository
        saved_order = await self._order_repository.save(order)

        return saved_order

