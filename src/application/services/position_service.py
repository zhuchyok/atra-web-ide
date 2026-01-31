"""
Position Service - Application Service

Orchestrates position-related use cases.
"""

from typing import List
from decimal import Decimal

from src.domain.entities.signal import Signal
from src.domain.entities.position import Position
from src.domain.repositories.position_repository import PositionRepository
from src.application.use_cases.positions.open_position import OpenPositionUseCase
from src.application.use_cases.positions.close_position import ClosePositionUseCase
from src.application.use_cases.risk.calculate_risk import CalculateRiskUseCase


class PositionService:
    """
    Application Service for position operations
    
    This service orchestrates multiple use cases and provides
    a higher-level interface for position management.
    """
    
    def __init__(
        self,
        position_repository: PositionRepository,
        open_position_use_case: OpenPositionUseCase,
        close_position_use_case: ClosePositionUseCase,
        calculate_risk_use_case: CalculateRiskUseCase,
    ):
        self._position_repository = position_repository
        self._open_position = open_position_use_case
        self._close_position = close_position_use_case
        self._calculate_risk = calculate_risk_use_case
    
    async def open_position_from_signal(
        self,
        signal: Signal,
        risk_percentage: Decimal,
    ) -> Position:
        """
        Open a position from a signal
        
        Returns:
            Created Position entity
        """
        return await self._open_position.execute(
            signal=signal,
            risk_percentage=risk_percentage,
        )
    
    async def close_position_by_id(self, position_id: str) -> Position:
        """
        Close a position by ID
        
        Returns:
            Closed Position entity
        """
        return await self._close_position.execute(position_id)
    
    async def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        return await self._position_repository.get_open_positions()
    
    async def get_portfolio_risk(self) -> dict:
        """Get portfolio risk metrics"""
        return await self._calculate_risk.execute()

