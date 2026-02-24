"""
Volume Imbalance Filter - фильтр имбалансов объема
Обнаружение разрывов в объеме (volume spikes) для подтверждения сигналов
"""

import logging
from typing import Any, Dict

import pandas as pd

from src.filters.base import BaseFilter, FilterResult

# Импорты для анализа по уровням цены
try:
    from src.analysis.order_flow.price_level_imbalance import PriceLevelImbalance

    PRICE_LEVEL_IMBALANCE_AVAILABLE = True
except ImportError:
    PRICE_LEVEL_IMBALANCE_AVAILABLE = False

logger = logging.getLogger(__name__)


class VolumeImbalanceFilter(BaseFilter):
    """
    Фильтр имбалансов объема

    Логика:
    - Обнаруживает резкие скачки объема (volume spikes)
    - LONG: требует подтверждения объемом (высокий объем на росте)
    - SHORT: требует подтверждения объемом (высокий объем на падении)
    - Блокирует сигналы без подтверждения объемом
    """

    def __init__(
        self,
        enabled: bool = True,
        lookback_periods: int = 20,  # Период для расчета среднего объема
        volume_spike_threshold: float = 2.0,  # Порог скачка объема (кратность среднего)
        min_volume_ratio: float = 1.2,  # Минимальный объем для подтверждения
        require_volume_confirmation: bool = True,  # Требовать подтверждение объемом
        use_ml_optimization: bool = True,  # 🆕 Использовать ML оптимизацию
    ):
        super().__init__(
            name="VolumeImbalanceFilter",
            enabled=enabled,
            priority=4,  # Средний приоритет
        )
        self.lookback_periods = lookback_periods
        self.volume_spike_threshold = volume_spike_threshold
        self.min_volume_ratio = min_volume_ratio
        self.require_volume_confirmation = require_volume_confirmation
        self.use_ml_optimization = use_ml_optimization
        self.ml_optimizer = None

        # Инициализация анализатора по уровням цены
        self.price_level_analyzer = None
        if PRICE_LEVEL_IMBALANCE_AVAILABLE:
            try:
                self.price_level_analyzer = PriceLevelImbalance(
                    price_levels=10,
                    min_imbalance_threshold=0.3,
                )
            except Exception as e:
                logger.warning("⚠️ PriceLevelImbalance недоступен: %s", e)

        # 🆕 Инициализация ML оптимизатора
        if self.use_ml_optimization:
            try:
                from scripts.ml.filter_optimizer import get_ml_filter_optimizer

                self.ml_optimizer = get_ml_filter_optimizer()
                # Пытаемся загрузить обученную модель
                if not self.ml_optimizer.is_trained:
                    self.ml_optimizer.load_model()
                logger.info("✅ VolumeImbalanceFilter: ML оптимизатор подключен")
            except Exception as e:
                logger.warning("⚠️ VolumeImbalanceFilter: ML оптимизатор недоступен: %s", e)
                self.use_ml_optimization = False

    def _detect_volume_imbalance(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Обнаруживает имбаланс объема

        Args:
            df: DataFrame с OHLCV данными

        Returns:
            Dict с информацией об имбалансе:
            - has_imbalance: bool
            - volume_ratio: float
            - imbalance_type: "buy" | "sell" | "neutral"
            - spike_detected: bool
        """
        try:
            if len(df) < self.lookback_periods + 1:
                return {
                    "has_imbalance": False,
                    "volume_ratio": 1.0,
                    "imbalance_type": "neutral",
                    "spike_detected": False,
                }

            # Берем последние N свечей
            df_recent = df.tail(self.lookback_periods + 1).copy()

            # Текущая свеча
            current_volume = float(df_recent["volume"].iloc[-1])
            current_close = float(df_recent["close"].iloc[-1])

            # Предыдущая свеча
            prev_close = float(df_recent["close"].iloc[-2])

            # Средний объем за период
            avg_volume = float(df_recent["volume"].iloc[:-1].mean())

            if avg_volume == 0:
                return {
                    "has_imbalance": False,
                    "volume_ratio": 1.0,
                    "imbalance_type": "neutral",
                    "spike_detected": False,
                }

            # Отношение текущего объема к среднему
            volume_ratio = current_volume / avg_volume

            # Обнаружение скачка объема
            spike_detected = volume_ratio >= self.volume_spike_threshold

            # Определение типа имбаланса
            price_change = current_close - prev_close
            price_change_pct = (price_change / prev_close) * 100 if prev_close > 0 else 0

            if spike_detected:
                if price_change_pct > 0.5:  # Рост цены
                    imbalance_type = "buy"
                elif price_change_pct < -0.5:  # Падение цены
                    imbalance_type = "sell"
                else:
                    imbalance_type = "neutral"
            else:
                imbalance_type = "neutral"

            has_imbalance = spike_detected and imbalance_type != "neutral"

            return {
                "has_imbalance": has_imbalance,
                "volume_ratio": volume_ratio,
                "imbalance_type": imbalance_type,
                "spike_detected": spike_detected,
                "price_change_pct": price_change_pct,
            }

        except Exception as e:
            logger.error("❌ Ошибка обнаружения имбаланса объема: %s", e)
            return {
                "has_imbalance": False,
                "volume_ratio": 1.0,
                "imbalance_type": "neutral",
                "spike_detected": False,
            }

    async def filter_signal(self, signal_data: Dict[str, Any]) -> FilterResult:
        """
        Фильтрует сигнал на основе имбаланса объема

        🆕 ML ОПТИМИЗАЦИЯ: Динамически адаптирует параметры на основе текущих рыночных условий

        Args:
            signal_data: Данные сигнала
                - direction: "LONG" | "SHORT"
                - symbol: торговый символ
                - entry_price: цена входа
                - df: DataFrame с OHLCV данными

        Returns:
            FilterResult: Результат фильтрации
        """
        if not self.enabled:
            return FilterResult(passed=True, reason="FILTER_DISABLED")

        self.filter_stats["total_checked"] += 1

        try:
            direction = signal_data.get("direction", "").upper()
            symbol = signal_data.get("symbol", "")
            df = signal_data.get("df")

            # 🆕 ML ОПТИМИЗАЦИЯ: Получаем оптимальные параметры для текущих условий
            original_min_ratio = self.min_volume_ratio
            original_require_conf = self.require_volume_confirmation

            if self.use_ml_optimization and self.ml_optimizer and self.ml_optimizer.is_trained:
                try:
                    # Подготавливаем текущие рыночные условия
                    current_conditions = self._prepare_market_conditions(symbol, df, signal_data)

                    # Получаем оптимизированные параметры
                    optimized_params = self.ml_optimizer.optimize_filter_parameters(
                        current_conditions
                    )

                    # Временно применяем оптимизированные параметры
                    # 🔧 НЕ перезаписываем require_volume_confirmation, если он явно отключен в config
                    self.min_volume_ratio = optimized_params.get(
                        "min_volume_ratio", self.min_volume_ratio
                    )
                    # Если require_volume_confirmation=False в config, не перезаписываем его ML оптимизатором
                    if self.require_volume_confirmation:  # Только если True, позволяем ML менять
                        self.require_volume_confirmation = optimized_params.get(
                            "require_volume_confirmation", self.require_volume_confirmation
                        )

                    logger.debug(
                        "🎯 [ML_OPTIMIZE] %s: min_ratio=%.2f (было %.2f), "
                        "require_conf=%s (было %s)",
                        symbol,
                        self.min_volume_ratio,
                        original_min_ratio,
                        self.require_volume_confirmation,
                        original_require_conf,
                    )
                except Exception as e:
                    logger.debug(
                        "⚠️ [ML_OPTIMIZE] %s: ошибка оптимизации, "
                        "используем стандартные параметры: %s",
                        symbol,
                        e,
                    )

            if df is None or len(df) < self.lookback_periods + 1:
                logger.debug(
                    "⚠️ VolumeImbalanceFilter: недостаточно данных для %s, пропускаем", symbol
                )
                return FilterResult(passed=True, reason="INSUFFICIENT_DATA")

            # Обнаруживаем имбаланс объема
            imbalance_info = self._detect_volume_imbalance(df)

            volume_ratio = imbalance_info.get("volume_ratio", 1.0)
            imbalance_type = imbalance_info.get("imbalance_type", "neutral")
            spike_detected = imbalance_info.get("spike_detected", False)

            # Дополнительный анализ по уровням цены
            price_level_imbalance = None
            if self.price_level_analyzer and len(df) > 0:
                try:
                    price_level_imbalance = self.price_level_analyzer.calculate_imbalance_by_levels(
                        df, len(df) - 1
                    )
                    # Добавляем информацию о зонах максимального дисбаланса
                    imbalance_info["price_level_imbalance"] = price_level_imbalance
                    imbalance_info["max_imbalance_zones"] = price_level_imbalance.get(
                        "max_imbalance_zones", []
                    )
                except Exception as e:
                    logger.debug("⚠️ Ошибка анализа по уровням цены: %s", e)

            # Детальное логирование для диагностики (всегда INFO для видимости)
            try:
                current_vol = (
                    float(df["volume"].iloc[-1]) if "volume" in df.columns and len(df) > 0 else 0
                )
                avg_vol = (
                    float(df["volume"].iloc[:-1].mean())
                    if "volume" in df.columns and len(df) > 1
                    else 0
                )
            except:
                current_vol = 0
                avg_vol = 0

            logger.info(
                "🔍 [VolumeImbalance] %s: volume_ratio=%.3f, min_required=%.2f, imbalance_type=%s, spike=%s, current_vol=%.0f, avg_vol=%.0f",
                symbol,
                volume_ratio,
                self.min_volume_ratio,
                imbalance_type,
                spike_detected,
                current_vol,
                avg_vol,
            )

            # Если не требуем подтверждение объемом - разрешаем
            if not self.require_volume_confirmation:
                self.filter_stats["passed"] += 1
                return FilterResult(
                    passed=True, reason="VOLUME_CONFIRMATION_NOT_REQUIRED", details=imbalance_info
                )

            # Проверяем минимальный объем
            if volume_ratio < self.min_volume_ratio:
                # Объем ниже порога - блокируем
                self.filter_stats["blocked"] += 1
                try:
                    current_vol = (
                        float(df["volume"].iloc[-1])
                        if "volume" in df.columns and len(df) > 0
                        else 0
                    )
                    avg_vol = (
                        float(df["volume"].iloc[:-1].mean())
                        if "volume" in df.columns and len(df) > 1
                        else 0
                    )
                except:
                    current_vol = 0
                    avg_vol = 0

                logger.info(
                    "📊 [VolumeImbalance] %s: LOW_VOLUME - volume_ratio=%.3f (требуется >= %.2f, недостаточно на %.1f%%) | current_vol=%.0f, avg_vol=%.0f",
                    symbol,
                    volume_ratio,
                    self.min_volume_ratio,
                    ((self.min_volume_ratio - volume_ratio) / self.min_volume_ratio * 100)
                    if self.min_volume_ratio > 0
                    else 0,
                    current_vol,
                    avg_vol,
                )
                return FilterResult(
                    passed=False,
                    reason="LOW_VOLUME",
                    details={
                        "volume_ratio": volume_ratio,
                        "min_required": self.min_volume_ratio,
                        "message": f"Объем недостаточен ({volume_ratio:.2f}x < {self.min_volume_ratio}x)",
                    },
                )

            # Проверяем соответствие имбаланса направлению сигнала
            if direction == "LONG":
                # LONG: требуем имбаланс покупок (buy)
                if imbalance_type == "buy" and spike_detected:
                    self.filter_stats["passed"] += 1
                    return FilterResult(
                        passed=True,
                        reason="VOLUME_CONFIRMED_BUY",
                        details={
                            "volume_ratio": volume_ratio,
                            "imbalance_type": imbalance_type,
                            "spike_detected": spike_detected,
                        },
                    )
                elif imbalance_type == "sell" and spike_detected:
                    # Имбаланс продаж при LONG - блокируем
                    self.filter_stats["blocked"] += 1
                    return FilterResult(
                        passed=False,
                        reason="VOLUME_IMBALANCE_SELL",
                        details={
                            "volume_ratio": volume_ratio,
                            "imbalance_type": imbalance_type,
                            "message": "LONG сигнал при имбалансе продаж",
                        },
                    )
                else:
                    # Нет явного имбаланса - разрешаем (не блокируем)
                    self.filter_stats["passed"] += 1
                    return FilterResult(
                        passed=True,
                        reason="NO_VOLUME_IMBALANCE",
                        details={"volume_ratio": volume_ratio, "imbalance_type": imbalance_type},
                    )

            elif direction == "SHORT":
                # SHORT: требуем имбаланс продаж (sell)
                if imbalance_type == "sell" and spike_detected:
                    self.filter_stats["passed"] += 1
                    return FilterResult(
                        passed=True,
                        reason="VOLUME_CONFIRMED_SELL",
                        details={
                            "volume_ratio": volume_ratio,
                            "imbalance_type": imbalance_type,
                            "spike_detected": spike_detected,
                        },
                    )
                elif imbalance_type == "buy" and spike_detected:
                    # Имбаланс покупок при SHORT - блокируем
                    self.filter_stats["blocked"] += 1
                    return FilterResult(
                        passed=False,
                        reason="VOLUME_IMBALANCE_BUY",
                        details={
                            "volume_ratio": volume_ratio,
                            "imbalance_type": imbalance_type,
                            "message": "SHORT сигнал при имбалансе покупок",
                        },
                    )
                else:
                    # Нет явного имбаланса - разрешаем (не блокируем)
                    self.filter_stats["passed"] += 1
                    return FilterResult(
                        passed=True,
                        reason="NO_VOLUME_IMBALANCE",
                        details={"volume_ratio": volume_ratio, "imbalance_type": imbalance_type},
                    )

            # Неизвестное направление - разрешаем
            self.filter_stats["passed"] += 1
            return FilterResult(passed=True, reason="UNKNOWN_DIRECTION")

        except Exception as e:
            logger.error("❌ Ошибка в VolumeImbalanceFilter для %s: %s", symbol, e, exc_info=True)
            self.filter_stats["errors"] += 1
            # При ошибке разрешаем сигнал (graceful degradation)
            return FilterResult(
                passed=True, reason="ERROR_FALLBACK", details={"error": str(e), "symbol": symbol}
            )
        finally:
            # 🆕 Восстанавливаем оригинальные параметры после проверки (если использовали ML)
            if self.use_ml_optimization and self.ml_optimizer and self.ml_optimizer.is_trained:
                self.min_volume_ratio = original_min_ratio
                self.require_volume_confirmation = original_require_conf

    def _prepare_market_conditions(
        self, symbol: str, df: Any, signal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Подготавливает текущие рыночные условия для ML оптимизатора"""
        try:
            indicators = {}
            market_conditions = {}

            if df is not None and len(df) > 0:
                # Извлекаем индикаторы из DataFrame
                if "rsi" in df.columns:
                    indicators["rsi"] = float(df["rsi"].iloc[-1])
                if "ema_fast" in df.columns:
                    indicators["ema_fast"] = float(df["ema_fast"].iloc[-1])
                if "ema_slow" in df.columns:
                    indicators["ema_slow"] = float(df["ema_slow"].iloc[-1])
                if "macd" in df.columns:
                    indicators["macd"] = float(df["macd"].iloc[-1])
                if "bb_upper" in df.columns:
                    indicators["bb_upper"] = float(df["bb_upper"].iloc[-1])
                if "bb_lower" in df.columns:
                    indicators["bb_lower"] = float(df["bb_lower"].iloc[-1])

                # Рыночные условия
                if "volume_ratio" in df.columns:
                    market_conditions["volume_ratio"] = float(df["volume_ratio"].iloc[-1])
                if "volatility" in df.columns:
                    market_conditions["volatility"] = float(df["volatility"].iloc[-1])

            return {
                "indicators": indicators,
                "market_conditions": market_conditions,
                "risk_pct": signal_data.get("risk_pct", 2.0),
                "leverage": signal_data.get("leverage", 1.0),
            }
        except Exception as e:
            logger.debug("⚠️ Ошибка подготовки рыночных условий: %s", e)
            return {"indicators": {}, "market_conditions": {}, "risk_pct": 2.0, "leverage": 1.0}
