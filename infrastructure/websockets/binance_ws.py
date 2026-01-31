import asyncio
import json
import logging
import time
from typing import Dict, Optional
import aiohttp

logger = logging.getLogger(__name__)

class PriceStreamCache:
    """Global cache for latest bid/ask prices from WebSocket stream."""
    _prices: Dict[str, Dict[str, float]] = {}
    _last_update: float = 0

    @classmethod
    def update_price(cls, symbol: str, bid: float, ask: float):
        cls._prices[symbol] = {
            "bid": bid,
            "ask": ask,
            "last": ask,  # Use ask as last price for consistency
            "ts": time.time()
        }
        cls._last_update = time.time()

    @classmethod
    def get_price(cls, symbol: str) -> Optional[Dict[str, float]]:
        return cls._prices.get(symbol)

    @classmethod
    def get_all_prices(cls) -> Dict[str, Dict[str, float]]:
        return cls._prices

class BinanceWebSocketStreamer:
    """Manages Binance WebSocket connection for real-time price updates."""
    
    def __init__(self, url: str = "wss://stream.binance.com:9443/ws/!bookTicker"):
        self.url = url
        self.is_running = False
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Starts the WebSocket stream with auto-reconnect."""
        self.is_running = True
        retry_delay = 1
        
        while self.is_running:
            try:
                async with aiohttp.ClientSession() as session:
                    self._session = session
                    async with session.ws_connect(self.url) as ws:
                        logger.info("✅ Connected to Binance WebSocket !bookTicker stream")
                        retry_delay = 1 # Reset retry delay on successful connection
                        
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                # Binance !bookTicker format: {"u":400900217, "s":"BNBBTC", "b":"0.0024", "B":"10", "a":"0.0025", "A":"10"}
                                symbol = data.get('s')
                                if symbol:
                                    PriceStreamCache.update_price(
                                        symbol, 
                                        float(data.get('b', 0)), 
                                        float(data.get('a', 0))
                                    )
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                break
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                break
                                
            except Exception as e:
                if self.is_running:
                    logger.error(f"❌ Binance WebSocket error: {e}. Reconnecting in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60) # Exponential backoff
            
            if not self.is_running:
                break

    def stop(self):
        """Stops the WebSocket stream."""
        self.is_running = False
        logger.info("Stopping Binance WebSocket streamer...")

# Global instance for easy access
binance_ws_streamer = BinanceWebSocketStreamer()

async def start_binance_ws():
    """Helper function to start the global streamer."""
    await binance_ws_streamer.start()

