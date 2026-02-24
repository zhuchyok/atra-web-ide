"""
TelegramButtonsConfig - Конфигурация кнопок и сообщений для Telegram
"""

# Конфигурация кнопок
TELEGRAM_BUTTONS = {
    "accept": {"text": "✅ Принять", "callback_data": "accept_signal", "color": "green"},
    "accept_long": {"text": "✅ Принять LONG", "callback_data": "accept_long", "color": "green"},
    "accept_short": {"text": "🔴 Принять SHORT", "callback_data": "accept_short", "color": "red"},
    "accepted_long": {"text": "✅ В работе (LONG)", "color": "green", "disabled": True},
    "accepted_short": {"text": "🔴 В работе (SHORT)", "color": "red", "disabled": True},
    "close_position": {
        "text": "🔴 Закрыть позицию",
        "callback_data": "close_position",
        "color": "red",
    },
    "close_long": {"text": "🔴 Закрыть LONG", "callback_data": "close_long", "color": "red"},
    "close_short": {"text": "✅ Закрыть SHORT", "callback_data": "close_short", "color": "green"},
    "info": {"text": "ℹ️ Информация", "callback_data": "info", "color": "blue"},
    "statistics": {"text": "📊 Статистика", "callback_data": "statistics", "color": "blue"},
    "my_signals": {"text": "📋 Мои сигналы", "callback_data": "my_signals", "color": "blue"},
    "active_positions": {
        "text": "🔄 Активные позиции",
        "callback_data": "active_positions",
        "color": "blue",
    },
}

# Шаблоны сообщений
SIGNAL_MESSAGES = {
    "new_signal": """🟡 **НОВЫЙ ТОРГОВЫЙ СИГНАЛ**

📊 **Символ:** {symbol}
📈 **Сторона:** {direction}
💰 **Цена входа:** {entry_price}
🎯 **Количество:** {quantity}
🔢 **Плечо:** {leverage}x
💡 **Риск:** {risk}%
💵 **Сумма входа:** {entry_amount} USDT
📅 **Время:** {time}

🎯 **TP1:** {tp1} ({tp1_percent}% / {tp1_leveraged}%)
🎯 **TP2:** {tp2} ({tp2_percent}% / {tp2_leveraged}%)
🛡️ **Стоп-лосс:** {sl} ({sl_percent}%)

⏰ **Уверенность:** {confidence}%""",
    "accepted_signal": """✅ **ПРИНЯТ СИГНАЛ**

📊 **Символ:** {symbol}
📈 **Сторона:** {direction}
💰 **Цена входа:** {entry_price}
📅 **Время принятия:** {accepted_time}
👤 **Пользователь:** {user}

🔄 **Статус:** Активная позиция""",
    "in_progress": """🔄 **ПОЗИЦИЯ В РАБОТЕ**

📊 **Символ:** {symbol}
📈 **Сторона:** {direction}
💰 **Цена входа:** {entry_price}
💵 **Текущая цена:** {current_price}
📊 **PnL:** {pnl_percent:+.2f}% ({pnl_usd:+.2f} USDT)
⏰ **Время в позиции:** {time_in_position}
👤 **Пользователь:** {user}""",
    "position_closed": """📊 **ПОЗИЦИЯ ЗАКРЫТА**

📊 **Символ:** {symbol}
📈 **Сторона:** {direction}
💰 **Цена входа:** {entry_price}
💵 **Цена закрытия:** {close_price}
📊 **PnL:** {pnl_percent:+.2f}% ({pnl_usd:+.2f} USDT)
🔚 **Причина:** {reason}
⏰ **Время закрытия:** {close_time}
👤 **Пользователь:** {user}""",
    "expired_signal": """⏰ **СИГНАЛ ИСТЕК**

📊 **Символ:** {symbol}
📈 **Сторона:** {direction}
💰 **Цена входа:** {entry_price}
⏰ **Время истечения:** {expired_time}
👤 **Пользователь:** {user}""",
}

