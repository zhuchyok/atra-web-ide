"""
Telegram Bot - Infrastructure Implementation

Infrastructure layer implementation of Telegram bot.
"""

from typing import Optional
from telegram import Bot
from telegram.ext import Application

from src.shared.config.settings import settings
from src.application.dto.signal_dto import SignalDTO


class TelegramBot:
    """
    Telegram Bot Infrastructure Implementation
    
    This is an infrastructure concern - it implements the messaging interface.
    """
    
    def __init__(self):
        """Initialize Telegram bot"""
        if not settings.telegram.enabled or not settings.telegram.token:
            raise ValueError("Telegram is not configured")
        
        self._bot = Bot(token=settings.telegram.token)
        self._application = Application.builder().token(settings.telegram.token).build()
        self._chat_id = settings.telegram.chat_id
    
    async def send_signal(self, signal_dto: SignalDTO) -> None:
        """Send signal to Telegram"""
        message = self._format_signal_message(signal_dto)
        await self._bot.send_message(
            chat_id=self._chat_id,
            text=message,
            parse_mode='HTML',
        )
    
    def _format_signal_message(self, signal_dto: SignalDTO) -> str:
        """Format signal as Telegram message"""
        side_emoji = "🟢" if signal_dto.side == "long" else "🔴"
        
        return f"""
{side_emoji} <b>Новый торговый сигнал</b>

📊 Символ: <code>{signal_dto.symbol}</code>
📈 Направление: <b>{signal_dto.side.upper()}</b>
💰 Цена входа: <code>{signal_dto.entry_price}</code>
🎯 Take Profit: <code>{signal_dto.take_profit}</code>
🛑 Stop Loss: <code>{signal_dto.stop_loss}</code>
📊 Уверенность: <code>{signal_dto.confidence or 'N/A'}</code>
⚠️ Риск: <code>{signal_dto.risk_percentage or 'N/A'}%</code>
        """.strip()
    
    async def start(self) -> None:
        """Start the bot"""
        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling()
    
    async def stop(self) -> None:
        """Stop the bot"""
        await self._application.updater.stop()
        await self._application.stop()
        await self._application.shutdown()

