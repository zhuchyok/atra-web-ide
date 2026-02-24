#!/usr/bin/env python3

"""
Интеграция новых улучшенных систем с существующей системой генерации сигналов.

Обеспечивает интеграцию источников данных, качества данных, риск-менеджмента,
мониторинга и логирования с существующим модулем signal_live.py.
"""

import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.shared.utils.datetime_utils import get_utc_now

# from src.core.exceptions import (
#     RiskError,
#     ValidationError,
#     DataError
# )

# Импорты для мониторинга (опциональные, импортируются здесь для типизации)
try:
    from src.monitoring.system import AlertSeverity, AlertType
    from src.monitoring.system import monitoring_system as global_monitoring_system
except ImportError:
    # Заглушки если модуль недоступен
    class AlertType:
        """Stub for AlertType"""

        DATA_QUALITY_ISSUE = "data_quality_issue"
        RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
        PERFORMANCE_DEGRADATION = "performance_degradation"

    class AlertSeverity:
        """Stub for AlertSeverity"""

        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
        CRITICAL = "critical"

    global_monitoring_system = None

logger = logging.getLogger(__name__)


class SignalLiveIntegration:
    """Интеграция новых систем с signal_live.py"""

    def __init__(self):
        self.data_sources_manager = None
        self.data_quality_monitor = None
        self.risk_manager = None
        self.monitoring_system = None
        self.enhanced_logging = None

        # Время запуска для статистики
        self._start_timestamp = time.time()

        # Статистика интеграции
        self.integration_stats = {
            "signals_generated": 0,
            "signals_with_risk_check": 0,
            "signals_blocked_by_risk": 0,
            "data_quality_issues": 0,
            "monitoring_alerts": 0,
        }

        self.is_initialized = False

    async def initialize(self):
        """Инициализирует интеграцию с новыми системами"""
        try:
            # Инициализация источников данных
            try:
                from src.data.sources_manager import data_sources_manager

                self.data_sources_manager = data_sources_manager
                logger.info("✅ Data sources manager integrated")
            except ImportError:
                logger.warning("⚠️ Data sources manager not available")

            # Инициализация мониторинга качества данных
            try:
                from src.monitoring.data_quality import data_quality_monitor

                self.data_quality_monitor = data_quality_monitor
                logger.info("✅ Data quality monitor integrated")
            except ImportError:
                logger.warning("⚠️ Data quality monitor not available")

            # Инициализация риск-менеджмента
            try:
                from src.risk.risk_manager import risk_manager

                self.risk_manager = risk_manager
                logger.info("✅ Risk manager integrated")
            except ImportError:
                logger.warning("⚠️ Risk manager not available")

            # Инициализация системы мониторинга
            if global_monitoring_system:
                self.monitoring_system = global_monitoring_system
                logger.info("✅ Monitoring system integrated")
            else:
                logger.warning("⚠️ Monitoring system not available")

            # Инициализация улучшенного логирования
            try:
                from enhanced_logging import (
                    add_metric,
                    get_logger,
                    log_performance,
                    start_performance_timer,
                )

                self.enhanced_logging = {
                    "get_logger": get_logger,
                    "add_metric": add_metric,
                    "log_performance": log_performance,
                    "start_performance_timer": start_performance_timer,
                }
                logger.info("✅ Enhanced logging integrated")
            except ImportError:
                logger.warning("⚠️ Enhanced logging not available")

            self.is_initialized = True
            logger.info("🎯 Signal live integration initialized successfully")

        except Exception as e:
            logger.error("❌ Error initializing signal live integration: %s", e)
            self.is_initialized = False

    async def get_enhanced_price_data(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> Optional[pd.DataFrame]:
        """Получает данные о ценах через улучшенную систему источников данных"""
        try:
            if not self.data_sources_manager:
                return None

            # Используем улучшенный менеджер источников данных
            df = await self.data_sources_manager.get_ohlcv_data(symbol, interval, limit)

            if df is not None:
                # Добавляем метрику качества данных
                if self.data_quality_monitor:
                    # Проверяем качество данных
                    await self._validate_data_quality(symbol, df)

                # Логируем получение данных
                if self.monitoring_system:
                    self.monitoring_system.add_metric(
                        "data_fetch_success", 1.0, "count", {"symbol": symbol, "source": "enhanced"}
                    )

            return df

        except Exception as e:
            logger.error("Error getting enhanced price data for %s: %s", symbol, e)

            # Логируем ошибку
            if self.monitoring_system:
                self.monitoring_system.add_metric(
                    "data_fetch_error", 1.0, "count", {"symbol": symbol, "error": str(e)}
                )

            return None

    async def _validate_data_quality(self, symbol: str, df: pd.DataFrame):
        """Валидирует качество полученных данных"""
        try:
            if not self.data_quality_monitor or df is None:
                return

            # Проверяем наличие пропущенных значений
            missing_values = df.isnull().sum().sum()
            if missing_values > 0:
                self.integration_stats["data_quality_issues"] += 1

                if self.monitoring_system:
                    self.monitoring_system.add_alert(
                        AlertType.DATA_QUALITY_ISSUE,
                        AlertSeverity.MEDIUM,
                        "Missing data detected",
                        "Symbol %s has %s missing values" % (symbol, missing_values),
                        "signal_live_integration",
                    )

            # Проверяем аномалии в ценах
            price_columns = ["open", "high", "low", "close"]
            for col in price_columns:
                if col in df.columns:
                    prices = df[col].dropna()
                    if len(prices) > 1:
                        # Проверяем на резкие скачки цен (>10%)
                        price_changes = prices.pct_change().abs()
                        large_changes = price_changes[price_changes > 0.1]

                        if len(large_changes) > 0:
                            self.integration_stats["data_quality_issues"] += 1

                            if self.monitoring_system:
                                self.monitoring_system.add_alert(
                                    AlertType.DATA_QUALITY_ISSUE,
                                    AlertSeverity.LOW,
                                    "Price anomaly detected",
                                    f"Symbol {symbol} column {col} has {len(large_changes)} large price changes",
                                    "signal_live_integration",
                                )

        except Exception as e:
            logger.error("Error validating data quality for %s: %s", symbol, e)

    async def check_risk_limits(
        self, symbol: str, side: str, quantity: Decimal, entry_price: Decimal, user_balance: Decimal
    ) -> Tuple[bool, str]:
        """Проверяет лимиты риска перед генерацией сигнала"""
        try:
            if not self.risk_manager:
                return True, "Risk manager not available"

            # Обновляем баланс в риск-менеджере
            self.risk_manager.update_balance(float(user_balance))

            # Проверяем лимиты риска
            can_open = self.risk_manager.check_position_limits(
                type(
                    "Position",
                    (),
                    {
                        "symbol": symbol,
                        "side": side,
                        "quantity": float(quantity),
                        "entry_price": float(entry_price),
                        "margin_used": float(quantity * entry_price),
                    },
                )()
            )

            if not can_open:
                self.integration_stats["signals_blocked_by_risk"] += 1

                if self.monitoring_system:
                    self.monitoring_system.add_alert(
                        AlertType.RISK_LIMIT_EXCEEDED,
                        AlertSeverity.MEDIUM,
                        "Signal blocked by risk limits",
                        "Symbol %s %s signal blocked due to risk limits" % (symbol, side),
                        "signal_live_integration",
                    )

                return False, "Signal blocked by risk limits"

            self.integration_stats["signals_with_risk_check"] += 1
            return True, "Risk check passed"

        except Exception as e:
            logger.error("Error checking risk limits for %s: %s", symbol, e)
            return True, "Risk check error: %s" % str(e)

    async def calculate_adaptive_position_size(
        self,
        symbol: str,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        user_balance: Decimal,
        risk_pct: Decimal = Decimal("2.0"),
    ) -> Dict[str, Decimal]:
        """Вычисляет адаптивный размер позиции"""
        try:
            if not self.risk_manager:
                # Возвращаем базовый расчет
                risk_amount = user_balance * (risk_pct / Decimal("100"))
                stop_distance = abs(entry_price - stop_loss_price) / entry_price

                if stop_distance == 0:
                    position_size = Decimal("0.0")
                else:
                    position_size = risk_amount / (stop_distance * entry_price)

                return {
                    "position_size": position_size,
                    "margin_used": position_size * entry_price,
                    "risk_amount": risk_amount,
                }

            # Используем улучшенный риск-менеджер
            position_info_raw = self.risk_manager.calculate_adaptive_position_size(
                symbol, float(entry_price), float(stop_loss_price), volatility=0.02
            )

            # Конвертируем результаты в Decimal
            return {
                k: Decimal(str(v)) if isinstance(v, (float, int)) else v
                for k, v in position_info_raw.items()
            }

        except Exception as e:
            logger.error("Error calculating adaptive position size for %s: %s", symbol, e)
            # Возвращаем базовый расчет при ошибке
            risk_amount = user_balance * (risk_pct / Decimal("100"))
            stop_dist = abs(entry_price - stop_loss_price) / entry_price
            pos_size = risk_amount / (stop_dist * entry_price) if stop_dist != 0 else Decimal("0")

            return {
                "position_size": pos_size,
                "margin_used": pos_size * entry_price,
                "risk_amount": risk_amount,
            }

    async def log_signal_generation(
        self,
        symbol: str,
        side: str,
        price: Decimal,
        filters_passed: List[str],
        execution_time: float,
    ):
        """Логирует генерацию сигнала через улучшенную систему"""
        try:
            self.integration_stats["signals_generated"] += 1

            # Логируем метрики
            if self.monitoring_system:
                self.monitoring_system.add_metric(
                    "signals_generated", 1.0, "count", {"symbol": symbol, "side": side}
                )

                self.monitoring_system.add_metric(
                    "signal_generation_time", execution_time, "seconds", {"symbol": symbol}
                )

            # Логируем через улучшенное логирование
            if self.enhanced_logging:
                self.enhanced_logging["add_metric"](f"signal_{symbol}_{side}", 1.0, "count")

            logger.info(
                "📊 Signal logged: %s %s at %.6f, filters: %d, time: %.3fs",
                symbol,
                side,
                float(price),
                len(filters_passed),
                execution_time,
            )

        except Exception as e:
            logger.error("Error logging signal generation for %s: %s", symbol, e)

    async def monitor_system_performance(self):
        """Мониторит производительность системы генерации сигналов"""
        try:
            if not self.monitoring_system:
                return

            # Добавляем метрики производительности
            self.monitoring_system.add_metric(
                "signals_generated_total", self.integration_stats["signals_generated"], "count"
            )

            self.monitoring_system.add_metric(
                "signals_with_risk_check_total",
                self.integration_stats["signals_with_risk_check"],
                "count",
            )

            self.monitoring_system.add_metric(
                "signals_blocked_by_risk_total",
                self.integration_stats["signals_blocked_by_risk"],
                "count",
            )

            self.monitoring_system.add_metric(
                "data_quality_issues_total", self.integration_stats["data_quality_issues"], "count"
            )

            # Вычисляем процент заблокированных сигналов
            if self.integration_stats["signals_with_risk_check"] > 0:
                blocked_percentage = (
                    self.integration_stats["signals_blocked_by_risk"]
                    / self.integration_stats["signals_with_risk_check"]
                ) * 100

                self.monitoring_system.add_metric(
                    "signals_blocked_percentage", blocked_percentage, "%"
                )

                # Алерт при высоком проценте блокировки
                if blocked_percentage > 50:
                    self.monitoring_system.add_alert(
                        AlertType.PERFORMANCE_DEGRADATION,
                        AlertSeverity.HIGH,
                        "High signal blocking rate",
                        f"{blocked_percentage:.1f}% of signals are blocked by risk limits",
                        "signal_live_integration",
                    )

        except Exception as e:
            logger.error("Error monitoring system performance: %s", e)

    async def get_integration_report(self) -> Dict[str, Any]:
        """Возвращает отчет об интеграции"""
        return {
            "timestamp": get_utc_now().isoformat(),
            "is_initialized": self.is_initialized,
            "available_systems": {
                "data_sources_manager": self.data_sources_manager is not None,
                "data_quality_monitor": self.data_quality_monitor is not None,
                "risk_manager": self.risk_manager is not None,
                "monitoring_system": self.monitoring_system is not None,
                "enhanced_logging": self.enhanced_logging is not None,
            },
            "integration_stats": self.integration_stats.copy(),
            "performance_metrics": {
                "signals_per_minute": self.integration_stats["signals_generated"]
                / max(1, (time.time() - self._start_time()) / 60),
                "risk_check_success_rate": (
                    self.integration_stats["signals_with_risk_check"]
                    - self.integration_stats["signals_blocked_by_risk"]
                )
                / max(1, self.integration_stats["signals_with_risk_check"])
                * 100,
            },
        }

    def _start_time(self):
        """Возвращает время запуска интеграции"""
        return getattr(self, "_start_timestamp", time.time())


# Глобальный экземпляр интеграции
signal_live_integration = SignalLiveIntegration()


# Удобные функции для использования в signal_live.py
async def get_enhanced_price_data(
    symbol: str, interval: str = "1h", limit: int = 100
) -> Optional[pd.DataFrame]:
    """Получает данные о ценах через улучшенную систему"""
    return await signal_live_integration.get_enhanced_price_data(symbol, interval, limit)


async def check_risk_limits(
    symbol: str, side: str, quantity: Decimal, entry_price: Decimal, user_balance: Decimal
) -> Tuple[bool, str]:
    """Проверяет лимиты риска"""
    return await signal_live_integration.check_risk_limits(
        symbol, side, quantity, entry_price, user_balance
    )


async def calculate_adaptive_position_size(
    symbol: str,
    entry_price: Decimal,
    stop_loss_price: Decimal,
    user_balance: Decimal,
    risk_pct: Decimal = Decimal("2.0"),
) -> Dict[str, Decimal]:
    """Вычисляет адаптивный размер позиции"""
    return await signal_live_integration.calculate_adaptive_position_size(
        symbol, entry_price, stop_loss_price, user_balance, risk_pct
    )


async def log_signal_generation(
    symbol: str, side: str, price: Decimal, filters_passed: List[str], execution_time: float
):
    """Логирует генерацию сигнала"""
    await signal_live_integration.log_signal_generation(
        symbol, side, price, filters_passed, execution_time
    )


async def initialize_signal_live_integration():
    """Инициализирует интеграцию"""
    await signal_live_integration.initialize()
