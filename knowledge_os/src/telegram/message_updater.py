"""
TelegramMessageUpdater - Обновление сообщений в Telegram с интерактивными кнопками
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from src.signals.acceptance_manager import SignalData

logger = logging.getLogger(__name__)

class TelegramMessageUpdater:
    """Обновление сообщений в Telegram"""
    
    def __init__(self, bot=None):
        """Инициализация с передачей объекта бота"""
        self.bot = bot
        self.logger = logging.getLogger('telegram_updater')
        logger.info("✅ TelegramMessageUpdater инициализирован")
    
    def set_bot(self, bot):
        """Установить объект бота после инициализации"""
        self.bot = bot
        self.logger.info("✅ Бот установлен в TelegramMessageUpdater")
    
    def format_signal_message(self, signal_data: SignalData) -> str:
        """Форматирует сообщение сигнала"""
        try:
            # Базовое сообщение
            if signal_data.status == "pending":
                status_emoji = "🟡"
                status_text = "НОВЫЙ СИГНАЛ"
            elif signal_data.status == "accepted":
                status_emoji = "✅"
                status_text = "ПРИНЯТ СИГНАЛ"
            elif signal_data.status == "in_progress":
                status_emoji = "🔄"
                status_text = "В РАБОТЕ"
            elif signal_data.status == "closed":
                status_emoji = "📊"
                status_text = "ПОЗИЦИЯ ЗАКРЫТА"
            else:
                status_emoji = "❓"
                status_text = "НЕИЗВЕСТНО"
            
            # Форматирование цены
            price_str = f"{signal_data.entry_price:.4f}"
            
            # Форматирование времени
            time_str = signal_data.signal_time.strftime("%d.%m.%Y %H:%M")
            
            # Основное сообщение
            message = f"""{status_emoji} **{status_text}**

📊 **Символ:** {signal_data.symbol}
📈 **Сторона:** {signal_data.direction}
💰 **Цена входа:** {price_str}
📅 **Время:** {time_str}"""
            
            # Дополнительная информация в зависимости от статуса
            if signal_data.status == "accepted" and signal_data.accepted_time:
                accepted_time = signal_data.accepted_time.strftime("%d.%m.%Y %H:%M")
                message += f"\n✅ **Принят:** {accepted_time}"
                if signal_data.accepted_by:
                    message += f"\n👤 **Пользователь:** {signal_data.accepted_by}"
            
            elif signal_data.status == "in_progress":
                message += f"\n🔄 **Статус:** Активная позиция"
                if signal_data.accepted_by:
                    message += f"\n👤 **Пользователь:** {signal_data.accepted_by}"
            
            elif signal_data.status == "closed":
                message += f"\n📊 **Статус:** Позиция закрыта"
                if signal_data.accepted_by:
                    message += f"\n👤 **Пользователь:** {signal_data.accepted_by}"
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования сообщения: {e}")
            return f"❌ Ошибка форматирования сигнала: {e}"
    
    async def update_signal_message(self, chat_id: int, message_id: int, 
                                  signal_data: SignalData, keyboard: Optional[Dict[str, Any]] = None) -> bool:
        """Обновляет сообщение сигнала в Telegram"""
        try:
            if not self.bot:
                self.logger.error("❌ Бот не установлен в TelegramMessageUpdater")
                return False
            
            # Форматируем новое сообщение
            new_message = self.format_signal_message(signal_data)
            
            # Обновляем сообщение
            if keyboard:
                await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=new_message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            else:
                await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=new_message,
                    parse_mode='Markdown'
                )
            
            self.logger.info(f"✅ Сообщение обновлено: {signal_data.symbol} -> {signal_data.status}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка обновления сообщения: {e}")
            return False

    async def update_acceptance_status(self, chat_id: int, message_id: int, 
                                     symbol: str, direction: str, accepted_by: int) -> bool:
        """Обновить статус принятия сигнала"""
        try:
            if not self.bot:
                self.logger.error("❌ Бот не установлен в TelegramMessageUpdater")
                return False

            new_text = f"""
