#!/usr/bin/env python3
"""
Сравнение результатов Data-Driven Bottom-Up подхода с текущими параметрами
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.shared.utils.datetime_utils import get_utc_now

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PORTFOLIO_SYMBOLS = [
    "BONKUSDT",
    "WIFUSDT",
    "NEIROUSDT",
    "SOLUSDT",
    "SUIUSDT",
    "POLUSDT",
    "LINKUSDT",
    "PENGUUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "CRVUSDT",
    "OPUSDT",
]


def load_csv_data(symbol: str, data_dir: Path = None) -> pd.DataFrame:
    """Загружает данные из CSV файла"""
    if data_dir is None:
        data_dir = PROJECT_ROOT / "data" / "backtest_data"

    csv_file = data_dir / f"{symbol}.csv"
    df = pd.read_csv(csv_file)

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
    else:
        df.index = pd.to_datetime(df.index)

    return df


async def run_backtest_with_params(
    symbol: str, df: pd.DataFrame, btc_df: pd.DataFrame, params: Dict[str, Any], days: int = 365
) -> Dict[str, Any]:
    """Запускает бектест с заданными параметрами"""
    from src.core.config import SYMBOL_SPECIFIC_CONFIG

    original_params = SYMBOL_SPECIFIC_CONFIG.get(symbol, {}).copy()

    SYMBOL_SPECIFIC_CONFIG[symbol] = {
        "optimal_rsi_oversold": int(params.get("rsi_oversold", 25)),
        "optimal_rsi_overbought": int(params.get("rsi_overbought", 75)),
        "ai_score_threshold": params.get("ai_score_threshold", 5.0),
        "min_confidence": int(params.get("min_confidence", 65)),
        "soft_volume_ratio": 1.2,
        "position_size_multiplier": 1.0,
        "filter_mode": "soft",
    }

    backtest = AdvancedBacktest(initial_balance=10000.0, risk_per_trade=2.0, leverage=2.0)
    backtest.btc_df = btc_df
    backtest.eth_df = load_csv_data("ETHUSDT")
    backtest.sol_df = load_csv_data("SOLUSDT")

    if hasattr(backtest, "_symbol_params_cache"):
        backtest._symbol_params_cache.clear()

    await backtest.run_backtest(symbol, df, btc_df, days)
    metrics = backtest.calculate_metrics()

    if original_params:
        SYMBOL_SPECIFIC_CONFIG[symbol] = original_params
    elif symbol in SYMBOL_SPECIFIC_CONFIG:
        del SYMBOL_SPECIFIC_CONFIG[symbol]

    return {
        "symbol": symbol,
        "total_trades": metrics.get("total_trades", 0),
        "win_rate": metrics.get("win_rate", 0.0),
        "profit_factor": metrics.get("profit_factor", 0.0),
        "total_pnl": metrics.get("total_pnl", 0.0),
    }


async def main():
    """Сравнивает Bottom-Up оптимизацию с текущими параметрами"""
    # Загружаем результаты оптимизации
    report_dir = PROJECT_ROOT / "data" / "reports"
    optimization_files = sorted(report_dir.glob("bottom_up_optimization_*.json"), reverse=True)

    if not optimization_files:
        logger.error(
            "❌ Файлы оптимизации не найдены. Запустите сначала auto_optimize_all_portfolio_coins.py"
        )
        return

    optimization_data = json.load(open(optimization_files[0]))
    best_params = optimization_data.get("best_params_by_symbol", {})

    logger.info("📊 СРАВНЕНИЕ: Bottom-Up vs Текущие параметры")
    logger.info("=" * 80)

    data_dir = PROJECT_ROOT / "data" / "backtest_data"
    btc_df = load_csv_data("BTCUSDT", data_dir)

    # Загружаем текущие параметры
    from src.core.config import SYMBOL_SPECIFIC_CONFIG

    comparison_results = {"bottom_up": {}, "current": {}, "improvement": {}}

    for symbol in PORTFOLIO_SYMBOLS:
        df = load_csv_data(symbol, data_dir)
        if df is None:
            continue

        # Бектест с оптимизированными параметрами
        optimized_params = best_params.get(symbol, {}).get("parameters", {})
        if optimized_params:
            optimized_result = await run_backtest_with_params(symbol, df, btc_df, optimized_params)
            comparison_results["bottom_up"][symbol] = optimized_result

        # Бектест с текущими параметрами
        current_params = SYMBOL_SPECIFIC_CONFIG.get(
            symbol,
            {
                "optimal_rsi_oversold": 25,
                "optimal_rsi_overbought": 75,
                "ai_score_threshold": 5.0,
                "min_confidence": 65,
            },
        )

        current_test_params = {
            "rsi_oversold": current_params.get("optimal_rsi_oversold", 25),
            "rsi_overbought": current_params.get("optimal_rsi_overbought", 75),
            "ai_score_threshold": current_params.get("ai_score_threshold", 5.0),
            "min_confidence": current_params.get("min_confidence", 65),
        }

        current_result = await run_backtest_with_params(symbol, df, btc_df, current_test_params)
        comparison_results["current"][symbol] = current_result

        # Считаем улучшение
        if symbol in comparison_results["bottom_up"]:
            improvement = (
                comparison_results["bottom_up"][symbol]["total_pnl"] - current_result["total_pnl"]
            )
            comparison_results["improvement"][symbol] = improvement

    # Сохраняем сравнение
    comparison_file = (
        PROJECT_ROOT
        / "data"
        / "reports"
        / f"bottom_up_vs_current_{get_utc_now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(comparison_file, "w", encoding="utf-8") as f:
        json.dump(comparison_results, f, indent=2, ensure_ascii=False)

    # Выводим результаты
    print("\n" + "=" * 80)
    print("📊 СРАВНЕНИЕ РЕЗУЛЬТАТОВ:")
    print("=" * 80)

    total_bottom_up_pnl = sum(
        r.get("total_pnl", 0) for r in comparison_results["bottom_up"].values()
    )
    total_current_pnl = sum(r.get("total_pnl", 0) for r in comparison_results["current"].values())
    total_improvement = total_bottom_up_pnl - total_current_pnl

    print(f"\n💰 Bottom-Up подход: {total_bottom_up_pnl:.2f} USDT")
    print(f"💰 Текущие параметры: {total_current_pnl:.2f} USDT")
    print(
        f"📈 Улучшение: {total_improvement:+.2f} USDT ({total_improvement / total_current_pnl * 100:+.1f}% if total_current_pnl > 0 else 0)"
    )

    print("\n" + "-" * 80)
    print("Детальное сравнение по монетам:")
    print("-" * 80)

    for symbol in PORTFOLIO_SYMBOLS:
        if symbol in comparison_results["bottom_up"] and symbol in comparison_results["current"]:
            bottom_up = comparison_results["bottom_up"][symbol]
            current = comparison_results["current"][symbol]
            improvement = comparison_results["improvement"].get(symbol, 0)

            print(f"\n{symbol}:")
            print(
                f"  Bottom-Up:  PnL {bottom_up['total_pnl']:8.2f} USDT | Сделок {bottom_up['total_trades']:3d} | WR {bottom_up['win_rate']:5.2f}%"
            )
            print(
                f"  Текущие:    PnL {current['total_pnl']:8.2f} USDT | Сделок {current['total_trades']:3d} | WR {current['win_rate']:5.2f}%"
            )
            print(f"  Улучшение:  {improvement:+.2f} USDT")


if __name__ == "__main__":
    asyncio.run(main())
