#!/usr/bin/env python3
"""
Оптимизация параметров для новых монет на основе результатов бектеста
Проверяет существующие параметры и подбирает оптимальные для новых монет
"""

import asyncio
import itertools
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Базовые параметры для оптимизации
PARAMETER_GRID = {
    "rsi_oversold": [20, 25, 30, 35],
    "rsi_overbought": [65, 70, 75, 80],
    "ai_score_threshold": [5.0, 6.0, 7.0, 8.0],
    "position_size_multiplier": [0.7, 0.8, 1.0, 1.2, 1.5],
    "min_confidence": [60, 65, 70, 75],
}


def load_csv_data(symbol: str, data_dir: Path = None) -> Optional[pd.DataFrame]:
    """Загружает данные из CSV файла"""
    if data_dir is None:
        data_dir = PROJECT_ROOT / "data" / "backtest_data"

    csv_file = data_dir / f"{symbol}.csv"

    if not csv_file.exists():
        return None

    try:
        df = pd.read_csv(csv_file)

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
        elif df.index.name == "timestamp" or df.index.dtype == "object":
            df.index = pd.to_datetime(df.index)

        required_cols = ["open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_cols):
            return None

        return df

    except Exception as e:
        logger.error("❌ Ошибка загрузки данных для %s: %s", symbol, e)
        return None


async def test_parameters(
    symbol: str,
    df: pd.DataFrame,
    btc_df: pd.DataFrame,
    eth_df: pd.DataFrame,
    sol_df: pd.DataFrame,
    params: Dict[str, Any],
    days: int = 90,  # Используем 90 дней для быстрой оптимизации
) -> Dict[str, Any]:
    """
    Тестирует набор параметров для монеты

    Returns:
        Метрики бектеста с указанными параметрами
    """
    try:
        backtest = AdvancedBacktest(initial_balance=10000.0, risk_per_trade=2.0, leverage=2.0)
        backtest.btc_df = btc_df
        backtest.eth_df = eth_df
        backtest.sol_df = sol_df
        # Передаём параметры в кэш символа (AdvancedBacktest использует get_symbol_params(symbol))
        if hasattr(backtest, "_symbol_params_cache"):
            backtest._symbol_params_cache[symbol] = {
                "optimal_rsi_oversold": params.get(
                    "optimal_rsi_oversold", params.get("rsi_oversold", 25)
                ),
                "optimal_rsi_overbought": params.get(
                    "optimal_rsi_overbought", params.get("rsi_overbought", 75)
                ),
                "ai_score_threshold": params.get("ai_score_threshold", 5.0),
                "min_confidence": params.get("min_confidence", 65),
                "filter_mode": params.get("filter_mode", "soft"),
            }

        await backtest.run_backtest(df, days=days)

        metrics = backtest.calculate_metrics()

        # Вычисляем комбинированный скор
        score = (
            metrics.get("win_rate", 0.0) * 0.4
            + metrics.get("profit_factor", 0.0) * 0.3
            + max(0, metrics.get("total_pnl_pct", 0.0)) * 0.2
            + (100 - min(metrics.get("max_drawdown", 100.0), 100.0)) * 0.1
        )

        return {
            "params": params,
            "score": score,
            "win_rate": metrics.get("win_rate", 0.0),
            "profit_factor": metrics.get("profit_factor", 0.0),
            "total_pnl_pct": metrics.get("total_pnl_pct", 0.0),
            "max_drawdown": metrics.get("max_drawdown", 0.0),
            "total_trades": metrics.get("total_trades", 0),
        }

    except Exception as e:
        logger.error("❌ Ошибка тестирования параметров для %s: %s", symbol, e)
        return {"params": params, "score": 0.0, "error": str(e)}


async def optimize_symbol_parameters(symbol: str, days: int = 90) -> Dict[str, Any]:
    """
    Оптимизирует параметры для одной монеты

    Returns:
        Оптимальные параметры и результаты тестирования
    """
    data_dir = PROJECT_ROOT / "data" / "backtest_data"

    df = load_csv_data(symbol, data_dir)
    if df is None or df.empty:
        return {"error": "Нет данных"}

    btc_df = load_csv_data("BTCUSDT", data_dir)
    eth_df = load_csv_data("ETHUSDT", data_dir)
    sol_df = load_csv_data("SOLUSDT", data_dir)

    if btc_df is None or eth_df is None or sol_df is None:
        return {"error": "Нет данных BTC/ETH/SOL"}

    logger.info("🔍 Оптимизация параметров для %s...", symbol)

    # Grid search по PARAMETER_GRID (ограниченное число комбинаций)
    param_map = {
        "rsi_oversold": "optimal_rsi_oversold",
        "rsi_overbought": "optimal_rsi_overbought",
        "ai_score_threshold": "ai_score_threshold",
        "position_size_multiplier": "position_size_multiplier",
        "min_confidence": "min_confidence",
    }
    keys = list(PARAMETER_GRID.keys())
    value_lists = [PARAMETER_GRID[k] for k in keys]
    combinations = list(itertools.product(*value_lists))[:12]
    best_score = -1.0
    best_params: Dict[str, Any] = {}
    best_result: Dict[str, Any] = {}
    for combo_values in combinations:
        combo = {
            "optimal_rsi_oversold": 25,
            "optimal_rsi_overbought": 75,
            "ai_score_threshold": 5.0,
            "position_size_multiplier": 1.0,
            "min_confidence": 65,
            "filter_mode": "soft",
        }
        for key, val in zip(keys, combo_values):
            combo[param_map.get(key, key)] = val
        result = await test_parameters(symbol, df, btc_df, eth_df, sol_df, combo, days=days)
        score = result.get("score", 0.0)
        if score > best_score and "error" not in result:
            best_score = score
            best_params = result.get("params", combo)
            best_result = result
    if best_params:
        base_params = best_params
        result = best_result
    else:
        base_params = {
            "optimal_rsi_oversold": 25,
            "optimal_rsi_overbought": 75,
            "ai_score_threshold": 5.0,
            "position_size_multiplier": 1.0,
            "min_confidence": 65,
            "filter_mode": "soft",
        }
        result = await test_parameters(symbol, df, btc_df, eth_df, sol_df, base_params, days=days)

    return {
        "symbol": symbol,
        "optimal_params": base_params,
        "test_results": result,
    }


async def check_existing_parameters(symbols: List[str], days: int = 90) -> Dict[str, Any]:
    """
    Проверяет существующие параметры для монет из текущего портфеля
    """
    results = {}

    for symbol in symbols:
        logger.info("📊 Проверка параметров для %s...", symbol)
        result = await optimize_symbol_parameters(symbol, days=days)
        results[symbol] = result

    return results


if __name__ == "__main__":
    # Пример использования
    existing_symbols = ["AVAXUSDT", "LINKUSDT", "SOLUSDT", "SUIUSDT", "DOGEUSDT"]
    asyncio.run(check_existing_parameters(existing_symbols, days=90))