# Уведомления
NOTIFICATION_MESSAGES = {
    "signal_accepted": "✅ Сигнал {symbol} {direction} принят пользователем {user}",
    "position_closed": "📊 Позиция {symbol} {direction} закрыта. PnL: {pnl:+.2f}%",
    "position_expired": "⏰ Позиция {symbol} {direction} истекла",
    "stop_loss_hit": "🛡️ Сработал стоп-лосс для {symbol} {direction}",
    "take_profit_hit": "🎯 Сработал тейк-профит для {symbol} {direction}",
    "error": "❌ Ошибка: {error}",
    "success": "✅ {message}",
    "warning": "⚠️ {message}",
    "info": "ℹ️ {message}",
}

# Команды бота
BOT_COMMANDS = {
    "start": "🚀 Запуск бота",
    "help": "❓ Помощь",
    "my_signals": "📋 Мои сигналы",
    "active_positions": "🔄 Активные позиции",
    "statistics": "📊 Статистика",
    "settings": "⚙️ Настройки",
    "status": "ℹ️ Статус системы",
}

# Эмодзи для разных состояний
STATUS_EMOJIS = {
    "pending": "⏳",
    "accepted": "✅",
    "in_progress": "🔄",
    "closed": "📊",
    "expired": "⏰",
    "error": "❌",
    "success": "✅",
    "warning": "⚠️",
    "info": "ℹ️",
}

# Цвета кнопок
BUTTON_COLORS = {
    "green": "✅",
    "red": "🔴",
    "blue": "🔵",
    "yellow": "🟡",
    "orange": "🟠",
    "purple": "🟣",
}

# Настройки форматирования
FORMATTING_CONFIG = {
    "price_decimal_places": 4,
    "percentage_decimal_places": 2,
    "time_format": "%d.%m.%Y %H:%M",
    "date_format": "%d.%m.%Y",
    "currency_symbol": "USDT",
    "leverage_symbol": "x",
}

# Лимиты и ограничения
LIMITS = {
    "max_signals_per_user": 10,
    "max_active_positions": 5,
    "signal_timeout_hours": 24,
    "position_timeout_hours": 48,
    "max_message_length": 4096,
    "update_interval_seconds": 300,
}

# Настройки уведомлений
NOTIFICATION_SETTINGS = {
    "enable_signal_notifications": True,
    "enable_position_updates": True,
    "enable_pnl_alerts": True,
    "enable_expiry_warnings": True,
    "pnl_alert_threshold": 5.0,  # Процент для алерта PnL
    "expiry_warning_hours": 2,  # За сколько часов предупреждать об истечении
}


def get_button_text(button_type: str, **kwargs) -> str:
    """Получает текст кнопки с подстановкой параметров"""
    try:
        button_config = TELEGRAM_BUTTONS.get(button_type, {})
        text = button_config.get("text", button_type)

        # Подставляем параметры
        if kwargs:
            text = text.format(**kwargs)

        return text
    except Exception:
        return button_type


def get_message_template(template_type: str) -> str:
    """Получает шаблон сообщения"""
    return SIGNAL_MESSAGES.get(template_type, "❌ Шаблон не найден")


def get_notification_message(notification_type: str, **kwargs) -> str:
    """Получает сообщение уведомления с подстановкой параметров"""
    try:
        template = NOTIFICATION_MESSAGES.get(notification_type, "❌ {message}")
        return template.format(**kwargs)
    except Exception:
        return f"❌ {notification_type}"


def format_price(price: float) -> str:
    """Форматирует цену"""
    decimal_places = FORMATTING_CONFIG["price_decimal_places"]
    return f"{price:.{decimal_places}f}"


def format_percentage(percentage: float) -> str:
    """Форматирует процент"""
    decimal_places = FORMATTING_CONFIG["percentage_decimal_places"]
    return f"{percentage:+.{decimal_places}f}%"


def format_time(dt) -> str:
    """Форматирует время"""
    time_format = FORMATTING_CONFIG["time_format"]
    return dt.strftime(time_format)


def get_status_emoji(status: str) -> str:
    """Получает эмодзи для статуса"""
    return STATUS_EMOJIS.get(status, "❓")
