"""
Telegram Signal Handlers

Presentation layer handlers for signal-related Telegram commands.
"""

from typing import Protocol, Optional
from decimal import Decimal

from src.application.services.signal_service import SignalService
from src.application.dto.signal_dto import SignalDTO
from src.domain.entities.signal import SignalSide


class TelegramBot(Protocol):
    """Protocol for Telegram bot"""
    
    async def send_message(self, chat_id: str, text: str) -> None:
        """Send message to Telegram"""
        ...


class SignalHandlers:
    """
    Telegram handlers for signal operations
    
    This is a presentation layer concern - it handles user interactions.
    """
    
    def __init__(
        self,
        signal_service: SignalService,
        telegram_bot: TelegramBot,
    ):
        self._signal_service = signal_service
        self._bot = telegram_bot
    
    async def handle_generate_signal(
        self,
        chat_id: str,
        symbol: str,
        side: str,
        confidence: Decimal,
        risk_percentage: Decimal,
    ) -> None:
        """Handle generate signal command"""
        try:
            signal_side = SignalSide.LONG if side.lower() == "long" else SignalSide.SHORT
            
            signal_dto = await self._signal_service.generate_and_save_signal(
                symbol=symbol,
                side=signal_side,
                confidence=confidence,
                risk_percentage=risk_percentage,
            )
            
            message = f"""
✅ Сигнал создан!

ID: {signal_dto.id}
Символ: {signal_dto.symbol}
Направление: {signal_dto.side.upper()}
Цена входа: {signal_dto.entry_price}
Take Profit: {signal_dto.take_profit}
Stop Loss: {signal_dto.stop_loss}
Уверенность: {signal_dto.confidence or 'N/A'}
            """.strip()
            
            await self._bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            await self._bot.send_message(
                chat_id=chat_id,
                text=f"❌ Ошибка создания сигнала: {str(e)}"
            )
    
    async def handle_accept_signal(
        self,
        chat_id: str,
        signal_id: str,
    ) -> None:
        """Handle accept signal command"""
        try:
            signal_dto = await self._signal_service.accept_signal_by_id(signal_id)
            
            message = f"""
✅ Сигнал принят!

ID: {signal_dto.id}
Символ: {signal_dto.symbol}
Статус: {signal_dto.status.upper()}
            """.strip()
            
            await self._bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            await self._bot.send_message(
                chat_id=chat_id,
                text=f"❌ Ошибка принятия сигнала: {str(e)}"
            )
    
    async def handle_list_signals(
        self,
        chat_id: str,
        symbol: Optional[str] = None,
    ) -> None:
        """Handle list signals command"""
        try:
            if symbol:
                signals = await self._signal_service.get_signals_by_symbol(symbol)
            else:
                signals = await self._signal_service.get_pending_signals()
            
            if not signals:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text="📭 Нет сигналов"
                )
                return
            
            message = f"📊 Найдено сигналов: {len(signals)}\n\n"
            for signal in signals[:10]:  # Limit to 10
                message += f"• {signal.symbol} {signal.side.upper()} - {signal.status}\n"
            
            await self._bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            await self._bot.send_message(
                chat_id=chat_id,
                text=f"❌ Ошибка получения сигналов: {str(e)}"
            )

