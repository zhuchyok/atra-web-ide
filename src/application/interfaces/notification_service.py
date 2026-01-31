"""
Notification Service Interface

Application layer interface for notifications.
"""

from typing import Protocol

from src.domain.entities.signal import Signal


class NotificationService(Protocol):
    """Protocol for notification service"""
    
    async def notify_signal_generated(self, signal: Signal) -> None:
        """Notify that a signal was generated"""
        ...
    
    async def notify_signal_accepted(self, signal: Signal) -> None:
        """Notify that a signal was accepted"""
        ...
    
    async def notify_position_opened(self, position) -> None:
        """Notify that a position was opened"""
        ...
    
    async def notify_position_closed(self, position) -> None:
        """Notify that a position was closed"""
        ...

