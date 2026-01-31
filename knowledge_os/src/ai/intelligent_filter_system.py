"""
🤖 ИНТЕЛЛЕКТУАЛЬНАЯ СИСТЕМА АДАПТАЦИИ ФИЛЬТРОВ
Комбинирует несколько подходов для оптимальной фильтрации сигналов:
1. Динамическая адаптация под рыночные условия
2. Индивидуальные параметры для каждой монеты
3. Система приоритетов и компенсации
4. Адаптация на основе исторической эффективности
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

# Импорты с fallback
try:
    from src.ai.adaptive_filter_regulator import get_adaptive_regulator
    ADAPTIVE_REGULATOR_AVAILABLE = True
except ImportError:
    ADAPTIVE_REGULATOR_AVAILABLE = False
    get_adaptive_regulator = None
    logger.warning("⚠️ AdaptiveFilterRegulator недоступен")


@dataclass
class MarketConditions:
    """Рыночные условия"""
    volatility: float
    trend_strength: float
    historical_volatility: float = 0.0
    avg_volume: float = 0.0
    market_regime: str = "normal"  # normal, volatile, trending, flat


@dataclass
class FilterPerformance:
    """Статистика эффективности фильтра"""
    total_signals: int = 0
    profitable_signals: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    win_rate: float = 0.5
    profit_factor: float = 1.0

    def update(self, is_profitable: bool, profit: float = 0.0):
        """Обновляет статистику"""
        self.total_signals += 1
        if is_profitable:
            self.profitable_signals += 1
            self.total_profit += abs(profit)
        else:
            self.total_loss += abs(profit)

        if self.total_signals > 0:
            self.win_rate = self.profitable_signals / self.total_signals

        if self.total_loss > 0:
            self.profit_factor = self.total_profit / self.total_loss
        elif self.total_profit > 0:
            self.profit_factor = float('inf')


class AdaptiveFilterSystem:
    """Динамическая адаптация параметров на основе рыночных условий"""

    def __init__(self):
        self.market_regime = "normal"

    def adapt_filters_to_market(
        self,
        symbol: str,
        current_volatility: float,
        trend_strength: float
    ) -> Dict[str, float]:
        """Адаптирует параметры фильтров под текущие рыночные условия"""

        # Определяем рыночный режим
        if current_volatility > 0.08:
            self.market_regime = "volatile"
        elif trend_strength > 0.7:
            self.market_regime = "trending"
        elif current_volatility < 0.02:
            self.market_regime = "flat"
        else:
            self.market_regime = "normal"

        return self._get_adaptive_params(symbol)

    def _get_adaptive_params(self, symbol: str) -> Dict[str, float]:
        """Возвращает адаптированные параметры для текущего режима"""

        base_params = {
            'volume_ratio': 0.5,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'trend_strength': 0.6,
            'quality_score': 0.7,
            'momentum_threshold': 0.0
        }

        # Адаптация под рыночный режим
        if self.market_regime == "volatile":
            return {
                **base_params,
                'volume_ratio': 0.4,      # Снижаем требования в волатильность
                'rsi_oversold': 25,      # Более глубокие уровни RSI
                'rsi_overbought': 75,
                'trend_strength': 0.5,   # Снижаем требование к тренду
                'quality_score': 0.65,
                'momentum_threshold': -1.0
            }
        elif self.market_regime == "trending":
            return {
                **base_params,
                'volume_ratio': 0.6,      # Повышаем в тренде
                'rsi_oversold': 35,
                'rsi_overbought': 65,
                'trend_strength': 0.75,   # Сильнее требование к тренду
                'quality_score': 0.75,
                'momentum_threshold': 0.5
            }
        elif self.market_regime == "flat":
            return {
                **base_params,
                'volume_ratio': 0.3,      # Сильно снижаем во флэте
                'rsi_oversold': 20,       # Очень глубокие уровни
                'rsi_overbought': 80,
                'trend_strength': 0.4,    # Слабый тренд допустим
                'quality_score': 0.6,
                'momentum_threshold': -2.0
            }

        return base_params


def get_all_optimized_symbols() -> list:
    """Возвращает список всех монет с оптимизированными параметрами из intelligent_filter_system"""
    # Импортируем функцию для получения параметров
    # и извлекаем все ключи из symbol_profiles
    import re
    import os
    file_path = os.path.join(os.path.dirname(__file__), 'intelligent_filter_system.py')
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Находим все символы в формате 'SYMBOLUSDT': {
    symbols = re.findall(r"'([A-Z]+USDT)':\s*{", content)
    return sorted(list(set(symbols)))


def get_symbol_specific_parameters(
    symbol: str,
    historical_volatility: float = 0.0,
    avg_volume: float = 0.0
) -> Dict[str, float]:
    """Возвращает оптимизированные параметры для конкретной монеты"""

    symbol_profiles = {
        'BTCUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.7 (было 0.7)
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.65,    # ✅ Пересчитано: 0.65 (было 0.72)
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.71%, Sharpe=+2.000, WinRate=70.6%
        },
        'ETHUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.7 (было 0.6)
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.65,    # ✅ Пересчитано: 0.65 (было 0.7)
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.81%, Sharpe=+2.000, WinRate=76.1%
        },
        'ADAUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.6 (было 0.3)
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.72,    # ✅ Пересчитано: 0.72 (было 0.6)
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+1.76%, Sharpe=+2.000, WinRate=87.1%
        },
        'SOLUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.7 (было 0.4)
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.7,     # ✅ Пересчитано: 0.7 (было 0.65)
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.93%, Sharpe=+2.000, WinRate=76.1%
        },
        'BNBUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.4 (было 0.5)
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.72,    # ✅ Пересчитано: 0.72 (было 0.68)
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.69%, Sharpe=+2.000, WinRate=73.8%
        },
        # 🔧 ТОП 6-10 (пересчитаны 30.11.2025 с исправленной формулой Sharpe)
        'XRPUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.7 (было 0.4)
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.65,    # ✅ Пересчитано: 0.65 (было 0.7)
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.69%, Sharpe=+2.000, WinRate=77.6%
        },
        'AVAXUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.7 (было 0.4)
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.65,    # ✅ Пересчитано: 0.65 (было 0.72)
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.98%, Sharpe=+2.000, WinRate=80.6%
        },
        'DOGEUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.7 (было 0.6)
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.65,    # ✅ Пересчитано: 0.65 (было 0.6)
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.51%, Sharpe=+2.000, WinRate=75.9%
        },
        'DOTUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.7 (без изменений)
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.65,    # ✅ Пересчитано: 0.65 (было 0.6)
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=-0.25%, Sharpe=-2.000, WinRate=69.8%
        },
        'LINKUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.7 (было 0.6)
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.7,     # ✅ Пересчитано: 0.7 (было 0.65)
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.31%, Sharpe=+2.000, WinRate=74.6%
        },
        # 🔧 ТОП 11-20 (пересчитаны 30.11.2025 с исправленной формулой Sharpe)
        'LTCUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.7
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.6,     # ✅ Пересчитано: 0.6
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.25%, Sharpe=+2.000, WinRate=73.6%
        },
        'TRXUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.5
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.72,    # ✅ Пересчитано: 0.72
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.61%, Sharpe=+2.000, WinRate=73.5%
        },
        'UNIUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.6
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.72,    # ✅ Пересчитано: 0.72
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.14%, Sharpe=+2.000, WinRate=76.7%
        },
        'NEARUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.4
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.72,    # ✅ Пересчитано: 0.72
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=+0.16%, Sharpe=+2.000, WinRate=80.2%
        },
        'SUIUSDT': {
            'volume_ratio': 0.7,      # ✅ Пересчитано: 0.7
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.7,     # ✅ Пересчитано: 0.7
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (пересчет 30.11.2025): return=-0.01%, Sharpe=-0.00
        },
        'PEPEUSDT': {
            'volume_ratio': 0.7,      # ✅ Пересчитано: 0.7
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.65,    # ✅ Пересчитано: 0.65
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (пересчет 30.11.2025): return=+0.19%, Sharpe=+0.05
        },
        'ENAUSDT': {
            'volume_ratio': 0.7,      # ✅ Пересчитано: 0.7
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.7,     # ✅ Пересчитано: 0.7
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (пересчет 30.11.2025): return=+0.45%, Sharpe=+0.13
        },
        'ICPUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.7
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.7,     # ✅ Пересчитано: 0.7
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025, переоптимизация): return=-3.43%, Sharpe=-2.000, WinRate=73.0%
        },
        'FETUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.65,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.7
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.72,    # ✅ Пересчитано: 0.72
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025): return=-16.06%, Sharpe=-0.030, WinRate=80.4%
        },
        'HBARUSDT': {
            'volume_ratio': 0.7,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.72,
                   'momentum_threshold': -5.0,      # ✅ Пересчитано: 0.4
            'rsi_oversold': 40,       # Фиксировано
            'rsi_overbought': 60,     # Фиксировано
            'trend_strength': 0.15,   # Фиксировано
            'quality_score': 0.7,     # ✅ Пересчитано: 0.7
            'momentum_threshold': -5.0  # Фиксировано
            # Результаты (13.12.2025): return=+114.56%, Sharpe=+0.306, WinRate=78.4%
        },
        # 🔧 НОВЫЕ 30 МОНЕТ (топ 21-50, добавлены 29.11.2025)
        # Топ 21-30
        'BCHUSDT': {
            'volume_ratio': 0.3,
                   'rsi_oversold': 40,
                   'rsi_overbought': 60,
                   'trend_strength': 0.15,
                   'quality_score': 0.6,
                   'momentum_threshold': -5.0,      # ✅ Оптимизировано: 0.6 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.7,
            'momentum_threshold': -5.0
            # Результаты (13.12.2025, переоптимизация): return=-0.38%, Sharpe=-2.000, WinRate=66.7%
        },
        'STRKUSDT': {
            'volume_ratio': 0.5,      # ✅ Оптимизировано: 0.3 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.65,
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=-0.11%, Sharpe=-0.01
        },
        'TAOUSDT': {
            'volume_ratio': 0.5,      # ✅ Оптимизировано: 0.7 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.65,    # ✅ Оптимизировано: 0.72 (было 0.65)
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=+0.05%, Sharpe=+0.01
        },
        'PENGUUSDT': {
            'volume_ratio': 0.6,      # ✅ Оптимизировано: 0.4
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.7,     # ✅ Оптимизировано: 0.7 (было 0.65)
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=+0.08%, Sharpe=+0.01
        },
        'ALLOUSDT': {
            'volume_ratio': 0.6,      # ✅ Оптимизировано: 0.3 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.72,     # ✅ Оптимизировано: 0.6 (было 0.65)
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=+0.01%, Sharpe=+0.00
        },
        'ASTERUSDT': {
            'volume_ratio': 0.5,      # ✅ Оптимизировано: 0.3 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.72,     # ✅ Оптимизировано: 0.7 (было 0.65)
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=+0.41%, Sharpe=+0.05
        },
        'MMTUSDT': {
            'volume_ratio': 0.3,      # ✅ Оптимизировано: 0.7 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.65,     # ✅ Оптимизировано: 0.7 (было 0.65)
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=+0.00%, Sharpe=+0.00
        },
        'PUMPUSDT': {
            'volume_ratio': 0.7,      # ✅ Оптимизировано: 0.5 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.7,
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=-0.32%, Sharpe=-0.04
        },
        'TNSRUSDT': {
            'volume_ratio': 0.7,      # ✅ Оптимизировано: 0.7 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.72,     # ✅ Оптимизировано: 0.6 (было 0.65)
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=+0.20%, Sharpe=+0.14
        },
        'WLFIUSDT': {
            'volume_ratio': 0.7,      # ✅ Оптимизировано: 0.7 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.6,     # ✅ Оптимизировано: 0.6 (было 0.65)
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=+0.66%, Sharpe=+0.14
        },
        # Топ 31-40
        'XPLUSDT': {
            'volume_ratio': 0.7,      # ✅ Оптимизировано: 0.7 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.72,     # ✅ Оптимизировано: 0.6 (было 0.65)
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=-0.27%, Sharpe=-0.03
        },
        'ZECUSDT': {
            'volume_ratio': 0.6,      # ✅ Оптимизировано: 0.7 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.6,     # ✅ Оптимизировано: 0.7 (было 0.65)
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=+1.09%, Sharpe=+0.29
        },
        'PAXGUSDT': {
            'volume_ratio': 0.4,      # ✅ Оптимизировано: 0.5 (было 0.4)
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.65,     # ✅ Оптимизировано: 0.6 (было 0.65)
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=-0.05%, Sharpe=-0.04
        },
        'USDEUSDT': {
            'volume_ratio': 0.4,      # ✅ Оптимизировано: 0.4
            'rsi_oversold': 40,
            'rsi_overbought': 60,
            'trend_strength': 0.15,
            'quality_score': 0.7,    # ✅ Оптимизировано: 0.72 (было 0.65)
            'momentum_threshold': -5.0
            # Результаты (пересчет 30.11.2025): return=+0.00%, Sharpe=+0.00
        },
        'TONUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=0.35%
                },
        'MATICUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=0.26%
                },
        'ATOMUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.98%
                },
        'ETCUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=0.12%
                },
        'FILUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.87%
                },
        'OPUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.57%
                },
        # Топ 41-50
        'APTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=1.14%
                },
        'ARBUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.40%
                },
        'WLDUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.67%
                },
        'SEIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.84%
                },
        'CFXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=0.31%
                },
        'BONKUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.10%
                },
        'WIFUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.53%
                },
        'FLOKIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.41%
                },
        'SHIBUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.73%
                },
        'CRVUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.59%
                },
        # 🔧 НОВЫЕ 50 МОНЕТ (топ 51-100, добавлены 30.11.2025)
        # Топ 51-60: DeFi и L2
        'AAVEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.45%
                },
        'MKRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.85%
                },
        'COMPUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.20%
                },
        'SNXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=1.78%
                },
        'YFIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.24%
                },
        'LRCUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.80%
                },
        'STXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.73%
                },
        'DYDXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.71%
                },
        'GMXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.40%
                },
        'RDNTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.16%
                },
        # Топ 61-70: NFT и Metaverse
        'SANDUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=1.02%
                },
        'MANAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.65%
                },
        'AXSUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.92%
                },
        'ENJUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=-2.000, Return=-0.10%
                },
        'GALAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=1.25%
                },
        'IMXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=1.05%
                },
        'APEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=1.03%
                },
        'RENDERUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.03%
                },
        'RNDRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.09%
                },
        'FLOWUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.30%
                },
        # Топ 71-80: Layer 1 альтернативы
        'XLMUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.47%
                },
        'ALGOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.86%
                },
        'VETUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.04%
                },
        'THETAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.99%
                },
        'EOSUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=-2.000, Return=-0.59%
                },
        'XTZUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.47%
                },
        'EGLDUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.16%
                },
        'KLAYUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=0.000, Return=0.10%
                },
        'ROSEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.37%
                },
        'IOTXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=-2.000, Return=-0.09%
                },
        # Топ 81-90: Privacy и старые монеты
        'COTIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=1.07%
                },
        'ONEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=1.37%
                },
        'IOTAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.44%
                },
        'QTUMUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.51%
                },
        'XMRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=0.63%
                },
        'DASHUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=-2.000, Return=-0.59%
                },
        'ZRXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.87%
                },
        'BATUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=-2.000, Return=-1.80%
                },
        'NEOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.58%
                },
        'ONTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.38%
                },
        # Топ 91-100: Новые популярные
        'ZILUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=1.06%
                },
        'CHZUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=-2.000, Return=-0.08%
                },
        'FTMUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=1.33%
                },
        'HOTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.78%
                },
        'CELRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.68%
                },
        'DENTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=-2.000, Return=-0.01%
                },
        'CELOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=1.53%
                },
        'KEEPUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=-2.000, Return=-0.47%
                },
        'C98USDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.09%
                },
        'MASKUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.13%
                },
        # 🔧 НОВЫЕ 59 МОНЕТ (топ 101-159, добавлены 01.12.2025)
        # Топ 101-110: Мемкоины и популярные альткоины
                                'BOMEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.29%
                },
                '1000SHIBUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=0.03%
                },
        'JUPUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.50%
                },
                        'TIAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=1.67%
                },
        # Топ 111-120: Layer 2 и DeFi протоколы
                                'GRTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.49%
                },
        'BALUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=1.56%
                },
                'SUSHIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.61%
                },
        '1INCHUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.35%
                },
        'ENSUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=1.03%
                },
        'LDOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.73%
                },
        # Топ 121-130: Инфраструктурные и утилитарные токены
                'INJUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.59%
                },
                'TWTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=0.24%
                },
                                'LUNCUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=-2.000, Return=-1.58%
                },
        'LUNAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=-2.000, Return=-1.47%
                },
        'USTCUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=-2.000, Return=-2.23%
                },
        # Топ 131-140: Exchange токены и стейкинг
        'CAKEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.20%
                },
        'JTOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=1.13%
                },
        'PYTHUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.99%
                },
        'RUNEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.80%
                },
        'WOOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=-2.000, Return=-0.38%
                },
        'IDUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.71%
                },
        'ARKMUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=1.49%
                },
        'AGIXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=2.39%
                },
        # Топ 141-150: AI и новые протоколы
                'AIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.84%
                },
        'PHBUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.28%
                },
        'XAIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 3, 14.12.2025): Sharpe=2.000, Return=1.66%
                },
        'NMRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.72%
                },
        'OCEANUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=1.61%
                },
        'VGXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=1.99%
                },
        'ARDRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.08%
                },
        'ARKUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.75%
                },
        'API3USDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=0.19%
                },
        # Топ 151-159: Разное
        'BANDUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (пария 1, 14.12.2025): Sharpe=2.000, Return=1.22%
                },
        'BLZUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=2.69%
                },
        'CTSIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.00%
                },
        'CTXCUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=1.07%
                },
        'DATAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=-2.000, Return=-0.29%
                },
        'DCRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=1.14%
                },
        'DOCKUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=2.000, Return=4.01%
                },
        'DGBUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (обновлено 14.12.2025): Sharpe=2.000, Return=0.90%
                },
        'ELFUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (загружены и оптимизированы 14.12.2025): Sharpe=-2.000, Return=-0.34%
                },
        'PORTALUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.84%
                },
        'PENDLEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=0.15%
                },
        'PIXELUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (партия 2, 14.12.2025): Sharpe=2.000, Return=1.12%
                },
        # 🔧 НОВЫЕ 55 МОНЕТ (добавлены 14.12.2025)
        'FLMUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=-2.000, Return=-0.05%
                },
        'LINAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.41%
                },
        'BAKEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=-2.000, Return=-1.03%
                },
        'CTKUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.36%
                },
        'OMGUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.09%
                },
        'YFIIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.77%
                },
        'SFPUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.53%
                },
        'LITUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.09%
                },
        'PERPUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.39%
                },
        'ALPHAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.41%
                },
        'FORTHUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.42%
                },
        'WAVESUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=2.07%
                },
        'OGNUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.49%
                },
        'ANKRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.25%
                },
        'KSMUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.05%
                },
        'IOSTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.07%
                },
        'SUNUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.21%
                },
        'CVCUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.54%
                },
        'SXPUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.35%
                },
        'COSUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.35%
                },
        'AUDIOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.34%
                },
        'SKLUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.82%
                },
        'CHRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.40%
                },
        'FTTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.69%
                },
        'BTTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.19%
                },
        'ICXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.59%
                },
        'TLMUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.45%
                },
        'RVNUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.03%
                },
        'WAXPUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.50%
                },
        'ZENUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.78%
                },
        'RENUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=-2.000, Return=-1.94%
                },
        'RSRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.17%
                },
        'STORJUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.40%
                },
        'XEMUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=1.28%
                },
        'HNTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.96%
                },
        'BETAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=-2.000, Return=-0.25%
                },
        'RADUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.47%
                },
        'RAREUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.10%
                },
        'LAZIOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.22%
                },
        'ADXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.65%
                },
        'AUCTIONUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.44%
                },
        'DARUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.46%
                },
        'BNXUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=-2.000, Return=-2.17%
                },
        'RGTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.94%
                },
        'MOVRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.80%
                },
        'CITYUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.83%
                },
        'KP3RUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.65%
                },
        'QIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.87%
                },
        'PORTOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.37%
                },
        'POWRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.54%
                },
        'JASMYUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.44%
                },
        'AMPUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.54%
                },
        'PLAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.82%
                },
        'GFTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.96%
                },
        'LPTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 55 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.30%
                },
        'USDCUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=0.000, Return=0.00%
                },
        'FDUSDUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=0.000, Return=-0.01%
                },
        'GIGGLEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.21%
                },
        'MOVEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=1.43%
                },
        'GUNUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.78%
                },
        'SOMIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=-2.000, Return=-0.17%
                },
        'JUVUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.06%
                },
        'AXLUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.43%
                },
        'HUMAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.19%
                },
        'EURUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=0.000, Return=-0.04%
                },
        'USD1USDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=0.000, Return=0.00%
                },
        'BIOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.22%
                },
        'BARDUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=-2.000, Return=-0.29%
                },
        'TRUMPUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=1.01%
                },
        'XUSDUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=0.000, Return=0.00%
                },
        'HYPERUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.80%
                },
        'ORDIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=-2.000, Return=-0.10%
                },
        'ATUSDT': {
                    'volume_ratio': 0.4,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.65,
                    'momentum_threshold': -5.0
                },
        'BFUSDUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=0.000, Return=0.00%
                },
        'TURBOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=-2.000, Return=-0.89%
                },
        'POLUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.91%
                },
        '0GUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.83%
                },
        'KDAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.39%
                },
        'VIRTUALUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=1.16%
                },
        'EIGENUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.66%
                },
        'ZROUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=-2.000, Return=-0.14%
                },
        'SANTOSUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=-2.000, Return=-0.48%
                },
        'BERAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.80%
                },
        'ONDOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.36%
                },
        'USUALUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=1.08%
                },
        'WBTCUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=0.28%
                },
        'IOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.63%
                },
        'ETHFIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.10%
                },
        'LAYERUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.78%
                },
        'GLMRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.33%
                },
        'ARUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.57%
                },
        'SAHARAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=1.02%
                },
        'SYRUPUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=1.33%
                },
        'KITEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=-2.000, Return=-1.88%
                },
        'RESOLVUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=-2.000, Return=-1.13%
                },
        'ACTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=-2.000, Return=-1.54%
                },
        'FISUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.13%
                },
        'VOXELUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=0.67%
                },
        'ZKUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=2.40%
                },
        'NEIROUSDT': {
                    'volume_ratio': 0.4,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.65,
                    'momentum_threshold': -5.0
                },
        'BANANAS31USDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=-2.000, Return=-0.53%
                },
        'SKYUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=-2.000, Return=-1.23%
                },
        'SUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=0.79%
                },
        'METUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.60%
                },
        'SAPIENUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.93%
                },
        'ALTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.19%
                },
        'PLUMEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=2.53%
                },
        'FFUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.36%
                },
        'SCRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.47%
                },
        'INITUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.81%
                },
        'BARUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.60%
                },
        'BUSDUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=0.000, Return=-0.00%
                },
        'PNUTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.96%
                },
        'MORPHOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=1.64%
                },
        'MEUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.77%
                },
        'LINEAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.14%
                },
        'NOTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.96%
                },
        'COCOSUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.50%
                },
        'QNTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=1.36%
                },
        'POLYUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=-2.000, Return=-0.34%
                },
        'EPICUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.34%
                },
        'VANAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=0.48%
                },
        'WUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=0.45%
                },
        'KMNOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.73%
                },
        'PARTIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=-2.000, Return=-0.28%
                },
        'XVGUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=0.21%
                },
        'HEMIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=1.03%
                },
        'GALUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.36%
                },
        'TRBUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=1.42%
                },
        'MAVUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.65%
                },
        'RAYUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.39%
                },
        'MAGICUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.19%
                },
        'FORMUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.54%
                },
        'GLMUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.39%
                },
        'AVNTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.44%
                },
        'AIXBTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.70%
                },
        'AUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.33%
                },
        'SHELLUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=1.21%
                },
        'OMNIUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.57%
                },
        'LSKUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=-2.000, Return=-0.16%
                },
        'TOMOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=2.000, Return=0.21%
                },
        'JSTUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.02%
                },
        'ONGUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.41%
                },
        'SAGAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.10%
                },
        'ENSOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.23%
                },
        'SUPERUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=-2.000, Return=-0.64%
                },
        'KAITOUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 2, 14.12.2025): Sharpe=2.000, Return=0.42%
                },
        'TVKUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=-2.000, Return=-5.74%
                },
        'OGUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=0.65%
                },
        'MINAUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 3, 14.12.2025): Sharpe=2.000, Return=1.60%
                },
        'SSVUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 4, 14.12.2025): Sharpe=-2.000, Return=-0.45%
                },
        '1000CHEEMSUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=-2.000, Return=-0.73%
                },
        '2ZUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=1.25%
                },
        '1000SATSUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.94%
                },
        'ACHUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (новые 100 монет, партия 1, 14.12.2025): Sharpe=2.000, Return=0.90%
                },
        'WBETHUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (2 новые монеты, 14.12.2025): Sharpe=2.000, Return=0.37%
                },
        'HMSTRUSDT': {
                    'volume_ratio': 0.3,
                    'rsi_oversold': 40,
                    'rsi_overbought': 60,
                    'trend_strength': 0.15,
                    'quality_score': 0.6,
                    'momentum_threshold': -5.0
                    # Результаты оптимизации (2 новые монеты, 14.12.2025): Sharpe=2.000, Return=1.08%
                }
    }

    return symbol_profiles.get(symbol, {
        'volume_ratio': 0.4,
        'rsi_oversold': 40,       # 🔧 Ослаблено: 40 вместо 25
        'rsi_overbought': 60,     # 🔧 Ослаблено: 60 вместо 75
        'trend_strength': 0.15,   # 🔧 Ослаблено: 0.15 вместо 0.6
        'quality_score': 0.65,
        'momentum_threshold': -5.0  # 🔧 Ослаблено: -5.0 вместо 0.0
    })


class PriorityFilterSystem:
    """Система приоритетов и компенсации фильтров"""

    def __init__(self):
        self.essential_filters = ['volume_liquidity', 'rsi_momentum']
        self.important_filters = ['trend_strength', 'quality_score']
        self.optional_filters = ['volume_profile', 'vwap', 'order_flow', 'microstructure', 'momentum']

    def evaluate_signal(
        self,
        signal_data: Dict[str, Any],
        adaptive_params: Dict[str, float]
    ) -> Tuple[bool, str, float]:
        """Оценивает сигнал с системой компенсации"""

        # Базовые обязательные фильтры
        essential_score = self._check_essential_filters(signal_data, adaptive_params)
        if essential_score < 0.5:  # 🔧 Ослаблено: 0.5 вместо 0.8
            return False, "Failed essential filters", essential_score

        # Важные фильтры с компенсацией
        important_score = self._check_important_filters(signal_data, adaptive_params)
        if important_score < 0.3:  # 🔧 Ослаблено: 0.3 вместо 0.6
            return False, "Failed important filters", important_score

        # Опциональные фильтры (бонус)
        optional_score = self._check_optional_filters(signal_data, adaptive_params)

        # Общая оценка с весами
        total_score = (
            essential_score * 0.4 +      # 40% обязательные
            important_score * 0.4 +       # 40% важные
            optional_score * 0.2          # 20% опциональные
        )

        passed = total_score >= 0.4  # 🔧 Ослаблено: 0.4 вместо 0.65
        reason = (
            f"Score: {total_score:.2f} "
            f"(essential={essential_score:.2f}, "
            f"important={important_score:.2f}, "
            f"optional={optional_score:.2f})"
        )

        return passed, reason, total_score

    def _check_essential_filters(
        self,
        signal_data: Dict[str, Any],
        adaptive_params: Dict[str, float]
    ) -> float:
        """Проверяет обязательные фильтры"""
        scores = []

        # Volume Liquidity
        volume_ratio = signal_data.get('volume_ratio', 0)
        volume_threshold = adaptive_params.get('volume_ratio', 0.5)
        if volume_ratio >= volume_threshold:
            scores.append(1.0)
        elif volume_ratio >= volume_threshold * 0.7:  # Частичное прохождение
            scores.append(0.5)
        else:
            scores.append(0.0)

        # RSI Momentum
        rsi = signal_data.get('rsi', 50)
        side = signal_data.get('side', 'LONG')
        if side == 'LONG':
            rsi_threshold = adaptive_params.get('rsi_oversold', 30)
            if rsi <= rsi_threshold:
                scores.append(1.0)
            elif rsi <= rsi_threshold + 10:  # Частичное прохождение
                scores.append(0.5)
            else:
                scores.append(0.0)
        else:  # SHORT
            rsi_threshold = adaptive_params.get('rsi_overbought', 70)
            if rsi >= rsi_threshold:
                scores.append(1.0)
            elif rsi >= rsi_threshold - 10:
                scores.append(0.5)
            else:
                scores.append(0.0)

        return sum(scores) / len(scores) if scores else 0.0

    def _check_important_filters(
        self,
        signal_data: Dict[str, Any],
        adaptive_params: Dict[str, float]
    ) -> float:
        """Проверяет важные фильтры"""
        scores = []

        # Trend Strength
        trend_strength = signal_data.get('trend_strength', 0)
        trend_threshold = adaptive_params.get('trend_strength', 0.6)
        if trend_strength >= trend_threshold:
            scores.append(1.0)
        elif trend_strength >= trend_threshold * 0.8:
            scores.append(0.6)
        else:
            scores.append(0.2)

        # Quality Score (если доступен)
        quality_score = signal_data.get('quality_score', 0.5)
        quality_threshold = adaptive_params.get('quality_score', 0.7)
        if quality_score >= quality_threshold:
            scores.append(1.0)
        elif quality_score >= quality_threshold * 0.8:
            scores.append(0.6)
        else:
            scores.append(0.3)

        return sum(scores) / len(scores) if scores else 0.0

    def _check_optional_filters(
        self,
        signal_data: Dict[str, Any],
        adaptive_params: Dict[str, float]
    ) -> float:
        """Проверяет опциональные фильтры (бонус)"""
        scores = []

        # Volume Profile
        if signal_data.get('vp_ok', True):
            scores.append(1.0)
        else:
            scores.append(0.5)  # Не критично

        # VWAP
        if signal_data.get('vwap_ok', True):
            scores.append(1.0)
        else:
            scores.append(0.5)

        # Momentum
        momentum = signal_data.get('momentum', 0)
        momentum_threshold = adaptive_params.get('momentum_threshold', 0.0)
        if momentum >= momentum_threshold:
            scores.append(1.0)
        else:
            scores.append(0.4)

        return sum(scores) / len(scores) if scores else 0.7  # По умолчанию нейтрально


class PerformanceBasedAdaptation:
    """Адаптация на основе исторической эффективности"""

    def __init__(self, learning_period: int = 1000):
        self.filter_performance: Dict[str, FilterPerformance] = defaultdict(FilterPerformance)
        self.learning_period = learning_period

    def update_performance(
        self,
        filter_name: str,
        is_profitable: bool,
        profit: float = 0.0
    ):
        """Обновляет статистику эффективности фильтра"""
        self.filter_performance[filter_name].update(is_profitable, profit)

    def get_adaptive_threshold(
        self,
        filter_name: str,
        base_threshold: float
    ) -> float:
        """Возвращает адаптированный порог на основе эффективности"""
        if filter_name not in self.filter_performance:
            return base_threshold

        stats = self.filter_performance[filter_name]

        if stats.total_signals < 10:  # Недостаточно данных
            return base_threshold

        # Адаптируем порог based on performance
        win_rate = stats.win_rate
        profit_factor = stats.profit_factor

        if win_rate > 0.7 and profit_factor > 2.0:  # Фильтр очень эффективен
            return base_threshold * 0.9  # Ослабляем немного
        elif win_rate < 0.4 or profit_factor < 1.0:  # Фильтр неэффективен
            return base_threshold * 1.2  # Ужесточаем
        else:
            return base_threshold


class IntelligentFilterSystem:
    """Интегрированная интеллектуальная система фильтрации"""

    def __init__(self):
        self.adaptive_system = AdaptiveFilterSystem()
        self.priority_system = PriorityFilterSystem()
        self.performance_system = PerformanceBasedAdaptation()
        self.adaptive_regulator = None

        if ADAPTIVE_REGULATOR_AVAILABLE and get_adaptive_regulator:
            try:
                self.adaptive_regulator = get_adaptive_regulator()
                logger.info("✅ AdaptiveFilterRegulator загружен")
            except Exception as e:
                logger.warning("⚠️ Не удалось загрузить AdaptiveFilterRegulator: %s", e)

    def process_signal(
        self,
        symbol: str,
        signal_data: Dict[str, Any],
        market_conditions: MarketConditions,
        historical_metrics: Optional[Dict[str, float]] = None
    ) -> Tuple[bool, str, Dict[str, float]]:
        """
        Обрабатывает сигнал с интеллектуальной адаптацией

        Args:
            symbol: Символ монеты
            signal_data: Данные сигнала (volume_ratio, rsi, trend_strength, и т.д.)
            market_conditions: Рыночные условия
            historical_metrics: Исторические метрики (win_rate, profit_factor)

        Returns:
            Tuple[bool, str, Dict]: (прошел_фильтры, причина, финальные_параметры)
        """

        # 1. Получаем адаптированные параметры под рыночные условия
        adaptive_params = self.adaptive_system.adapt_filters_to_market(
            symbol,
            market_conditions.volatility,
            market_conditions.trend_strength
        )

        # 2. Индивидуальные настройки для монеты
        symbol_params = get_symbol_specific_parameters(
            symbol,
            market_conditions.historical_volatility,
            market_conditions.avg_volume
        )

        # 3. Объединяем параметры (символ имеет приоритет)
        final_params = {**adaptive_params, **symbol_params}

        # 4. Используем AdaptiveFilterRegulator если доступен
        if self.adaptive_regulator:
            try:
                ai_volume_ratio = self.adaptive_regulator.get_adaptive_volume_ratio(
                    df=None,
                    market_volatility=market_conditions.volatility,
                    win_rate=historical_metrics.get('win_rate') if historical_metrics else None,
                    profit_factor=historical_metrics.get('profit_factor') if historical_metrics else None,
                    filter_mode="soft"
                )
                # Объединяем с финальными параметрами (AI имеет приоритет для volume_ratio)
                final_params['volume_ratio'] = min(
                    ai_volume_ratio,
                    final_params.get('volume_ratio', 0.5)
                )
            except Exception as e:
                logger.debug("⚠️ Ошибка AI адаптации: %s", e)

        # 5. Адаптируем пороги на основе эффективности
        for param_name, base_value in final_params.items():
            if param_name in ['volume_ratio', 'rsi_oversold', 'trend_strength', 'quality_score']:
                final_params[param_name] = self.performance_system.get_adaptive_threshold(
                    param_name, base_value
                )

        # 6. Применяем фильтры с системой приоритетов
        passed, reason, _ = self.priority_system.evaluate_signal(
            signal_data, final_params
        )

        return passed, reason, final_params

    def update_performance_from_trade(
        self,
        filter_params_used: Dict[str, float],
        is_profitable: bool,
        profit: float = 0.0
    ):
        """Обновляет статистику эффективности на основе результата сделки"""
        for param_name, _ in filter_params_used.items():
            self.performance_system.update_performance(
                param_name, is_profitable, profit
            )


# Глобальный экземпляр
_intelligent_filter_system: Optional[IntelligentFilterSystem] = None


def get_intelligent_filter_system() -> IntelligentFilterSystem:
    """Получает глобальный экземпляр IntelligentFilterSystem"""
    global _intelligent_filter_system
    if _intelligent_filter_system is None:
        _intelligent_filter_system = IntelligentFilterSystem()
    return _intelligent_filter_system
