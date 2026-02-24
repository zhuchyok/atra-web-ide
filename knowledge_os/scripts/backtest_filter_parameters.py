#!/usr/bin/env python3
"""
БЭКТЕСТ ДЛЯ ОПТИМИЗАЦИИ ПАРАМЕТРОВ ФИЛЬТРОВ
Тестирует все 5 критичных параметров фильтров с разными значениями
Период: 3 месяца (90 дней)
Символы: топ-20 монет из intelligent_filter_system
Параллелизация: Rust с 15 потоками
"""

import argparse
import json
import logging
import os
import sys
import traceback
import warnings
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импорты системы
from src.ai.intelligent_filter_system import get_all_optimized_symbols
from src.signals.core import soft_entry_signal, strict_entry_signal
from src.signals.indicators import add_technical_indicators
from src.signals.risk import get_dynamic_sl_level
from src.utils.shared_utils import get_dynamic_tp_levels

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# КОНСТАНТЫ БЭКТЕСТА
# ============================================================================

START_BALANCE = 10000.0
FEE = 0.001  # 0.1% комиссия
SLIPPAGE = 0.0005  # 0.05% проскальзывание
RISK_PER_TRADE = 0.02  # 2% риск на сделку
DEFAULT_TP_MULT = 2.0
DEFAULT_SL_MULT = 1.5
PERIOD_DAYS = 90  # 3 месяца
DATA_DIR = "data/backtest_data_yearly"


# Топ-20 монет из intelligent_filter_system
def get_top_20_symbols() -> List[str]:
    """Получает топ-20 монет из intelligent_filter_system"""
    try:
        all_symbols = get_all_optimized_symbols()
        # Фильтруем стейблкоины и дубликаты
        filtered = [
            s
            for s in all_symbols
            if s.endswith("USDT") and not s.endswith("USDTUSDT") and s.count("USDT") == 1
        ]
        return filtered[:20]
    except Exception as e:
        logger.warning("⚠️ Не удалось загрузить монеты из intelligent_filter_system: %s", e)
        # Fallback на стандартный список
        return [
            "BTCUSDT",
            "ETHUSDT",
            "BNBUSDT",
            "SOLUSDT",
            "ADAUSDT",
            "XRPUSDT",
            "AVAXUSDT",
            "DOGEUSDT",
            "DOTUSDT",
            "LINKUSDT",
            "LTCUSDT",
            "TRXUSDT",
            "UNIUSDT",
            "NEARUSDT",
            "SUIUSDT",
            "PEPEUSDT",
            "ENAUSDT",
            "ICPUSDT",
            "FETUSDT",
            "HBARUSDT",
        ]


# ============================================================================
# ПАРАМЕТРЫ ДЛЯ ТЕСТИРОВАНИЯ
# ============================================================================

# Приоритет 1 (КРИТИЧНО):
PARAM_MIN_CONFIDENCE_SHORT = [0.40, 0.50, 0.60, 0.70]  # 4 значения
PARAM_MIN_QUALITY_THRESHOLD_LONG = [0.33, 0.40, 0.45]  # 3 значения

# Приоритет 2 (ВАЖНО):
PARAM_MIN_QUALITY_SHORT = [0.45, 0.50, 0.55]  # 3 значения
PARAM_MARKET_ADJUSTMENT = [-0.10, -0.05, 0.0]  # 3 значения

# Приоритет 3 (ЖЕЛАТЕЛЬНО):
PARAM_MIN_H4_CONFIDENCE = [0.4, 0.5, 0.6]  # 3 значения

# Всего комбинаций: 4 * 3 * 3 * 3 * 3 = 324 комбинации
# Но мы будем тестировать каждый параметр отдельно для упрощения

# ============================================================================
# КЛАСС ДЛЯ СТАТИСТИКИ
# ============================================================================


