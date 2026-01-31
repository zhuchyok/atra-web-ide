"""
Validation Utilities

Common validation functions.
"""

from decimal import Decimal
from typing import Optional


def validate_positive(value: Decimal, name: str = "Value") -> None:
    """Validate that value is positive"""
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def validate_percentage(value: Decimal, name: str = "Percentage") -> None:
    """Validate that value is a valid percentage (0-100)"""
    if value < 0 or value > 100:
        raise ValueError(f"{name} must be between 0 and 100")


def validate_not_empty(value: str, name: str = "Value") -> None:
    """Validate that string is not empty"""
    if not value or not value.strip():
        raise ValueError(f"{name} cannot be empty")


def validate_range(
    value: Decimal,
    min_value: Optional[Decimal] = None,
    max_value: Optional[Decimal] = None,
    name: str = "Value"
) -> None:
    """Validate that value is within range"""
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be at least {min_value}")
    
    if max_value is not None and value > max_value:
        raise ValueError(f"{name} must be at most {max_value}")

