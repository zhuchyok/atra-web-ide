"""
Telegram Notification Service Implementation

Infrastructure implementation of NotificationService using Telegram.
"""

from src.application.interfaces.notification_service import NotificationService
from src.domain.entities.signal import Signal
from .bot import TelegramBot
from src.application.dto.signal_dto import SignalDTO


class TelegramNotificationService:
    """
    Telegram implementation of NotificationService
    
    This is an infrastructure concern - it implements the application interface.
    """
    
    def __init__(self, telegram_bot: TelegramBot):
        self._bot = telegram_bot
    
    async def notify_signal_generated(self, signal: Signal) -> None:
        """Notify that a signal was generated"""
        signal_dto = SignalDTO.from_entity(signal)
        await self._bot.send_signal(signal_dto)
    
    async def notify_signal_accepted(self, signal: Signal) -> None:
        """Notify that a signal was accepted"""
        signal_dto = SignalDTO.from_entity(signal)
        await self._bot.send_signal(signal_dto)
    
    async def notify_position_opened(self, position) -> None:
        """Notify that a position was opened"""
        # Implementation would format and send position notification
        pass
    
    async def notify_position_closed(self, position) -> None:
        """Notify that a position was closed"""
        # Implementation would format and send position notification
        pass

