"""
Stateless cache registry for ATRA trading system.

This module provides a centralized cache registry that manages all caches
using stateless architecture principles, replacing module-level variables
with explicit state management.
"""

from typing import Optional, Any
from src.shared.utils.datetime_utils import get_utc_now

try:
    from src.infrastructure.cache import StatelessCacheManager
except ImportError:
    StatelessCacheManager = None


class CacheRegistry:
    """
    Centralized cache registry for ATRA trading system.
    
    This class manages all caches using stateless architecture:
    - Sent signals cache (prevents duplicate signals)
    - Anomaly cache (volume/market cap anomalies)
    - News cache (news filtering)
    
    Example:
        ```python
        registry = get_cache_registry()
        
        # Use sent signals cache
        cached = registry.sent_signals.get("signal_key")
        registry.sent_signals.set("signal_key", data, ttl=60)
        
        # Use anomaly cache
        cached = registry.anomalies.get("anomaly_key")
        registry.anomalies.set("anomaly_key", data, ttl=600)
        ```
    """
    
    def __init__(self):
        """Initialize cache registry with stateless cache managers"""
        if StatelessCacheManager is not None:
            # Use stateless cache managers
            self.sent_signals = StatelessCacheManager()
            self.anomalies = StatelessCacheManager()
            self.news_blocked = StatelessCacheManager()
            self.news_positive = StatelessCacheManager()
            self.news_combined = StatelessCacheManager()
            self._use_dict_cache = False
        else:
            # Fallback to dict-based cache if StatelessCacheManager unavailable
            self.sent_signals = {}
            self.anomalies = {}
            self.news_blocked = {}
            self.news_positive = {}
            self.news_combined = {}
            self._use_dict_cache = True
    
    def clear_all(self) -> None:
        """Clear all caches"""
        if self._use_dict_cache:
            self.sent_signals.clear()
            self.anomalies.clear()
            self.news_blocked.clear()
            self.news_positive.clear()
            self.news_combined.clear()
        else:
            self.sent_signals.clear()
            self.anomalies.clear()
            self.news_blocked.clear()
            self.news_positive.clear()
            self.news_combined.clear()
    
    def get_sent_signals_dict(self) -> dict:
        """
        Get sent signals cache as dict (for backward compatibility).
        
        Returns:
            Dictionary representation of sent signals cache
        """
        if self._use_dict_cache:
            return self.sent_signals
        
        # Convert StatelessCacheManager to dict
        result = {}
        for key in self.sent_signals.get_all_keys():
            value = self.sent_signals.get(key)
            if value:
                result[key] = value
        return result
    
    def get_anomaly_cache_dict(self) -> dict:
        """
        Get anomaly cache as dict (for backward compatibility).
        
        Returns:
            Dictionary representation of anomaly cache
        """
        if self._use_dict_cache:
            return self.anomalies
        
        # Convert StatelessCacheManager to dict
        result = {}
        for key in self.anomalies.get_all_keys():
            value = self.anomalies.get(key)
            if value:
                result[key] = value
        return result
    
    def get_news_cache_dict(self) -> dict:
        """
        Get news cache as dict (for backward compatibility).
        
        Returns:
            Dictionary representation of news cache
        """
        if self._use_dict_cache:
            return {
                'blocked': self.news_blocked,
                'positive': self.news_positive,
                'combined': self.news_combined
            }
        
        # Convert StatelessCacheManager to dict
        result = {
            'blocked': {},
            'positive': {},
            'combined': {}
        }
        
        for key in self.news_blocked.get_all_keys():
            value = self.news_blocked.get(key)
            if value:
                result['blocked'][key] = value
        
        for key in self.news_positive.get_all_keys():
            value = self.news_positive.get(key)
            if value:
                result['positive'][key] = value
        
        for key in self.news_combined.get_all_keys():
            value = self.news_combined.get(key)
            if value:
                result['combined'][key] = value
        
        return result


# Singleton instance for application-wide cache registry
_cache_registry: Optional[CacheRegistry] = None


def get_cache_registry() -> CacheRegistry:
    """
    Get singleton cache registry instance.
    
    Returns:
        CacheRegistry instance
    """
    global _cache_registry
    if _cache_registry is None:
        _cache_registry = CacheRegistry()
    return _cache_registry


def reset_cache_registry() -> None:
    """Reset cache registry (useful for testing)"""
    global _cache_registry
    _cache_registry = None


def get_cache_stats() -> dict:
    """
    Get cache statistics (for monitoring).
    
    Returns:
        Dictionary with cache statistics
    """
    registry = get_cache_registry()
    stats = {
        "sent_signals": len(registry.get_sent_signals_dict()),
        "anomalies": len(registry.get_anomaly_cache_dict()),
        "news_combined": len(registry.news_combined) if registry._use_dict_cache else "active"
    }
    return stats


# Backward compatibility functions
def get_cached_news(symbol: str) -> Optional[Any]:
    """
    Get cached news for symbol (backward compatibility)
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        
    Returns:
        Cached news data or None
    """
    registry = get_cache_registry()
    return registry.news_combined.get(f"news:{symbol}")


def cache_news(symbol: str, news_data: Any, ttl: Optional[int] = 900):
    """
    Cache news for symbol (backward compatibility)
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        news_data: News data to cache
        ttl: Time to live in seconds (default: 900 = 15 minutes)
    """
    registry = get_cache_registry()
    registry.news_combined.set(f"news:{symbol}", news_data, ttl)


def get_cached_anomaly(symbol: str) -> Optional[Any]:
    """
    Get cached anomaly data for symbol (backward compatibility)
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        
    Returns:
        Cached anomaly data or None
    """
    registry = get_cache_registry()
    return registry.anomalies.get(f"anomaly:{symbol}")


def cache_anomaly(symbol: str, anomaly_data: Any, ttl: Optional[int] = 600):
    """
    Cache anomaly data for symbol (backward compatibility)
    
    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')
        anomaly_data: Anomaly data to cache
        ttl: Time to live in seconds (default: 600 = 10 minutes)
    """
    registry = get_cache_registry()
    registry.anomalies.set(f"anomaly:{symbol}", anomaly_data, ttl)
