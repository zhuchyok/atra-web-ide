"""
Adaptive Strategy - адаптивная стратегия с разными подходами для разных режимов рынка
"""

import logging
from typing import Dict, Any, Optional, Tuple

import pandas as pd

from src.analysis.market_structure import MarketStructureAnalyzer, MarketRegime
from src.analysis.entry_quality import EntryQualityScorer
# НЕ импортируем PullbackEntryLogic здесь, чтобы избежать циклической зависимости

logger = logging.getLogger(__name__)


class TrendFollowingStrategy:
    """
    Стратегия следования за трендом
    
    Используется в режиме TREND_UP или TREND_DOWN
    - Вход на откате к поддержке/сопротивлению
    - Более строгие требования к качеству
    - Увеличенный риск для высококачественных сигналов
    """
    
    def __init__(self):
        # НЕ создаем PullbackEntryLogic здесь, чтобы избежать циклической зависимости
        self.entry_quality = EntryQualityScorer()
    
    def get_entry_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию для входа в тренде"""
        return {
            "min_quality_score": 0.7,  # Строгие требования
            "require_trend": True,
            "support_tolerance_pct": 0.8,
            "resistance_tolerance_pct": 0.8,
        }
    
    def calculate_adaptive_risk(
        self,
        entry_quality: float,
        base_risk: float = 0.02,
    ) -> float:
        """
        Рассчитывает адаптивный риск для трендовой стратегии
        
        Args:
            entry_quality: Оценка качества входа (0.0-1.0)
            base_risk: Базовый риск (по умолчанию 2%)
        
        Returns:
            Адаптивный риск
        """
        # Для высококачественных сигналов в тренде увеличиваем риск
        if entry_quality > 0.8:
            return base_risk * 1.5  # 3%
        elif entry_quality > 0.7:
            return base_risk * 1.25  # 2.5%
        else:
            return base_risk  # 2%


class RangeTradingStrategy:
    """
    Стратегия торговли в диапазоне (флэт)
    
    Используется в режиме RANGE
    - Вход на границах диапазона
    - Менее строгие требования к качеству
    - Уменьшенный риск
    """
    
    def __init__(self):
        # НЕ создаем PullbackEntryLogic здесь, чтобы избежать циклической зависимости
        self.entry_quality = EntryQualityScorer()
    
    def get_entry_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию для входа во флэте"""
        return {
            "min_quality_score": 0.65,  # Менее строгие требования
            "require_trend": False,  # Разрешаем входы в флэте
            "support_tolerance_pct": 1.0,  # Более широкие зоны
            "resistance_tolerance_pct": 1.0,
        }
    
    def calculate_adaptive_risk(
        self,
        entry_quality: float,
        base_risk: float = 0.02,
    ) -> float:
        """
        Рассчитывает адаптивный риск для флэтовой стратегии
        
        Args:
            entry_quality: Оценка качества входа (0.0-1.0)
            base_risk: Базовый риск (по умолчанию 2%)
        
        Returns:
            Адаптивный риск
        """
        # Во флэте уменьшаем риск
        if entry_quality > 0.75:
            return base_risk * 1.0  # 2%
        elif entry_quality > 0.65:
            return base_risk * 0.75  # 1.5%
        else:
            return base_risk * 0.5  # 1%


