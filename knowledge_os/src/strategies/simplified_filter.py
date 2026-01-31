#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Упрощенная система фильтров с приоритизацией
Решает проблему переоптимизации и излишней сложности
"""

import pandas as pd
import talib as ta
from typing import Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# ПРИОРИТИЗИРОВАННАЯ СИСТЕМА ФИЛЬТРОВ
# ============================================================================

class FilterPriority:
    """Приоритеты фильтров для упрощенной системы"""
    
    # ПРИОРИТЕТ 1: Обязательные фильтры (все должны пройти)
    PRIORITY_1 = [
        "bb_direction",      # Направление Bollinger Bands
        "ema50_slope"        # Наклон EMA50 (тренд)
    ]
    
    # ПРИОРИТЕТ 2: Важные фильтры (минимум 2 из 3 должны пройти)
    PRIORITY_2 = [
        "bos_retest",           # Break of Structure + Retest
        "structure_min_distance",  # Минимальное расстояние структуры
        "volume_confirmation"   # Подтверждение объемом
    ]
    
    # ПРИОРИТЕТ 3: Дополнительные фильтры (минимум 1 из 3 должен пройти)
    PRIORITY_3 = [
        "rsi_momentum",         # RSI + Momentum
        "adx_trend_strength",   # ADX + сила тренда
        "anomaly_detection"     # Аномалии и киты
    ]

class MarketRegime:
    """Определение режима рынка для адаптивных параметров"""
    
    @staticmethod
    def detect_market_regime(df: pd.DataFrame, i: int) -> str:
        """
        Определяет режим рынка на основе волатильности и тренда
        
        Returns:
            str: "TREND", "RANGE", "TRANSITION"
        """
        try:
            if i < 50:
                return "TRANSITION"
            
            current = df.iloc[i]
            
            # Получаем индикаторы
            adx = current.get("adx", 20)
            bb_width = (current.get("bb_high", 0) - current.get("bb_low", 0)) / current.get("close", 1)
            
            # Определяем режим
            if adx > 25 and bb_width > 0.15:
                return "TREND"
            elif adx < 15 and bb_width < 0.10:
                return "RANGE"
            else:
                return "TRANSITION"
                
        except Exception as e:
            logger.warning("Ошибка определения режима рынка: %s", e)
            return "TRANSITION"

class SimplifiedFilterSystem:
    """Упрощенная система фильтров с приоритизацией"""
    
    def __init__(self):
        self.regime_params = {
            "TREND": {
                "min_distance": 0.12,
                "adx_threshold": 18,
                "volume_threshold": 1.1,
                "rsi_range": (35, 75)
            },
            "RANGE": {
                "min_distance": 0.08,
                "adx_threshold": 12,
                "volume_threshold": 1.0,
                "rsi_range": (30, 80)
            },
            "TRANSITION": {
                "min_distance": 0.15,
                "adx_threshold": 15,
                "volume_threshold": 1.2,
                "rsi_range": (25, 85)
            }
        }
    
    def check_priority_1_filters(self, df: pd.DataFrame, i: int, symbol: str) -> Dict[str, bool]:
        """Проверяет фильтры приоритета 1 (обязательные)"""
        results = {}
        
        try:
            # BB Direction - направление Bollinger Bands
            bb_direction_ok = self._check_bb_direction(df, i)
            results["bb_direction"] = bb_direction_ok
            
            # EMA50 Slope - наклон тренда
            ema50_slope_ok = self._check_ema50_slope(df, i)
            results["ema50_slope"] = ema50_slope_ok
            
        except Exception as e:
            logger.error("Ошибка в фильтрах приоритета 1 для %s: %s", symbol, e)
            results = {"bb_direction": True, "ema50_slope": True}  # Fallback
        
        return results
    
    def check_priority_2_filters(self, df: pd.DataFrame, i: int, symbol: str, regime: str) -> Dict[str, bool]:
        """Проверяет фильтры приоритета 2 (важные)"""
        results = {}
        params = self.regime_params[regime]
        
        try:
            # BOS + Retest
            bos_retest_ok = self._check_bos_retest(df, i, params["min_distance"])
            results["bos_retest"] = bos_retest_ok
            
            # Structure Min Distance
            structure_ok = self._check_structure_distance(df, i, params["min_distance"])
            results["structure_min_distance"] = structure_ok
            
            # Volume Confirmation
            volume_ok = self._check_volume_confirmation(df, i, params["volume_threshold"])
            results["volume_confirmation"] = volume_ok
            
        except Exception as e:
            logger.error("Ошибка в фильтрах приоритета 2 для %s: %s", symbol, e)
            results = {"bos_retest": True, "structure_min_distance": True, "volume_confirmation": True}
        
        return results
    
    def check_priority_3_filters(self, df: pd.DataFrame, i: int, symbol: str, regime: str) -> Dict[str, bool]:
        """Проверяет фильтры приоритета 3 (дополнительные)"""
        results = {}
        params = self.regime_params[regime]
        
        try:
            # RSI + Momentum
            rsi_momentum_ok = self._check_rsi_momentum(df, i, params["rsi_range"])
            results["rsi_momentum"] = rsi_momentum_ok
            
            # ADX + Trend Strength
            adx_trend_ok = self._check_adx_trend_strength(df, i, params["adx_threshold"])
            results["adx_trend_strength"] = adx_trend_ok
            
            # Anomaly Detection
            anomaly_ok = self._check_anomaly_detection(df, i)
            results["anomaly_detection"] = anomaly_ok
            
        except Exception as e:
            logger.error("Ошибка в фильтрах приоритета 3 для %s: %s", symbol, e)
            results = {"rsi_momentum": True, "adx_trend_strength": True, "anomaly_detection": True}
        
        return results
    
    def check_signal_passed(self, df: pd.DataFrame, i: int, symbol: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Основная функция проверки сигнала с приоритизацией
        
        Returns:
            Tuple[bool, str, Dict]: (прошел_фильтры, сообщение, детали)
        """
        try:
            # Определяем режим рынка
            regime = MarketRegime.detect_market_regime(df, i)
            
            # Проверяем фильтры по приоритетам
            priority_1_results = self.check_priority_1_filters(df, i, symbol)
            priority_2_results = self.check_priority_2_filters(df, i, symbol, regime)
            priority_3_results = self.check_priority_3_filters(df, i, symbol, regime)
            
            # Проверяем условия прохождения
            priority_1_passed = all(priority_1_results.values())
            priority_2_passed = sum(priority_2_results.values()) >= 2  # Минимум 2 из 3
            priority_3_passed = sum(priority_3_results.values()) >= 1   # Минимум 1 из 3
            
            # Общий результат
            signal_passed = priority_1_passed and priority_2_passed and priority_3_passed
            
            # Формируем сообщение
            if signal_passed:
                message = f"Signal passed ({regime} regime)"
            else:
                failed_priorities = []
                if not priority_1_passed:
                    failed_priorities.append("P1")
                if not priority_2_passed:
                    failed_priorities.append("P2")
                if not priority_3_passed:
                    failed_priorities.append("P3")
                message = f"Signal blocked - failed priorities: {', '.join(failed_priorities)}"
            
            # Детали для диагностики
            details = {
                "regime": regime,
                "priority_1": priority_1_results,
                "priority_2": priority_2_results,
                "priority_3": priority_3_results,
                "priority_1_passed": priority_1_passed,
                "priority_2_passed": priority_2_passed,
                "priority_3_passed": priority_3_passed
            }
            
            return signal_passed, message, details
            
        except Exception as e:
            logger.error("Критическая ошибка в упрощенной системе фильтров для %s: %s", symbol, e)
            return True, "Fallback: filters error", {"error": str(e)}
    
    # ========================================================================
    # РЕАЛИЗАЦИЯ КОНКРЕТНЫХ ФИЛЬТРОВ
    # ========================================================================
    
    def _check_bb_direction(self, df: pd.DataFrame, i: int) -> bool:
        """Проверяет направление Bollinger Bands"""
        try:
            if i < 20:
                return True
            
            current = df.iloc[i]
            
            # Проверяем, что цена находится в правильной зоне BB
            bb_low = current.get("bb_low", current["close"])
            bb_high = current.get("bb_high", current["close"])
            
            # Для LONG: цена должна быть в нижней половине BB
            # Для SHORT: цена должна быть в верхней половине BB
            bb_position = (current["close"] - bb_low) / (bb_high - bb_low) if bb_high != bb_low else 0.5
            
            # Принимаем сигналы в зонах 0.2-0.8 (избегаем экстремумов)
            return 0.2 <= bb_position <= 0.8
            
        except Exception:
            return True
    
    def _check_ema50_slope(self, df: pd.DataFrame, i: int) -> bool:
        """Проверяет наклон EMA50 (тренд)"""
        try:
            if i < 50:
                return True
            
            current = df.iloc[i]
            prev = df.iloc[i-1]
            
            ema50_current = current.get("ema50", current["close"])
            ema50_prev = prev.get("ema50", prev["close"])
            
            # EMA50 должна иметь четкий наклон (не горизонтальная)
            slope = (ema50_current - ema50_prev) / ema50_prev if ema50_prev != 0 else 0
            
            # Принимаем наклоны больше 0.001 (0.1%)
            return abs(slope) > 0.001
            
        except Exception:
            return True
    
    def _check_bos_retest(self, df: pd.DataFrame, i: int, min_distance: float) -> bool:
        """Улучшенная проверка BOS + Retest с зонами"""
        try:
            if i < 20:
                return True
            
            current = df.iloc[i]
            
            # Получаем ATR для адаптивного баффера
            atr = current.get("atr", current["close"] * 0.02)  # 2% по умолчанию
            
            # Проверяем наличие структуры в последних 20 свечах
            recent_data = df.iloc[max(0, i-20):i+1]
            
            # Ищем локальные максимумы и минимумы
            highs = recent_data["high"].rolling(5, center=True).max() == recent_data["high"]
            lows = recent_data["low"].rolling(5, center=True).min() == recent_data["low"]
            
            # Проверяем, есть ли достаточное расстояние между экстремумами
            if highs.any() and lows.any():
                max_high = recent_data[highs]["high"].max()
                min_low = recent_data[lows]["low"].min()
                distance = (max_high - min_low) / current["close"]
                
                return distance >= min_distance
            
            return True  # Если нет четкой структуры, пропускаем
            
        except Exception:
            return True
    
    def _check_structure_distance(self, df: pd.DataFrame, i: int, min_distance: float) -> bool:
        """Проверяет минимальное расстояние структуры"""
        try:
            if i < 20:
                return True
            
            current = df.iloc[i]
            
            # Анализируем последние 20 свечей
            recent_data = df.iloc[max(0, i-20):i+1]
            
            # Находим максимум и минимум за период
            max_price = recent_data["high"].max()
            min_price = recent_data["low"].min()
            
            # Проверяем расстояние
            distance = (max_price - min_price) / current["close"]
            
            return distance >= min_distance
            
        except Exception:
            return True
    
    def _check_volume_confirmation(self, df: pd.DataFrame, i: int, volume_threshold: float) -> bool:
        """Проверяет подтверждение объемом"""
        try:
            if i < 20:
                return True
            
            current = df.iloc[i]
            
            # Используем volume_ratio если доступен
            volume_ratio = current.get("volume_ratio", 1.0)
            
            return volume_ratio >= volume_threshold
            
        except Exception:
            return True
    
    def _check_rsi_momentum(self, df: pd.DataFrame, i: int, rsi_range: Tuple[int, int]) -> bool:
        """Проверяет RSI и momentum"""
        try:
            if i < 14:
                return True
            
            current = df.iloc[i]
            prev = df.iloc[i-1]
            
            # RSI
            rsi = current.get("rsi", 50)
            rsi_ok = rsi_range[0] <= rsi <= rsi_range[1]
            
            # Momentum (рост RSI)
            rsi_momentum = rsi > prev.get("rsi", rsi)
            
            return rsi_ok and rsi_momentum
            
        except Exception:
            return True
    
    def _check_adx_trend_strength(self, df: pd.DataFrame, i: int, adx_threshold: float) -> bool:
        """Проверяет ADX и силу тренда"""
        try:
            if i < 14:
                return True
            
            current = df.iloc[i]
            
            # ADX
            adx = current.get("adx", 20)
            adx_ok = adx >= adx_threshold
            
            # Дополнительная проверка силы тренда через EMA
            ema20 = current.get("ema20", current["close"])
            ema50 = current.get("ema50", current["close"])
            
            # Расстояние между EMA как индикатор силы тренда
            ema_distance = abs(ema20 - ema50) / ema50 if ema50 != 0 else 0
            trend_strength_ok = ema_distance > 0.01  # 1%
            
            return adx_ok and trend_strength_ok
            
        except Exception:
            return True
    
    def _check_anomaly_detection(self, df: pd.DataFrame, i: int) -> bool:
        """Проверяет аномалии и китовую активность"""
        try:
            if i < 20:
                return True
            
            current = df.iloc[i]
            
            # Простая проверка на аномалии объема
            volume_ratio = current.get("volume_ratio", 1.0)
            
            # Не блокируем при нормальном объеме, блокируем только при экстремальных значениях
            return 0.1 <= volume_ratio <= 10.0  # Избегаем экстремальных объемов
            
        except Exception:
            return True


