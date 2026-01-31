"""
Common Type Definitions

Shared type definitions used across the application.
"""

from typing import TypedDict, Optional
from decimal import Decimal
from datetime import datetime


class TradingPair(TypedDict):
    """Trading pair representation"""
    base: str
    quote: str
    symbol: str


class MarketData(TypedDict):
    """Market data snapshot"""
    symbol: str
    price: Decimal
    volume: Decimal
    timestamp: datetime
    high_24h: Optional[Decimal]
    low_24h: Optional[Decimal]
    change_24h: Optional[Decimal]


class OrderRequest(TypedDict):
    """Order request"""
    symbol: str
    side: str  # "buy" or "sell"
    quantity: Decimal
    price: Optional[Decimal]  # None for market orders
    order_type: str  # "limit" or "market"


class OrderResponse(TypedDict):
    """Order response"""
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    status: str
    filled_quantity: Decimal
    timestamp: datetime


class RiskMetrics(TypedDict):
    """Risk metrics"""
    total_risk_percentage: float
    max_drawdown_percentage: float
    total_exposure: float
    total_pnl: float
    open_positions_count: int

