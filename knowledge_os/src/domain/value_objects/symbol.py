"""
Symbol Value Object

Immutable value object representing a trading symbol.
"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Symbol:
    """
    Symbol Value Object
    
    Immutable representation of a trading symbol with validation.
    """
    
    base: str  # e.g., "BTC"
    quote: str  # e.g., "USDT"
    
    def __post_init__(self):
        """Validate symbol components"""
        if not self.base or not self.quote:
            raise ValueError("Base and quote cannot be empty")
        
        # Validate format (alphanumeric, uppercase)
        if not re.match(r'^[A-Z0-9]+$', self.base.upper()):
            raise ValueError(f"Invalid base symbol format: {self.base}")
        if not re.match(r'^[A-Z0-9]+$', self.quote.upper()):
            raise ValueError(f"Invalid quote symbol format: {self.quote}")
    
    @property
    def pair(self) -> str:
        """Get trading pair string (e.g., 'BTCUSDT')"""
        return f"{self.base}{self.quote}"
    
    @property
    def pair_with_separator(self) -> str:
        """Get trading pair with separator (e.g., 'BTC/USDT')"""
        return f"{self.base}/{self.quote}"
    
    @classmethod
    def from_string(cls, symbol_str: str) -> 'Symbol':
        """
        Create Symbol from string
        
        Supports formats:
        - "BTCUSDT" -> Symbol("BTC", "USDT")
        - "BTC/USDT" -> Symbol("BTC", "USDT")
        - "BTC-USDT" -> Symbol("BTC", "USDT")
        """
        # Remove separators
        clean = symbol_str.replace("/", "").replace("-", "").upper()
        
        # Common quote currencies
        quotes = ["USDT", "USDC", "BUSD", "BTC", "ETH", "BNB"]
        
        for quote in quotes:
            if clean.endswith(quote):
                base = clean[:-len(quote)]
                if base:
                    return cls(base=base, quote=quote)
        
        # Fallback: try to split in the middle (for unknown quotes)
        if len(clean) >= 6:
            mid = len(clean) // 2
            return cls(base=clean[:mid], quote=clean[mid:])
        
        raise ValueError(f"Cannot parse symbol: {symbol_str}")
    
    def __str__(self) -> str:
        return self.pair
    
    def __repr__(self) -> str:
        return f"Symbol(base='{self.base}', quote='{self.quote}')"