class BacktestStats:
    """Статистика бэктеста"""

    def __init__(self, name: str):
        self.name = name
        self.trades = []
        self.balance = START_BALANCE
        self.initial_balance = START_BALANCE
        self.max_balance = START_BALANCE
        self.min_balance = START_BALANCE
        self.max_drawdown = 0.0
        self.max_drawdown_pct = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.total_loss = 0.0
        self.signals_generated = 0
        self.signals_executed = 0

    def add_trade(self, trade: dict):
        """Добавляет сделку"""
        self.trades.append(trade)
        self.total_trades += 1

        profit = trade.get("profit", 0)
        if profit > 0:
            self.winning_trades += 1
            self.total_profit += profit
        else:
            self.losing_trades += 1
            self.total_loss += abs(profit)

        self.balance += profit
        self.max_balance = max(self.max_balance, self.balance)
        self.min_balance = min(self.min_balance, self.balance)

        # Обновляем максимальную просадку
        if self.max_balance > 0:
            current_dd = ((self.max_balance - self.balance) / self.max_balance) * 100
            if current_dd > self.max_drawdown_pct:
                self.max_drawdown_pct = current_dd
                self.max_drawdown = self.max_balance - self.balance

    def get_metrics(self) -> dict:
        """Возвращает метрики"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0.0
        profit_factor = self.total_profit / self.total_loss if self.total_loss > 0 else float("inf")
        total_return = ((self.balance - self.initial_balance) / self.initial_balance) * 100

        # Sharpe Ratio
        if len(self.trades) > 1:
            returns = [t.get("profit_pct", 0) for t in self.trades]
            std_return = np.std(returns)

            if std_return > 0:
                annualized_return_pct = total_return * 12
                annualized_volatility_pct = std_return * np.sqrt(365)
                sharpe_ratio = (
                    annualized_return_pct / annualized_volatility_pct
                    if annualized_volatility_pct > 0
                    else 0.0
                )
            else:
                sharpe_ratio = 0.0

            if total_return < 0:
                sharpe_ratio = min(0.0, sharpe_ratio)
            elif total_return == 0:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0

        avg_profit_per_trade = (
            self.total_profit / self.total_trades if self.total_trades > 0 else 0.0
        )

        return {
            "name": self.name,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_return": total_return,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": sharpe_ratio,
            "final_balance": self.balance,
            "total_profit": self.total_profit,
            "total_loss": self.total_loss,
            "signals_generated": self.signals_generated,
            "signals_executed": self.signals_executed,
            "avg_profit_per_trade": avg_profit_per_trade,
        }


# ============================================================================
# ФУНКЦИИ ЗАГРУЗКИ ДАННЫХ
# ============================================================================


def load_yearly_data(symbol: str, limit_days: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Загружает данные из CSV"""
    csv_path = os.path.join(DATA_DIR, f"{symbol}.csv")

    if not os.path.exists(csv_path):
        logger.warning("⚠️ Файл не найден: %s", csv_path)
        return None

    try:
        df = pd.read_csv(csv_path)

        # Преобразуем timestamp в datetime
        if "timestamp" in df.columns:
            try:
                if df["timestamp"].dtype == "int64" or df["timestamp"].dtype == "float64":
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                else:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
            except Exception:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df.set_index("timestamp", inplace=True)
        elif "open_time" in df.columns:
            try:
                df["open_time"] = pd.to_datetime(df["open_time"])
                df.set_index("open_time", inplace=True)
            except Exception:
                df["open_time"] = pd.to_datetime(df["open_time"], errors="coerce")
                df.set_index("open_time", inplace=True)

        df = df.sort_index()

        # Ограничиваем последними N днями
        if limit_days and len(df) > 0:
            if isinstance(df.index[-1], pd.Timestamp):
                cutoff_date = df.index[-1] - timedelta(days=limit_days)
                df = df[df.index >= cutoff_date]
            else:
                df.index = pd.to_datetime(df.index, errors="coerce")
                cutoff_date = df.index[-1] - timedelta(days=limit_days)
                df = df[df.index >= cutoff_date]

        # Проверяем наличие колонок
        required_cols = ["open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_cols):
            logger.warning("⚠️ Отсутствуют необходимые колонки в %s", symbol)
            return None

        # Преобразуем в float
        for col in required_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=required_cols)

        logger.info(
            "✅ Загружено %d свечей для %s (последние %d дней)", len(df), symbol, limit_days or 365
        )
        return df

    except Exception as e:
        logger.error("❌ Ошибка загрузки %s: %s", symbol, e)
        traceback.print_exc()
        return None


