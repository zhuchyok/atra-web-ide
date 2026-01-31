# -*- coding: utf-8 -*-
"""
Cache management for exchange data

⚠️ MIGRATION TO STATELESS ARCHITECTURE:
This module is being migrated to stateless architecture. The old module-level
variables are being replaced with explicit state management through
StatelessCacheManager.

For new code, use StatelessCacheManager from src.infrastructure.cache.
For existing code, backward compatibility is maintained through a singleton
instance.
"""
import time
from typing import Optional, Dict, Any

# Try to import external cache manager, fallback to local if not available
try:
    try:
        from src.utils.cache_utils import CacheManager as ExternalCacheManager  # noqa: F401
    except ImportError:
        from cache_utils import CacheManager as ExternalCacheManager  # noqa: F401
    EXTERNAL_CACHE_AVAILABLE = True
except ImportError:
    ExternalCacheManager = None  # Placeholder for when import fails
    EXTERNAL_CACHE_AVAILABLE = False

# Import stateless cache manager
try:
    from src.infrastructure.cache import StatelessCacheManager
except ImportError:
    # Fallback if stateless cache is not available
    StatelessCacheManager = None

# Constants
CACHE_TTL = 10  # seconds
SYMBOL_INFO_CACHE_TTL = 3600  # 1 hour

# =============================================================================
# STATELESS CACHE MANAGER (NEW APPROACH)
# =============================================================================