🎯 <b>СИГНАЛ ПРИНЯТ</b>
├ Сигнал: {symbol} {direction}
├ Принял: {accepted_by}
├ Статус: <b>✅ В РАБОТЕ</b>
└ Время: {get_utc_now().strftime('%H:%M:%S')}
            """
            
            if direction.upper() == 'BUY':
                status_button = InlineKeyboardButton(
                    "✅ В РАБОТЕ (LONG)", 
                    callback_data="position_open"
                )
            else:
                status_button = InlineKeyboardButton(
                    "🔴 В РАБОТЕ (SHORT)", 
                    callback_data="position_open"
                )
            
            close_button = InlineKeyboardButton(
                "🔴 Закрыть позицию", 
                callback_data=f"close_{symbol}"
            )
            
            new_keyboard = InlineKeyboardMarkup([
                [status_button],
                [close_button]
            ])
            
            await self.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=new_text,
                reply_markup=new_keyboard,
                parse_mode='HTML'
            )
            
            self.logger.info(f"✅ Статус принятия обновлен для {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка обновления статуса: {e}")
            return False
    
    async def send_signal_with_buttons(self, chat_id: int, signal_data: SignalData, 
                                     keyboard: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Отправляет новый сигнал с кнопками"""
        try:
            if not self.bot:
                self.logger.error("❌ Бот не установлен в TelegramMessageUpdater")
                return None
            
            # Форматируем сообщение
            message = self.format_signal_message(signal_data)
            
            # Отправляем сообщение
            if keyboard:
                sent_message = await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            else:
                sent_message = await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
            
            self.logger.info(f"✅ Сигнал отправлен: {signal_data.symbol}")
            return sent_message.message_id
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки сигнала: {e}")
            return None
    
    async def send_notification(self, chat_id: int, message: str, 
                              notification_type: str = "info") -> bool:
        """Отправляет уведомление"""
        try:
            if not self.bot:
                self.logger.error("❌ Бот не установлен в TelegramMessageUpdater")
                return False
            
            # Эмодзи в зависимости от типа уведомления
            emoji_map = {
                "info": "ℹ️",
                "success": "✅",
                "warning": "⚠️",
                "error": "❌",
                "signal": "📊"
            }
            
            emoji = emoji_map.get(notification_type, "ℹ️")
            formatted_message = f"{emoji} {message}"
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=formatted_message,
                parse_mode='Markdown'
            )
            
            self.logger.info(f"✅ Уведомление отправлено: {notification_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки уведомления: {e}")
            return False
    
    async def send_statistics(self, chat_id: int, stats: Dict[str, Any]) -> bool:
        """Отправляет статистику"""
        try:
            if not self.bot:
                self.logger.error("❌ Бот не установлен в TelegramMessageUpdater")
                return False
            
            # Форматируем статистику
            message = "📊 **СТАТИСТИКА ПРИНЯТИЯ СИГНАЛОВ**\n\n"
            
            message += f"📈 **Всего сигналов:** {stats.get('total_signals', 0)}\n"
            message += f"✅ **Принято:** {stats.get('accepted_signals', 0)}\n"
            message += f"📊 **Закрыто:** {stats.get('closed_positions', 0)}\n"
            message += f"⏳ **Ожидает:** {stats.get('pending_signals', 0)}\n"
            
            # Топ символы
            top_symbols = stats.get('top_symbols', [])
            if top_symbols:
                message += "\n🏆 **Топ символы:**\n"
                for i, symbol_data in enumerate(top_symbols[:5], 1):
                    message += f"{i}. {symbol_data['symbol']}: {symbol_data['count']} сигналов\n"
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            self.logger.info("✅ Статистика отправлена")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки статистики: {e}")
            return False
    
    async def send_user_signals(self, chat_id: int, user_signals: list) -> bool:
        """Отправляет список сигналов пользователя"""
        try:
            if not self.bot:
                self.logger.error("❌ Бот не установлен в TelegramMessageUpdater")
                return False
            
            if not user_signals:
                message = "📊 **ВАШИ СИГНАЛЫ**\n\n❌ У вас нет принятых сигналов"
            else:
                message = "📊 **ВАШИ СИГНАЛЫ**\n\n"
                
                for i, signal in enumerate(user_signals[:10], 1):  # Показываем только последние 10
                    status_emoji = {
                        "pending": "⏳",
                        "accepted": "✅",
                        "in_progress": "🔄",
                        "closed": "📊"
                    }.get(signal.status, "❓")
                    
                    time_str = signal.signal_time.strftime("%d.%m %H:%M")
                    message += f"{i}. {status_emoji} {signal.symbol} {signal.direction} - {time_str}\n"
                
                if len(user_signals) > 10:
                    message += f"\n... и еще {len(user_signals) - 10} сигналов"
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode='Markdown'
            )
            
            self.logger.info(f"✅ Список сигналов отправлен: {len(user_signals)} сигналов")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки списка сигналов: {e}")
            return False
