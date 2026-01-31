#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Centralized stablecoin filtering helpers.

Provides a single place to decide whether a symbol should be skipped
in data-fetching contexts, while allowing exceptions for cases like
open-position monitoring or depeg monitoring.
"""

from typing import Optional

try:
    # Prefer canonical list from config
    from config import STABLECOIN_SYMBOLS as _CONFIG_STABLES
except Exception:
    _CONFIG_STABLES = []


# Fallback set if config import fails; kept minimal to avoid divergence
_FALLBACK_STABLES = {
    "USDTUSDT", "USDCUSDT", "BUSDUSDT", "FDUSDUSDT", "TUSDUSDT",
    "USDDUSDT", "USDEUSDT", "DAIUSDT", "FRAXUSDT", "LUSDUSDT",
    "USTCUSDT", "USTUSDT", "MIMUSDT", "ALGUSDT", "EURSUSDT", "USD1USDT",
}


def is_stablecoin(symbol: Optional[str]) -> bool:
    if not symbol:
        return False
    s = symbol.upper()
    if _CONFIG_STABLES:
        return s in _CONFIG_STABLES
    return s in _FALLBACK_STABLES


def should_skip_stablecoin(symbol: Optional[str], context: str = "default") -> bool:
    """
    Returns True if the symbol should be skipped in the given context.

    Contexts (convention):
    - "default" / "data_update" / "price_update": skip stablecoins
    - "position_monitoring": do NOT skip; open positions must be tracked
    - "depeg_monitoring": do NOT skip; allows dedicated depeg checks

    Any unknown context falls back to skipping when it is a stablecoin.
    """
    if not is_stablecoin(symbol):
        return False

    ctx = (context or "").lower()
    if ctx in ("position_monitoring", "depeg_monitoring"):
        return False
    return True


