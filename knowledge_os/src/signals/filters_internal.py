#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Внутренние классы фильтров для signal_live.py

Вынесено из signal_live.py для улучшения структуры кода (Игорь + Павел - To 10/10)

Автор: Игорь (Backend Developer) + Павел (Backend Developer #2)
"""

import logging
import time
from typing import Dict, Any, Optional, List
from collections import defaultdict
import pandas as pd

# Импорты с адаптивной регуляцией
try:
    from src.ai.adaptive_filter_regulator import get_adaptive_regulator
    ADAPTIVE_REGULATOR_AVAILABLE = True
except ImportError:
    ADAPTIVE_REGULATOR_AVAILABLE = False
    get_adaptive_regulator = None

logger = logging.getLogger(__name__)


class SignalQualityValidator:
    """
    Валидатор качества сигналов.
    Проверяет качество данных, тренд, объём, волатильность и RSI.
    """
    
    def __init__(
        self,
        min_quality_score: float = 0.68,
        min_pattern_confidence: float = 0.6,
        min_volume_quality: float = 0.8
    ):
        self.min_quality_score = min_quality_score
        self.min_pattern_confidence = min_pattern_confidence
        self.min_volume_quality = min_volume_quality
    
    def _check_data_quality(self, df: pd.DataFrame) -> float:
        """Проверяет качество данных"""
        if df.empty or len(df) < 50:
            return 0.0
        
        # Проверяем наличие NaN
        nan_ratio = df.isnull().sum().sum() / (len(df) * len(df.columns))
        score = max(0.0, 1.0 - nan_ratio * 2)  # Штраф за NaN
        
        return score
    
    def _check_trend_strength(self, df: pd.DataFrame) -> float:
        """Проверяет силу тренда"""
        if 'adx' not in df.columns or df.empty:
            return 0.5  # Нейтральная оценка
        
        adx = df['adx'].iloc[-1]
        if adx >= 50:
            return 1.0  # Сильный тренд
        elif adx >= 25:
            return 0.7  # Средний тренд
        else:
            return 0.3  # Слабый тренд
    
    def _check_volume_quality(self, df: pd.DataFrame) -> float:
        """Проверяет качество объёма"""
        if 'volume_ratio' not in df.columns or df.empty:
            return 0.5  # Нейтральная оценка
        
        volume_ratio = df['volume_ratio'].iloc[-1]
        if volume_ratio >= 1.5:
            return 1.0  # Высокий объём
        elif volume_ratio >= 1.2:
            return 0.7  # Средний объём
        else:
            return 0.3  # Низкий объём
    
    def _check_volatility_quality(self, df: pd.DataFrame) -> float:
        """Проверяет качество волатильности"""
        if 'volatility' not in df.columns or df.empty:
            return 0.5  # Нейтральная оценка
        
        volatility = df['volatility'].iloc[-1]
        # Оптимальная волатильность: 2-5%
        if 2.0 <= volatility <= 5.0:
            return 1.0
        elif 1.0 <= volatility < 2.0 or 5.0 < volatility <= 8.0:
            return 0.7
        else:
            return 0.3
    
    def _check_rsi_quality(self, df: pd.DataFrame, signal_type: str) -> float:
        """Проверяет качество RSI"""
        if 'rsi' not in df.columns or df.empty:
            return 0.5  # Нейтральная оценка
        
        rsi = df['rsi'].iloc[-1]
        
        if signal_type.upper() == "BUY":
            # Для покупки оптимальный RSI: 30-50
            if 30 <= rsi <= 50:
                return 1.0
            elif 20 <= rsi < 30 or 50 < rsi <= 60:
                return 0.7
            else:
                return 0.3
        else:  # SELL
            # Для продажи оптимальный RSI: 50-70
            if 50 <= rsi <= 70:
                return 1.0
            elif 40 <= rsi < 50 or 70 < rsi <= 80:
                return 0.7
            else:
                return 0.3
    
    def calculate_quality_score(
        self,
        df: pd.DataFrame,
        signal_type: str,
        symbol: str
    ) -> float:
        """
        Рассчитывает общий score качества сигнала
        
        Returns:
            Score от 0.0 до 1.0
        """
        data_quality = self._check_data_quality(df)
        trend_strength = self._check_trend_strength(df)
        volume_quality = self._check_volume_quality(df)
        volatility_quality = self._check_volatility_quality(df)
        rsi_quality = self._check_rsi_quality(df, signal_type)
        
        # Взвешенная сумма
        quality_score = (
            data_quality * 0.2 +
            trend_strength * 0.25 +
            volume_quality * 0.25 +
            volatility_quality * 0.15 +
            rsi_quality * 0.15
        )
        
        return quality_score
    
    def is_signal_valid(self, quality_score: float) -> bool:
        """Проверяет, валиден ли сигнал по качеству"""
        return quality_score >= self.min_quality_score


class PatternConfidenceScorer:
    """
    Scorer для оценки уверенности в паттерне.
    """
    
    def __init__(self, min_confidence: float = 0.6):
        self.min_confidence = min_confidence
    
    def calculate_pattern_confidence(
        self,
        pattern_type: str,
        df: pd.DataFrame,
        signal_type: str
    ) -> float:
        """
        Рассчитывает уверенность в паттерне
        
        Returns:
            Confidence от 0.0 до 1.0
        """
        base_confidence = {
            'classic_ema': 0.8,
            'alternative_1': 0.7,
            'alternative_2': 0.6,
            'alternative_3': 0.5
        }.get(pattern_type, 0.5)
        
        # Бонусы за качество данных
        if not df.empty:
            # Бонус за объём
            if 'volume_ratio' in df.columns:
                volume_ratio = df['volume_ratio'].iloc[-1]
                if volume_ratio > 1.2:
                    base_confidence += 0.1
            
            # Бонус за тренд
            if 'adx' in df.columns:
                adx = df['adx'].iloc[-1]
                if adx > 30:
                    base_confidence += 0.1
        
        return min(1.0, base_confidence)
    
    def is_pattern_reliable(self, confidence: float) -> bool:
        """Проверяет, надёжен ли паттерн"""
        return confidence >= self.min_confidence


class DynamicSymbolBlocker:
    """
    Динамический блокировщик символов.
    Блокирует символы после нескольких неудачных сигналов.
    """
    
    def __init__(
        self,
        max_failures: int = 3,
        block_duration: int = 3600  # 1 час
    ):
        self.max_failures = max_failures
        self.block_duration = block_duration
        self.blocked_symbols: Dict[str, float] = {}  # symbol -> unblock_time
        self.symbol_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {'success_count': 0, 'failure_count': 0}
        )
    
    def is_blocked(self, symbol: str) -> bool:
        """Проверяет, заблокирован ли символ"""
        if symbol not in self.blocked_symbols:
            return False
        
        unblock_time = self.blocked_symbols[symbol]
        if time.time() > unblock_time:
            # Время блокировки истекло
            del self.blocked_symbols[symbol]
            return False
        
        return True
    
    def record_signal_result(self, symbol: str, success: bool):
        """Записывает результат сигнала"""
        if success:
            self.symbol_stats[symbol]['success_count'] += 1
            # Сбрасываем счётчик неудач при успехе
            self.symbol_stats[symbol]['failure_count'] = 0
        else:
            self.symbol_stats[symbol]['failure_count'] += 1
            
            # Блокируем если превышен лимит неудач
            if self.symbol_stats[symbol]['failure_count'] >= self.max_failures:
                self.block_symbol(symbol)
    
    def block_symbol(self, symbol: str):
        """Блокирует символ"""
        unblock_time = time.time() + self.block_duration
        self.blocked_symbols[symbol] = unblock_time
        logger.warning(f"🚫 Символ {symbol} заблокирован на {self.block_duration} секунд")
    
    def get_symbol_health(self, symbol: str) -> float:
        """Возвращает здоровье символа (0.0 - 1.0)"""
        if symbol not in self.symbol_stats:
            return 1.0
        
        stats = self.symbol_stats[symbol]
        total = stats['success_count'] + stats['failure_count']
        
        if total == 0:
            return 1.0
        
        return stats['success_count'] / total


class SmartRSIFilter:
    """
    Умный RSI фильтр с адаптивными порогами.
    """
    
    def __init__(self):
        self.config = {
            'rsi_extreme_threshold': {
                'buy': 85,
                'sell': 15
            },
            'rsi_warning_zone': {
                'buy': (70, 85),
                'sell': (15, 30)
            }
        }
    
    def evaluate(
        self,
        rsi: float = None,
        direction: str = None,
        trend_strength: float = None,
        volume_ratio: float = None,
        ai_confidence: float = None,
        btc_alignment: str = None,
        df: pd.DataFrame = None,
        signal_type: str = None
    ) -> Dict[str, Any]:
        """
        Оценивает сигнал по RSI
        
        Поддерживает два режима:
        1. Новый: с отдельными параметрами (rsi, direction, ...)
        2. Старый: с df и signal_type (для обратной совместимости)
        
        Returns:
            Dict с 'decision' (str: 'accept'/'reject') и 'reason' (str)
        """
        # Определяем режим вызова
        if rsi is not None and direction is not None:
            # Новый режим: используем переданные параметры
            rsi_value = float(rsi)
            signal_direction = direction.upper()
        elif df is not None and signal_type is not None:
            # Старый режим: извлекаем из DataFrame
            if 'rsi' not in df.columns or df.empty:
                return {'decision': 'accept', 'reason': 'RSI не доступен', 'adjustments': None}
            rsi_value = df['rsi'].iloc[-1]
            signal_direction = signal_type.upper()
        else:
            return {'decision': 'accept', 'reason': 'Недостаточно параметров', 'adjustments': None}
        
        # Основная логика проверки RSI
        adjustments = None
        
        # 🆕 ИСПОЛЬЗУЕМ АДАПТИВНУЮ РЕГУЛЯЦИЮ (если доступна)
        rsi_long_threshold = self.config['rsi_extreme_threshold']['buy']
        rsi_short_threshold = self.config['rsi_extreme_threshold']['sell']
        
        if ADAPTIVE_REGULATOR_AVAILABLE and get_adaptive_regulator:
            try:
                regulator = get_adaptive_regulator()
                # Для SmartRSI мы используем чуть более широкие границы, чем для обычного RSI фильтра
                # поэтому берем адаптивные значения и добавляем к ним 5-10 пунктов запаса
                base_long, base_short = regulator.get_adaptive_rsi_thresholds(
                    df=df,
                    market_volatility=None, # Можно добавить расчет волатильности
                    volume_ratio=volume_ratio
                )
                rsi_long_threshold = base_long + 10.0 # Например, 70 -> 80
                rsi_short_threshold = base_short - 10.0 # Например, 30 -> 20
                adjustments = {'adaptive': True, 'long_threshold': rsi_long_threshold, 'short_threshold': rsi_short_threshold}
            except Exception as e:
                logger.debug("⚠️ Ошибка адаптивной регуляции в SmartRSIFilter: %s", e)

        if signal_direction == "BUY" or signal_direction == "LONG":
            if rsi_value >= rsi_long_threshold:
                return {
                    'decision': 'reject',
                    'reason': f'RSI в зоне перекупленности ({rsi_value:.1f}) > {rsi_long_threshold:.1f}',
                    'adjustments': adjustments
                }
            elif self.config['rsi_warning_zone']['buy'][0] <= rsi_value < rsi_long_threshold:
                return {
                    'decision': 'accept',
                    'reason': f'RSI в зоне внимания ({rsi_value:.1f}), лимит {rsi_long_threshold:.1f}',
                    'adjustments': adjustments
                }
            else:
                return {
                    'decision': 'accept',
                    'reason': f'RSI в норме ({rsi_value:.1f})',
                    'adjustments': adjustments
                }
        else:  # SELL или SHORT
            if rsi_value <= rsi_short_threshold:
                return {
                    'decision': 'reject',
                    'reason': f'RSI в зоне перепроданности ({rsi_value:.1f}) < {rsi_short_threshold:.1f}',
                    'adjustments': adjustments
                }
            elif rsi_short_threshold < rsi_value <= self.config['rsi_warning_zone']['sell'][1]:
                return {
                    'decision': 'accept',
                    'reason': f'RSI в зоне внимания ({rsi_value:.1f}), лимит {rsi_short_threshold:.1f}',
                    'adjustments': adjustments
                }
            else:
                return {
                    'decision': 'accept',
                    'reason': f'RSI в норме ({rsi_value:.1f})',
                    'adjustments': adjustments
                }


class PipelineMonitor:
    """
    Мониторинг пайплайна генерации сигналов.
    """
    
    def __init__(self):
        self.stats: Dict[str, Any] = {
            'total_attempts': 0,
            'validation_passed': 0,
            'quality_passed': 0,
            'mtf_passed': 0,
            'ml_passed': 0,
            'final_signals': 0,
            'pattern_types': defaultdict(int)
        }
    
    def log_stage(self, stage: str, symbol: str, passed: bool, details: str = ""):
        """Логирует прохождение этапа"""
        self.stats['total_attempts'] += 1
        
        if passed:
            self.stats[f'{stage}_passed'] = self.stats.get(f'{stage}_passed', 0) + 1
    
    def log_pattern_type(self, pattern_type: str):
        """Логирует тип паттерна"""
        self.stats['pattern_types'][pattern_type] += 1
    
    def get_success_rates(self) -> Dict[str, float]:
        """Возвращает проценты успешности по этапам"""
        total = self.stats['total_attempts']
        if total == 0:
            return {}
        
        return {
            'validation': self.stats['validation_passed'] / total,
            'quality': self.stats['quality_passed'] / total,
            'mtf': self.stats['mtf_passed'] / total,
            'ml': self.stats['ml_passed'] / total,
            'final': self.stats['final_signals'] / total
        }
    
    def get_pattern_distribution(self) -> Dict[str, int]:
        """Возвращает распределение паттернов"""
        return dict(self.stats['pattern_types'])
    
    def print_stats(self):
        """Выводит статистику"""
        rates = self.get_success_rates()
        logger.info("📊 Статистика пайплайна:")
        for stage, rate in rates.items():
            logger.info(f"   {stage}: {rate*100:.1f}%")
        
        patterns = self.get_pattern_distribution()
        logger.info("📊 Распределение паттернов:")
        for pattern, count in patterns.items():
            logger.info(f"   {pattern}: {count}")

