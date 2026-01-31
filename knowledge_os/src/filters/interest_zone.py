"""
Interest Zone Filter - фильтр зон скопления ликвидности
Базовая версия: определение зон по кластерам объема из OHLCV данных
Расширенная версия: использование Order Book для точных зон (опционально)
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd

from src.filters.base import BaseFilter, FilterResult

logger = logging.getLogger(__name__)


@dataclass
class InterestZone:
    """Зона интереса (скопление ликвидности)"""
    low: float
    high: float
    volume_cluster: float  # Объем в зоне
    zone_type: str  # "support" | "resistance" | "neutral"
    strength: float  # Сила зоны (0-1)


class InterestZoneFilter(BaseFilter):
    """
    Фильтр зон интереса (Interest Zones)

    Базовая версия:
    - Определяет зоны по кластерам объема из OHLCV
    - Использует ценовые уровни с высокой концентрацией объема
    - LONG: разрешаем в зонах поддержки
    - SHORT: разрешаем в зонах сопротивления
    """

    def __init__(
        self,
        enabled: bool = True,
        lookback_periods: int = 100,  # Количество свечей для анализа
        min_volume_cluster: float = 1.5,  # Минимальный объем кластера (кратность среднего)
        zone_width_pct: float = 0.5,  # Ширина зоны (% от цены)
        min_zone_strength: float = 0.6,  # Минимальная сила зоны
        use_orderbook: bool = False,  # Использовать Order Book для точных зон (пока не реализовано)
    ):
        super().__init__(
            name="InterestZoneFilter",
            enabled=enabled,
            priority=4  # Низкий приоритет (после других фильтров)
        )
        self.lookback_periods = lookback_periods
        self.min_volume_cluster = min_volume_cluster
        self.zone_width_pct = zone_width_pct
        self.min_zone_strength = min_zone_strength
        self.use_orderbook = use_orderbook
        if use_orderbook:
            logger.warning(
                "⚠️ InterestZoneFilter: use_orderbook=True, но функциональность Order Book "
                "еще не реализована. Используется только OHLCV анализ."
            )

    def _calculate_volume_clusters(self, df: pd.DataFrame) -> List[Tuple[float, float, float]]:
        """
        Рассчитывает кластеры объема для определения зон интереса

        Args:
            df: DataFrame с OHLCV данными

        Returns:
            List[Tuple[price_level, volume_sum, strength]]
        """
        try:
            if len(df) < 20:
                return []

            # Берем последние N свечей
            df_recent = df.tail(self.lookback_periods).copy()

            # Рассчитываем средний объем
            avg_volume = df_recent["volume"].mean()

            # Создаем ценовые уровни (binning)
            price_min = df_recent["low"].min()
            price_max = df_recent["high"].max()
            num_bins = 20  # Количество уровней

            bins = np.linspace(price_min, price_max, num_bins + 1)

            # Распределяем объем по уровням
            volume_by_level = {}
            for _, row in df_recent.iterrows():
                # Определяем, в какие бины попадает свеча
                for i in range(len(bins) - 1):
                    if bins[i] <= row["close"] <= bins[i + 1]:
                        level = (bins[i] + bins[i + 1]) / 2
                        volume_by_level[level] = volume_by_level.get(level, 0) + row["volume"]

            # Фильтруем уровни с достаточным объемом
            clusters = []
            for level, volume_sum in volume_by_level.items():
                volume_ratio = volume_sum / avg_volume if avg_volume > 0 else 0
                if volume_ratio >= self.min_volume_cluster:
                    strength = min(volume_ratio / 3.0, 1.0)  # Нормализуем силу (макс 3x среднего = 1.0)
                    clusters.append((level, volume_sum, strength))

            # Сортируем по объему (убывание)
            clusters.sort(key=lambda x: x[1], reverse=True)

            return clusters[:10]  # Топ-10 кластеров

        except Exception as e:
            logger.error("❌ Ошибка расчета кластеров объема: %s", e)
            return []

    def _identify_zones(self, df: pd.DataFrame, current_price: float) -> List[InterestZone]:
        """
        Определяет зоны интереса на основе кластеров объема

        Args:
            df: DataFrame с OHLCV данными
            current_price: Текущая цена

        Returns:
            List[InterestZone]: Список зон интереса
        """
        try:
            clusters = self._calculate_volume_clusters(df)
            if not clusters:
                return []

            zones = []
            for level, volume_sum, strength in clusters:
                if strength < self.min_zone_strength:
                    continue

                # Определяем ширину зоны
                zone_width = current_price * (self.zone_width_pct / 100)
                zone_low = level - zone_width / 2
                zone_high = level + zone_width / 2

                # Определяем тип зоны
                if level < current_price:
                    zone_type = "support"
                elif level > current_price:
                    zone_type = "resistance"
                else:
                    zone_type = "neutral"

                zones.append(InterestZone(
                    low=zone_low,
                    high=zone_high,
                    volume_cluster=volume_sum,
                    zone_type=zone_type,
                    strength=strength
                ))

            return zones

        except Exception as e:
            logger.error("❌ Ошибка определения зон: %s", e)
            return []

    def get_zones(self, df: pd.DataFrame, current_price: float) -> List[InterestZone]:
        """
        Публичный метод для получения зон интереса

        Args:
            df: DataFrame с OHLCV данными
            current_price: Текущая цена

        Returns:
            List[InterestZone]: Список зон интереса
        """
        return self._identify_zones(df, current_price)

    async def filter_signal(self, signal_data: Dict[str, Any]) -> FilterResult:
        """
        Фильтрует сигнал на основе зон интереса

        Args:
            signal_data: Данные сигнала
                - direction: "LONG" | "SHORT"
                - symbol: торговый символ
                - entry_price: цена входа
                - df: DataFrame с OHLCV данными (опционально)

        Returns:
            FilterResult: Результат фильтрации
        """
        if not self.enabled:
            return FilterResult(passed=True, reason="FILTER_DISABLED")

        self.filter_stats['total_checked'] += 1

        try:
            direction = signal_data.get("direction", "").upper()
            symbol = signal_data.get("symbol", "")
            entry_price = signal_data.get("entry_price") or signal_data.get("close")
            df = signal_data.get("df")

            if df is None or len(df) < 20:
                logger.debug("⚠️ InterestZoneFilter: недостаточно данных для %s, пропускаем", symbol)
                return FilterResult(passed=True, reason="INSUFFICIENT_DATA")

            if entry_price is None:
                logger.debug("⚠️ InterestZoneFilter: нет цены входа для %s, пропускаем", symbol)
                return FilterResult(passed=True, reason="NO_ENTRY_PRICE")

            # Определяем зоны интереса
            zones = self._identify_zones(df, entry_price)

            if not zones:
                # Нет зон - разрешаем сигнал (не блокируем)
                self.filter_stats['passed'] += 1
                return FilterResult(passed=True, reason="NO_ZONES_DETECTED")

            # Проверяем, находится ли цена в зоне интереса
            in_zone = False
            zone_type = None
            zone_strength = 0.0

            for zone in zones:
                if zone.low <= entry_price <= zone.high:
                    in_zone = True
                    zone_type = zone.zone_type
                    zone_strength = zone.strength
                    break

            if not in_zone:
                # Цена не в зоне - разрешаем (не блокируем, но снижаем приоритет)
                self.filter_stats['passed'] += 1
                return FilterResult(
                    passed=True,
                    reason="PRICE_OUTSIDE_ZONES",
                    details={
                        "zones_count": len(zones),
                        "nearest_zone": zones[0].zone_type if zones else None
                    }
                )

            # Цена в зоне - проверяем соответствие направлению
            if direction == "LONG":
                # LONG: разрешаем в зонах поддержки
                if zone_type == "support":
                    self.filter_stats['passed'] += 1
                    return FilterResult(
                        passed=True,
                        reason="IN_SUPPORT_ZONE",
                        details={
                            "zone_type": zone_type,
                            "zone_strength": zone_strength,
                            "zone_range": (zones[0].low, zones[0].high)
                        }
                    )
                else:
                    # LONG в зоне сопротивления - блокируем
                    self.filter_stats['blocked'] += 1
                    return FilterResult(
                        passed=False,
                        reason="IN_RESISTANCE_ZONE",
                        details={
                            "zone_type": zone_type,
                            "zone_strength": zone_strength,
                            "message": "LONG сигнал в зоне сопротивления"
                        }
                    )

            elif direction == "SHORT":
                # SHORT: разрешаем в зонах сопротивления
                if zone_type == "resistance":
                    self.filter_stats['passed'] += 1
                    return FilterResult(
                        passed=True,
                        reason="IN_RESISTANCE_ZONE",
                        details={
                            "zone_type": zone_type,
                            "zone_strength": zone_strength,
                            "zone_range": (zones[0].low, zones[0].high)
                        }
                    )
                else:
                    # SHORT в зоне поддержки - блокируем
                    self.filter_stats['blocked'] += 1
                    return FilterResult(
                        passed=False,
                        reason="IN_SUPPORT_ZONE",
                        details={
                            "zone_type": zone_type,
                            "zone_strength": zone_strength,
                            "message": "SHORT сигнал в зоне поддержки"
                        }
                    )

            # Неизвестное направление - разрешаем
            self.filter_stats['passed'] += 1
            return FilterResult(passed=True, reason="UNKNOWN_DIRECTION")

        except Exception as e:
            logger.error("❌ Ошибка в InterestZoneFilter: %s", e)
            self.filter_stats['errors'] += 1
            # При ошибке разрешаем сигнал (graceful degradation)
            return FilterResult(passed=True, reason="ERROR_FALLBACK", details={"error": str(e)})
