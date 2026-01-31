"""
Signal Service - Application Service

Orchestrates signal-related use cases.
"""

from typing import List
from decimal import Decimal

from src.domain.entities.signal import Signal, SignalSide
from src.domain.repositories.signal_repository import SignalRepository
from src.application.use_cases.signals.generate_signal import GenerateSignalUseCase
from src.application.use_cases.signals.accept_signal import AcceptSignalUseCase
from src.application.dto.signal_dto import SignalDTO


class SignalService:
    """
    Application Service for signal operations
    
    This service orchestrates multiple use cases and provides
    a higher-level interface for signal management.
    """
    
    def __init__(
        self,
        signal_repository: SignalRepository,
        generate_signal_use_case: GenerateSignalUseCase,
        accept_signal_use_case: AcceptSignalUseCase,
    ):
        self._signal_repository = signal_repository
        self._generate_signal = generate_signal_use_case
        self._accept_signal = accept_signal_use_case
    
    async def generate_and_save_signal(
        self,
        symbol: str,
        side: SignalSide,
        confidence: Decimal,
        risk_percentage: Decimal,
    ) -> SignalDTO:
        """
        Generate a new signal and save it
        
        Returns:
            SignalDTO
        """
        signal = await self._generate_signal.execute(
            symbol=symbol,
            side=side,
            confidence=confidence,
            risk_percentage=risk_percentage,
        )
        
        return SignalDTO.from_entity(signal)
    
    async def accept_signal_by_id(self, signal_id: str) -> SignalDTO:
        """
        Accept a signal by ID
        
        Returns:
            SignalDTO
        """
        signal = await self._accept_signal.execute(signal_id)
        return SignalDTO.from_entity(signal)
    
    async def get_pending_signals(self) -> List[SignalDTO]:
        """Get all pending signals"""
        signals = await self._signal_repository.get_pending()
        return [SignalDTO.from_entity(s) for s in signals]
    
    async def get_signals_by_symbol(self, symbol: str, limit: int = 10) -> List[SignalDTO]:
        """Get signals by symbol"""
        signals = await self._signal_repository.get_by_symbol(symbol, limit)
        return [SignalDTO.from_entity(s) for s in signals]

