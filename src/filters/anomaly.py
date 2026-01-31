"""
Anomaly Filter Module
Модуль фильтров аномалий

This module contains anomaly detection and filtering functions
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from ..core.config import INDICATOR_SETTINGS
from ..core.cache import get_cached_anomaly, cache_anomaly
from .base import BaseFilter, FilterResult
from .config import ANOMALY_FILTER


class AnomalyFilter(BaseFilter):
    """Фильтр аномалий объема и капитализации"""

    def __init__(self, enabled: bool = True):
        super().__init__("anomaly", enabled, priority=3)

    def filter_signal(self, signal_data: Dict[str, Any]) -> FilterResult:
        """Фильтрация сигнала на основе аномалий"""
        try:
            symbol = signal_data.get('symbol', '')
            df = signal_data.get('df')

            if df is None or df.empty:
                return FilterResult(False, "Нет данных для анализа аномалий")

            # Проверяем кэш
            cached_result = get_cached_anomaly(symbol)
            if cached_result:
                return FilterResult(cached_result.get('passed', True),
                                  cached_result.get('reason', ''))

            # Анализируем аномалии
            anomaly_score = self.calculate_anomaly_score(df)
            is_anomaly = self.is_anomaly_detected(anomaly_score)

            if is_anomaly:
                reason = f"Обнаружена аномалия (скор: {anomaly_score:.2f})"
                result = FilterResult(False, reason)
            else:
                reason = f"Аномалий не обнаружено (скор: {anomaly_score:.2f})"
                result = FilterResult(True, reason)

            # Кэшируем результат
            cache_data = {
                'passed': result.passed,
                'reason': result.reason,
                'anomaly_score': anomaly_score,
                'timestamp': get_utc_now().isoformat()
            }
            cache_anomaly(symbol, cache_data)

            return result

        except Exception as e:
            return FilterResult(False, f"Ошибка анализа аномалий: {e}")

    def calculate_anomaly_score(self, df: pd.DataFrame) -> float:
        """Расчет скора аномалий"""
        try:
            if df.empty or 'volume' not in df.columns or 'close' not in df.columns:
                return 0.0

            lookback = ANOMALY_FILTER["settings"]["lookback_periods"]

            if len(df) < lookback:
                return 0.0

            # Расчет аномалий объема
            volume_anomaly = self.calculate_volume_anomaly(df, lookback)

            # Расчет аномалий капитализации (если есть данные)
            market_cap_anomaly = self.calculate_market_cap_anomaly(df, lookback)

            # Расчет аномалий цены
            price_anomaly = self.calculate_price_anomaly(df, lookback)

            # Комбинированный скор аномалий
            combined_score = (
                volume_anomaly * 0.5 +
                market_cap_anomaly * 0.3 +
                price_anomaly * 0.2
            )

            return min(combined_score, 10.0)  # Ограничиваем максимум

        except Exception as e:
            print(f"[AnomalyFilter] Ошибка расчета скора аномалий: {e}")
            return 0.0

    def calculate_volume_anomaly(self, df: pd.DataFrame, lookback: int) -> float:
        """Расчет аномалий объема"""
        try:
            # Текущий объем
            current_volume = df['volume'].iloc[-1]

            # Средний объем за период
            avg_volume = df['volume'].iloc[-lookback:-1].mean()

            if avg_volume <= 0:
                return 0.0

            # Коэффициент аномалии
            anomaly_ratio = current_volume / avg_volume

            # Применяем порог
            threshold = ANOMALY_FILTER["settings"]["volume_anomaly_threshold"]
            if anomaly_ratio > threshold:
                # Нормализуем скор от 0 до 5
                return min((anomaly_ratio - threshold) * 2, 5.0)

            return 0.0

        except Exception as e:
            print(f"[AnomalyFilter] Ошибка расчета аномалий объема: {e}")
            return 0.0

    def calculate_market_cap_anomaly(self, df: pd.DataFrame, lookback: int) -> float:
        """Расчет аномалий капитализации"""
        try:
            # Если нет данных о капитализации, используем объем * цена как proxy
            if 'market_cap' in df.columns:
                current_cap = df['market_cap'].iloc[-1]
                avg_cap = df['market_cap'].iloc[-lookback:-1].mean()
            else:
                # Используем объем * цена как proxy для капитализации
                current_volume = df['volume'].iloc[-1]
                current_price = df['close'].iloc[-1]
                current_cap = current_volume * current_price

                avg_volume = df['volume'].iloc[-lookback:-1].mean()
                avg_price = df['close'].iloc[-lookback:-1].mean()
                avg_cap = avg_volume * avg_price

            if avg_cap <= 0:
                return 0.0

            # Коэффициент аномалии
            anomaly_ratio = current_cap / avg_cap

            # Применяем порог
            threshold = ANOMALY_FILTER["settings"]["market_cap_anomaly_threshold"]
            if anomaly_ratio > threshold:
                # Нормализуем скор от 0 до 3
                return min((anomaly_ratio - threshold) * 1.5, 3.0)

            return 0.0

        except Exception as e:
            print(f"[AnomalyFilter] Ошибка расчета аномалий капитализации: {e}")
            return 0.0

    def calculate_price_anomaly(self, df: pd.DataFrame, lookback: int) -> float:
        """Расчет аномалий цены"""
        try:
            current_price = df['close'].iloc[-1]
            prices = df['close'].iloc[-lookback:-1]

            if len(prices) == 0:
                return 0.0

            # Статистические характеристики
            mean_price = prices.mean()
            std_price = prices.std()

            if std_price <= 0 or mean_price <= 0:
                return 0.0

            # Z-score текущей цены
            z_score = abs(current_price - mean_price) / std_price

            # Если z-score > 3, считаем это аномалией
            if z_score > 3.0:
                return min(z_score / 3.0, 2.0)

            return 0.0

        except Exception as e:
            print(f"[AnomalyFilter] Ошибка расчета аномалий цены: {e}")
            return 0.0

    def is_anomaly_detected(self, anomaly_score: float) -> bool:
        """Определение, является ли скор аномалией"""
        # Пороговое значение для определения аномалии
        anomaly_threshold = 2.0

        return anomaly_score > anomaly_threshold

    def get_anomaly_level(self, anomaly_score: float) -> str:
        """Получение уровня аномалии"""
        if anomaly_score >= 4.0:
            return "critical"
        elif anomaly_score >= 3.0:
            return "high"
        elif anomaly_score >= 2.0:
            return "medium"
        elif anomaly_score >= 1.0:
            return "low"
        else:
            return "normal"

    def calculate_anomaly_based_volume(self, df: pd.DataFrame, base_volume: float) -> float:
        """Расчет объема на основе аномалий"""
        try:
            anomaly_score = self.calculate_anomaly_score(df)

            # Модификатор объема на основе аномалий
            if anomaly_score > 2.0:
                # При аномалиях снижаем объем
                volume_modifier = max(0.3, 1.0 - (anomaly_score - 2.0) * 0.2)
            elif anomaly_score > 1.0:
                # При слабых аномалиях слегка снижаем объем
                volume_modifier = 0.8
            else:
                # При нормальных условиях используем базовый объем
                volume_modifier = 1.0

            return base_volume * volume_modifier

        except Exception as e:
            print(f"[AnomalyFilter] Ошибка расчета объема на основе аномалий: {e}")
            return base_volume

    def calculate_anomaly_based_risk(self, base_risk: float, df: pd.DataFrame) -> float:
        """Расчет риска на основе аномалий"""
        try:
            anomaly_score = self.calculate_anomaly_score(df)

            # Модификатор риска на основе аномалий
            if anomaly_score > 3.0:
                # При высоких аномалиях значительно снижаем риск
                risk_modifier = max(0.3, 1.0 - (anomaly_score - 3.0) * 0.3)
            elif anomaly_score > 2.0:
                # При средних аномалиях снижаем риск
                risk_modifier = 0.7
            elif anomaly_score > 1.0:
                # При слабых аномалиях слегка снижаем риск
                risk_modifier = 0.9
            else:
                # При нормальных условиях используем базовый риск
                risk_modifier = 1.0

            return base_risk * risk_modifier

        except Exception as e:
            print(f"[AnomalyFilter] Ошибка расчета риска на основе аномалий: {e}")
            return base_risk

    def get_anomaly_indicator(self, symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
        """Получить индикатор аномалий для символа"""
        try:
            anomaly_score = self.calculate_anomaly_score(df)
            is_anomaly = self.is_anomaly_detected(anomaly_score)
            level = self.get_anomaly_level(anomaly_score)

            return {
                'symbol': symbol,
                'anomaly_score': anomaly_score,
                'is_anomaly': is_anomaly,
                'level': level,
                'timestamp': get_utc_now().isoformat(),
                'threshold': 2.0
            }

        except Exception as e:
            print(f"[AnomalyFilter] Ошибка получения индикатора аномалий для {symbol}: {e}")
            return {
                'symbol': symbol,
                'anomaly_score': 0.0,
                'is_anomaly': False,
                'level': 'error',
                'timestamp': get_utc_now().isoformat(),
                'threshold': 2.0,
                'error': str(e)
            }


# Глобальный экземпляр фильтра аномалий
anomaly_filter = AnomalyFilter()
