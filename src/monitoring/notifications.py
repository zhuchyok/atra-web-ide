import logging
from typing import Optional
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class AlertNotifications:
    """Система алертов для критичных событий."""

    def __init__(self, bot=None):
        self.bot = bot

    async def send_alert(self, user_id: int, alert_type: str, message: str):
        """Отправляет алерт пользователю."""
        try:
            if not self.bot:
                logger.warning("⚠️ Бот не подключен для алертов")
                return False

            emoji_map = {
                'order_failed': '🚨',
                'large_order': '⚠️',
                'exchange_error': '❌',
                'sync_error': '⚠️',
                'key_error': '🔐',
                'position_closed': '✅',
            }
            emoji = emoji_map.get(alert_type, '📢')

            formatted = f"{emoji} <b>АЛЕРТ</b>\n{message}\n\n🕒 {get_utc_now().strftime('%H:%M:%S')}"

            await self.bot.send_message(chat_id=user_id, text=formatted, parse_mode='HTML')
            logger.info("📢 Алерт отправлен user %s: %s", user_id, alert_type)
            return True
        except Exception as e:
            logger.error("❌ Ошибка отправки алерта: %s", e)
            return False

    async def alert_large_order(self, user_id: int, symbol: str, amount_usdt: float):
        """Алерт о большом ордере."""
        msg = f"💰 <b>Большой ордер</b>\n├ Символ: {symbol}\n├ Сумма: {amount_usdt:.2f} USDT\n└ Проверьте параметры"
        await self.send_alert(user_id, 'large_order', msg)

    async def alert_order_failed(self, user_id: int, symbol: str, reason: str):
        """Алерт о неудачном ордере."""
        msg = f"🚨 <b>Ордер не исполнен</b>\n├ Символ: {symbol}\n└ Причина: {reason}"
        await self.send_alert(user_id, 'order_failed', msg)

    async def alert_exchange_error(self, user_id: int, exchange: str, error: str):
        """Алерт об ошибке биржи."""
        msg = f"❌ <b>Ошибка {exchange}</b>\n└ {error}"
        await self.send_alert(user_id, 'exchange_error', msg)

    async def alert_position_closed_by_exchange(self, user_id: int, symbol: str):
        """Алерт о закрытии позиции на бирже."""
        msg = f"✅ <b>Позиция закрыта</b>\n├ Символ: {symbol}\n└ Закрыта на бирже (автосинхронизация)"
        await self.send_alert(user_id, 'position_closed', msg)


_alert_instance: Optional[AlertNotifications] = None


def get_alert_service(bot=None) -> AlertNotifications:
    global _alert_instance
    if _alert_instance is None:
        _alert_instance = AlertNotifications(bot)
    elif bot and not _alert_instance.bot:
        _alert_instance.bot = bot
    return _alert_instance

