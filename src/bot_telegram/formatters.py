"""
Telegram Message Formatters
Форматировщики сообщений для Telegram

This module contains enhanced message formatting for better UX
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import math

from ..core.localization import gettext
from ...shared.utils.datetime_utils import get_utc_now


class SignalFormatter:
    """Форматировщик сигналов с улучшенным UX"""

    def __init__(self):
        self.emoji_map = {
            'LONG': '🟢',
            'SHORT': '🔴',
            'high': '🔥',
            'medium': '⚡',
            'low': '🐌',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌',
            'info': 'ℹ️',
            'money': '💰',
            'chart': '📊',
            'rocket': '🚀',
            'target': '🎯',
            'shield': '🛡️',
            'boost': '⚡'
        }

    def format_signal_message(self, signal_data: Dict[str, Any], mode: str = "full") -> str:
        """
        Форматирование сигнала с улучшенным UX

        Args:
            signal_data: Данные сигнала
            mode: Режим форматирования ("full", "compact", "mini")

        Returns:
            str: Отформатированное сообщение
        """
        try:
            signal_type = signal_data.get('signal', 'LONG')
            symbol = signal_data.get('symbol', 'UNKNOWN')
            entry_price = signal_data.get('entry_price', 0)
            leverage = signal_data.get('leverage', 1.0)
            risk_pct = signal_data.get('risk_pct', 2.0)
            strength = signal_data.get('strength', 'medium')

            if mode == "compact":
                return self._format_compact_signal(signal_data)
            elif mode == "mini":
                return self._format_mini_signal(signal_data)
            else:
                return self._format_full_signal(signal_data)

        except Exception as e:
            return f"❌ Ошибка форматирования сигнала: {e}"

    def _format_full_signal(self, signal_data: Dict[str, Any]) -> str:
        """Полное форматирование сигнала"""
        try:
            signal_type = signal_data.get('signal', 'LONG')
            symbol = signal_data.get('symbol', 'UNKNOWN')
            entry_price = signal_data.get('entry_price', 0)
            stop_loss_price = signal_data.get('stop_loss_price', 0)
            take_profit_1 = signal_data.get('take_profit_1', 0)
            take_profit_2 = signal_data.get('take_profit_2', 0)
            leverage = signal_data.get('leverage', 1.0)
            risk_pct = signal_data.get('risk_pct', 2.0)
            recommended_qty_coins = signal_data.get('recommended_qty_coins', 0)
            recommended_qty_usdt = signal_data.get('recommended_qty_usdt', 0)
            risk_amount_usdt = signal_data.get('risk_amount_usdt', 0)
            strength = signal_data.get('strength', 'medium')
            reason = signal_data.get('reason', 'Сигнал сгенерирован')

            emoji = self.emoji_map.get(signal_type, '📊')
            strength_emoji = self.emoji_map.get(strength, '⚡')

            # Расчет потенциальной прибыли
            if signal_type == "LONG":
                profit_1 = ((take_profit_1 - entry_price) / entry_price) * 100
                profit_2 = ((take_profit_2 - entry_price) / entry_price) * 100
                loss = ((entry_price - stop_loss_price) / entry_price) * 100
            else:
                profit_1 = ((entry_price - take_profit_1) / entry_price) * 100
                profit_2 = ((entry_price - take_profit_2) / entry_price) * 100
                loss = ((stop_loss_price - entry_price) / entry_price) * 100

            # Форматирование чисел
            price_format = self._get_price_format(entry_price)

            # Используем локализацию для текстов
            lang = signal_data.get('language', 'ru')  # По умолчанию русский

            message = f"""
{emoji} <b>{gettext('signal_' + signal_type.lower(), lang)} {symbol}</b> {strength_emoji}

💰 <b>{gettext('entry_price', lang)}:</b> {entry_price:{price_format}} USDT
🎯 <b>Take Profit 1:</b> {take_profit_1:{price_format}} USDT (+{profit_1:.1f}%)
🎯 <b>Take Profit 2:</b> {take_profit_2:{price_format}} USDT (+{profit_2:.1f}%)
🛡️ <b>Stop Loss:</b> {stop_loss_price:{price_format}} USDT (-{loss:.1f}%)

