#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система динамических ATR порогов
Решает проблему фиксированных порогов, которые не работают при изменении волатильности
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class DynamicATRSystem:
    """Система динамических ATR порогов на основе волатильности"""
    
    def __init__(self):
        # Базовые пороги для разных режимов волатильности
        self.volatility_regimes = {
            "LOW": {
                "atr_ratio_threshold": 0.7,      # ATR5/ATR20 < 0.7
                "min_distance_multiplier": 0.10, # 10% от ATR
                "max_distance_multiplier": 0.20, # 20% от ATR
                "adx_threshold": 12,             # Более мягкий ADX
                "volume_threshold": 0.9          # Более мягкий объем
            },
            "NORMAL": {
                "atr_ratio_threshold": 1.0,      # ATR5/ATR20 = 1.0
                "min_distance_multiplier": 0.15, # 15% от ATR
                "max_distance_multiplier": 0.25, # 25% от ATR
                "adx_threshold": 15,             # Стандартный ADX
                "volume_threshold": 1.0          # Стандартный объем
            },
            "HIGH": {
                "atr_ratio_threshold": 1.5,      # ATR5/ATR20 > 1.5
                "min_distance_multiplier": 0.20, # 20% от ATR
                "max_distance_multiplier": 0.30, # 30% от ATR
                "adx_threshold": 18,             # Более строгий ADX
                "volume_threshold": 1.2          # Более строгий объем
            }
        }
    
    def detect_volatility_regime(self, df: pd.DataFrame, i: int) -> str:
        """
        Определяет режим волатильности на основе ATR
        
        Returns:
            str: "LOW", "NORMAL", "HIGH"
        """
        try:
            if i < 20:
                return "NORMAL"  # Fallback для недостаточных данных
            
            # Получаем ATR за разные периоды
            atr_5 = self._calculate_atr(df, i, 5)
            atr_20 = self._calculate_atr(df, i, 20)
            
            if atr_5 is None or atr_20 is None or atr_20 == 0:
                return "NORMAL"  # Fallback
            
            # Вычисляем соотношение краткосрочной и среднесрочной волатильности
            atr_ratio = atr_5 / atr_20
            
            # Определяем режим
            if atr_ratio < 0.7:
                return "LOW"      # Низкая волатильность
            elif atr_ratio > 1.5:
                return "HIGH"     # Высокая волатильность
            else:
                return "NORMAL"   # Нормальная волатильность
                
        except Exception as e:
            logger.warning("Ошибка определения режима волатильности: %s", e)
            return "NORMAL"
    
    def _calculate_atr(self, df: pd.DataFrame, i: int, period: int) -> Optional[float]:
        """Вычисляет ATR за указанный период"""
        try:
            if i < period:
                return None
            
            # Используем встроенный ATR если доступен
            if "atr" in df.columns:
                return df["atr"].iloc[max(0, i-period+1):i+1].mean()
            
            # Ручной расчет ATR
            start_idx = max(0, i - period + 1)
            data_slice = df.iloc[start_idx:i+1]
            
            if len(data_slice) < 2:
                return None
            
            # True Range для каждой свечи
            tr_values = []
            for j in range(1, len(data_slice)):
                high = data_slice["high"].iloc[j]
                low = data_slice["low"].iloc[j]
                prev_close = data_slice["close"].iloc[j-1]
                
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                tr_values.append(tr)
            
            return np.mean(tr_values) if tr_values else None
            
        except Exception as e:
            logger.error("Ошибка расчета ATR: %s", e)
            return None
    
    def get_adaptive_parameters(self, df: pd.DataFrame, i: int, symbol: str = None) -> Dict[str, float]:
        """
        Возвращает адаптивные параметры на основе текущей волатильности
        
        Returns:
            Dict с адаптивными параметрами
        """
        try:
            # Определяем режим волатильности
            volatility_regime = self.detect_volatility_regime(df, i)
            regime_params = self.volatility_regimes[volatility_regime]
            
            # Получаем текущий ATR
            current_atr = self._calculate_atr(df, i, 14)  # Стандартный ATR(14)
            if current_atr is None:
                current_atr = df.iloc[i]["close"] * 0.02  # 2% fallback
            
            # Вычисляем адаптивные пороги
            min_distance = current_atr * regime_params["min_distance_multiplier"]
            max_distance = current_atr * regime_params["max_distance_multiplier"]
            
            # Адаптивные пороги для других индикаторов
            adaptive_params = {
                "volatility_regime": volatility_regime,
                "current_atr": current_atr,
                "min_distance": min_distance,
                "max_distance": max_distance,
                "adx_threshold": regime_params["adx_threshold"],
                "volume_threshold": regime_params["volume_threshold"],
                "atr_ratio": self._get_atr_ratio(df, i),
                "volatility_percentile": self._get_volatility_percentile(df, i),
                "symbol": symbol or "unknown"
            }
            
            return adaptive_params
            
        except Exception as e:
            logger.error("Ошибка получения адаптивных параметров для %s: %s", symbol, e)
            # Fallback параметры
            return {
                "volatility_regime": "NORMAL",
                "current_atr": 0.02,
                "min_distance": 0.15,
                "max_distance": 0.25,
                "adx_threshold": 15,
                "volume_threshold": 1.0,
                "atr_ratio": 1.0,
                "volatility_percentile": 50.0,
                "symbol": symbol or "unknown"
            }
    
    def _get_atr_ratio(self, df: pd.DataFrame, i: int) -> float:
        """Получает соотношение ATR5/ATR20"""
        try:
            atr_5 = self._calculate_atr(df, i, 5)
            atr_20 = self._calculate_atr(df, i, 20)
            
            if atr_5 is None or atr_20 is None or atr_20 == 0:
                return 1.0  # Fallback
            
            return atr_5 / atr_20
            
        except Exception:
            return 1.0
    
    def _get_volatility_percentile(self, df: pd.DataFrame, i: int) -> float:
        """Получает перцентиль текущей волатильности"""
        try:
            if i < 50:
                return 50.0  # Fallback для недостаточных данных
            
            # Анализируем последние 50 баров
            lookback = min(50, i)
            start_idx = max(0, i - lookback)
            
            recent_data = df.iloc[start_idx:i+1]
            
            # Вычисляем ATR для каждого бара
            atr_values = []
            for j in range(1, len(recent_data)):
                atr = self._calculate_atr(recent_data, j, 1)  # 1-периодный ATR
                if atr is not None:
                    atr_values.append(atr)
            
            if not atr_values:
                return 50.0
            
            # Текущий ATR
            current_atr = atr_values[-1]
            
            # Вычисляем перцентиль
            percentile = (np.sum(np.array(atr_values) <= current_atr) / len(atr_values)) * 100
            
            return percentile
            
        except Exception:
            return 50.0
    
    def check_adaptive_filters(self, df: pd.DataFrame, i: int, symbol: str = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Проверяет фильтры с адаптивными параметрами
        
        Returns:
            Tuple[bool, str, Dict]: (прошел_фильтры, сообщение, детали)
        """
        try:
            # Получаем адаптивные параметры
            adaptive_params = self.get_adaptive_parameters(df, i, symbol)
            
            current = df.iloc[i]
            
            # Проверяем фильтры с адаптивными порогами
            filters_passed = []
            filter_details = {}
            
            # 1. Проверка минимального расстояния
            min_distance_ok = self._check_min_distance(df, i, adaptive_params)
            filters_passed.append(min_distance_ok)
            filter_details["min_distance"] = {
                "passed": min_distance_ok,
                "threshold": adaptive_params["min_distance"],
                "regime": adaptive_params["volatility_regime"]
            }
            
            # 2. Проверка ADX с адаптивным порогом
            adx_ok = self._check_adaptive_adx(current, adaptive_params)
            filters_passed.append(adx_ok)
            filter_details["adx"] = {
                "passed": adx_ok,
                "threshold": adaptive_params["adx_threshold"],
                "current_adx": current.get("adx", 0)
            }
            
            # 3. Проверка объема с адаптивным порогом
            volume_ok = self._check_adaptive_volume(current, adaptive_params)
            filters_passed.append(volume_ok)
            filter_details["volume"] = {
                "passed": volume_ok,
                "threshold": adaptive_params["volume_threshold"],
                "current_volume_ratio": current.get("volume_ratio", 1.0)
            }
            
            # 4. Проверка волатильности
            volatility_ok = self._check_volatility_regime(adaptive_params)
            filters_passed.append(volatility_ok)
            filter_details["volatility"] = {
                "passed": volatility_ok,
                "regime": adaptive_params["volatility_regime"],
                "atr_ratio": adaptive_params["atr_ratio"]
            }
            
            # Общий результат
            all_passed = all(filters_passed)
            passed_count = sum(filters_passed)
            
            if all_passed:
                message = f"All adaptive filters passed ({adaptive_params['volatility_regime']} volatility)"
            else:
                message = f"Adaptive filters blocked ({passed_count}/4 passed, {adaptive_params['volatility_regime']} volatility)"
            
            return all_passed, message, {
                "adaptive_params": adaptive_params,
                "filter_details": filter_details,
                "passed_count": passed_count,
                "total_filters": len(filters_passed)
            }
            
        except Exception as e:
            logger.error("Ошибка в адаптивных фильтрах для %s: %s", symbol, e)
            return True, f"Fallback: {e}", {"error": str(e)}
    
    def _check_min_distance(self, df: pd.DataFrame, i: int, params: Dict) -> bool:
        """Проверяет минимальное расстояние с адаптивным порогом"""
        try:
            if i < 20:
                return True
            
            # Анализируем последние 20 баров
            recent_data = df.iloc[max(0, i-20):i+1]
            
            # Находим максимум и минимум
            max_price = recent_data["high"].max()
            min_price = recent_data["low"].min()
            current_price = df.iloc[i]["close"]
            
            # Вычисляем расстояние
            distance = (max_price - min_price) / current_price
            
            # Проверяем с адаптивным порогом
            return distance >= params["min_distance"] / current_price
            
        except Exception:
            return True
    
    def _check_adaptive_adx(self, current: pd.Series, params: Dict) -> bool:
        """Проверяет ADX с адаптивным порогом"""
        try:
            adx = current.get("adx", 20)
            return adx >= params["adx_threshold"]
        except Exception:
            return True
    
    def _check_adaptive_volume(self, current: pd.Series, params: Dict) -> bool:
        """Проверяет объем с адаптивным порогом"""
        try:
            volume_ratio = current.get("volume_ratio", 1.0)
            return volume_ratio >= params["volume_threshold"]
        except Exception:
            return True
    
    def _check_volatility_regime(self, params: Dict) -> bool:
        """Проверяет, что режим волатильности подходящий"""
        try:
            regime = params["volatility_regime"]
            atr_ratio = params["atr_ratio"]
            
            # Блокируем только экстремальные режимы
            if regime == "LOW" and atr_ratio < 0.5:
                return False  # Слишком низкая волатильность
            elif regime == "HIGH" and atr_ratio > 3.0:
                return False  # Слишком высокая волатильность
            
            return True
            
        except Exception:
            return True


# ============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================================

# Создаем глобальный экземпляр системы динамических ATR
dynamic_atr_system = DynamicATRSystem()

# Функция для обратной совместимости
def check_dynamic_atr_filters(df: pd.DataFrame, i: int, symbol: str = None) -> Tuple[bool, str]:
    """
    Проверка фильтров с динамическими ATR порогами
    
    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        symbol: Символ для логирования
        
    Returns:
        Tuple[bool, str]: (прошел_фильтры, сообщение)
    """
    try:
        passed, message, details = dynamic_atr_system.check_adaptive_filters(df, i, symbol)
        
        # Логируем детали для диагностики
        if not passed:
            logger.debug("Dynamic ATR filters blocked for %s: %s", symbol, message)
            logger.debug("Dynamic ATR details: %s", details)
        
        return passed, message
        
    except Exception as e:
        logger.error("Ошибка в системе динамических ATR: %s", e)
        return True, f"Fallback: {e}"
