"""
Close Position Use Case

This use case handles closing a trading position.
"""

from typing import Optional
from src.shared.utils.datetime_utils import get_utc_now

from src.domain.entities.position import Position
from src.domain.repositories.position_repository import PositionRepository
from src.domain.value_objects.price import Price
from src.infrastructure.external.exchanges.base import ExchangeAdapter


class ClosePositionUseCase:
    """Use case for closing a trading position"""

    def __init__(
        self,
        position_repository: PositionRepository,
        exchange_adapter: ExchangeAdapter,
    ):
        self._position_repository = position_repository
        self._exchange = exchange_adapter

    async def execute(
        self,
        position_id: str,
        close_price: Optional[Price] = None,
    ) -> Position:
        """
        Close a position

        Args:
            position_id: ID of the position to close
            close_price: Close price (None to use current market price)

        Returns:
            Closed Position entity
        """
        # Get position from repository
        position = await self._position_repository.get_by_id(position_id)

        if position is None:
            raise ValueError(f"Position {position_id} not found")

        if position.status.value != "open":
            raise ValueError(f"Cannot close position in status {position.status}")

        # Get close price if not provided
        if close_price is None:
            close_price = await self._exchange.get_current_price(position.symbol)

        # Close position (domain logic)
        closed_position = position.close(close_price, get_utc_now())

        # Save to repository
        saved_position = await self._position_repository.save(closed_position)

        return saved_position
