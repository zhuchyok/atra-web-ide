"""
Bitget Exchange Adapter

Infrastructure implementation of ExchangeAdapter for Bitget exchange.
"""

from decimal import Decimal
from typing import Optional
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now

import ccxt

from ...base import ExchangeAdapter
from src.domain.value_objects.price import Price
from src.domain.value_objects.symbol import Symbol
from src.domain.entities.position import PositionSide
from src.shared.types.types import OrderResponse
from src.shared.config.settings import settings


class BitgetAdapter(ExchangeAdapter):
    """Bitget exchange adapter implementation"""
    
    def __init__(self):
        """Initialize Bitget exchange client"""
        self._exchange = ccxt.bitget({
            'apiKey': settings.exchange.api_key,
            'secret': settings.exchange.api_secret,
            'sandbox': settings.exchange.sandbox,
            'enableRateLimit': True,
        })
    
    async def get_current_price(self, symbol: Symbol) -> Price:
        """Get current market price from Bitget"""
        ticker = self._exchange.fetch_ticker(symbol.pair)
        return Price(Decimal(str(ticker['last'])), "USDT")
    
    async def place_order(
        self,
        symbol: Symbol,
        side: PositionSide,
        quantity: Decimal,
        price: Optional[Price] = None,
    ) -> str:
        """Place order on Bitget"""
        order_type = 'limit' if price else 'market'
        order_side = 'buy' if side == PositionSide.LONG else 'sell'
        
        order = self._exchange.create_order(
            symbol=symbol.pair,
            type=order_type,
            side=order_side,
            amount=float(quantity),
            price=float(price.value) if price else None,
        )
        
        return order['id']
    
    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Get order status from Bitget"""
        # Implementation would fetch order from exchange
        # This is a placeholder
        return {
            'order_id': order_id,
            'symbol': '',
            'side': '',
            'quantity': Decimal('0'),
            'price': Decimal('0'),
            'status': 'pending',
            'filled_quantity': Decimal('0'),
            'timestamp': get_utc_now(),
        }
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order on Bitget"""
        try:
            self._exchange.cancel_order(order_id)
            return True
        except Exception:
            return False
    
    async def get_balance(self, currency: str) -> Decimal:
        """Get account balance from Bitget"""
        balance = self._exchange.fetch_balance()
        return Decimal(str(balance.get(currency, {}).get('free', 0)))

