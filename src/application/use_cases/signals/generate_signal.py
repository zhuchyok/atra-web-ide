"""
Generate Signal Use Case

This use case handles signal generation business logic.
"""

from typing import Protocol
from decimal import Decimal
from src.shared.utils.datetime_utils import get_utc_now

from src.domain.entities.signal import Signal, SignalSide, SignalStatus
from src.domain.repositories.signal_repository import SignalRepository


class MarketDataProvider(Protocol):
    """Protocol for market data provider"""

    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current market price"""

    async def calculate_take_profit(
        self,
        symbol: str,
        entry: Decimal,
        side: SignalSide
    ) -> Decimal:
        """Calculate take profit level"""

    async def calculate_stop_loss(
        self,
        symbol: str,
        entry: Decimal,
        side: SignalSide
    ) -> Decimal:
        """Calculate stop loss level"""


class GenerateSignalUseCase:
    """Use case for generating trading signals"""

    def __init__(
        self,
        signal_repository: SignalRepository,
        market_data_provider: MarketDataProvider,
    ):
        self._signal_repository = signal_repository
        self._market_data = market_data_provider

    async def execute(
        self,
        symbol: str,
        side: SignalSide,
        confidence: Decimal,
        risk_percentage: Decimal,
    ) -> Signal:
        """
        Generate a new trading signal

        Args:
            symbol: Trading pair symbol
            side: Signal direction (LONG/SHORT)
            confidence: Signal confidence (0-1)
            risk_percentage: Risk percentage for position sizing

        Returns:
            Created Signal entity
        """
        # Get current market price
        entry_price = await self._market_data.get_current_price(symbol)

        # Calculate TP/SL
        take_profit = await self._market_data.calculate_take_profit(
            symbol, entry_price, side
        )
        stop_loss = await self._market_data.calculate_stop_loss(
            symbol, entry_price, side
        )

        # Create signal entity
        signal = Signal(
            id=f"{symbol}_{side.value}_{int(get_utc_now().timestamp())}",
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            timestamp=get_utc_now(),
            status=SignalStatus.PENDING,
            confidence=confidence,
            risk_percentage=risk_percentage,
        )

        # Save to repository
        saved_signal = await self._signal_repository.save(signal)

        return saved_signal
