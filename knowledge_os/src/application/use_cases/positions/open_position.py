"""
Open Position Use Case

This use case handles opening a new trading position.
"""

from typing import Protocol
from decimal import Decimal
from src.shared.utils.datetime_utils import get_utc_now

from src.domain.entities.position import Position, PositionSide, PositionStatus
from src.domain.entities.signal import Signal
from src.domain.repositories.position_repository import PositionRepository
from src.domain.services.risk_calculator import RiskCalculator
from src.domain.value_objects.price import Price
from src.domain.value_objects.symbol import Symbol


class ExchangeAdapter(Protocol):
    """Protocol for exchange operations"""

    async def place_order(
        self,
        symbol: Symbol,
        side: PositionSide,
        quantity: Decimal,
        price: Price,
    ) -> str:
        """Place order and return order ID"""

    async def get_current_price(self, symbol: Symbol) -> Price:
        """Get current market price"""


class OpenPositionUseCase:
    """Use case for opening a trading position"""

    def __init__(
        self,
        position_repository: PositionRepository,
        exchange_adapter: ExchangeAdapter,
        risk_calculator: RiskCalculator,
        account_balance: Decimal,
    ):
        self._position_repository = position_repository
        self._exchange = exchange_adapter
        self._risk_calculator = risk_calculator
        self._account_balance = account_balance

    async def execute(
        self,
        signal: Signal,
        risk_percentage: Decimal,
    ) -> Position:
        """
        Open a new position based on signal
        
        Args:
            signal: Trading signal
            risk_percentage: Risk percentage for position sizing
            
        Returns:
            Created Position entity
        """
        # Convert signal to domain objects
        symbol = Symbol.from_string(signal.symbol)
        side = PositionSide.LONG if signal.side.value == "long" else PositionSide.SHORT
        entry_price = Price(signal.entry_price, "USDT")
        stop_loss = Price(signal.stop_loss, "USDT")

        # Calculate position size based on risk
        position_size = self._risk_calculator.calculate_position_size(
            account_balance=self._account_balance,
            risk_percentage=risk_percentage,
            entry_price=entry_price,
            stop_loss=stop_loss,
        )

        # Get current price
        current_price = await self._exchange.get_current_price(symbol)

        # Place order on exchange
        order_id = await self._exchange.place_order(
            symbol=symbol,
            side=side,
            quantity=position_size,
            price=entry_price,
        )

        # Create position entity
        position = Position(
            id=order_id,
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=position_size,
            opened_at=get_utc_now(),
            status=PositionStatus.OPEN,
            current_price=current_price,
            take_profit=Price(signal.take_profit, "USDT"),
            stop_loss=stop_loss,
        )

        # Save to repository
        saved_position = await self._position_repository.save(position)

        return saved_position
