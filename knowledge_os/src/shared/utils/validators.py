"""
Validation Utilities

Shared validation functions.
"""

from decimal import Decimal
from typing import Optional


def validate_price(price: Decimal, min_price: Optional[Decimal] = None) -> bool:
    """
    Validate price value
    
    Args:
        price: Price to validate
        min_price: Minimum price (optional)
        
    Returns:
        True if valid
    """
    if price <= 0:
        return False
    
    if min_price and price < min_price:
        return False
    
    return True


def validate_quantity(quantity: Decimal, min_quantity: Optional[Decimal] = None) -> bool:
    """
    Validate quantity value
    
    Args:
        quantity: Quantity to validate
        min_quantity: Minimum quantity (optional)
        
    Returns:
        True if valid
    """
    if quantity <= 0:
        return False
    
    if min_quantity and quantity < min_quantity:
        return False
    
    return True


def validate_percentage(percentage: Decimal, min_val: Decimal = Decimal("0"), max_val: Decimal = Decimal("100")) -> bool:
    """
    Validate percentage value
    
    Args:
        percentage: Percentage to validate
        min_val: Minimum value (default 0)
        max_val: Maximum value (default 100)
        
    Returns:
        True if valid
    """
    return min_val <= percentage <= max_val


def validate_symbol(symbol: str) -> bool:
    """
    Validate trading symbol format
    
    Args:
        symbol: Symbol to validate
        
    Returns:
        True if valid
    """
    if not symbol or len(symbol) < 3:
        return False
    
    # Basic validation - alphanumeric
    return symbol.replace("/", "").replace("-", "").isalnum()