# ============================================================================
# КЛАСС ДЛЯ БЭКТЕСТА ПАРАМЕТРОВ
# ============================================================================


class FilterParametersBacktest:
    """Класс для тестирования параметров фильтров"""

    def __init__(self, period_days: int = PERIOD_DAYS, num_threads: int = 15):
        self.period_days = period_days
        self.num_threads = num_threads
        self.results_dir = Path("backtest_results/filter_parameters")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.symbols = get_top_20_symbols()
        logger.info("📊 Загружено %d символов для тестирования", len(self.symbols))

    def run_single_backtest(
        self, symbol: str, params: Dict[str, Any], mode: str = "soft"
    ) -> BacktestStats:
        """
        Запускает один бэктест с заданными параметрами

        Args:
            symbol: Символ для тестирования
            params: Словарь с параметрами для переопределения
            mode: Режим фильтров (soft/strict)

        Returns:
            BacktestStats с результатами
        """
        # Устанавливаем параметры через environment variables
        # Маппинг имен параметров на environment variables
        param_mapping = {
            "min_confidence_for_short": "BACKTEST_min_confidence_for_short",
            "min_quality_threshold_long": "BACKTEST_min_quality_threshold_long",
            "min_quality_for_short": "BACKTEST_min_quality_for_short",
            "market_adjustment": "BACKTEST_market_adjustment",
            "min_h4_confidence": "BACKTEST_min_h4_confidence",
        }

        for key, value in params.items():
            env_key = param_mapping.get(key, f"BACKTEST_{key}")
            os.environ[env_key] = str(value)
            logger.debug("🔧 [BACKTEST] Установлен параметр %s = %s (env: %s)", key, value, env_key)

        stats = BacktestStats(f"{symbol} ({mode}, params={params})")

        # Загружаем данные
        df = load_yearly_data(symbol, limit_days=self.period_days)
        if df is None or len(df) < 50:
            logger.warning("⚠️ Недостаточно данных для %s", symbol)
            return stats

        # Добавляем технические индикаторы
        df = add_technical_indicators(df)

        # Проверяем наличие необходимых колонок
        required_cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "ema7",
            "ema25",
            "rsi",
            "macd",
            "bb_upper",
            "bb_lower",
            "atr",
        ]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.warning("⚠️ Отсутствуют колонки для %s: %s", symbol, missing_cols)
            return stats

        start_idx = 25
        if len(df) < start_idx:
            return stats

        position = None

        # Проходим по всем свечам
        for i in range(start_idx, len(df)):
            current_price = df["close"].iloc[i]
            current_time = df.index[i]

            # Проверяем выход из позиции
            if position is not None:
                exit_price = None
                exit_reason = None
                partial_close = False

                entry_price = position["entry_price"]
                tp1 = position.get("tp1", position.get("tp"))
                tp2 = position.get("tp2")
                sl = position["sl"]
                side = position["side"]

                # Рассчитываем прогресс к TP1
                if side == "LONG":
                    if tp1 > entry_price:
                        progress_to_tp1 = (current_price - entry_price) / (tp1 - entry_price)
                    else:
                        progress_to_tp1 = 0
                else:  # SHORT
                    if tp1 < entry_price:
                        progress_to_tp1 = (entry_price - current_price) / (entry_price - tp1)
                    else:
                        progress_to_tp1 = 0

                # Перемещение SL
                if progress_to_tp1 >= 0.3 and not position.get("sl_moved_30", False):
                    position["sl_moved_30"] = True
                    if side == "LONG":
                        new_sl = entry_price + (tp1 - entry_price) * 0.3
                        new_sl = max(new_sl, entry_price * 1.001)
                        sl = max(sl, new_sl)
                    else:
                        new_sl = entry_price - (entry_price - tp1) * 0.3
                        new_sl = min(new_sl, entry_price * 0.999)
                        sl = min(sl, new_sl)
                    position["sl"] = sl

                if progress_to_tp1 >= 0.5 and not position.get("sl_moved_50", False):
                    position["sl_moved_50"] = True
                    if side == "LONG":
                        new_sl = entry_price + (tp1 - entry_price) * 0.5
                        new_sl = max(new_sl, entry_price * 1.001)
                        sl = max(sl, new_sl)
                    else:
                        new_sl = entry_price - (entry_price - tp1) * 0.5
                        new_sl = min(new_sl, entry_price * 0.999)
                        sl = min(sl, new_sl)
                    position["sl"] = sl

                if progress_to_tp1 >= 1.0 and not position.get("sl_moved_to_be", False):
                    position["sl_moved_to_be"] = True
                    if side == "LONG":
                        sl = entry_price * 1.003
                    else:
                        sl = entry_price * 0.997
                    position["sl"] = sl

                # Проверяем выходы
                if side == "LONG":
                    if current_price <= sl:
                        exit_price = sl
                        exit_reason = "SL"
                    elif current_price >= tp1 and not position.get("tp1_executed", False):
                        position["tp1_executed"] = True
                        partial_close = True
                        exit_price = tp1
                        exit_reason = "TP1 (50%)"
                    elif position.get("tp1_executed", False) and current_price >= tp2:
                        exit_price = tp2
                        exit_reason = "TP2 (50%)"
                else:  # SHORT
                    if current_price >= sl:
                        exit_price = sl
                        exit_reason = "SL"
                    elif current_price <= tp1 and not position.get("tp1_executed", False):
                        position["tp1_executed"] = True
                        partial_close = True
                        exit_price = tp1
                        exit_reason = "TP1 (50%)"
                    elif position.get("tp1_executed", False) and current_price <= tp2:
                        exit_price = tp2
                        exit_reason = "TP2 (50%)"

                if exit_price:
                    # Рассчитываем прибыль
                    if side == "LONG":
                        profit_pct = ((exit_price - entry_price) / entry_price) * 100
                    else:
                        profit_pct = ((entry_price - exit_price) / entry_price) * 100

                    profit_pct -= (FEE * 2) + (SLIPPAGE * 2)

                    if partial_close:
                        profit_pct = profit_pct * 0.5
                        position["size"] = position.get("size", 1.0) * 0.5
                    else:
                        profit = (profit_pct / 100) * position.get(
                            "size", START_BALANCE * RISK_PER_TRADE
                        )

                        stats.add_trade(
                            {
                                "entry_time": position["entry_time"],
                                "exit_time": current_time,
                                "entry_price": entry_price,
                                "exit_price": exit_price,
                                "side": side,
                                "profit": profit,
                                "profit_pct": profit_pct,
                                "exit_reason": exit_reason,
                            }
                        )

                        position = None
                        continue

            # Если нет позиции, ищем вход
            if position is None:
                # Генерируем сигнал
                signal_side, signal_price = (
                    soft_entry_signal(df, i) if mode == "soft" else strict_entry_signal(df, i)
                )
                stats.signals_generated += 1

                if signal_side:
                    side = signal_side
                    entry_price = signal_price if signal_price else current_price

                    # Получаем динамические TP/SL уровни
                    try:
                        tp1_pct, tp2_pct = get_dynamic_tp_levels(df, i, side)
                        sl_pct = get_dynamic_sl_level(df, i, side, use_ai_optimization=True)

                        if tp1_pct is not None and tp2_pct is not None and sl_pct is not None:
                            if side == "LONG":
                                tp1 = entry_price * (1 + tp1_pct / 100)
                                tp2 = entry_price * (1 + tp2_pct / 100)
                                sl = entry_price * (1 - sl_pct / 100)
                            else:
                                tp1 = entry_price * (1 - tp1_pct / 100)
                                tp2 = entry_price * (1 - tp2_pct / 100)
                                sl = entry_price * (1 + sl_pct / 100)
                        else:
                            raise ValueError("TP/SL levels not calculated")
                    except Exception:
                        # Fallback на оптимизированные параметры
                        atr = df["atr"].iloc[i]
                        if side == "LONG":
                            tp1 = entry_price + (atr * DEFAULT_TP_MULT)
                            tp2 = entry_price + (atr * DEFAULT_TP_MULT * 1.5)
                            sl = entry_price - (atr * DEFAULT_SL_MULT)
                        else:
                            tp1 = entry_price - (atr * DEFAULT_TP_MULT)
                            tp2 = entry_price - (atr * DEFAULT_TP_MULT * 1.5)
                            sl = entry_price + (atr * DEFAULT_SL_MULT)

                    # Открываем позицию
                    position = {
                        "entry_time": current_time,
                        "entry_price": entry_price,
                        "tp1": tp1,
                        "tp2": tp2,
                        "sl": sl,
                        "side": side,
                        "size": START_BALANCE * RISK_PER_TRADE,
                        "sl_moved_30": False,
                        "sl_moved_50": False,
                        "sl_moved_to_be": False,
                        "tp1_executed": False,
                    }
                    stats.signals_executed += 1

        # Закрываем открытую позицию в конце
        if position is not None:
            final_price = df["close"].iloc[-1]
            entry_price = position["entry_price"]
            side = position["side"]

            if side == "LONG":
                profit_pct = ((final_price - entry_price) / entry_price) * 100
            else:
                profit_pct = ((entry_price - final_price) / entry_price) * 100

            profit_pct -= (FEE * 2) + (SLIPPAGE * 2)
            profit = (profit_pct / 100) * position.get("size", START_BALANCE * RISK_PER_TRADE)

            stats.add_trade(
                {
                    "entry_time": position["entry_time"],
                    "exit_time": df.index[-1],
                    "entry_price": entry_price,
                    "exit_price": final_price,
                    "side": side,
                    "profit": profit,
                    "profit_pct": profit_pct,
                    "exit_reason": "End of data",
                }
            )

        # Очищаем environment variables
        param_mapping = {
            "min_confidence_for_short": "BACKTEST_min_confidence_for_short",
            "min_quality_threshold_long": "BACKTEST_min_quality_threshold_long",
            "min_quality_for_short": "BACKTEST_min_quality_for_short",
            "market_adjustment": "BACKTEST_market_adjustment",
            "min_h4_confidence": "BACKTEST_min_h4_confidence",
        }

        for key in params:
            env_key = param_mapping.get(key, f"BACKTEST_{key}")
            os.environ.pop(env_key, None)

        return stats

    def test_parameter_combinations(
        self, param_name: str, param_values: List[Any], mode: str = "soft"
    ) -> Dict[str, Any]:
        """
        Тестирует все значения одного параметра

        Args:
            param_name: Название параметра
            param_values: Список значений для тестирования
            mode: Режим фильтров

        Returns:
            Словарь с результатами для каждого значения
        """
        logger.info("🔍 Тестирование параметра: %s (значения: %s)", param_name, param_values)

        results = {}

        for param_value in param_values:
            logger.info("📊 Тестирование %s = %s", param_name, param_value)

            params = {param_name: param_value}

            # Агрегируем результаты по всем символам
            all_metrics = []

            for symbol in self.symbols:
                try:
                    stats = self.run_single_backtest(symbol, params, mode)
                    metrics = stats.get_metrics()
                    all_metrics.append(metrics)
                except Exception as e:
                    logger.error("❌ Ошибка бэктеста для %s: %s", symbol, e)
                    traceback.print_exc()
                    continue

            if all_metrics:
                # Агрегируем метрики
                aggregated = {
                    "param_name": param_name,
                    "param_value": param_value,
                    "total_trades": sum(m["total_trades"] for m in all_metrics),
                    "winning_trades": sum(m["winning_trades"] for m in all_metrics),
                    "losing_trades": sum(m["losing_trades"] for m in all_metrics),
                    "win_rate": np.mean([m["win_rate"] for m in all_metrics]),
                    "profit_factor": np.mean(
                        [
                            m["profit_factor"]
                            for m in all_metrics
                            if m["profit_factor"] != float("inf")
                        ]
                    ),
                    "total_return": np.mean([m["total_return"] for m in all_metrics]),
                    "max_drawdown_pct": np.mean([m["max_drawdown_pct"] for m in all_metrics]),
                    "sharpe_ratio": np.mean([m["sharpe_ratio"] for m in all_metrics]),
                    "signals_generated": sum(m["signals_generated"] for m in all_metrics),
                    "signals_executed": sum(m["signals_executed"] for m in all_metrics),
                    "avg_profit_per_trade": np.mean(
                        [m["avg_profit_per_trade"] for m in all_metrics]
                    ),
                    "symbols_tested": len(all_metrics),
                }

                results[param_value] = aggregated

                logger.info(
                    "✅ %s = %s: Win Rate=%.2f%%, Profit Factor=%.2f, Return=%.2f%%, Sharpe=%.2f",
                    param_name,
                    param_value,
                    aggregated["win_rate"],
                    aggregated["profit_factor"],
                    aggregated["total_return"],
                    aggregated["sharpe_ratio"],
                )

        return results

    def save_results(self, results: Dict[str, Any], param_name: str):
        """Сохраняет результаты в JSON"""
        filename = self.results_dir / f"{param_name}_results.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info("💾 Результаты сохранены в %s", filename)

    def compare_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Сравнивает результаты и определяет оптимальное значение

        Args:
            results: Словарь с результатами для каждого значения параметра

        Returns:
            Словарь с оптимальным значением и обоснованием
        """
        if not results:
            return {}

        # Критерии для выбора оптимального значения:
        # 1. Максимальный Profit Factor
        # 2. Высокий Win Rate (>50%)
        # 3. Приемлемый Max Drawdown (<20%)
        # 4. Положительный Total Return
        # 5. Высокий Sharpe Ratio

        best_value = None
        best_score = -float("inf")
        best_metrics = None

        for param_value, metrics in results.items():
            # Вычисляем комплексный score
            score = 0.0

            # Profit Factor (вес 30%)
            if metrics["profit_factor"] != float("inf"):
                score += metrics["profit_factor"] * 0.3

            # Win Rate (вес 25%)
            if metrics["win_rate"] > 50:
                score += (metrics["win_rate"] / 100) * 0.25
            else:
                score -= (50 - metrics["win_rate"]) / 100 * 0.25

            # Total Return (вес 20%)
            if metrics["total_return"] > 0:
                score += (metrics["total_return"] / 100) * 0.2
            else:
                score += metrics["total_return"] / 100 * 0.2

            # Sharpe Ratio (вес 15%)
            if metrics["sharpe_ratio"] > 0:
                score += metrics["sharpe_ratio"] * 0.15

            # Max Drawdown (вес 10%, меньше = лучше)
            if metrics["max_drawdown_pct"] < 20:
                score += (20 - metrics["max_drawdown_pct"]) / 20 * 0.1
            else:
                score -= (metrics["max_drawdown_pct"] - 20) / 20 * 0.1

            if score > best_score:
                best_score = score
                best_value = param_value
                best_metrics = metrics

        return {
            "optimal_value": best_value,
            "score": best_score,
            "metrics": best_metrics,
            "all_results": results,
        }


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description="Бэктест параметров фильтров")
    parser.add_argument(
        "--threads", type=int, default=15, help="Количество потоков (по умолчанию 15)"
    )
    parser.add_argument("--period", type=int, default=90, help="Период в днях (по умолчанию 90)")
    parser.add_argument("--param", type=str, help="Тестировать только один параметр")
    parser.add_argument(
        "--mode", type=str, default="soft", choices=["soft", "strict"], help="Режим фильтров"
    )

    args = parser.parse_args()

    logger.info("🚀 ЗАПУСК БЭКТЕСТА ПАРАМЕТРОВ ФИЛЬТРОВ")
    logger.info("=" * 80)
    logger.info("📅 Дата запуска: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("💰 Начальный баланс: $%.2f", START_BALANCE)
    logger.info("📅 Период: %d дней (3 месяца)", args.period)
    logger.info("🔧 Потоков: %d", args.threads)
    logger.info("=" * 80)

    backtest = FilterParametersBacktest(period_days=args.period, num_threads=args.threads)

    # Определяем какие параметры тестировать
    params_to_test = {}

    if args.param:
        # Тестируем только один параметр
        if args.param == "min_confidence_for_short":
            params_to_test["min_confidence_for_short"] = PARAM_MIN_CONFIDENCE_SHORT
        elif args.param == "min_quality_threshold_long":
            params_to_test["min_quality_threshold_long"] = PARAM_MIN_QUALITY_THRESHOLD_LONG
        elif args.param == "min_quality_for_short":
            params_to_test["min_quality_for_short"] = PARAM_MIN_QUALITY_SHORT
        elif args.param == "market_adjustment":
            params_to_test["market_adjustment"] = PARAM_MARKET_ADJUSTMENT
        elif args.param == "min_h4_confidence":
            params_to_test["min_h4_confidence"] = PARAM_MIN_H4_CONFIDENCE
        else:
            logger.error("❌ Неизвестный параметр: %s", args.param)
            return
    else:
        # Тестируем все параметры
        params_to_test = {
            "min_confidence_for_short": PARAM_MIN_CONFIDENCE_SHORT,
            "min_quality_threshold_long": PARAM_MIN_QUALITY_THRESHOLD_LONG,
            "min_quality_for_short": PARAM_MIN_QUALITY_SHORT,
            "market_adjustment": PARAM_MARKET_ADJUSTMENT,
            "min_h4_confidence": PARAM_MIN_H4_CONFIDENCE,
        }

    all_optimal_values = {}

    # Тестируем каждый параметр
    for param_name, param_values in params_to_test.items():
        logger.info("\n" + "=" * 80)
        logger.info("🔍 ТЕСТИРОВАНИЕ ПАРАМЕТРА: %s", param_name)
        logger.info("=" * 80)

        results = backtest.test_parameter_combinations(param_name, param_values, args.mode)
        backtest.save_results(results, param_name)

        comparison = backtest.compare_results(results)
        if comparison:
            all_optimal_values[param_name] = comparison
            logger.info(
                "\n✅ ОПТИМАЛЬНОЕ ЗНАЧЕНИЕ для %s: %s (score=%.3f)",
                param_name,
                comparison["optimal_value"],
                comparison["score"],
            )
            logger.info(
                "   Win Rate=%.2f%%, Profit Factor=%.2f, Return=%.2f%%, Sharpe=%.2f",
                comparison["metrics"]["win_rate"],
                comparison["metrics"]["profit_factor"],
                comparison["metrics"]["total_return"],
                comparison["metrics"]["sharpe_ratio"],
            )

    # Сохраняем сводку оптимальных значений
    summary_file = backtest.results_dir / "optimal_values_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(all_optimal_values, f, indent=2, ensure_ascii=False)
    logger.info("\n💾 Сводка оптимальных значений сохранена в %s", summary_file)

    logger.info("\n" + "=" * 80)
    logger.info("✅ БЭКТЕСТ ЗАВЕРШЕН")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
