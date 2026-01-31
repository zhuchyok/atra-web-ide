#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entry Timing Optimizer - оптимизация timing входа в позицию
Определяет оптимальную стратегию входа (немедленный vs откат)
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class EntryTimingOptimizer:
    """
    Оптимизатор timing входа в позицию
    
    Стратегии:
    1. IMMEDIATE - немедленный вход по текущей цене
    2. RETRACEMENT - вход на откате (лучшая цена)
    3. BREAKOUT_CONFIRMATION - ждем подтверждения пробоя
    """
    
    def __init__(self):
        # Настройки
        self.settings = {
            'retracement_pct': 0.003,  # 0.3% откат для улучшения входа
            'confirmation_candles': 2,  # Количество свечей для подтверждения
            'max_wait_minutes': 15,     # Максимум ждать 15 минут
        }
        
        # Статистика (для самообучения)
        self.stats = {
            'immediate': {'total': 0, 'successful': 0, 'avg_pnl': 0.0},
            'retracement': {'total': 0, 'successful': 0, 'avg_pnl': 0.0},
            'breakout_confirmation': {'total': 0, 'successful': 0, 'avg_pnl': 0.0}
        }
    
    async def get_optimal_entry_strategy(
        self, 
        df: pd.DataFrame, 
        signal_type: str, 
        current_price: float,
        market_regime: str = "NEUTRAL",
        composite_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Определяет оптимальную стратегию входа
        
        Args:
            df: DataFrame с OHLC данными
            signal_type: 'BUY' или 'SELL'
            current_price: Текущая цена
            market_regime: Рыночный режим
            composite_confidence: Уверенность composite signal
        
        Returns:
            {
                'strategy': 'immediate'|'retracement'|'breakout_confirmation',
                'entry_price': float,
                'confidence': float (0-1),
                'wait_minutes': int,
                'reason': str
            }
        """
        try:
            # Рассчитываем параметры для каждой стратегии
            strategies = {}
            
            # 1. IMMEDIATE - немедленный вход
            strategies['immediate'] = self._calc_immediate_strategy(
                df, signal_type, current_price, market_regime, composite_confidence
            )
            
            # 2. RETRACEMENT - вход на откате
            strategies['retracement'] = self._calc_retracement_strategy(
                df, signal_type, current_price, market_regime, composite_confidence
            )
            
            # 3. BREAKOUT CONFIRMATION - ждем подтверждения
            strategies['breakout_confirmation'] = self._calc_confirmation_strategy(
                df, signal_type, current_price, market_regime, composite_confidence
            )
            
            # Выбираем стратегию с наивысшей уверенностью
            best_strategy_name = max(strategies.keys(), key=lambda k: strategies[k]['confidence'])
            best_strategy = strategies[best_strategy_name]
            best_strategy['strategy'] = best_strategy_name
            
            logger.info("📍 [ENTRY TIMING] %s: %s (conf: %.2f, цена: %.8f)",
                       signal_type, best_strategy_name.upper(), 
                       best_strategy['confidence'], best_strategy['entry_price'])
            
            return best_strategy
            
        except Exception as e:
            logger.error("❌ Ошибка get_optimal_entry_strategy: %s", e)
            # Fallback: immediate entry
            return {
                'strategy': 'immediate',
                'entry_price': current_price,
                'confidence': 0.5,
                'wait_minutes': 0,
                'reason': f'Fallback (error: {e})'
            }
    
    def _calc_immediate_strategy(
        self, 
        df: pd.DataFrame, 
        signal_type: str, 
        current_price: float,
        market_regime: str,
        composite_confidence: float
    ) -> Dict[str, Any]:
        """Расчет immediate стратегии с использованием централизованных индикаторов"""
        try:
            confidence = 0.5  # Базовая уверенность
            
            # Обеспечиваем наличие индикаторов
            from src.signals.indicators import add_technical_indicators
            if 'momentum' not in df.columns or 'volume_ratio' not in df.columns:
                df = add_technical_indicators(df)
            
            # Факторы в пользу немедленного входа:
            
            # 1. Высокая уверенность composite signal
            if composite_confidence > 0.75:
                confidence += 0.20
            
            # 2. Сильный тренд (momentum)
            momentum_5 = df['momentum'].iloc[-1] / 100.0 if 'momentum' in df.columns else 0.0
            if signal_type == "BUY" and momentum_5 > 0.02:  # +2% за 5 свечей
                confidence += 0.15
            elif signal_type == "SELL" and momentum_5 < -0.02:  # -2% за 5 свечей
                confidence += 0.15
            
            # 3. Режим рынка
            if market_regime == "BULL_TREND" and signal_type == "BUY":
                confidence += 0.10
            elif market_regime == "BEAR_TREND" and signal_type == "SELL":
                confidence += 0.10
            elif market_regime == "HIGH_VOL_RANGE":
                confidence -= 0.10  # В волатильности лучше подождать
            
            # 4. Объем
            if 'volume_ratio' in df.columns:
                if df['volume_ratio'].iloc[-1] > 1.5:
                    confidence += 0.10  # Высокий объем = подтверждение
            
            confidence = max(0.0, min(1.0, confidence))
            
            return {
                'entry_price': current_price,
                'confidence': confidence,
                'wait_minutes': 0,
                'reason': f'Немедленный вход (momentum={momentum_5:.2%})'
            }
            
        except Exception as e:
            logger.debug("Ошибка _calc_immediate_strategy: %s", e)
            return {
                'entry_price': current_price,
                'confidence': 0.5,
                'wait_minutes': 0,
                'reason': 'Immediate (default)'
            }
    
    def _calc_retracement_strategy(
        self, 
        df: pd.DataFrame, 
        signal_type: str, 
        current_price: float,
        market_regime: str,
        composite_confidence: float
    ) -> Dict[str, Any]:
        """Расчет retracement стратегии (вход на откате)"""
        try:
            confidence = 0.5  # Базовая уверенность
            
            # Рассчитываем цену отката
            retracement_pct = self.settings['retracement_pct']
            if signal_type == "BUY":
                entry_price = current_price * (1 - retracement_pct)  # Ждем падения
            else:  # SELL
                entry_price = current_price * (1 + retracement_pct)  # Ждем роста
            
            # Факторы в пользу ожидания отката:
            
            # 1. Средняя уверенность composite (не очень сильный сигнал)
            if 0.55 < composite_confidence < 0.75:
                confidence += 0.20
            
            # 2. Недавнее резкое движение (вероятен откат)
            if len(df) >= 5:
                recent_move = abs(current_price - df['close'].iloc[-5]) / df['close'].iloc[-5]
                if recent_move > 0.03:  # Движение > 3%
                    confidence += 0.20
            
            # 3. Режим рынка (range-bound лучше для откатов)
            if market_regime in ["LOW_VOL_RANGE", "HIGH_VOL_RANGE"]:
                confidence += 0.15
            
            # 4. RSI перекуплен/перепродан (вероятен откат)
            if 'rsi' in df.columns:
                rsi = df['rsi'].iloc[-1]
                if signal_type == "BUY" and rsi < 35:  # Перепродано
                    confidence += 0.10
                elif signal_type == "SELL" and rsi > 65:  # Перекуплено
                    confidence += 0.10
            
            confidence = max(0.0, min(1.0, confidence))
            wait_minutes = 5  # Ждем 5 минут для отката
            
            return {
                'entry_price': entry_price,
                'confidence': confidence,
                'wait_minutes': wait_minutes,
                'reason': f'Откат {retracement_pct*100:.1f}% (better price)'
            }
            
        except Exception as e:
            logger.debug("Ошибка _calc_retracement_strategy: %s", e)
            return {
                'entry_price': current_price,
                'confidence': 0.3,
                'wait_minutes': 5,
                'reason': 'Retracement (default)'
            }
    
    def _calc_confirmation_strategy(
        self, 
        df: pd.DataFrame, 
        signal_type: str, 
        current_price: float,
        market_regime: str,
        composite_confidence: float
    ) -> Dict[str, Any]:
        """Расчет breakout confirmation стратегии"""
        try:
            confidence = 0.5  # Базовая уверенность
            
            # Факторы в пользу ожидания подтверждения:
            
            # 1. Низкая уверенность composite (нужно подтверждение)
            if composite_confidence < 0.60:
                confidence += 0.25
            
            # 2. Высокая волатильность (нужно подтверждение)
            if market_regime == "HIGH_VOL_RANGE":
                confidence += 0.20
            
            # 3. Цена близко к важному уровню (может отскочить)
            if len(df) >= 20:
                if signal_type == "BUY":
                    resistance = df['high'].iloc[-20:].max()
                    if abs(current_price - resistance) / resistance < 0.005:  # В пределах 0.5%
                        confidence += 0.15
                else:  # SELL
                    support = df['low'].iloc[-20:].min()
                    if abs(current_price - support) / support < 0.005:
                        confidence += 0.15
            
            # 4. Слабый объем (нужно подтверждение)
            if 'volume' in df.columns and len(df) >= 20:
                current_volume = df['volume'].iloc[-1]
                avg_volume = df['volume'].rolling(20).mean().iloc[-1]
                if current_volume < avg_volume * 1.2:
                    confidence += 0.10
            
            confidence = max(0.0, min(1.0, confidence))
            wait_minutes = 10  # Ждем 10 минут для подтверждения (2 свечи по 5 мин)
            
            return {
                'entry_price': current_price,  # Вход по текущей после подтверждения
                'confidence': confidence,
                'wait_minutes': wait_minutes,
                'reason': f'Ждем подтверждения ({self.settings["confirmation_candles"]} свечи)'
            }
            
        except Exception as e:
            logger.debug("Ошибка _calc_confirmation_strategy: %s", e)
            return {
                'entry_price': current_price,
                'confidence': 0.3,
                'wait_minutes': 10,
                'reason': 'Confirmation (default)'
            }
    
    def update_strategy_stats(self, strategy: str, was_successful: bool, pnl_pct: float):
        """Обновляет статистику для самообучения"""
        if strategy not in self.stats:
            return
        
        self.stats[strategy]['total'] += 1
        if was_successful:
            self.stats[strategy]['successful'] += 1
        
        # Обновляем средний PnL (экспоненциальное сглаживание)
        alpha = 0.1
        current_avg = self.stats[strategy]['avg_pnl']
        self.stats[strategy]['avg_pnl'] = current_avg * (1 - alpha) + pnl_pct * alpha
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по стратегиям"""
        result = {}
        for strategy, stats in self.stats.items():
            if stats['total'] > 0:
                result[strategy] = {
                    'total': stats['total'],
                    'successful': stats['successful'],
                    'winrate': stats['successful'] / stats['total'],
                    'avg_pnl': stats['avg_pnl']
                }
        return result


# Глобальный экземпляр
_entry_timing_optimizer = None

def get_entry_timing_optimizer() -> EntryTimingOptimizer:
    """Получение глобального экземпляра оптимизатора"""
    global _entry_timing_optimizer
    if _entry_timing_optimizer is None:
        _entry_timing_optimizer = EntryTimingOptimizer()
        logger.info("✅ EntryTimingOptimizer инициализирован")
    return _entry_timing_optimizer

