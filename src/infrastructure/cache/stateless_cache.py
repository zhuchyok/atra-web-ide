"""
Stateless Cache Manager for ATRA trading system.

This module provides a stateless cache manager that explicitly manages state
instead of using module-level variables. This ensures reusability, testability,
and thread-safety.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from src.shared.utils.datetime_utils import get_utc_now


@dataclass
class CacheEntry:
    """Entry in the cache with TTL support"""
    value: Any
    timestamp: datetime
    ttl: Optional[int] = None  # Time to live in seconds
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        if self.ttl is None:
            return False
        
        elapsed = (get_utc_now() - self.timestamp).total_seconds()
        return elapsed > self.ttl


class StatelessCacheManager:
    """
    Stateless cache manager with explicit state management.
    
    This class manages cache state explicitly, allowing for:
    - Reusability in different contexts
    - Easy testing with different cache states
    - Thread-safe operations
    - Clear debugging (all state is visible)
    
    Example:
        ```python
        cache_manager = StatelessCacheManager()
        
        # Set value with TTL
        cache_manager.set("key", "value", ttl=60)
        
        # Get value
        value = cache_manager.get("key")
        
        # Clear cache
        cache_manager.clear()
        ```
    """
    
    def __init__(self):
        """Initialize empty cache"""
        self._cache: Dict[str, CacheEntry] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        entry = self._cache.get(key)
        if entry is None:
            return None
        
        if entry.is_expired():
            # Remove expired entry
            del self._cache[key]
            return None
        
        return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for no expiration)
        """
        self._cache[key] = CacheEntry(
            value=value,
            timestamp=get_utc_now(),
            ttl=ttl
        )
    
    def delete(self, key: str) -> None:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
        """
        self._cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
    
    def size(self) -> int:
        """Get number of cache entries"""
        return len(self._cache)
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of removed entries
        """
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)
    
    def get_all_keys(self) -> list:
        """Get all cache keys"""
        return list(self._cache.keys())
    
    def has_key(self, key: str) -> bool:
        """
        Check if key exists in cache (and is not expired).
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists and is not expired
        """
        entry = self._cache.get(key)
        if entry is None:
            return False
        
        if entry.is_expired():
            del self._cache[key]
            return False
        
        return True

