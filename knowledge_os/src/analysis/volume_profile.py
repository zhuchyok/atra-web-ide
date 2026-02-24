"""
Volume Profile Analyzer - анализ профиля объема для определения зон высокой ликвидности
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class VolumeProfileAnalyzer:
    """
    Анализатор профиля объема

    Определяет:
    - Point of Control (POC) - уровень с максимальным объемом
    - Value Area High/Low (VAH/VAL) - зоны высокой стоимости
    - Зоны высокой ликвидности
    """

    def __init__(
        self,
        bins: int = 50,  # Количество бинов для профиля объема (улучшено с 24 до 50)
        value_area_pct: float = 0.70,  # Процент объема для Value Area
        default_lookback: int = 100,  # Дефолтный lookback период (улучшено с 20 до 100)
    ):
        self.bins = bins
        self.value_area_pct = value_area_pct
        self.default_lookback = default_lookback

    def calculate_volume_profile(
        self,
        df: pd.DataFrame,
        lookback_periods: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Рассчитывает профиль объема для заданного периода

        Args:
            df: DataFrame с OHLCV данными
            lookback_periods: Количество свечей для анализа (по умолчанию self.default_lookback)

        Returns:
            Dict с информацией о профиле объема
        """
        try:
            if lookback_periods is None:
                lookback_periods = self.default_lookback

            if len(df) < lookback_periods:
                lookback_periods = len(df)

            recent_df = df.tail(lookback_periods).copy()

            # Собираем все цены с их объемами
            price_volume_pairs = []

            for _, row in recent_df.iterrows():
                # Распределяем объем по диапазону свечи
                price_range = row["high"] - row["low"]
                if price_range == 0:
                    # Если свеча без движения, весь объем на close
                    price_volume_pairs.append((row["close"], row["volume"]))
                else:
                    # 🔧 ОПТИМИЗАЦИЯ: Уменьшаем количество точек для ускорения
                    # Используем фиксированное количество точек (3-5) вместо адаптивного
                    num_points = min(
                        5, max(3, int(price_range / (row["close"] * 0.002)))
                    )  # Упрощенная формула
                    volume_per_point = row["volume"] / num_points

                    for i in range(num_points):
                        price = (
                            row["low"] + (row["high"] - row["low"]) * (i / (num_points - 1))
                            if num_points > 1
                            else row["close"]
                        )
                        price_volume_pairs.append((price, volume_per_point))

            if not price_volume_pairs:
                return {
                    "poc": None,
                    "value_area_high": None,
                    "value_area_low": None,
                    "high_volume_zones": [],
                }

            # Создаем гистограмму
            prices = [p[0] for p in price_volume_pairs]
            volumes = [p[1] for p in price_volume_pairs]

            # Определяем диапазон цен
            min_price = min(prices)
            max_price = max(prices)

            if min_price == max_price:
                return {
                    "poc": min_price,
                    "value_area_high": min_price,
                    "value_area_low": min_price,
                    "high_volume_zones": [{"price": min_price, "volume": sum(volumes)}],
                }

            # Создаем бины
            bin_edges = np.linspace(min_price, max_price, self.bins + 1)
            bin_volumes, _ = np.histogram(prices, bins=bin_edges, weights=volumes)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

            # Находим POC (Point of Control) - бин с максимальным объемом
            poc_idx = np.argmax(bin_volumes)
            poc_price = bin_centers[poc_idx]
            poc_volume = bin_volumes[poc_idx]

            # Рассчитываем Value Area (70% объема)
            total_volume = sum(bin_volumes)
            target_volume = total_volume * self.value_area_pct

            # Находим бины, которые входят в Value Area
            sorted_indices = np.argsort(bin_volumes)[::-1]  # От большего к меньшему
            cumulative_volume = 0
            value_area_indices = []

            for idx in sorted_indices:
                cumulative_volume += bin_volumes[idx]
                value_area_indices.append(idx)
                if cumulative_volume >= target_volume:
                    break

            value_area_indices.sort()
            value_area_low = bin_centers[value_area_indices[0]]
            value_area_high = bin_centers[value_area_indices[-1]]

            # Определяем зоны высокой ликвидности (топ-30% объема)
            high_volume_threshold = total_volume * 0.30
            high_volume_zones = []

            for i, (center, volume) in enumerate(zip(bin_centers, bin_volumes)):
                if volume >= high_volume_threshold:
                    high_volume_zones.append(
                        {
                            "price": float(center),
                            "volume": float(volume),
                            "volume_pct": float(volume / total_volume * 100),
                        }
                    )

            # Сортируем зоны по объему
            high_volume_zones.sort(key=lambda x: x["volume"], reverse=True)

            result = {
                "poc": float(poc_price),
                "poc_volume": float(poc_volume),
                "value_area_high": float(value_area_high),
                "value_area_low": float(value_area_low),
                "high_volume_zones": high_volume_zones[:5],  # Топ-5 зон
                "total_volume": float(total_volume),
            }

            # Сохраняем для использования в combine_with_tpo
            self._last_poc = float(poc_price)
            self._last_vah = float(value_area_high)
            self._last_val = float(value_area_low)

            return result

        except Exception as e:
            logger.error("❌ Ошибка расчета профиля объема: %s", e)
            return {
                "poc": None,
                "value_area_high": None,
                "value_area_low": None,
                "high_volume_zones": [],
            }

    def is_in_high_volume_zone(
        self,
        current_price: float,
        volume_profile: Dict[str, Any],
        tolerance_pct: float = 1.0,
    ) -> Tuple[bool, Optional[float]]:
        """
        Проверяет, находится ли цена в зоне высокой ликвидности

        Args:
            current_price: Текущая цена
            volume_profile: Результат calculate_volume_profile
            tolerance_pct: Допустимое отклонение от зоны (%)

        Returns:
            Tuple[находится_ли_в_зоне, цена_ближайшей_зоны]
        """
        try:
            if not volume_profile.get("high_volume_zones"):
                return False, None

            # Проверяем POC
            poc = volume_profile.get("poc")
            if poc:
                distance_pct = abs(current_price - poc) / current_price * 100
                if distance_pct <= tolerance_pct:
                    return True, poc

            # Проверяем Value Area
            val = volume_profile.get("value_area_low")
            vah = volume_profile.get("value_area_high")
            if val and vah:
                if val <= current_price <= vah:
                    return True, (val + vah) / 2

            # Проверяем зоны высокой ликвидности
            for zone in volume_profile.get("high_volume_zones", []):
                zone_price = zone.get("price")
                if zone_price:
                    distance_pct = abs(current_price - zone_price) / current_price * 100
                    if distance_pct <= tolerance_pct:
                        return True, zone_price

            return False, None

        except Exception as e:
            logger.error("❌ Ошибка проверки зоны высокой ликвидности: %s", e)
            return False, None

    def get_poc_zones(
        self,
        df: pd.DataFrame,
        window: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Получает список зон POC за период

        Args:
            df: DataFrame с OHLCV данными
            window: Размер окна для анализа (по умолчанию self.default_lookback)

        Returns:
            List зон POC
        """
        try:
            if window is None:
                window = self.default_lookback

            zones = []

            # Скользящее окно для анализа
            for i in range(window, len(df)):
                window_df = df.iloc[i - window : i]
                profile = self.calculate_volume_profile(window_df, lookback_periods=window)

                poc = profile.get("poc")
                if poc:
                    zones.append(
                        {
                            "price": poc,
                            "volume": profile.get("poc_volume", 0),
                            "timestamp": df.index[i] if hasattr(df.index[i], "timestamp") else i,
                        }
                    )

            return zones

        except Exception as e:
            logger.error("❌ Ошибка получения зон POC: %s", e)
            return []

    def get_liquidity_zones(
        self,
        df: pd.DataFrame,
        lookback_periods: Optional[int] = None,
        min_volume_pct: float = 0.15,  # Минимальный процент объема для зоны
        cluster_tolerance_pct: float = 0.5,  # Толерантность для кластеризации уровней
    ) -> List[Dict[str, Any]]:
        """
        Определяет зоны ликвидности (скопление стоп-лоссов)

        Зоны ликвидности - это уровни, где:
        - Скапливаются стоп-лоссы трейдеров
        - Крупные игроки будут охотиться за ликвидностью
        - Обычно находятся выше/ниже значимых уровней

        Args:
            df: DataFrame с OHLCV данными
            lookback_periods: Количество свечей для анализа
            min_volume_pct: Минимальный процент объема для зоны
            cluster_tolerance_pct: Толерантность для кластеризации уровней (%)

        Returns:
            List зон ликвидности:
            [
                {
                    'price': float,
                    'type': 'support' | 'resistance',
                    'strength': float (0-1),
                    'volume_pct': float,
                    'distance_from_poc': float
                }
            ]
        """
        try:
            if lookback_periods is None:
                lookback_periods = self.default_lookback

            if len(df) < lookback_periods:
                return []

            recent_df = df.tail(lookback_periods).copy()

            # Рассчитываем Volume Profile
            profile = self.calculate_volume_profile(recent_df, lookback_periods=lookback_periods)
            poc = profile.get("poc")
            vah = profile.get("value_area_high")
            val = profile.get("value_area_low")

            if poc is None:
                return []

            # Находим локальные экстремумы (где обычно стоп-лоссы)
            price_range = recent_df["high"].max() - recent_df["low"].min()
            tolerance = price_range * cluster_tolerance_pct / 100

            liquidity_zones = []

            # Ищем уровни поддержки (ниже VAL) - где стоп-лоссы LONG
            if val:
                # Ищем локальные минимумы ниже VAL
                lows = recent_df["low"].values
                min_price = recent_df["low"].min()
                val_price = val

                # Кластеризуем минимумы
                support_clusters = self._cluster_price_levels(lows[lows < val_price], tolerance)

                for cluster in support_clusters:
                    cluster_price = cluster["price"]
                    cluster_volume = cluster.get("volume", 0)
                    total_volume = profile.get("total_volume", 1)

                    volume_pct = (cluster_volume / total_volume * 100) if total_volume > 0 else 0

                    if volume_pct >= min_volume_pct:
                        distance_from_poc = abs(cluster_price - poc) / poc * 100
                        strength = min(1.0, cluster["touches"] / 5.0)  # Сила по количеству касаний

                        liquidity_zones.append(
                            {
                                "price": float(cluster_price),
                                "type": "support",
                                "strength": float(strength),
                                "volume_pct": float(volume_pct),
                                "distance_from_poc": float(distance_from_poc),
                            }
                        )

            # Ищем уровни сопротивления (выше VAH) - где стоп-лоссы SHORT
            if vah:
                # Ищем локальные максимумы выше VAH
                highs = recent_df["high"].values
                max_price = recent_df["high"].max()
                vah_price = vah

                # Кластеризуем максимумы
                resistance_clusters = self._cluster_price_levels(
                    highs[highs > vah_price], tolerance
                )

                for cluster in resistance_clusters:
                    cluster_price = cluster["price"]
                    cluster_volume = cluster.get("volume", 0)
                    total_volume = profile.get("total_volume", 1)

                    volume_pct = (cluster_volume / total_volume * 100) if total_volume > 0 else 0

                    if volume_pct >= min_volume_pct:
                        distance_from_poc = abs(cluster_price - poc) / poc * 100
                        strength = min(1.0, cluster["touches"] / 5.0)

                        liquidity_zones.append(
                            {
                                "price": float(cluster_price),
                                "type": "resistance",
                                "strength": float(strength),
                                "volume_pct": float(volume_pct),
                                "distance_from_poc": float(distance_from_poc),
                            }
                        )

            # Сортируем по силе
            liquidity_zones.sort(key=lambda x: x["strength"], reverse=True)

            return liquidity_zones[:10]  # Топ-10 зон

        except Exception as e:
            logger.error("❌ Ошибка определения зон ликвидности: %s", e)
            return []

    def _cluster_price_levels(self, prices: np.ndarray, tolerance: float) -> List[Dict[str, Any]]:
        """
        Кластеризует близкие ценовые уровни

        Args:
            prices: Массив цен
            tolerance: Толерантность для кластеризации

        Returns:
            List кластеров
        """
        try:
            if len(prices) == 0:
                return []

            clusters = []
            sorted_prices = np.sort(prices)

            current_cluster = {
                "price": sorted_prices[0],
                "touches": 1,
                "prices": [sorted_prices[0]],
            }

            for price in sorted_prices[1:]:
                if abs(price - current_cluster["price"]) <= tolerance:
                    # Добавляем в текущий кластер
                    current_cluster["prices"].append(price)
                    current_cluster["touches"] += 1
                    # Обновляем среднюю цену
                    current_cluster["price"] = np.mean(current_cluster["prices"])
                else:
                    # Сохраняем текущий кластер и начинаем новый
                    if current_cluster["touches"] >= 2:  # Минимум 2 касания
                        clusters.append(current_cluster)
                    current_cluster = {"price": price, "touches": 1, "prices": [price]}

            # Добавляем последний кластер
            if current_cluster["touches"] >= 2:
                clusters.append(current_cluster)

            return clusters

        except Exception as e:
            logger.error("❌ Ошибка кластеризации уровней: %s", e)
            return []

    def combine_with_tpo(
        self,
        tpo_profile: Dict[str, Any],
        weight_volume: float = 0.6,
        weight_time: float = 0.4,
    ) -> Dict[str, Any]:
        """
        Комбинирует Volume Profile с TPO Profile для более точного POC

        Args:
            tpo_profile: Результат TPO Profile (из TimePriceOpportunity)
            weight_volume: Вес Volume Profile (по умолчанию 0.6)
            weight_time: Вес TPO Profile (по умолчанию 0.4)

        Returns:
            Комбинированный профиль с улучшенным POC и Value Area
        """
        try:
            # Получаем текущий Volume Profile (нужно вызвать calculate_volume_profile перед этим)
            # Этот метод должен вызываться после calculate_volume_profile

            volume_poc = getattr(self, "_last_poc", None)
            volume_vah = getattr(self, "_last_vah", None)
            volume_val = getattr(self, "_last_val", None)

            tpo_poc = tpo_profile.get("tpo_poc")
            tpo_vah = tpo_profile.get("tpo_value_area_high")
            tpo_val = tpo_profile.get("tpo_value_area_low")

            if volume_poc is None and tpo_poc is None:
                return {
                    "combined_poc": None,
                    "combined_value_area_high": None,
                    "combined_value_area_low": None,
                }

            # Комбинируем POC
            if volume_poc is not None and tpo_poc is not None:
                combined_poc = (volume_poc * weight_volume + tpo_poc * weight_time) / (
                    weight_volume + weight_time
                )
            elif volume_poc is not None:
                combined_poc = volume_poc
            else:
                combined_poc = tpo_poc

            # Комбинируем Value Area
            if volume_vah is not None and tpo_vah is not None:
                combined_vah = (volume_vah * weight_volume + tpo_vah * weight_time) / (
                    weight_volume + weight_time
                )
            elif volume_vah is not None:
                combined_vah = volume_vah
            else:
                combined_vah = tpo_vah

            if volume_val is not None and tpo_val is not None:
                combined_val = (volume_val * weight_volume + tpo_val * weight_time) / (
                    weight_volume + weight_time
                )
            elif volume_val is not None:
                combined_val = volume_val
            else:
                combined_val = tpo_val

            return {
                "combined_poc": float(combined_poc) if combined_poc is not None else None,
                "combined_value_area_high": float(combined_vah)
                if combined_vah is not None
                else None,
                "combined_value_area_low": float(combined_val)
                if combined_val is not None
                else None,
                "volume_poc": float(volume_poc) if volume_poc is not None else None,
                "tpo_poc": float(tpo_poc) if tpo_poc is not None else None,
            }

        except Exception as e:
            logger.error("❌ Ошибка комбинирования Volume Profile с TPO: %s", e)
            return {
                "combined_poc": None,
                "combined_value_area_high": None,
                "combined_value_area_low": None,
            }

    def combine_with_vwt(
        self,
        vwt_profile: Dict[str, Any],
        weight_volume: float = 0.5,
        weight_vwt: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Комбинирует Volume Profile с VWT Profile для более точного POC

        Args:
            vwt_profile: Результат VWT Profile (из VolumeWeightedTime)
            weight_volume: Вес Volume Profile (по умолчанию 0.5)
            weight_vwt: Вес VWT Profile (по умолчанию 0.5)

        Returns:
            Комбинированный профиль с улучшенным POC и Value Area
        """
        try:
            volume_poc = getattr(self, "_last_poc", None)
            volume_vah = getattr(self, "_last_vah", None)
            volume_val = getattr(self, "_last_val", None)

            vwt_poc = vwt_profile.get("vwt_poc")
            vwt_vah = vwt_profile.get("vwt_value_area_high")
            vwt_val = vwt_profile.get("vwt_value_area_low")

            if volume_poc is None and vwt_poc is None:
                return {
                    "combined_poc": None,
                    "combined_value_area_high": None,
                    "combined_value_area_low": None,
                }

            # Комбинируем POC
            if volume_poc is not None and vwt_poc is not None:
                total_weight = weight_volume + weight_vwt
                combined_poc = (volume_poc * weight_volume + vwt_poc * weight_vwt) / total_weight
            elif volume_poc is not None:
                combined_poc = volume_poc
            else:
                combined_poc = vwt_poc

            # Комбинируем Value Area
            if volume_vah is not None and vwt_vah is not None:
                total_weight = weight_volume + weight_vwt
                combined_vah = (volume_vah * weight_volume + vwt_vah * weight_vwt) / total_weight
            elif volume_vah is not None:
                combined_vah = volume_vah
            else:
                combined_vah = vwt_vah

            if volume_val is not None and vwt_val is not None:
                total_weight = weight_volume + weight_vwt
                combined_val = (volume_val * weight_volume + vwt_val * weight_vwt) / total_weight
            elif volume_val is not None:
                combined_val = volume_val
            else:
                combined_val = vwt_val

            return {
                "combined_poc": float(combined_poc) if combined_poc is not None else None,
                "combined_value_area_high": float(combined_vah)
                if combined_vah is not None
                else None,
                "combined_value_area_low": float(combined_val)
                if combined_val is not None
                else None,
                "volume_poc": float(volume_poc) if volume_poc is not None else None,
                "vwt_poc": float(vwt_poc) if vwt_poc is not None else None,
            }

        except Exception as e:
            logger.error("❌ Ошибка комбинирования Volume Profile с VWT: %s", e)
            return {
                "combined_poc": None,
                "combined_value_area_high": None,
                "combined_value_area_low": None,
            }
