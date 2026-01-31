"""
Accept Signal Use Case

This use case handles signal acceptance business logic.
"""

from typing import Protocol
from src.shared.utils.datetime_utils import get_utc_now

from src.domain.entities.signal import Signal
from src.domain.repositories.signal_repository import SignalRepository


class NotificationService(Protocol):
    """Protocol for notification service"""

    async def notify_signal_accepted(self, signal: Signal) -> None:
        """Notify that signal was accepted"""
        pass


class AcceptSignalUseCase:
    """Use case for accepting a trading signal"""

    def __init__(
        self,
        signal_repository: SignalRepository,
        notification_service: NotificationService,
    ):
        self._signal_repository = signal_repository
        self._notification_service = notification_service

    async def execute(self, signal_id: str) -> Signal:
        """
        Accept a signal

        Args:
            signal_id: ID of the signal to accept

        Returns:
            Accepted Signal entity
        """
        # Get signal from repository
        signal = await self._signal_repository.get_by_id(signal_id)

        if signal is None:
            raise ValueError(f"Signal {signal_id} not found")

        # Check if signal is expired
        if signal.is_expired(get_utc_now(), expiry_minutes=60):
            # Auto-reject expired signals
            rejected = signal.reject()
            await self._signal_repository.save(rejected)
            raise ValueError(f"Signal {signal_id} is expired")

        # Accept signal (domain logic)
        accepted = signal.accept()

        # Save to repository
        saved_signal = await self._signal_repository.save(accepted)

        # Notify
        await self._notification_service.notify_signal_accepted(saved_signal)

        return saved_signal