# ============================================================================
# АДАПТИВНЫЕ ПОРОГИ ПО ВОЛАТИЛЬНОСТИ
# ============================================================================

class AdaptiveVolatilityThresholds:
    """Адаптивные пороги на основе волатильности"""
    
    @staticmethod
    def get_adaptive_min_distance(symbol: str, df: pd.DataFrame, i: int) -> float:
        """
        Возвращает адаптивный минимальный порог расстояния на основе волатильности
        """
        try:
            if i < 20:
                return 0.15  # По умолчанию
            
            # Получаем ATR за разные периоды
            atr_5 = df["atr"].iloc[max(0, i-5):i+1].mean() if "atr" in df.columns else None
            atr_20 = df["atr"].iloc[max(0, i-20):i+1].mean() if "atr" in df.columns else None
            
            if atr_5 is None or atr_20 is None:
                return 0.15  # Fallback
            
            # Определяем режим волатильности
            if atr_5 > atr_20 * 1.5:
                return 0.20  # Высокая волатильность - более строгие пороги
            elif atr_5 < atr_20 * 0.7:
                return 0.10  # Низкая волатильность - более мягкие пороги
            else:
                return 0.15  # Нормальная волатильность
                
        except Exception:
            return 0.15


# ============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================================

# Создаем глобальный экземпляр упрощенной системы фильтров
simplified_filter_system = SimplifiedFilterSystem()

# Функция для обратной совместимости
def check_simplified_trade_filters(df: pd.DataFrame, i: int, symbol: str = None) -> Tuple[bool, str]:
    """
    Упрощенная проверка фильтров с приоритизацией
    
    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        symbol: Символ для логирования
        
    Returns:
        Tuple[bool, str]: (прошел_фильтры, сообщение)
    """
    try:
        passed, message, details = simplified_filter_system.check_signal_passed(df, i, symbol or "unknown")
        
        # Логируем детали для диагностики
        if not passed:
            logger.debug("Signal blocked for %s: %s", symbol, message)
            logger.debug("Filter details: %s", details)
        
        return passed, message
        
    except Exception as e:
        logger.error("Ошибка в упрощенной системе фильтров: %s", e)
        return True, f"Fallback: {e}"