class BreakoutStrategy:
    """
    Стратегия пробоя
    
    Используется в режиме VOLATILE
    - Вход на пробое уровней
    - Средние требования к качеству
    - Стандартный риск
    """
    
    def __init__(self):
        # НЕ создаем PullbackEntryLogic здесь, чтобы избежать циклической зависимости
        self.entry_quality = EntryQualityScorer()
    
    def get_entry_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию для входа при пробое"""
        return {
            "min_quality_score": 0.68,  # Средние требования
            "require_trend": False,  # Пробои могут быть в любом режиме
            "support_tolerance_pct": 0.9,
            "resistance_tolerance_pct": 0.9,
        }
    
    def calculate_adaptive_risk(
        self,
        entry_quality: float,
        base_risk: float = 0.02,
    ) -> float:
        """
        Рассчитывает адаптивный риск для стратегии пробоя
        
        Args:
            entry_quality: Оценка качества входа (0.0-1.0)
            base_risk: Базовый риск (по умолчанию 2%)
        
        Returns:
            Адаптивный риск
        """
        # При пробое используем стандартный риск
        if entry_quality > 0.75:
            return base_risk * 1.2  # 2.4%
        else:
            return base_risk  # 2%


class ReversalStrategy:
    """
    Стратегия разворота
    
    Используется в режиме REVERSAL
    - Вход на развороте тренда
    - Очень строгие требования к качеству
    - Уменьшенный риск
    """
    
    def __init__(self):
        # НЕ создаем PullbackEntryLogic здесь, чтобы избежать циклической зависимости
        self.entry_quality = EntryQualityScorer()
    
    def get_entry_config(self) -> Dict[str, Any]:
        """Возвращает конфигурацию для входа на развороте"""
        return {
            "min_quality_score": 0.75,  # Очень строгие требования
            "require_trend": False,  # Разворот не требует тренда
            "support_tolerance_pct": 0.7,  # Строгие уровни
            "resistance_tolerance_pct": 0.7,
        }
    
    def calculate_adaptive_risk(
        self,
        entry_quality: float,
        base_risk: float = 0.02,
    ) -> float:
        """
        Рассчитывает адаптивный риск для стратегии разворота
        
        Args:
            entry_quality: Оценка качества входа (0.0-1.0)
            base_risk: Базовый риск (по умолчанию 2%)
        
        Returns:
            Адаптивный риск
        """
        # На развороте уменьшаем риск
        if entry_quality > 0.8:
            return base_risk * 0.75  # 1.5%
        else:
            return base_risk * 0.5  # 1%


class AdaptiveStrategySelector:
    """
    Селектор адаптивной стратегии
    
    Выбирает стратегию на основе режима рынка
    """
    
    def __init__(self):
        self.market_structure = MarketStructureAnalyzer()
        self.strategies = {
            MarketRegime.TREND_UP: TrendFollowingStrategy(),
            MarketRegime.TREND_DOWN: TrendFollowingStrategy(),
            MarketRegime.RANGE: RangeTradingStrategy(),
            MarketRegime.VOLATILE: BreakoutStrategy(),
            MarketRegime.REVERSAL: ReversalStrategy(),
        }
        # Стратегия по умолчанию
        self.default_strategy = TrendFollowingStrategy()
    
    def get_strategy(self, df: pd.DataFrame) -> Tuple[Any, MarketRegime]:
        """
        Получает стратегию для текущего режима рынка
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            Tuple[стратегия, режим_рынка]
        """
        try:
            regime = self.market_structure.get_market_regime(df)
            strategy = self.strategies.get(regime, self.default_strategy)
            return strategy, regime
        except Exception as e:
            logger.error("❌ Ошибка выбора стратегии: %s", e)
            return self.default_strategy, MarketRegime.VOLATILE
    
    def get_entry_config(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Получает конфигурацию входа для текущего режима рынка
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            Dict с конфигурацией входа
        """
        strategy, regime = self.get_strategy(df)
        config = strategy.get_entry_config()
        config["regime"] = regime.value
        return config
    
    def calculate_adaptive_risk(
        self,
        df: pd.DataFrame,
        entry_quality: float,
        base_risk: float = 0.02,
    ) -> Tuple[float, str]:
        """
        Рассчитывает адаптивный риск на основе режима рынка и качества входа
        
        Args:
            df: DataFrame с OHLCV данными
            entry_quality: Оценка качества входа (0.0-1.0)
            base_risk: Базовый риск (по умолчанию 2%)
        
        Returns:
            Tuple[адаптивный_риск, режим_рынка]
        """
        strategy, regime = self.get_strategy(df)
        adaptive_risk = strategy.calculate_adaptive_risk(entry_quality, base_risk)
        return adaptive_risk, regime.value

