"""
Фильтры для торговых сигналов
Модуль содержит различные фильтры для улучшения качества сигналов
"""

# Экспорт основных функций фильтров
from .news import get_news_data, check_negative_news
from .btc_trend import get_btc_trend_status
from .whale import get_whale_signal

__all__ = [
    'get_news_data',
    'check_negative_news',
    'get_btc_trend_status',
    'get_whale_signal'
]
