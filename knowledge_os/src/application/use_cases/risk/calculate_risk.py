"""
Calculate Risk Use Case

This use case handles risk calculation for positions.
"""

from typing import List
from decimal import Decimal

from src.domain.entities.position import Position
from src.domain.repositories.position_repository import PositionRepository
from src.domain.services.risk_calculator import RiskCalculator


class CalculateRiskUseCase:
    """Use case for calculating portfolio risk"""
    
    def __init__(
        self,
        position_repository: PositionRepository,
        risk_calculator: RiskCalculator,
    ):
        self._position_repository = position_repository
        self._risk_calculator = risk_calculator
    
    async def execute(self) -> dict:
        """
        Calculate portfolio risk metrics
        
        Returns:
            Dictionary with risk metrics
        """
        # Get all open positions
        positions = await self._position_repository.get_open_positions()
        
        # Calculate risk metrics
        total_risk = self._risk_calculator.calculate_portfolio_risk(positions)
        max_drawdown = self._risk_calculator.calculate_max_drawdown(positions)
        
        # Calculate total exposure
        total_exposure = sum(
            pos.entry_price.value * pos.quantity 
            for pos in positions 
            if pos.status.value == "open"
        )
        
        # Calculate total PnL
        total_pnl = sum(
            pos.pnl or Decimal("0") 
            for pos in positions 
            if pos.pnl is not None
        )
        
        return {
            'total_risk_percentage': float(total_risk),
            'max_drawdown_percentage': float(max_drawdown),
            'total_exposure': float(total_exposure),
            'total_pnl': float(total_pnl),
            'open_positions_count': len(positions),
        }