class StatelessCacheManagerWrapper:
    """
    Wrapper for stateless cache management.
    
    This class provides a stateless interface for cache management,
    replacing module-level variables with explicit state.
    """
    
    def __init__(self):
        """Initialize with stateless cache managers"""
        if StatelessCacheManager is not None:
            self._symbol_info_cache = StatelessCacheManager()
            self._pairs_cache = StatelessCacheManager()
            self._price_cache = StatelessCacheManager()
        else:
            # Fallback to dict-based cache if StatelessCacheManager unavailable
            self._symbol_info_cache = {}
            self._pairs_cache = {}
            self._price_cache = {}
            self._use_dict_cache = True
            return
        
        self._use_dict_cache = False
    
    def clear_symbol_info_cache(self):
        """Clears symbol info cache"""
        if self._use_dict_cache:
            self._symbol_info_cache.clear()
        else:
            self._symbol_info_cache.clear()
        print("🧹 Кэш информации о символах очищен")
    
    def get_symbol_info_cache(self) -> Dict[str, Any]:
        """
        Gets symbol info cache.
        
        Returns:
            Cache dictionary (for backward compatibility)
        """
        if self._use_dict_cache:
            return self._symbol_info_cache
        
        # Convert StatelessCacheManager to dict for backward compatibility
        result = {}
        for key in self._symbol_info_cache.get_all_keys():
            value = self._symbol_info_cache.get(key)
            if value:
                result[key] = value
        return result
    
    def set_symbol_info_cache(self, symbol: str, data: Dict[str, Any], timestamp: float):
        """
        Sets data in symbol info cache.
        
        Args:
            symbol: Symbol name
            data: Symbol info data
            timestamp: Timestamp
        """
        if self._use_dict_cache:
            self._symbol_info_cache[symbol] = {"data": data, "ts": timestamp}
        else:
            # Store in stateless cache with TTL
            cache_entry = {"data": data, "ts": timestamp}
            self._symbol_info_cache.set(
                f"symbol_info:{symbol}",
                cache_entry,
                ttl=SYMBOL_INFO_CACHE_TTL
            )
    
    def get_symbol_info_from_cache(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Gets symbol info from cache.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Cached symbol info or None
        """
        if self._use_dict_cache:
            return self._symbol_info_cache.get(symbol)
        
        return self._symbol_info_cache.get(f"symbol_info:{symbol}")
    
    def get_pairs_cache(self) -> Dict[str, Any]:
        """
        Gets pairs cache.
        
        Returns:
            Cache dictionary (for backward compatibility)
        """
        if self._use_dict_cache:
            return self._pairs_cache
        
        # Convert StatelessCacheManager to dict for backward compatibility
        result = {}
        for key in self._pairs_cache.get_all_keys():
            value = self._pairs_cache.get(key)
            if value:
                result[key] = value
        return result
    
    def set_pairs_cache_value(self, key: str, value: Any):
        """
        Sets value in pairs cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        if self._use_dict_cache:
            self._pairs_cache[key] = value
        else:
            self._pairs_cache.set(f"pairs:{key}", value, ttl=CACHE_TTL)


# =============================================================================
# LEGACY CACHE MANAGER (BACKWARD COMPATIBILITY)
# =============================================================================

class CacheManager:
    """
    Legacy cache manager for backward compatibility.
    
    ⚠️ DEPRECATED: Use StatelessCacheManagerWrapper for new code.
    This class is maintained for backward compatibility only.
    """
    
    # Singleton instance for application-wide cache
    _instance: Optional['StatelessCacheManagerWrapper'] = None
    
    @classmethod
    def _get_instance(cls) -> 'StatelessCacheManagerWrapper':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = StatelessCacheManagerWrapper()
        return cls._instance
    
    @staticmethod
    def clear_symbol_info_cache():
        """Clears symbol info cache"""
        CacheManager._get_instance().clear_symbol_info_cache()
    
    @staticmethod
    def get_symbol_info_cache():
        """Gets symbol info cache (for backward compatibility)"""
        return CacheManager._get_instance().get_symbol_info_cache()
    
    @staticmethod
    def set_symbol_info_cache(symbol, data, timestamp):
        """Sets data in symbol info cache"""
        CacheManager._get_instance().set_symbol_info_cache(symbol, data, timestamp)
    
    @staticmethod
    def get_pairs_cache():
        """Gets pairs cache"""
        return CacheManager._get_instance().get_pairs_cache()
    
    @staticmethod
    def set_pairs_cache_value(key, value):
        """Sets value in pairs cache"""
        CacheManager._get_instance().set_pairs_cache_value(key, value)


def clear_symbol_info_cache():
    """Clears symbol info cache"""
    CacheManager.clear_symbol_info_cache()


async def get_dynamic_price_precision(
    symbol: str,
    cache_manager: Optional[StatelessCacheManagerWrapper] = None
):
    """
    Gets price precision for symbol from exchange.
    
    Args:
        symbol: Symbol name (e.g., 'BTCUSDT')
        cache_manager: Optional cache manager instance (uses singleton if None)
    
    Returns:
        Price precision (number of decimal places)
    """
    try:
        from src.utils.exchange_utils import get_symbol_precision
        symbol_info = await get_symbol_info(symbol, cache_manager=cache_manager)
        return symbol_info.get("price_precision", 2)
    except (ValueError, TypeError, AttributeError) as e:
        import logging
        logging.error("Ошибка получения точности для %s: %s", symbol, e)
        # Fallback to static function
        from src.utils.exchange_utils import get_symbol_precision
        return get_symbol_precision(symbol)


async def get_symbol_info(
    symbol: str,
    cache_manager: Optional[StatelessCacheManagerWrapper] = None
):
    """
    Gets symbol info with caching.
    
    Args:
        symbol: Symbol name (e.g., 'BTCUSDT')
        cache_manager: Optional cache manager instance (uses singleton if None)
    
    Returns:
        Dictionary with symbol information
    """
    # Use singleton instance if not provided (backward compatibility)
    if cache_manager is None:
        cache_manager = CacheManager._get_instance()
    
    now = time.time()
    
    # Try to get from cache
    cached_entry = cache_manager.get_symbol_info_from_cache(symbol)
    if cached_entry:
        # Check if entry is still valid
        if isinstance(cached_entry, dict) and "ts" in cached_entry:
            if now - cached_entry["ts"] < SYMBOL_INFO_CACHE_TTL:
                return cached_entry["data"]
        else:
            # New stateless cache format
            return cached_entry

    # Get symbol info from exchanges (Bybit + Binance fallback for qty/step/minNotional)
    try:
        import requests
        import logging

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

        # 1) Bybit: price filters
        bybit_url = f"https://api.bybit.com/v5/market/instruments-info?category=spot&symbol={symbol}"
        price_tick = 0.0
        price_precision = 8
        min_price = 0.0
        max_price = 0.0
        try:
            resp = session.get(bybit_url, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("result", {}).get("list"):
                    item = data["result"]["list"][0]
                    price_tick = float(item.get("priceFilter", {}).get("tickSize", 0))
                    from src.utils.exchange_utils import get_price_precision_from_tick
                    price_precision = get_price_precision_from_tick(price_tick)
                    min_price = float(item.get("priceFilter", {}).get("minPrice", 0))
                    max_price = float(item.get("priceFilter", {}).get("maxPrice", 0))
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logging.warning("Bybit symbol info fetch failed for %s: %s", symbol, e)

        # 2) Binance: lots and notional
        qty_precision = None
        step_size = None
        min_notional = None
        try:
            binance_info_url = f"https://api.binance.com/api/v3/exchangeInfo?symbol={symbol}"
            resp_b = session.get(binance_info_url, timeout=20)
            if resp_b.status_code == 200:
                data_b = resp_b.json()
                symbols = data_b.get("symbols", [])
                if symbols:
                    s = symbols[0]
                    filters = s.get("filters", [])
                    lot = next((f for f in filters if f.get("filterType") == "LOT_SIZE"), None)
                    price_f = next((f for f in filters if f.get("filterType") == "PRICE_FILTER"), None)
                    notional_f = next((f for f in filters if f.get("filterType") in ("MIN_NOTIONAL", "NOTIONAL")), None)
                    if lot:
                        step_size = float(lot.get("stepSize", 0)) or None
                        # qty_precision as number of decimal places in step_size
                        if step_size:
                            ss = f"{step_size:.12f}".rstrip('0')
                            qty_precision = len(ss.split(".")[-1]) if "." in ss else 0
                    if price_f and price_tick == 0:
                        price_tick = float(price_f.get("tickSize", 0))
                        from src.utils.exchange_utils import get_price_precision_from_tick
                        price_precision = get_price_precision_from_tick(price_tick)
                        min_price = float(price_f.get("minPrice", 0))
                        max_price = float(price_f.get("maxPrice", 0))
                    if notional_f:
                        # Binance may return minNotional in different filters
                        min_notional = float(notional_f.get("minNotional") or notional_f.get("minNotional", 0) or 0)
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            logging.warning("Binance exchangeInfo fetch failed for %s: %s", e)

        symbol_info = {
            "symbol": symbol,
            "price_tick": price_tick or 0.0,
            "price_precision": price_precision,
            "min_price": min_price,
            "max_price": max_price,
        }
        if qty_precision is not None:
            symbol_info["qty_precision"] = qty_precision
        if step_size is not None:
            symbol_info["step_size"] = step_size
        if min_notional is not None:
            symbol_info["min_notional"] = min_notional

        # Store in cache using stateless approach
        cache_manager.set_symbol_info_cache(symbol, symbol_info, now)
        return symbol_info
    except (requests.exceptions.RequestException, ValueError, KeyError) as e:
        import logging
        logging.error("Ошибка получения информации о символе %s: %s", symbol, str(e))

    # Use new function for precision determination
    from src.utils.exchange_utils import get_symbol_precision
    default_precision = get_symbol_precision(symbol)

    default_info = {
        "symbol": symbol,
        "price_tick": 0.01,
        "price_precision": default_precision,
        "min_price": 0,
        "max_price": 0,
        "qty_precision": 4,
        "step_size": None,
        "min_notional": None,
    }
    # Store in cache using stateless approach
    cache_manager.set_symbol_info_cache(symbol, default_info, now)
    return default_info
