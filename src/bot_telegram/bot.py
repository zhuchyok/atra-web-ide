"""
Telegram Bot - Основной модуль

Этот файл теперь является точкой входа для Telegram бота.
Основная логика вынесена в отдельные модули для улучшения структуры кода.
"""

# Импортируем конкретные функции из основного модуля
from src.bot_telegram.bot_core import (
    run_telegram_bot_with_retry,
    run_telegram_bot_in_existing_loop,
    stop_telegram_bot,
    is_bot_ready,
    run_telegram_bot_stub,
    bot_application,
    bot_task,
    notify_user,
    notify_all
)

# Экспортируем основные функции для обратной совместимости
__all__ = [
    'run_telegram_bot_with_retry',
    'run_telegram_bot_in_existing_loop',
    'stop_telegram_bot',
    'is_bot_ready',
    'run_telegram_bot_stub',
    'bot_application',
    'bot_task',
    'notify_user',
    'notify_all',
    'save_user_data'
]

def save_user_data(context):
    """Функция для совместимости со скриптами симуляции"""
    from src.utils.user_utils import save_user_data_for_signals
    if hasattr(context, 'application') and hasattr(context.application, 'user_data'):
        save_user_data_for_signals(context.application.user_data)
        return True
    return False
