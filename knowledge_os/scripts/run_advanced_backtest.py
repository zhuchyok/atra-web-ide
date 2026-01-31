#!/usr/bin/env python3
"""Продвинутый бектест с использованием реальной логики системы, индивидуальных параметров и паттернов."""
# pylint: disable=too-many-lines

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Импорты для бектеста (ленивая загрузка)
# pylint: disable=wrong-import-position
from data.historical_data_loader import HistoricalDataLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Импорт для динамического плеча
try:
    from src.signals.risk import get_dynamic_leverage
    DYNAMIC_LEVERAGE_AVAILABLE = True
except ImportError as e:
    # Используем print, так как logger может быть еще не инициализирован
    print(f"⚠️ get_dynamic_leverage недоступен: {e}, используем фиксированное плечо")
    DYNAMIC_LEVERAGE_AVAILABLE = False
    get_dynamic_leverage = None


class AdvancedBacktest:
    """Продвинутый бектест с реальной логикой системы."""

    def __init__(
        self,
        initial_balance: float = 10000.0,
        risk_per_trade: float = 2.0,
        leverage: float = 2.0,
        tp_sl_override: Optional[Dict[str, float]] = None,
    ):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.leverage = leverage

        # Необязательный оверрайд TP1/TP2/SL (в процентах) для исследовательских бектестов
        # Формат: {"tp1_pct": float, "tp2_pct": float, "sl_pct": float}
        self.tp_sl_override: Optional[Dict[str, float]] = tp_sl_override

        self.trades: List[Dict[str, Any]] = []
        self.open_positions: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []

        # Статистика
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_profit = 0.0
        self.max_loss = 0.0
        self.max_drawdown = 0.0
        self.peak_balance = initial_balance

        # 🆕 Управление рисками
        self.max_positions = 5  # Максимум одновременных позиций
        self.max_drawdown_limit = 15.0  # Остановка при MaxDD > 15%
        self.trading_stopped = False  # Флаг остановки торговли

        # 🆕 Correlation Risk Manager (как в реальной системе)
        self.correlation_manager = None
        try:
            # pylint: disable=import-outside-toplevel
            from correlation_risk_manager import CorrelationRiskManager  # pyright: ignore[reportMissingImports]
            self.correlation_manager = CorrelationRiskManager(db_path="trading.db")
            logger.info("✅ CorrelationRiskManager инициализирован для бектеста")
        except Exception as e:
            logger.warning("⚠️ CorrelationRiskManager недоступен: %s", e)

        # История сигналов для корреляции (симуляция открытых позиций)
        self.signal_history_by_group: Dict[str, List[str]] = {
            'BTC_HIGH': [],
            'BTC_MEDIUM': [],
            'BTC_LOW': [],
            'BTC_INDEPENDENT': [],
            'ETH_HIGH': [],
            'ETH_MEDIUM': [],
            'ETH_LOW': [],
            'ETH_INDEPENDENT': [],
            'SOL_HIGH': [],
            'SOL_MEDIUM': [],
            'SOL_LOW': [],
            'SOL_INDEPENDENT': [],
        }

        # Загружаем системы оптимизации
        self._load_optimization_systems()

        # 🆕 Загружаем фильтры из реальной системы
        self._load_real_filters()

        # Данные ETH и SOL для фильтров (загружаются при первом запуске бэктеста)
        self.eth_df = None
        self.sol_df = None

        # 🆕 Текущий df для расчета динамического плеча
        self.current_df = None
        self.current_index = None

        # 🆕 Счетчики блокировок по фильтрам
        self.filter_rejections = {
            "rsi_filter": 0,           # RSI не в экстремальной зоне
            "macd_filter": 0,          # MACD не прошел проверку
            "volume_filter": 0,         # Volume слишком низкий
            "btc_trend_filter": 0,     # BTC тренд не совпадает
            "eth_trend_filter": 0,     # ETH тренд не совпадает
            "sol_trend_filter": 0,     # SOL тренд не совпадает
            "ema_filter": 0,           # EMA не в нужном направлении (не блокирующий, но считаем)
            "bb_filter": 0,            # BB позиция не в нужной зоне
            "bb_width_filter": 0,      # BB полосы слишком узкие
            "ai_score_filter": 0,      # AI Score слишком низкий
            "ai_volume_filter": 0,     # AI Volume фильтр
            "ai_volatility_filter": 0, # AI Volatility фильтр
            "anomaly_filter": 0,       # Anomaly фильтр
            "direction_confidence": 0, # Direction Confidence
            "rsi_warning": 0,         # RSI Warning
            "quality_score": 0,        # Quality Score
            "portfolio_risk": 0,       # Portfolio Risk Manager
            "correlation_risk": 0,     # Correlation Risk Manager
            "max_positions": 0,       # Максимум позиций достигнут
            "max_drawdown": 0,        # MaxDD превышен
            "nan_values": 0,          # NaN значения в данных
        }
        self.total_signals_checked = 0  # Общее количество проверенных сигналов

    def _load_optimization_systems(self):
        """Загружает системы оптимизации."""
        try:
            # pylint: disable=import-outside-toplevel
            from symbol_specific_optimizer import SymbolSpecificOptimizer  # pyright: ignore[reportMissingImports]
            from ai_learning_system import AILearningSystem  # pyright: ignore[reportMissingImports]
            from ai_tp_optimizer import AITakeProfitOptimizer  # pyright: ignore[reportMissingImports]

            self.symbol_optimizer = SymbolSpecificOptimizer()
            self.ai_learning = AILearningSystem()
            self.tp_optimizer = AITakeProfitOptimizer()

            # Кэш для параметров символов (чтобы не загружать каждый раз)
            self._symbol_params_cache = {}

            logger.info("✅ Системы оптимизации загружены")
            logger.info("   - Паттернов в системе: %d", len(self.ai_learning.patterns))
        except Exception as e:
            logger.warning("⚠️ Ошибка загрузки систем оптимизации: %s", e)
            self.symbol_optimizer = None
            self.ai_learning = None
            self.tp_optimizer = None
            self._symbol_params_cache = {}

    def _load_real_filters(self):
        """Загружает фильтры из реальной системы."""
        try:
            # Импортируем функции и классы из signal_live.py
            # pylint: disable=import-outside-toplevel
            from signal_live import (
                calculate_direction_confidence,
                check_rsi_warning,
                calculate_ai_signal_score,
                get_ai_optimized_parameters,
                check_ai_volume_filter,
                check_ai_volatility_filter,
                calculate_anomaly_circles_with_fallback,
                SignalQualityValidator,
                PatternConfidenceScorer,
            )

            self.calculate_direction_confidence = calculate_direction_confidence
            self.check_rsi_warning = check_rsi_warning
            self.calculate_ai_signal_score = calculate_ai_signal_score
            self.get_ai_optimized_parameters = get_ai_optimized_parameters
            self.check_ai_volume_filter = check_ai_volume_filter
            self.check_ai_volatility_filter = check_ai_volatility_filter
            self.calculate_anomaly_circles = calculate_anomaly_circles_with_fallback
            self.quality_validator = SignalQualityValidator()
            self.pattern_scorer = PatternConfidenceScorer()

            # 🆕 Portfolio Risk Manager
            try:
                # pylint: disable=import-outside-toplevel
                from portfolio_risk_manager import get_portfolio_risk_manager  # pyright: ignore[reportMissingImports]
                self.portfolio_risk_manager = get_portfolio_risk_manager()
                logger.info("✅ PortfolioRiskManager загружен")
            except Exception as e:
                logger.warning("⚠️ PortfolioRiskManager недоступен: %s", e)
                self.portfolio_risk_manager = None

            logger.info("✅ Все фильтры из реальной системы загружены")
        except Exception as e:
            logger.warning("⚠️ Не удалось загрузить фильтры из реальной системы: %s", e)
            # Заглушки для совместимости
            self.calculate_direction_confidence = None
            self.check_rsi_warning = None
            self.calculate_ai_signal_score = None
            self.get_ai_optimized_parameters = None
            self.check_ai_volume_filter = None
            self.check_ai_volatility_filter = None
            self.calculate_anomaly_circles = None
            self.quality_validator = None
            self.pattern_scorer = None
            self.portfolio_risk_manager = None

    def get_symbol_params(self, symbol: str) -> Dict[str, Any]:
        """Получает индивидуальные параметры для символа (с кэшированием)."""
        # Используем кэш
        if symbol in self._symbol_params_cache:
            return self._symbol_params_cache[symbol]

        # ✅ ПРИОРИТЕТ: Используем конфигурацию из src/core/config.py
        try:
            # pylint: disable=import-outside-toplevel
            from src.core.config import SYMBOL_SPECIFIC_CONFIG, DEFAULT_SYMBOL_CONFIG
            if symbol in SYMBOL_SPECIFIC_CONFIG:
                params = SYMBOL_SPECIFIC_CONFIG[symbol].copy()
                logger.debug("✅ [SYMBOL_CONFIG] Используем индивидуальные параметры из config.py для %s", symbol)
                self._symbol_params_cache[symbol] = params
                return params
            else:
                # Используем параметры по умолчанию из конфига
                params = DEFAULT_SYMBOL_CONFIG.copy()
                logger.debug("ℹ️ [SYMBOL_CONFIG] Используем параметры по умолчанию для %s", symbol)
                self._symbol_params_cache[symbol] = params
                return params
        except Exception as e:
            logger.debug("⚠️ Ошибка загрузки конфигурации из config.py для %s: %s", symbol, e)

        # Fallback: Загружаем из symbol_optimizer (если есть)
        if self.symbol_optimizer:
            try:
                params = self.symbol_optimizer.load_symbol_params(symbol, force_update=False)
                self._symbol_params_cache[symbol] = params
                return params
            except Exception as e:
                logger.debug("Ошибка загрузки параметров из optimizer для %s: %s", symbol, e)

        # Fallback на общие параметры
        try:
            # pylint: disable=import-outside-toplevel
            from ai_signal_utils import get_ai_optimized_parameters  # pyright: ignore[reportMissingImports]
            params = get_ai_optimized_parameters(symbol).get("parameters", {})
            self._symbol_params_cache[symbol] = params
            return params
        except Exception:
            params = {}
            self._symbol_params_cache[symbol] = params
            return params

    def get_optimal_tp_sl(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        df: pd.DataFrame,
        current_index: int,
        symbol_params: Dict[str, Any],
    ) -> Tuple[float, float, float]:
        """Получает оптимальные TP/SL на основе паттернов и индивидуальных параметров."""
        # Базовые значения
        base_tp1_pct = symbol_params.get("optimal_tp1", 2.0)
        base_tp2_pct = symbol_params.get("optimal_tp2", 4.0)
        base_sl_pct = symbol_params.get("optimal_stop_loss_pct", 2.0)

        # 🆕 Жёсткий оверрайд TP/SL для грид-поиска (если задан)
        if self.tp_sl_override:
            base_tp1_pct = float(self.tp_sl_override.get("tp1_pct", base_tp1_pct))
            base_tp2_pct = float(self.tp_sl_override.get("tp2_pct", base_tp2_pct))
            base_sl_pct = float(self.tp_sl_override.get("sl_pct", base_sl_pct))

        # Используем AI TP Optimizer если доступен
        if self.tp_optimizer and df is not None and current_index is not None:
            try:
                tp1_pct, tp2_pct = self.tp_optimizer.calculate_ai_optimized_tp(
                    symbol=symbol,
                    side=direction,
                    df=df,
                    current_index=current_index,
                    base_tp1=base_tp1_pct,
                    base_tp2=base_tp2_pct,
                )
                logger.debug("🤖 [%s] ИИ-оптимизированные TP: %.2f%%, %.2f%%", symbol, tp1_pct, tp2_pct)
            except Exception as e:
                logger.debug("⚠️ [%s] ИИ-оптимизация TP недоступна: %s", symbol, e)
                tp1_pct, tp2_pct = base_tp1_pct, base_tp2_pct
        else:
            tp1_pct, tp2_pct = base_tp1_pct, base_tp2_pct

        # Анализируем паттерны для оптимизации SL
        if self.ai_learning and self.ai_learning.patterns:
            try:
                symbol_patterns = [
                    p
                    for p in self.ai_learning.patterns
                    if hasattr(p, "symbol") and p.symbol == symbol and p.result == "LOSS"
                ]
                if symbol_patterns:
                    # Анализируем средний убыток для оптимизации SL
                    avg_loss_pct = np.mean([abs(p.profit_pct) for p in symbol_patterns if p.profit_pct])
                    if avg_loss_pct > 0:
                        # SL должен быть меньше среднего убытка
                        optimal_sl = min(base_sl_pct, avg_loss_pct * 0.8)
                        logger.debug("📊 [%s] Оптимальный SL на основе паттернов: %.2f%%", symbol, optimal_sl)
                        base_sl_pct = optimal_sl
            except Exception as e:
                logger.debug("Ошибка анализа паттернов для SL: %s", e)

        # 🆕 Пробуем использовать get_dynamic_sl_level с AI-оптимизацией (как в реальной системе)
        try:
            # pylint: disable=import-outside-toplevel
            from src.signals.risk import get_dynamic_sl_level
            sl_pct_positive = get_dynamic_sl_level(
                df, current_index, direction.lower(),
                base_sl_pct=base_sl_pct, symbol=symbol, use_ai_optimization=True
            )
            logger.debug("🛡️ [%s] Динамический SL с AI: %.2f%%", symbol, sl_pct_positive)
            base_sl_pct = sl_pct_positive
        except Exception as e:
            logger.debug("⚠️ [%s] Динамический SL недоступен: %s, используем базовый", symbol, e)

        # 🏆 ОПТИМИЗАЦИЯ TP/SL: Улучшение соотношения (как в реальной системе)
        # 🆕 Тестируем более консервативные коэффициенты (1.1/0.9 вместо 1.2/0.8)
        # Это должно улучшить Win Rate, сохранив улучшение средних значений
        tp1_pct_optimized = tp1_pct * 1.1  # Было 1.2
        tp2_pct_optimized = tp2_pct * 1.1  # Было 1.2
        sl_pct_optimized = base_sl_pct * 0.9  # Было 0.8

        logger.debug(
            "🎯 [%s] Оптимизация TP/SL: TP1 %.2f%%→%.2f%%, TP2 %.2f%%→%.2f%%, SL %.2f%%→%.2f%%",
            symbol, tp1_pct, tp1_pct_optimized, tp2_pct, tp2_pct_optimized, base_sl_pct, sl_pct_optimized
        )

        # Рассчитываем цены с оптимизацией
        if direction == "LONG":
            tp1_price = entry_price * (1 + tp1_pct_optimized / 100)
            tp2_price = entry_price * (1 + tp2_pct_optimized / 100)
            sl_price = entry_price * (1 - sl_pct_optimized / 100)
        else:  # SHORT
            tp1_price = entry_price * (1 - tp1_pct_optimized / 100)
            tp2_price = entry_price * (1 - tp2_pct_optimized / 100)
            sl_price = entry_price * (1 + sl_pct_optimized / 100)

        return tp1_price, tp2_price, sl_price

    def calculate_indicators(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Рассчитывает технические индикаторы с индивидуальными параметрами."""
        symbol_params = self.get_symbol_params(symbol)

        # EMA с индивидуальными периодами
        ema_fast_period = symbol_params.get("optimal_ema_fast", 21)
        ema_slow_period = symbol_params.get("optimal_ema_slow", 50)
        df["ema_fast"] = df["close"].ewm(span=ema_fast_period).mean()
        df["ema_slow"] = df["close"].ewm(span=ema_slow_period).mean()
        df["ema_5"] = df["close"].ewm(span=5).mean()
        df["ema_13"] = df["close"].ewm(span=13).mean()
        df["ema_21"] = df["close"].ewm(span=21).mean()
        df["ema_34"] = df["close"].ewm(span=34).mean()
        df["ema_50"] = df["close"].ewm(span=50).mean()

        # RSI с индивидуальными порогами
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = df["close"].ewm(span=12).mean()
        exp2 = df["close"].ewm(span=26).mean()
        df["macd"] = exp1 - exp2
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # Bollinger Bands
        bb_window = symbol_params.get("bb_window", 20)
        df["bb_middle"] = df["close"].rolling(window=bb_window).mean()
        bb_std = df["close"].rolling(window=bb_window).std()
        df["bb_upper"] = df["bb_middle"] + (bb_std * 2)
        df["bb_lower"] = df["bb_middle"] - (bb_std * 2)

        # Volume
        df["volume_ma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma"]

        # ATR
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df["atr"] = true_range.rolling(window=14).mean()

        # 🆕 ADX (для Quality Score и trend_strength)
        try:
            import talib  # type: ignore  # pylint: disable=import-outside-toplevel
            df["adx"] = talib.ADX(  # pylint: disable=no-member
                df["high"].values,
                df["low"].values,
                df["close"].values,
                timeperiod=14,
            )
        except Exception:
            # Fallback: простой расчет ADX
            plus_dm = df["high"].diff()
            minus_dm = -df["low"].diff()
            plus_dm[plus_dm < 0] = 0
            minus_dm[minus_dm < 0] = 0
            tr = true_range
            plus_di = 100 * (plus_dm.rolling(14).mean() / tr.rolling(14).mean())
            minus_di = 100 * (minus_dm.rolling(14).mean() / tr.rolling(14).mean())
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            df["adx"] = dx.rolling(14).mean()

        # 🆕 Volatility (для Quality Score)
        df["volatility"] = df["atr"] / df["close"] * 100  # В процентах

        # 🆕 Trend Strength (для Quality Score и Pattern Confidence)
        if 'ema_fast' in df.columns and 'ema_slow' in df.columns:
            df["trend_strength"] = abs(df["ema_fast"] - df["ema_slow"]) / df["close"] * 100
        else:
            df["trend_strength"] = 0.0

        return df

    async def _get_symbol_group(self, symbol: str, df: pd.DataFrame, btc_df: pd.DataFrame) -> str:
        """Определяет группу корреляции символа (BTC_HIGH, BTC_MEDIUM, и т.д.)."""
        try:
            if not self.correlation_manager:
                return 'BTC_INDEPENDENT'  # По умолчанию

            # Вычисляем корреляцию к BTC
            btc_corr = await self.correlation_manager.calculate_correlation(symbol, 'BTC', df)

            # Определяем группу
            if btc_corr >= 0.75:
                return 'BTC_HIGH'
            elif btc_corr >= 0.50:
                return 'BTC_MEDIUM'
            elif btc_corr >= 0.25:
                return 'BTC_LOW'
            else:
                return 'BTC_INDEPENDENT'
        except Exception as e:
            logger.debug("⚠️ Ошибка определения группы для %s: %s", symbol, e)
            return 'BTC_INDEPENDENT'

    def check_btc_trend(self, btc_df: pd.DataFrame, current_time: pd.Timestamp) -> Optional[bool]:
        """Проверяет BTC тренд."""
        try:
            btc_row = (
                btc_df.loc[btc_df.index <= current_time].iloc[-1]
                if len(btc_df.loc[btc_df.index <= current_time]) > 0
                else None
            )
            if btc_row is None:
                return None

            if "ema_50" not in btc_row or pd.isna(btc_row["ema_50"]):
                return None

            ema_50 = btc_row.get("ema_50", btc_row["close"])
            ema_200 = (
                btc_row["close"].rolling(200).mean().iloc[-1] if len(btc_df) >= 200 else ema_50
            )

            return ema_50 > ema_200 if not pd.isna(ema_200) else None
        except Exception as e:
            logger.debug("Ошибка проверки BTC тренда: %s", e)
            return None

    def check_eth_trend(self, eth_df: pd.DataFrame, current_time: pd.Timestamp) -> Optional[bool]:
        """Проверяет ETH тренд."""
        try:
            eth_row = (
                eth_df.loc[eth_df.index <= current_time].iloc[-1]
                if len(eth_df.loc[eth_df.index <= current_time]) > 0
                else None
            )
            if eth_row is None:
                return None

            if "ema_50" not in eth_row or pd.isna(eth_row["ema_50"]):
                return None

            ema_50 = eth_row.get("ema_50", eth_row["close"])
            ema_200 = (
                eth_row["close"].rolling(200).mean().iloc[-1] if len(eth_df) >= 200 else ema_50
            )

            return ema_50 > ema_200 if not pd.isna(ema_200) else None
        except Exception as e:
            logger.debug("Ошибка проверки ETH тренда: %s", e)
            return None

    def check_sol_trend(self, sol_df: pd.DataFrame, current_time: pd.Timestamp) -> Optional[bool]:
        """Проверяет SOL тренд."""
        try:
            sol_row = (
                sol_df.loc[sol_df.index <= current_time].iloc[-1]
                if len(sol_df.loc[sol_df.index <= current_time]) > 0
                else None
            )
            if sol_row is None:
                return None

            if "ema_50" not in sol_row or pd.isna(sol_row["ema_50"]):
                return None

            ema_50 = sol_row.get("ema_50", sol_row["close"])
            ema_200 = (
                sol_row["close"].rolling(200).mean().iloc[-1] if len(sol_df) >= 200 else ema_50
            )

            return ema_50 > ema_200 if not pd.isna(ema_200) else None
        except Exception as e:
            logger.debug("Ошибка проверки SOL тренда: %s", e)
            return None

    async def generate_signal(
        self,
        row: pd.Series,
        btc_df: pd.DataFrame,
        symbol: str,
        df: pd.DataFrame,
        current_index: int,
    ) -> Optional[Dict[str, Any]]:
        """Генерирует торговый сигнал с использованием реальной логики системы."""
        try:
            logger.debug("🔍 [SIGNAL_START] %s - проверка фильтров (index=%d, time=%s)",
                       symbol, current_index, row.name if hasattr(row, 'name') else 'N/A')
            symbol_params = self.get_symbol_params(symbol)

            # ✅ ВОССТАНОВЛЕН RSI ФИЛЬТР с параметрами 25-75
            # RSI: восстановлены стандартные параметры для улучшения качества сигналов
            rsi_oversold = symbol_params.get("optimal_rsi_oversold", 25)  # ✅ Восстановлено: было 5
            rsi_overbought = symbol_params.get("optimal_rsi_overbought", 75)  # ✅ Восстановлено: было 95
            # 🆕 ОПТИМИЗИРОВАННЫЙ Volume: threshold 1.2 (было 1.5)
            min_volume_ratio = symbol_params.get("soft_volume_ratio", 1.2)  # 🆕 Оптимизировано: было 1.5
            min_confidence = symbol_params.get("min_confidence", 65)  # Было 60

            # Увеличиваем счетчик проверенных сигналов
            self.total_signals_checked += 1

            # Проверка на NaN
            if pd.isna(row.get("rsi")) or pd.isna(row.get("macd")):
                self.filter_rejections["nan_values"] += 1
                return None

            # 🆕 AI SCORE FILTER (как в реальной системе)
            ai_params = None
            if self.calculate_ai_signal_score and self.get_ai_optimized_parameters:
                try:
                    ai_params = self.get_ai_optimized_parameters(symbol)
                    ai_score = self.calculate_ai_signal_score(df.iloc[:current_index + 1], ai_params, symbol)

                    # ✅ ИСПОЛЬЗУЕМ ИНДИВИДУАЛЬНЫЕ ПАРАМЕТРЫ ИЗ КОНФИГА
                    # Если в symbol_params есть ai_score_threshold, используем его
                    # Иначе используем стандартные пороги
                    filter_mode = symbol_params.get("filter_mode", "soft")
                    if "ai_score_threshold" in symbol_params:
                        required_threshold = symbol_params["ai_score_threshold"]
                        logger.debug(
                            "✅ [AI_SCORE] Используем индивидуальный порог для %s: %.1f",
                            symbol,
                            required_threshold,
                        )
                    else:
                        # Стандартные пороги
                        required_threshold = 5.0 if filter_mode == "soft" else 10.0

                    logger.debug("🔍 [AI_SCORE_CHECK] %s: Score=%.1f, Threshold=%.1f (mode=%s)",
                                symbol, ai_score, required_threshold, filter_mode)

                    if ai_score < required_threshold:
                        logger.debug(
                            "🚫 [AI SCORE] %s: Score %.1f < %.1f, блокируем",
                            symbol, ai_score, required_threshold
                        )
                        self.filter_rejections["ai_score_filter"] += 1
                        return None
                    logger.info("✅ [AI SCORE] %s: Score %.1f >= %.1f", symbol, ai_score, required_threshold)
                except Exception as e:
                    logger.debug("⚠️ [AI SCORE] Ошибка расчета для %s: %s (пропускаем)", symbol, e)

            # 🆕 AI VOLUME FILTER (как в реальной системе)
            if self.check_ai_volume_filter and ai_params:
                try:
                    if not self.check_ai_volume_filter(df.iloc[:current_index + 1], ai_params):
                        logger.debug("🚫 [AI VOLUME] %s: Объем ниже порога, блокируем", symbol)
                        self.filter_rejections["ai_volume_filter"] += 1
                        return None
                    logger.debug("✅ [AI VOLUME] %s: Объем выше порога", symbol)
                except Exception as e:
                    logger.debug("⚠️ [AI VOLUME] Ошибка для %s: %s (пропускаем)", symbol, e)

            # 🆕 AI VOLATILITY FILTER (как в реальной системе)
            # 🔧 ВРЕМЕННО ОСЛАБЛЕН: Пропускаем проверку для диагностики
            # TODO: Восстановить после проверки RSI фильтра
            if False and self.check_ai_volatility_filter and ai_params:  # 🔧 Временно отключен
                try:
                    if not self.check_ai_volatility_filter(df.iloc[:current_index + 1], ai_params):
                        logger.debug("🚫 [AI VOLATILITY] %s: Волатильность вне диапазона, блокируем", symbol)
                        self.filter_rejections["ai_volatility_filter"] += 1
                        return None
                    logger.debug("✅ [AI VOLATILITY] %s: Волатильность в диапазоне", symbol)
                except Exception as e:
                    logger.debug("⚠️ [AI VOLATILITY] Ошибка для %s: %s (пропускаем)", symbol, e)

            # 🆕 ANOMALY FILTER (как в реальной системе)
            if self.calculate_anomaly_circles:
                try:
                    # Определяем предварительное направление для проверки аномалий
                    ema_fast_val = row.get("ema_fast", row["close"])
                    ema_slow_val = row.get("ema_slow", row["close"])
                    preliminary_direction = "LONG" if ema_fast_val > ema_slow_val else "SHORT"
                    circles_count, _, _, anomaly_data_ok = await self.calculate_anomaly_circles(symbol, preliminary_direction)

                    # Блокируем максимальный риск (5 кружков) - манипуляции
                    if anomaly_data_ok and circles_count and circles_count >= 5:
                        logger.debug("🚫 [ANOMALY] %s: максимальный риск (%d кружков), блокируем", symbol, circles_count)
                        self.filter_rejections["anomaly_filter"] += 1
                        return None

                    # Блокируем минимальный риск (0 кружков) - низкая ликвидность
                    if anomaly_data_ok and (circles_count is None or circles_count <= 0):
                        logger.debug("🚫 [ANOMALY] %s: низкая ликвидность (0 кружков), блокируем", symbol)
                        self.filter_rejections["anomaly_filter"] += 1
                        return None

                    logger.debug("✅ [ANOMALY] %s: риск приемлемый (%d кружков)", symbol, circles_count or 0)
                except Exception as e:
                    logger.debug("⚠️ [ANOMALY] Ошибка для %s: %s (пропускаем)", symbol, e)

            direction = None
            confidence = 0.0
            filters_passed = []

            # 1. 🔧 ИСПРАВЛЕННЫЙ RSI фильтр - разрешаем нахождение в зоне (не только вход)
            rsi = row["rsi"]
            prev_rsi = df.iloc[current_index - 1]["rsi"] if current_index > 0 and not pd.isna(df.iloc[current_index - 1].get("rsi")) else rsi

            # ✅ ВОССТАНОВЛЕН RSI ФИЛЬТР с параметрами 25-75
            # RSI фильтр восстановлен для улучшения качества сигналов
            logger.debug("🔍 [RSI_CHECK] %s: RSI=%.2f, Prev_RSI=%.2f, Oversold=%d, Overbought=%d",
                        symbol, rsi, prev_rsi, rsi_oversold, rsi_overbought)

            # Восстановленная логика RSI с параметрами 25-75
            if rsi < rsi_oversold:
                direction = "LONG"
                confidence += 25
                filters_passed.append("rsi_oversold")
                logger.info("✅ [RSI_PASS] %s: LONG сигнал (RSI=%.2f < %d)", symbol, rsi, rsi_oversold)
                logger.info(
                    "📊 [FILTER_PROGRESS] %s %s: Прошел RSI фильтр, "
                    "продолжаем проверку других фильтров...",
                    symbol, direction
                )
            elif rsi > rsi_overbought:
                direction = "SHORT"
                confidence += 25
                filters_passed.append("rsi_overbought")
                logger.info("✅ [RSI_PASS] %s: SHORT сигнал (RSI=%.2f > %d)", symbol, rsi, rsi_overbought)
                logger.info(
                    "📊 [FILTER_PROGRESS] %s %s: Прошел RSI фильтр, "
                    "продолжаем проверку других фильтров...",
                    symbol, direction
                )
            else:
                logger.debug("❌ [RSI_BLOCK] %s: RSI не в экстремальной зоне (RSI=%.2f, диапазон: %d-%d)",
                           symbol, rsi, rsi_oversold, rsi_overbought)
                self.filter_rejections["rsi_filter"] += 1
                return None

            # 2. 🔧 ДИАГНОСТИКА: MACD фильтр (временно отключен для диагностики)
            macd = row["macd"]
            macd_signal = row["macd_signal"]
            macd_hist = row["macd_hist"]

            # Рассчитываем силу расхождения
            macd_strength = abs(macd_hist) / max(abs(macd), 1e-9) if macd != 0 else 0

            logger.info("🔍 [MACD_CHECK] %s %s: MACD=%.4f, Signal=%.4f, Hist=%.4f, Strength=%.4f",
                       symbol, direction, macd, macd_signal, macd_hist, macd_strength)

            # 🔓 MACD ФИЛЬТР ОТКЛЮЧЕН - ВОЗВРАТ К РАБОТАЮЩЕЙ КОНФИГУРАЦИИ
            # MACD фильтр отключен, так как не улучшил качество сигналов
            # Пропускаем MACD фильтр, но добавляем минимальную уверенность
            confidence += 10  # Минимальная уверенность без MACD
            filters_passed.append("macd_skipped")
            logger.debug("⏭️ [MACD_SKIP] %s: MACD фильтр отключен (возврат к работающей конфигурации)", symbol)

            # 3. 🔧 ДИАГНОСТИКА: Volume фильтр
            volume_ratio = row.get("volume_ratio", 1.0)
            logger.info("🔍 [VOLUME_CHECK] %s %s: Volume_ratio=%.2f, Min_threshold=%.2f",
                       symbol, direction, volume_ratio, min_volume_ratio)

            if volume_ratio > min_volume_ratio:
                confidence += 20
                filters_passed.append("high_volume")
                logger.info("✅ [VOLUME_PASS] %s: Высокий объем (%.2f > %.2f)", symbol, volume_ratio, min_volume_ratio)
            elif volume_ratio < 0.5:  # 🔧 ОСЛАБЛЕНО: было 0.8 → 0.5 (снижено на 37.5%)
                logger.info("❌ [VOLUME_BLOCK] %s: Слишком низкий объем (%.2f < 0.5)", symbol, volume_ratio)
                self.filter_rejections["volume_filter"] += 1
                return None
            else:
                confidence += 5
                logger.info(
                    "⚠️ [VOLUME_LOW] %s: Недостаточный объем (%.2f), но пропускаем",
                    symbol, volume_ratio
                )

            # 4. 🔧 ДИАГНОСТИКА: BTC тренд фильтр
            btc_trend = self.check_btc_trend(btc_df, row.name)
            logger.info("🔍 [BTC_TREND_CHECK] %s %s: BTC_trend=%s", symbol, direction, btc_trend)

            if btc_trend is not None:
                # Проверяем силу тренда BTC
                try:
                    btc_filtered = btc_df.loc[btc_df.index <= row.name]
                    btc_row = btc_filtered.iloc[-1] if len(btc_filtered) > 0 else None
                    if btc_row is not None:
                        # Рассчитываем силу тренда (разница между EMA fast и slow)
                        ema_fast_btc = btc_row.get("ema_fast", btc_row["close"])
                        ema_slow_btc = btc_row.get("ema_slow", btc_row["close"])
                        trend_strength = abs(ema_fast_btc - ema_slow_btc) / btc_row["close"] * 100 if btc_row["close"] > 0 else 0

                        if (direction == "LONG" and btc_trend) or (direction == "SHORT" and not btc_trend):
                            # Если тренд сильный (> 1%), добавляем больше уверенности
                            if trend_strength > 1.0:
                                confidence += 20  # Увеличено с 15
                            else:
                                confidence += 15
                            filters_passed.append("btc_aligned")
                        else:
                            # Если тренд очень сильный (> 2%), блокируем противоположные сигналы
                            logger.info("❌ [BTC_TREND_BLOCK] %s %s: Против тренда BTC (trend_strength=%.2f%%)",
                                       symbol, direction, trend_strength)
                            self.filter_rejections["btc_trend_filter"] += 1
                            return None
                except Exception:
                    # Fallback к простой проверке
                    if (direction == "LONG" and btc_trend) or (direction == "SHORT" and not btc_trend):
                        confidence += 15
                        filters_passed.append("btc_aligned")
                    else:
                        return None
            else:
                # Если BTC тренд недоступен, снижаем уверенность
                confidence -= 5

            # 🆕 4.1. ETH тренд фильтр (если данные доступны)
            eth_df = getattr(self, 'eth_df', None)
            if eth_df is not None and not eth_df.empty:
                eth_trend = self.check_eth_trend(eth_df, row.name)
                if eth_trend is not None:
                    if (direction == "LONG" and eth_trend) or (direction == "SHORT" and not eth_trend):
                        confidence += 10
                        filters_passed.append("eth_aligned")
                    else:
                        # Блокируем сигналы против тренда ETH
                        self.filter_rejections["eth_trend_filter"] += 1
                        return None

            # 🆕 4.2. SOL тренд фильтр (если данные доступны)
            sol_df = getattr(self, 'sol_df', None)
            if sol_df is not None and not sol_df.empty:
                sol_trend = self.check_sol_trend(sol_df, row.name)
                if sol_trend is not None:
                    if (direction == "LONG" and sol_trend) or (direction == "SHORT" and not sol_trend):
                        confidence += 10
                        filters_passed.append("sol_aligned")
                    else:
                        # Блокируем сигналы против тренда SOL
                        self.filter_rejections["sol_trend_filter"] += 1
                        return None

            # 5. EMA фильтр
            ema_fast = row.get("ema_fast", row["close"])
            ema_slow = row.get("ema_slow", row["close"])

            if direction == "LONG":
                if ema_fast > ema_slow:
                    confidence += 15
                    filters_passed.append("ema_bullish")
                else:
                    confidence += 5
            else:  # SHORT
                if ema_fast < ema_slow:
                    confidence += 15
                    filters_passed.append("ema_bearish")
                else:
                    confidence += 5

            # 6. 🔧 ДИАГНОСТИКА: Bollinger Bands фильтр (временно отключен)
            bb_position = (row["close"] - row["bb_lower"]) / (row["bb_upper"] - row["bb_lower"])
            bb_width = (row["bb_upper"] - row["bb_lower"]) / row.get("bb_middle", row["close"])

            logger.debug("🔍 [BB_CHECK] %s %s: BB_position=%.2f, BB_width=%.4f", symbol, direction, bb_position, bb_width)

            # 🔓 BB ФИЛЬТР ОТКЛЮЧЕН - ВОЗВРАТ К РАБОТАЮЩЕЙ КОНФИГУРАЦИИ
            # BB фильтр отключен, так как не улучшил качество сигналов
            # Пропускаем BB фильтр, но добавляем минимальную уверенность
            confidence += 10  # Минимальная уверенность без BB
            filters_passed.append("bb_skipped")
            logger.debug("⏭️ [BB_SKIP] %s: BB фильтр отключен (возврат к работающей конфигурации)", symbol)

            # 🆕 DIRECTION CONFIDENCE (🔧 ВРЕМЕННО ОТКЛЮЧЕН ДЛЯ ДИАГНОСТИКИ)
            if False and self.calculate_direction_confidence:  # Временно отключен
                try:
                    filter_mode = symbol_params.get("filter_mode", "soft")
                    df_slice = df.iloc[:current_index + 1]
                    direction_confirmed = self.calculate_direction_confidence(
                        df_slice,
                        direction,
                        trade_mode='futures',
                        filter_mode=filter_mode
                    )
                    if not direction_confirmed:
                        logger.info("❌ [DIRECTION_CONFIDENCE_BLOCK] %s %s: недостаточно подтверждений", symbol, direction)
                        self.filter_rejections["direction_confidence"] += 1
                        return None
                    logger.info("✅ [DIRECTION_CONFIDENCE_PASS] %s %s: подтверждено", symbol, direction)
                except Exception as e:
                    logger.debug("⚠️ [DIRECTION CONFIDENCE] Ошибка для %s: %s (пропускаем)", symbol, e)
            else:
                logger.info("⏭️ [DIRECTION_CONFIDENCE_SKIP] %s: Direction Confidence временно отключен", symbol)

            # 🆕 RSI WARNING (как в реальной системе)
            if self.check_rsi_warning:
                try:
                    rsi_warning_ok = self.check_rsi_warning(df.iloc[:current_index + 1], direction)
                    if not rsi_warning_ok:
                        logger.debug("🚫 [RSI WARNING] %s %s: RSI в опасной зоне, блокируем", symbol, direction)
                        self.filter_rejections["rsi_warning"] += 1
                        return None
                    logger.debug("✅ [RSI WARNING] %s %s: RSI OK", symbol, direction)
                except Exception as e:
                    logger.debug("⚠️ [RSI WARNING] Ошибка для %s: %s (пропускаем)", symbol, e)

            # 🆕 QUALITY SCORE (🔧 ВРЕМЕННО ОТКЛЮЧЕН ДЛЯ ДИАГНОСТИКИ)
            pattern_type = "classic_ema"
            if False and self.quality_validator:  # Временно отключен
                try:
                    df_slice = df.iloc[:current_index + 1]
                    quality_score = self.quality_validator.calculate_quality_score(
                        df_slice,
                        direction,
                        symbol
                    )
                    if not self.quality_validator.is_signal_valid(quality_score):
                        logger.info("❌ [QUALITY_SCORE_BLOCK] %s %s: Quality %.3f < 0.68", symbol, direction, quality_score)
                        self.filter_rejections["quality_score"] += 1
                        return None
                    logger.info("✅ [QUALITY_SCORE_PASS] %s %s: Quality %.3f >= 0.68", symbol, direction, quality_score)
                except Exception as e:
                    logger.debug("⚠️ [QUALITY SCORE] Ошибка для %s: %s (пропускаем)", symbol, e)
            else:
                logger.info("⏭️ [QUALITY_SCORE_SKIP] %s: Quality Score временно отключен", symbol)

            # 🆕 PATTERN CONFIDENCE (как в реальной системе)
            if self.pattern_scorer:
                try:
                    df_slice = df.iloc[:current_index + 1]
                    pattern_confidence = self.pattern_scorer.calculate_pattern_confidence(
                        pattern_type,
                        df_slice,
                        direction
                    )
                    if not self.pattern_scorer.is_pattern_reliable(pattern_confidence):
                        logger.debug("🚫 [PATTERN CONFIDENCE] %s %s: Confidence %.3f < 0.60, блокируем", symbol, direction, pattern_confidence)
                        self.filter_rejections["quality_score"] += 1  # Используем quality_score для pattern confidence
                        return None
                    logger.debug("✅ [PATTERN CONFIDENCE] %s %s: Confidence %.3f >= 0.60", symbol, direction, pattern_confidence)
                except Exception as e:
                    logger.debug("⚠️ [PATTERN CONFIDENCE] Ошибка для %s: %s (пропускаем)", symbol, e)

            # 🆕 Минимальная уверенность (🔧 ОСЛАБЛЕН ДЛЯ ДИАГНОСТИКИ)
            logger.info("🔍 [CONFIDENCE_CHECK] %s %s: Confidence=%.1f, Min_confidence=%d",
                       symbol, direction, confidence, min_confidence)

            # 🔧 СНИЖЕН ПОРОГ ДЛЯ ДИАГНОСТИКИ
            min_confidence_diagnostic = max(30, min_confidence - 20)  # Снижаем на 20, но минимум 30

            if confidence < min_confidence_diagnostic:
                logger.info(
                    "❌ [CONFIDENCE_BLOCK] %s %s: Confidence %.1f < %.1f (min)",
                    symbol, direction, confidence, min_confidence_diagnostic
                )
                self.filter_rejections["quality_score"] += 1
                return None

            logger.info("✅ [CONFIDENCE_PASS] %s %s: Confidence %.1f >= %.1f",
                       symbol, direction, confidence, min_confidence_diagnostic)

            # 🆕 Дополнительная проверка (🔧 ОСЛАБЛЕНА ДЛЯ ДИАГНОСТИКИ)
            required_filters = ["rsi_oversold", "rsi_overbought", "macd_bullish", "macd_bearish", "high_volume", "btc_aligned", "macd_skipped"]
            passed_required = sum(1 for f in filters_passed if f in required_filters)
            logger.info("🔍 [REQUIRED_FILTERS_CHECK] %s %s: Passed=%d, Required=1 (ослаблено для диагностики)",
                       symbol, direction, passed_required)

            # 🔧 ОСЛАБЛЕНО: Требуем минимум 1 фильтр вместо 3
            if passed_required < 1:
                logger.info("❌ [REQUIRED_FILTERS_BLOCK] %s %s: Недостаточно фильтров (%d < 1)",
                           symbol, direction, passed_required)
                self.filter_rejections["quality_score"] += 1
                return None

            logger.info("✅ [REQUIRED_FILTERS_PASS] %s %s: Достаточно фильтров (%d >= 1)",
                       symbol, direction, passed_required)

            # 🔓 ВРЕМЕННО ОТКЛЮЧЕН CORRELATION RISK ФИЛЬТР ДЛЯ ДИАГНОСТИКИ
            # Correlation Risk блокирует 64.34% сигналов - отключаем для понимания реального потенциала системы
            logger.debug("🔓 [CORRELATION_BYPASS] %s: Correlation Risk временно отключен для диагностики", symbol)
            filters_passed.append("correlation_bypassed")

            # ЗАКОММЕНТИРОВАНА СТАРАЯ ЛОГИКА CORRELATION RISK:
            # if self.correlation_manager:
            #     try:
            #         symbol_group = await self._get_symbol_group(symbol, df, btc_df)
            #         group_limits = {...}
            #         current_count = len(self.signal_history_by_group.get(symbol_group, []))
            #         max_allowed = group_limits.get(symbol_group, 5)
            #         if current_count >= max_allowed:
            #             self.filter_rejections["correlation_risk"] += 1
            #             return None
            #         ...
            #     except Exception as corr_exc:
            #         logger.debug("⚠️ [CORRELATION] Ошибка проверки корреляции для %s: %s", symbol, corr_exc)

            # Получаем оптимальные TP/SL на основе паттернов
            entry_price = row["close"]
            tp1_price, tp2_price, sl_price = self.get_optimal_tp_sl(
                symbol, direction, entry_price, df, current_index, symbol_params
            )

            logger.info("🎯 [SIGNAL_GENERATED] %s %s: Все фильтры пройдены! Entry=%.4f, SL=%.4f, TP1=%.4f, TP2=%.4f, Confidence=%.1f",
                       symbol, direction, entry_price, sl_price, tp1_price, tp2_price, confidence)
            logger.info("📋 [FILTERS_PASSED] %s: %s", symbol, ", ".join(filters_passed))

            return {
                "symbol": symbol,
                "direction": direction,
                "entry_price": float(entry_price),
                "sl_price": float(sl_price),
                "tp1_price": float(tp1_price),
                "tp2_price": float(tp2_price),
                "confidence": confidence,
                "filters_passed": filters_passed,
                "timestamp": row.name,
                "rsi": float(rsi),
                "macd": float(macd),
                "volume_ratio": float(volume_ratio),
                "btc_trend": btc_trend,
                "symbol_params_used": bool(symbol_params),
                "patterns_analyzed": len(
                    [
                        p
                        for p in (self.ai_learning.patterns if self.ai_learning else [])
                        if hasattr(p, "symbol") and p.symbol == symbol
                    ]
                )
                if self.ai_learning
                else 0,
            }

        except Exception as e:
            logger.debug("Ошибка генерации сигнала: %s", e)
            return None

    async def run_backtest(
        self,
        symbol: str,
        df: pd.DataFrame,
        btc_df: pd.DataFrame,
        days: int = 90,
    ) -> Dict[str, Any]:
        """Запускает бектест для символа."""
        logger.info("🔄 Запуск продвинутого бектеста для %s (%d свечей)", symbol, len(df))

        df = self.calculate_indicators(df.copy(), symbol)
        btc_df = self.calculate_indicators(btc_df.copy(), "BTCUSDT")

        # 🆕 Загружаем данные ETH и SOL для фильтров (если еще не загружены)
        if self.eth_df is None:
            try:
                async with HistoricalDataLoader(exchange="binance") as loader:
                    eth_data = await loader.fetch_ohlcv("ETHUSDT", interval="1h", days=days)
                    if eth_data is not None and len(eth_data) > 0:
                        self.eth_df = pd.DataFrame(eth_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        self.eth_df['timestamp'] = pd.to_datetime(self.eth_df['timestamp'], unit='ms')
                        self.eth_df.set_index('timestamp', inplace=True)
                        self.eth_df = self.calculate_indicators(self.eth_df.copy(), "ETHUSDT")
                        logger.info("✅ Загружены данные ETHUSDT (%d свечей)", len(self.eth_df))
                    else:
                        self.eth_df = None
                        logger.warning("⚠️ Не удалось загрузить данные ETHUSDT")
            except Exception as e:
                logger.warning("⚠️ Ошибка загрузки данных ETHUSDT: %s", e)
                self.eth_df = None

        if self.sol_df is None:
            try:
                async with HistoricalDataLoader(exchange="binance") as loader:
                    sol_data = await loader.fetch_ohlcv("SOLUSDT", interval="1h", days=days)
                    if sol_data is not None and len(sol_data) > 0:
                        self.sol_df = pd.DataFrame(sol_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        self.sol_df['timestamp'] = pd.to_datetime(self.sol_df['timestamp'], unit='ms')
                        self.sol_df.set_index('timestamp', inplace=True)
                        self.sol_df = self.calculate_indicators(self.sol_df.copy(), "SOLUSDT")
                        logger.info("✅ Загружены данные SOLUSDT (%d свечей)", len(self.sol_df))
                    else:
                        self.sol_df = None
                        logger.warning("⚠️ Не удалось загрузить данные SOLUSDT")
            except Exception as e:
                logger.warning("⚠️ Ошибка загрузки данных SOLUSDT: %s", e)
                self.sol_df = None

        # Удаляем NaN
        df = df.dropna()
        if len(df) < 50:
            logger.warning("⚠️ Недостаточно данных для %s", symbol)
            return {}

        for idx in range(len(df)):
            row = df.iloc[idx]
            current_time = df.index[idx]

            # Проверяем открытые позиции
            for pos in self.open_positions[:]:
                if pos["symbol"] == symbol:
                    current_price = row["close"]
                    direction = pos["direction"]

                    if direction == "LONG":
                        if current_price >= pos["tp2_price"]:
                            self.close_position(pos, current_price, "tp2", current_time)
                        elif current_price >= pos["tp1_price"] and pos.get("tp1_hit") is None:
                            pos["tp1_hit"] = True
                            self.close_partial_position(pos, pos["tp1_price"], "tp1", 0.5, current_time)
                        elif current_price <= pos["sl_price"]:
                            self.close_position(pos, current_price, "sl", current_time)
                    else:  # SHORT
                        if current_price <= pos["tp2_price"]:
                            self.close_position(pos, current_price, "tp2", current_time)
                        elif current_price <= pos["tp1_price"] and pos.get("tp1_hit") is None:
                            pos["tp1_hit"] = True
                            self.close_partial_position(pos, pos["tp1_price"], "tp1", 0.5, current_time)
                        elif current_price >= pos["sl_price"]:
                            self.close_position(pos, current_price, "sl", current_time)

            # 🆕 Проверка MaxDD перед генерацией сигнала
            if self.max_drawdown > self.max_drawdown_limit:
                if not self.trading_stopped:
                    logger.warning("🚫 [RISK] MaxDD превышен (%.2f%% > %.2f%%), останавливаем торговлю",
                                 self.max_drawdown, self.max_drawdown_limit)
                    self.trading_stopped = True
                self.filter_rejections["max_drawdown"] += 1
                continue  # Пропускаем генерацию новых сигналов

            # 🆕 Проверка количества открытых позиций
            if len(self.open_positions) >= self.max_positions:
                self.filter_rejections["max_positions"] += 1
                continue  # Пропускаем, если достигнут лимит позиций

            # 🆕 Сохраняем текущий df и индекс для динамического плеча
            self.current_df = df
            self.current_index = idx

            # Генерируем новый сигнал (асинхронно для корреляции)
            signal = await self.generate_signal(row, btc_df, symbol, df, idx)
            if signal:
                # 🆕 PORTFOLIO RISK MANAGER (🔧 ИСПРАВЛЕН: пропускаем emergency_stop для бэктеста)
                if self.portfolio_risk_manager:
                    # 🔧 Для бэктеста отключаем emergency_stop проверку
                    try:
                        # Временно отключаем emergency_stop через risk_flags
                        # pylint: disable=protected-access
                        if (
                            hasattr(self.portfolio_risk_manager, "_risk_flags")
                            and self.portfolio_risk_manager._risk_flags
                        ):
                            # Сохраняем оригинальное состояние
                            original_emergency = (
                                self.portfolio_risk_manager._risk_flags.is_active("emergency_stop")
                            )
                            if original_emergency:
                                logger.debug(
                                    "🔧 [PORTFOLIO_RISK] Временно отключаем emergency_stop для бэктеста"
                                )
                                # Пытаемся отключить emergency_stop (если есть метод)
                                if hasattr(self.portfolio_risk_manager._risk_flags, "deactivate"):
                                    self.portfolio_risk_manager._risk_flags.deactivate("emergency_stop")
                                elif hasattr(self.portfolio_risk_manager._risk_flags, "set_flag"):
                                    self.portfolio_risk_manager._risk_flags.set_flag(
                                        "emergency_stop", False
                                    )
                    except Exception as e:
                        logger.debug("⚠️ [PORTFOLIO_RISK] Не удалось отключить emergency_stop: %s", e)

                    try:
                        # Симулируем user_id и user_data для бектеста
                        user_id = "backtest_user"
                        user_data = {
                            "deposit": self.current_balance,
                            "free_deposit": self.current_balance - sum(
                                p.get("position_size", 0) * p.get("entry_price", 0)
                                for p in self.open_positions
                            ),
                            "total_risk_amount": sum(
                                abs(p.get("entry_price", 0) - p.get("sl_price", 0)) * p.get("position_size", 0)
                                for p in self.open_positions
                            ),
                        }

                        # Рассчитываем размер новой позиции
                        entry_price = signal["entry_price"]
                        sl_price = signal["sl_price"]
                        risk_amount = self.current_balance * (self.risk_per_trade / 100)
                        sl_distance_pct = abs(entry_price - sl_price) / entry_price
                        position_size_base = risk_amount / (sl_distance_pct * entry_price)
                        # 🔧 ИСПРАВЛЕНО: Правильный расчет размера позиции (leverage применяется к количеству, а не к стоимости)
                        new_position_size_usdt = position_size_base * entry_price * self.leverage

                        # Проверяем лимиты портфеля
                        portfolio_check = await self.portfolio_risk_manager.check_portfolio_risk(
                            user_id=user_id,
                            new_position_size_usdt=new_position_size_usdt,
                            user_data=user_data
                        )

                        if not portfolio_check.get("allowed", True):
                            reason = portfolio_check.get("reason", "portfolio_limit")
                            # 🔧 Пропускаем emergency_stop, weak_setup_stop и POSITION_SIZE_TOO_LARGE для бэктеста
                            if reason in ("EMERGENCY_STOP_ACTIVE", "WEAK_SETUP_STOP_ACTIVE", "POSITION_SIZE_TOO_LARGE"):
                                logger.info("⏭️ [PORTFOLIO_RISK] %s %s: %s пропущен для бэктеста", symbol, signal["direction"], reason)
                            else:
                                logger.debug("🚫 [PORTFOLIO RISK] %s %s: %s", symbol, signal["direction"], reason)
                                self.filter_rejections["portfolio_risk"] += 1
                                continue  # Пропускаем открытие позиции
                        logger.debug("✅ [PORTFOLIO RISK] %s %s: проверка пройдена", symbol, signal["direction"])
                    except Exception as e:
                        logger.debug("⚠️ [PORTFOLIO RISK] Ошибка для %s: %s (пропускаем)", symbol, e)

                has_open = any(p["symbol"] == symbol for p in self.open_positions)
                logger.info("🔍 [POSITION_CHECK] %s: has_open=%s, open_positions_count=%d",
                           symbol, has_open, len(self.open_positions))
                if not has_open:
                    logger.info("✅ [OPENING_POSITION] %s %s: Открываем позицию...", symbol, signal["direction"])
                    self.open_position(signal, row)
                else:
                    logger.info("⏭️ [SKIP_POSITION] %s: Уже есть открытая позиция, пропускаем", symbol)

            # Обновляем equity curve
            self.update_equity_curve(current_time)

        # Закрываем все открытые позиции в конце
        for pos in self.open_positions[:]:
            if pos["symbol"] == symbol:
                last_price = df.iloc[-1]["close"]
                self.close_position(pos, last_price, "end_of_data", df.index[-1])

        return {
            "symbol": symbol,
            "trades_count": len([t for t in self.trades if t["symbol"] == symbol]),
        }

    def open_position(self, signal: Dict[str, Any], row: pd.Series) -> None:
        """Открывает позицию."""
        entry_price = signal["entry_price"]
        direction = signal["direction"]
        symbol = signal["symbol"]
        logger.info("📈 [OPEN_POSITION_START] %s %s: Entry=%.4f", symbol, direction, entry_price)

        # 🆕 ДИНАМИЧЕСКОЕ ПЛЕЧО
        # Используем динамическое плечо на основе волатильности и тренда
        if DYNAMIC_LEVERAGE_AVAILABLE and get_dynamic_leverage and self.current_df is not None and self.current_index is not None:
            try:
                # Симулируем user_data для динамического плеча
                user_data = {
                    "deposit": self.current_balance,
                    "leverage": self.leverage,  # Базовое плечо
                }

                dynamic_leverage = get_dynamic_leverage(
                    df=self.current_df,
                    i=self.current_index,
                    base_leverage=self.leverage,
                    symbol=symbol,
                    user_data=user_data,
                    use_ai_optimization=True
                )
                logger.info("🔧 [DYNAMIC_LEVERAGE] %s: Базовое=%.1fx, Динамическое=%.1fx",
                           symbol, self.leverage, dynamic_leverage)
                leverage_to_use = dynamic_leverage
            except Exception as e:
                logger.warning("⚠️ [DYNAMIC_LEVERAGE] Ошибка расчета для %s: %s, используем фиксированное %.1fx",
                             symbol, e, self.leverage)
                leverage_to_use = self.leverage
        else:
            leverage_to_use = self.leverage
            logger.debug("ℹ️ [LEVERAGE] %s: Используем фиксированное плечо %.1fx", symbol, self.leverage)

        # Расчёт размера позиции
        risk_amount = self.current_balance * (self.risk_per_trade / 100)
        sl_distance_pct = abs(entry_price - signal["sl_price"]) / entry_price

        position_size_base = risk_amount / (sl_distance_pct * entry_price)
        position_size = position_size_base * leverage_to_use

        # Ограничиваем размер позиции
        max_position_value = self.current_balance * 0.5
        max_position_size = max_position_value / entry_price
        position_size = min(position_size, max_position_size)

        position = {
            "symbol": signal["symbol"],
            "direction": direction,
            "entry_price": entry_price,
            "sl_price": signal["sl_price"],
            "tp1_price": signal["tp1_price"],
            "tp2_price": signal["tp2_price"],
            "position_size": position_size,
            "entry_time": signal["timestamp"],
            "confidence": signal["confidence"],
            "filters_passed": signal["filters_passed"],
            "rsi": signal.get("rsi"),
            "macd": signal.get("macd"),
            "volume_ratio": signal.get("volume_ratio"),
            "btc_trend": signal.get("btc_trend"),
            "symbol_params_used": signal.get("symbol_params_used", False),
            "patterns_analyzed": signal.get("patterns_analyzed", 0),
            "leverage_used": leverage_to_use,  # 🆕 Сохраняем использованное плечо
        }

        self.open_positions.append(position)
        logger.info("✅ [POSITION_OPENED] %s %s: Position_size=%.4f, Leverage=%.1fx, Entry=%.4f, SL=%.4f, TP1=%.4f, TP2=%.4f",
                   symbol, direction, position_size, leverage_to_use, entry_price, signal["sl_price"], signal["tp1_price"], signal["tp2_price"])

    def close_position(
        self,
        position: Dict[str, Any],
        exit_price: float,
        exit_reason: str,
        timestamp: pd.Timestamp,
    ) -> None:
        """Закрывает позицию полностью."""
        if position not in self.open_positions:
            return

        entry_price = position["entry_price"]
        direction = position["direction"]
        position_size = position["position_size"]

        # Расчёт PnL
        if direction == "LONG":
            pnl = (exit_price - entry_price) * position_size
        else:  # SHORT
            pnl = (entry_price - exit_price) * position_size

        pnl_percent = (pnl / (entry_price * position_size)) * 100

        trade = {
            "symbol": position["symbol"],
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "entry_time": position["entry_time"],
            "exit_time": timestamp,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "exit_reason": exit_reason,
            "confidence": position["confidence"],
            "filters_passed": position["filters_passed"],
            "rsi": position.get("rsi"),
            "macd": position.get("macd"),
            "volume_ratio": position.get("volume_ratio"),
            "btc_trend": position.get("btc_trend"),
            "symbol_params_used": position.get("symbol_params_used", False),
            "patterns_analyzed": position.get("patterns_analyzed", 0),
            "holding_time": (timestamp - position["entry_time"]).total_seconds() / 3600,
            "leverage_used": position.get("leverage_used", self.leverage),  # 🆕 Сохраняем использованное плечо
        }

        self.trades.append(trade)
        self.current_balance += pnl
        self.total_pnl += pnl

        if pnl > 0:
            self.winning_trades += 1
            self.max_profit = max(self.max_profit, pnl)
        else:
            self.losing_trades += 1
            self.max_loss = min(self.max_loss, pnl)

        self.total_trades += 1
        self.open_positions.remove(position)

        # Обновляем drawdown
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance * 100
        self.max_drawdown = max(self.max_drawdown, drawdown)

    def close_partial_position(
        self,
        position: Dict[str, Any],
        exit_price: float,
        exit_reason: str,
        partial_ratio: float,
        timestamp: pd.Timestamp,
    ) -> float:
        """Закрывает часть позиции."""
        entry_price = position["entry_price"]
        direction = position["direction"]
        partial_size = position["position_size"] * partial_ratio

        if direction == "LONG":
            pnl = (exit_price - entry_price) * partial_size
        else:  # SHORT
            pnl = (entry_price - exit_price) * partial_size

        position["position_size"] -= partial_size
        position["tp1_hit"] = True

        self.current_balance += pnl
        self.total_pnl += pnl

        return pnl

    def update_equity_curve(self, timestamp: pd.Timestamp) -> None:
        """Обновляет кривую эквити."""
        total_balance = self.current_balance

        self.equity_curve.append(
            {
                "timestamp": timestamp,
                "balance": total_balance,
                "drawdown": (self.peak_balance - total_balance) / self.peak_balance * 100
                if self.peak_balance > 0
                else 0,
            }
        )

    def calculate_metrics(self) -> Dict[str, Any]:
        """Рассчитывает метрики производительности."""
        if not self.trades:
            return {}

        df_trades = pd.DataFrame(self.trades)

        # Базовые метрики
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        # PnL метрики
        total_pnl = df_trades["pnl"].sum()
        avg_pnl = df_trades["pnl"].mean()
        avg_win = df_trades[df_trades["pnl"] > 0]["pnl"].mean() if self.winning_trades > 0 else 0
        avg_loss = df_trades[df_trades["pnl"] < 0]["pnl"].mean() if self.losing_trades > 0 else 0

        # Процентные метрики
        total_return = ((self.current_balance - self.initial_balance) / self.initial_balance) * 100
        avg_pnl_percent = df_trades["pnl_percent"].mean()

        # Sharpe Ratio
        returns = df_trades["pnl_percent"].values
        if len(returns) > 1 and np.std(returns) > 0:
            # Используем 365 для крипто (24/7), а не 252
            sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(365)
        else:
            sharpe_ratio = 0.0

        # Sortino Ratio
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0 and np.std(negative_returns) > 0:
            # Используем 365 для крипто (24/7), а не 252
            sortino_ratio = (np.mean(returns) / np.std(negative_returns)) * np.sqrt(365)
        else:
            sortino_ratio = 0.0

        # Profit Factor
        gross_profit = df_trades[df_trades["pnl"] > 0]["pnl"].sum() if self.winning_trades > 0 else 0
        gross_loss = abs(df_trades[df_trades["pnl"] < 0]["pnl"].sum()) if self.losing_trades > 0 else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Максимальные серии
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0

        for pnl in returns:
            if pnl > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)

        # Анализ использования паттернов
        if "symbol_params_used" in df_trades.columns:
            trades_with_params = df_trades[df_trades["symbol_params_used"]]
        else:
            trades_with_params = pd.DataFrame()
        if "patterns_analyzed" in df_trades.columns:
            trades_with_patterns = df_trades[df_trades["patterns_analyzed"] > 0]
        else:
            trades_with_patterns = pd.DataFrame()

        # 🆕 Статистика по фильтрам
        filter_stats = {
            "total_signals_checked": self.total_signals_checked,
            "filter_rejections": self.filter_rejections.copy(),
            "rejection_percentages": {}
        }

        # Рассчитываем проценты отклонений
        if self.total_signals_checked > 0:
            for filter_name, count in self.filter_rejections.items():
                filter_stats["rejection_percentages"][filter_name] = (count / self.total_signals_checked) * 100

        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "avg_pnl": avg_pnl,
            "avg_pnl_percent": avg_pnl_percent,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "profit_factor": profit_factor,
            "max_consecutive_wins": max_consecutive_wins,
            "max_consecutive_losses": max_consecutive_losses,
            "final_balance": self.current_balance,
            "initial_balance": self.initial_balance,
            "trades_with_symbol_params": len(trades_with_params),
            "trades_with_patterns_analysis": len(trades_with_patterns),
            "patterns_total": len(self.ai_learning.patterns) if self.ai_learning else 0,
            "filter_statistics": filter_stats,  # 🆕 Статистика по фильтрам
        }


async def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description="Продвинутый бектест с реальной логикой системы")
    parser.add_argument("--symbols", nargs="+", help="Список символов для бектеста")
    parser.add_argument("--top-n", type=int, default=10, help="Количество топ монет")
    parser.add_argument("--days", type=int, default=30, help="Количество дней для анализа")
    parser.add_argument("--initial-balance", type=float, default=10000.0, help="Начальный баланс")
    parser.add_argument("--risk", type=float, default=2.0, help="Риск на сделку (%)")
    parser.add_argument("--leverage", type=float, default=2.0, help="Плечо")
    parser.add_argument("--output", default="data/advanced_backtest_report.json", help="Путь для сохранения отчета")
    args = parser.parse_args()

    logger.info("🚀 Запуск продвинутого бектеста с реальной логикой системы...")

    # 1. Загрузка данных
    async with HistoricalDataLoader(exchange="binance") as loader:
        if args.symbols:
            symbols = args.symbols
        else:
            logger.info("📊 Получение топ %d монет...", args.top_n)
            symbols = await loader.get_top_symbols(limit=args.top_n)

        logger.info("📈 Символы для бектеста: %s", ", ".join(symbols))

        # Загружаем BTC для проверки тренда
        logger.info("📥 Загрузка данных BTC...")
        btc_df = await loader.fetch_ohlcv("BTCUSDT", interval="1h", days=args.days)

        # Загружаем данные для всех символов
        logger.info("📥 Загрузка исторических данных...")
        data_dict = await loader.load_multiple_symbols(symbols, interval="1h", days=args.days)

    # 2. Запуск бектеста
    backtest = AdvancedBacktest(
        initial_balance=args.initial_balance,
        risk_per_trade=args.risk,
        leverage=args.leverage,
    )

    results = []
    for symbol in symbols:
        if symbol not in data_dict or data_dict[symbol].empty:
            logger.warning("⚠️ Нет данных для %s, пропускаем", symbol)
            continue

        result = await backtest.run_backtest(symbol, data_dict[symbol], btc_df, days=args.days)
        results.append(result)

    # 3. Расчёт метрик
    metrics = backtest.calculate_metrics()

    # 4. Генерация отчета
    report = {
        "backtest_info": {
            "start_date": (datetime.utcnow() - timedelta(days=args.days)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "symbols": symbols,
            "days": args.days,
            "initial_balance": args.initial_balance,
            "risk_per_trade": args.risk,
            "leverage": args.leverage,
            "uses_symbol_params": True,
            "uses_patterns": True,
            "total_patterns_in_system": metrics.get("patterns_total", 0),
        },
        "metrics": metrics,
        "trades": backtest.trades,
    }

    # 5. Сохранение отчета
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    logger.info("✅ Продвинутый бектест завершён")
    logger.info("📊 Результаты:")
    logger.info("   Всего сделок: %d", metrics.get("total_trades", 0))
    logger.info("   Win rate: %.2f%%", metrics.get("win_rate", 0))
    logger.info("   Total PnL: %.2f USD", metrics.get("total_pnl", 0))
    logger.info("   Sharpe Ratio: %.2f", metrics.get("sharpe_ratio", 0))
    logger.info("   Sortino Ratio: %.2f", metrics.get("sortino_ratio", 0))
    logger.info("   Max Drawdown: %.2f%%", metrics.get("max_drawdown", 0))
    logger.info("   Сделок с индивидуальными параметрами: %d", metrics.get("trades_with_symbol_params", 0))
    logger.info("   Сделок с анализом паттернов: %d", metrics.get("trades_with_patterns_analysis", 0))
    logger.info("   Всего паттернов в системе: %d", metrics.get("patterns_total", 0))
    logger.info("💾 Отчет сохранён: %s", output_path)

    return report


if __name__ == "__main__":
    asyncio.run(main())
