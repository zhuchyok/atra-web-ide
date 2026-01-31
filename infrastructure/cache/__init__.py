"""
Stateless cache infrastructure for ATRA trading system.

This module provides stateless cache managers that explicitly manage state
instead of using module-level variables.
"""

from .stateless_cache import (
    CacheEntry,
    StatelessCacheManager,
)

__all__ = [
    'CacheEntry',
    'StatelessCacheManager',
]

