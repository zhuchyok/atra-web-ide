"""
Telegram module - Bot interface and messaging
Модуль Telegram - интерфейс бота и сообщения
"""

# Импорты с fallback для обратной совместимости
try:
    from .bot import ATRATelegramBot
except ImportError:
    ATRATelegramBot = None

try:
    from .formatters import signal_formatter, SignalFormatter
except ImportError:
    signal_formatter = None
    SignalFormatter = None

try:
    from .handlers import command_handler, CommandHandler, set_signal_acceptance_manager
except ImportError:
    command_handler = None
    CommandHandler = None
    def set_signal_acceptance_manager(*args, **kwargs):
        pass

__all__ = [
    'ATRATelegramBot',
    'signal_formatter',
    'SignalFormatter',
    'command_handler',
    'CommandHandler',
    'set_signal_acceptance_manager'
]
