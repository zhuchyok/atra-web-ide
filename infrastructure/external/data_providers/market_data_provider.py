"""
Market Data Provider Implementation

Infrastructure implementation of market data provider.
"""

from typing import Protocol
from decimal import Decimal

from src.domain.value_objects.price import Price
from src.domain.value_objects.symbol import Symbol
from src.domain.entities.signal import SignalSide
from src.infrastructure.external.exchanges.base import ExchangeAdapter


class MarketDataProvider:
    """
    Market Data Provider Implementation
    
    This is an infrastructure concern - it provides market data.
    """
    
    def __init__(self, exchange_adapter: ExchangeAdapter):
        self._exchange = exchange_adapter
    
    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current market price"""
        symbol_obj = Symbol.from_string(symbol)
        price = await self._exchange.get_current_price(symbol_obj)
        return price.value
    
    async def calculate_take_profit(
        self, 
        symbol: str, 
        entry: Decimal, 
        side: SignalSide
    ) -> Decimal:
        """Calculate take profit level"""
        # Simple calculation (can be enhanced with ATR, volatility, etc.)
        if side == SignalSide.LONG:
            # 5% profit target for LONG
            return entry * Decimal("1.05")
        else:  # SHORT
            # 5% profit target for SHORT
            return entry * Decimal("0.95")
    
    async def calculate_stop_loss(
        self, 
        symbol: str, 
        entry: Decimal, 
        side: SignalSide
    ) -> Decimal:
        """Calculate stop loss level"""
        # Simple calculation (can be enhanced with ATR, volatility, etc.)
        if side == SignalSide.LONG:
            # 3% stop loss for LONG
            return entry * Decimal("0.97")
        else:  # SHORT
            # 3% stop loss for SHORT
            return entry * Decimal("1.03")