⚙️ <b>{gettext('settings', lang)}:</b>
• {gettext('leverage', lang)}: {int(round(float(leverage)))}x
• {gettext('risk_amount', lang)}: {risk_pct:.1f}%
• {gettext('signal_strength', lang)}: {strength}

💵 <b>{gettext('recommended_qty', lang)}:</b>
• {gettext('volume', lang)}: {recommended_qty_coins:.4f} {gettext('coins', lang, default='монет')}
• {gettext('amount', lang, default='Сумма')}: ${recommended_qty_usdt:.2f}
• {gettext('risk_amount', lang)}: ${risk_amount_usdt:.2f}

📈 <b>{gettext('reason', lang)}:</b> {reason}

⏰ {get_utc_now().strftime('%H:%M:%S')}
"""

            return message.strip()

        except Exception as e:
            return f"❌ Ошибка форматирования полного сигнала: {e}"

    def _format_compact_signal(self, signal_data: Dict[str, Any]) -> str:
        """Компактное форматирование сигнала"""
        try:
            signal_type = signal_data.get('signal', 'LONG')
            symbol = signal_data.get('symbol', 'UNKNOWN')
            entry_price = signal_data.get('entry_price', 0)
            leverage = signal_data.get('leverage', 1.0)
            risk_pct = signal_data.get('risk_pct', 2.0)
            recommended_qty_usdt = signal_data.get('recommended_qty_usdt', 0)

            emoji = self.emoji_map.get(signal_type, '📊')

            price_format = self._get_price_format(entry_price)

            message = f"""{emoji} <b>{signal_type} {symbol}</b>
💰 {entry_price:{price_format}} USDT | {int(round(float(leverage)))}x | {risk_pct:.1f}% риск
💵 Рекомендация: ${recommended_qty_usdt:.0f}"""

            return message

        except Exception as e:
            return f"❌ Ошибка компактного форматирования: {e}"

    def _format_mini_signal(self, signal_data: Dict[str, Any]) -> str:
        """Минимальное форматирование сигнала"""
        try:
            signal_type = signal_data.get('signal', 'LONG')
            symbol = signal_data.get('symbol', 'UNKNOWN')
            entry_price = signal_data.get('entry_price', 0)
            leverage = signal_data.get('leverage', 1.0)

            emoji = self.emoji_map.get(signal_type, '📊')
            price_format = self._get_price_format(entry_price)

            message = f"{emoji} {signal_type} {symbol} {entry_price:{price_format}} {int(round(float(leverage)))}x"

            return message

        except Exception as e:
            return f"❌ Ошибка мини-форматирования: {e}"

    def format_dca_message(self, dca_data: Dict[str, Any], mode: str = "full") -> str:
        """Форматирование DCA сообщения"""
        try:
            signal_type = dca_data.get('signal', 'LONG')
            symbol = dca_data.get('symbol', 'UNKNOWN')
            current_price = dca_data.get('current_price', 0)
            new_avg_price = dca_data.get('new_avg_price', 0)
            total_qty = dca_data.get('total_qty', 0)
            dca_count = dca_data.get('dca_count', 0)

            emoji = self.emoji_map.get(signal_type, '📊')

            if mode == "compact":
                message = f"""🔄 <b>DCA #{dca_count} {symbol}</b>
💰 Текущая: {current_price:.4f} | Новая средняя: {new_avg_price:.4f}
📦 Общий объем: {total_qty:.4f} монет"""
            else:
                profit_targets = dca_data.get('profit_targets', {})
                tp1 = profit_targets.get('tp1', 0)
                tp2 = profit_targets.get('tp2', 0)

                message = f"""🔄 <b>DCA #{dca_count} для {symbol}</b>

📊 <b>Информация:</b>
• Сигнал: {emoji} {signal_type}
• Текущая цена: {current_price:.4f} USDT
• Новая средняя: {new_avg_price:.4f} USDT
• Общий объем: {total_qty:.4f} монет

