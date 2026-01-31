"""
Risk Calculator - Domain Service

Calculates risk metrics for trading positions.
"""

from decimal import Decimal
from typing import List

from ..entities.position import Position
from ..value_objects.price import Price
from ...core.contracts import precondition, postcondition, invariant
from ...core.profiling import profile


class RiskCalculator:
    """
    Domain Service for risk calculations
    
    This service contains business logic that doesn't belong to entities.
    """
    
    @staticmethod
    @profile(threshold_ms=5.0)
    @precondition(
        lambda account_balance, risk_percentage, entry_price, stop_loss: (
            account_balance > Decimal("0") and
            Decimal("0.1") <= risk_percentage <= Decimal("10.0") and
            entry_price.value > Decimal("0") and
            stop_loss.value > Decimal("0")
        ),
        "Invalid input: account_balance > 0, risk_percentage in [0.1, 10.0]%, prices > 0"
    )
    @postcondition(
        lambda result, account_balance, risk_percentage, entry_price, stop_loss: (
            result >= Decimal("0") and
            result * entry_price.value <= account_balance * Decimal("2")  # Позиция не должна превышать 2x баланса
        ),
        "Invalid output: position size must be non-negative and reasonable"
    )
    def calculate_position_size(
        account_balance: Decimal,
        risk_percentage: Decimal,
        entry_price: Price,
        stop_loss: Price,
    ) -> Decimal:
        """
        Calculate position size based on risk
        
        Args:
            account_balance: Total account balance
            risk_percentage: Risk percentage (e.g., 2.0 for 2%)
            entry_price: Entry price
            stop_loss: Stop loss price
            
        Returns:
            Position size in base currency
        """
        if risk_percentage <= 0 or risk_percentage > 100:
            raise ValueError("Risk percentage must be between 0 and 100")
        
        if entry_price.value <= stop_loss.value:
            raise ValueError("Stop loss must be below entry price for LONG")
        
        # Risk amount in quote currency
        risk_amount = account_balance * (risk_percentage / Decimal("100"))
        
        # Price difference
        price_diff = entry_price.value - stop_loss.value
        
        # Position size = risk_amount / price_diff
        position_size = risk_amount / price_diff
        
        return position_size
    
    @staticmethod
    @precondition(
        lambda positions: positions is not None,
        "Invalid input: positions must not be None"
    )
    @postcondition(
        lambda result, positions: (
            result >= Decimal("0") and
            result <= Decimal("100")  # Риск не может превышать 100%
        ),
        "Invalid output: portfolio risk must be between 0% and 100%"
    )
    def calculate_portfolio_risk(positions: List[Position]) -> Decimal:
        """
        Calculate total portfolio risk
        
        Args:
            positions: List of open positions
            
        Returns:
            Total risk as percentage
        """
        if not positions:
            return Decimal("0")
        
        total_risk = Decimal("0")
        for position in positions:
            if position.status.value == "open" and position.pnl_percentage:
                # Risk is negative PnL percentage
                if position.pnl_percentage < 0:
                    total_risk += abs(position.pnl_percentage)
        
        return total_risk
    
    @staticmethod
    def calculate_max_drawdown(positions: List[Position]) -> Decimal:
        """
        Calculate maximum drawdown from positions
        
        Args:
            positions: List of positions (open and closed)
            
        Returns:
            Maximum drawdown as percentage
        """
        if not positions:
            return Decimal("0")
        
        max_dd = Decimal("0")
        peak = Decimal("0")
        
        for position in positions:
            if position.pnl_percentage:
                if position.pnl_percentage > peak:
                    peak = position.pnl_percentage
                
                drawdown = peak - position.pnl_percentage
                if drawdown > max_dd:
                    max_dd = drawdown
        
        return max_dd

