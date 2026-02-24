"""
Telegram Signal Commands

Presentation layer commands for signal operations.
"""

from decimal import Decimal
from typing import Optional

from src.application.services.signal_service import SignalService
from src.domain.entities.signal import SignalSide


class SignalCommands:
    """
    Telegram commands for signal operations

    This is a presentation layer concern - it handles user commands.
    """

    def __init__(self, signal_service: SignalService):
        self._signal_service = signal_service

    async def handle_generate_command(
        self,
        symbol: str,
        side: str,
        confidence: str,
        risk: str,
    ) -> str:
        """
        Handle /generate command

        Returns:
            Response message
        """
        try:
            signal_side = SignalSide.LONG if side.lower() == "long" else SignalSide.SHORT
            confidence_decimal = Decimal(confidence)
            risk_decimal = Decimal(risk)

            signal_dto = await self._signal_service.generate_and_save_signal(
                symbol=symbol,
                side=signal_side,
                confidence=confidence_decimal,
                risk_percentage=risk_decimal,
            )

            return f"""
✅ Сигнал создан!

ID: {signal_dto.id}
Символ: {signal_dto.symbol}
Направление: {signal_dto.side.upper()}
Цена входа: {signal_dto.entry_price}
Take Profit: {signal_dto.take_profit}
Stop Loss: {signal_dto.stop_loss}
            """.strip()
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"

    async def handle_accept_command(self, signal_id: str) -> str:
        """
        Handle /accept command

        Returns:
            Response message
        """
        try:
            signal_dto = await self._signal_service.accept_signal_by_id(signal_id)
            return f"✅ Сигнал {signal_id} принят!"
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"

    async def handle_list_command(self, symbol: Optional[str] = None) -> str:
        """
        Handle /list_signals command

        Returns:
            Response message
        """
        try:
            if symbol:
                signals = await self._signal_service.get_signals_by_symbol(symbol)
            else:
                signals = await self._signal_service.get_pending_signals()

            if not signals:
                return "📭 Нет сигналов"

            message = f"📊 Найдено сигналов: {len(signals)}\n\n"
            for signal in signals[:10]:
                message += f"• {signal.symbol} {signal.side.upper()} - {signal.status}\n"

            return message
        except Exception as e:
            return f"❌ Ошибка: {str(e)}"
