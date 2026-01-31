"""
Price Value Object

Immutable value object representing a price with currency.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class Price:
    """
    Price Value Object
    
    Immutable representation of a price with validation.
    """
    
    value: Decimal
    currency: str = "USDT"
    
    def __post_init__(self):
        """Validate price value"""
        if self.value < 0:
            raise ValueError("Price cannot be negative")
        if not self.currency:
            raise ValueError("Currency cannot be empty")
    
    def __add__(self, other: 'Price') -> 'Price':
        """Add two prices (same currency)"""
        if self.currency != other.currency:
            raise ValueError("Cannot add prices with different currencies")
        return Price(self.value + other.value, self.currency)
    
    def __sub__(self, other: 'Price') -> 'Price':
        """Subtract two prices (same currency)"""
        if self.currency != other.currency:
            raise ValueError("Cannot subtract prices with different currencies")
        return Price(self.value - other.value, self.currency)
    
    def __mul__(self, multiplier: Decimal) -> 'Price':
        """Multiply price by a multiplier"""
        return Price(self.value * multiplier, self.currency)
    
    def __truediv__(self, divisor: Decimal) -> 'Price':
        """Divide price by a divisor"""
        if divisor == 0:
            raise ValueError("Cannot divide by zero")
        return Price(self.value / divisor, self.currency)
    
    def percentage_change(self, other: 'Price') -> Decimal:
        """Calculate percentage change from other price"""
        if self.currency != other.currency:
            raise ValueError("Cannot compare prices with different currencies")
        if other.value == 0:
            raise ValueError("Cannot calculate percentage change from zero")
        return ((self.value - other.value) / other.value) * Decimal("100")
    
    def __str__(self) -> str:
        return f"{self.value} {self.currency}"