🎯 <b>Новые цели:</b>
• TP1: {tp1:.4f} USDT
• TP2: {tp2:.4f} USDT

⏰ {get_utc_now().strftime('%H:%M:%S')}"""

            return message

        except Exception as e:
            return f"❌ Ошибка форматирования DCA: {e}"

    def format_status_message(self, status_data: Dict[str, Any]) -> str:
        """Форматирование сообщения статуса"""
        try:
            total_balance = status_data.get('total_balance', 0)
            active_positions = status_data.get('active_positions', 0)
            total_pnl = status_data.get('total_pnl', 0)
            win_rate = status_data.get('win_rate', 0)

            emoji = "📈" if total_pnl >= 0 else "📉"

            message = f"""📊 <b>СТАТУС СИСТЕМЫ</b>

💰 <b>Баланс:</b> ${total_balance:.2f}
📦 <b>Активных позиций:</b> {active_positions}
{emoji} <b>P&L:</b> ${total_pnl:.2f}
🎯 <b>Win Rate:</b> {win_rate:.1f}%

⏰ {get_utc_now().strftime('%H:%M:%S')}"""

            return message

        except Exception as e:
            return f"❌ Ошибка форматирования статуса: {e}"

    def format_error_message(self, error: str, context: str = "") -> str:
        """Форматирование сообщения об ошибке"""
        message = f"""❌ <b>ОШИБКА</b>

🔍 <b>Контекст:</b> {context}
💥 <b>Ошибка:</b> {error}

⏰ {get_utc_now().strftime('%H:%M:%S')}"""

        return message

    def format_success_message(self, message: str, context: str = "") -> str:
        """Форматирование сообщения об успехе"""
        context_str = f"\n\n🎯 <b>Контекст:</b> {context}" if context else ""

        full_message = f"""✅ <b>УСПЕХ</b>

{message}{context_str}

⏰ {get_utc_now().strftime('%H:%M:%S')}"""

        return full_message

    def _get_price_format(self, price: float) -> str:
        """Определение формата цены на основе величины"""
        if price >= 1000:
            return ".2f"
        elif price >= 1:
            return ".4f"
        elif price >= 0.01:
            return ".6f"
        else:
            return ".8f"

    def create_signal_buttons(self, signal_data: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
        """Создание кнопок для сигнала"""
        try:
            symbol = signal_data.get('symbol', 'UNKNOWN')
            signal_type = signal_data.get('signal', 'LONG')
            entry_price = signal_data.get('entry_price', 0)
            take_profit_1 = signal_data.get('take_profit_1', entry_price)

            buttons = [
                [
                    {
                        "text": f"✅ Принять {signal_type}",
                        "callback_data": f"accept_{symbol}_{entry_price}_{take_profit_1}_{signal_type}"
                    },
                    {
                        "text": "❌ Отклонить",
                        "callback_data": f"reject_{symbol}_{entry_price}"
                    }
                ],
                [
                    {
                        "text": "📊 Детали",
                        "callback_data": f"details_{symbol}_{entry_price}"
                    },
                    {
                        "text": "🔄 Обновить",
                        "callback_data": f"refresh_{symbol}"
                    }
                ]
            ]

            return buttons

        except Exception as e:
            return []

    def create_dca_buttons(self, dca_data: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
        """Создание кнопок для DCA"""
        try:
            symbol = dca_data.get('symbol', 'UNKNOWN')
            dca_count = dca_data.get('dca_count', 0)

            buttons = [
                [
                    {
                        "text": f"✅ DCA #{dca_count}",
                        "callback_data": f"dca_accept_{symbol}_{dca_count}"
                    },
                    {
                        "text": "❌ Пропустить",
                        "callback_data": f"dca_reject_{symbol}_{dca_count}"
                    }
                ]
            ]

            return buttons

        except Exception as e:
            return []


# Глобальный экземпляр форматтера
signal_formatter = SignalFormatter()
