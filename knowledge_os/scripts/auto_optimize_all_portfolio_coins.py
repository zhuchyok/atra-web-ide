#!/usr/bin/env python3
"""
Автоматическая оптимизация параметров для ВСЕХ монет портфеля
Data-Driven Bottom-Up подход: оптимизируем каждую монету индивидуально
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Финальный портфель из 14 монет
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

# Расширенный набор вариантов параметров для более точной оптимизации
PARAMETER_VARIANTS = [
    # Консервативные варианты
    {
        "name": "Консервативный 1",
        "rsi_oversold": 29,
        "rsi_overbought": 71,
        "ai_score_threshold": 6.5,
        "min_confidence": 69,
    },
    {
        "name": "Консервативный 2",
        "rsi_oversold": 28,
        "rsi_overbought": 72,
        "ai_score_threshold": 6.0,
        "min_confidence": 68,
    },
    {
        "name": "Консервативный 3",
        "rsi_oversold": 27,
        "rsi_overbought": 73,
        "ai_score_threshold": 5.5,
        "min_confidence": 67,
    },
    # Средние варианты
    {
        "name": "Средний 1",
        "rsi_oversold": 26,
        "rsi_overbought": 74,
        "ai_score_threshold": 5.0,
        "min_confidence": 66,
    },
    {
        "name": "Средний 2",
        "rsi_oversold": 25,
        "rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "min_confidence": 65,
    },
    {
        "name": "Средний 3",
        "rsi_oversold": 26.5,
        "rsi_overbought": 73.5,
        "ai_score_threshold": 5.25,
        "min_confidence": 66.5,
    },
    # Агрессивные варианты
    {
        "name": "Агрессивный 1",
        "rsi_oversold": 24,
        "rsi_overbought": 76,
        "ai_score_threshold": 4.5,
        "min_confidence": 64,
    },
    {
        "name": "Агрессивный 2",
        "rsi_oversold": 23,
        "rsi_overbought": 77,
        "ai_score_threshold": 4.0,
        "min_confidence": 63,
    },
    {
        "name": "Агрессивный 3",
        "rsi_oversold": 22,
        "rsi_overbought": 78,
        "ai_score_threshold": 3.5,
        "min_confidence": 62,
    },
    # Экстремальные варианты
    {
        "name": "Экстремальный 1",
        "rsi_oversold": 20,
        "rsi_overbought": 80,
        "ai_score_threshold": 3.0,
        "min_confidence": 60,
    },
    {
        "name": "Экстремальный 2",
        "rsi_oversold": 25,
        "rsi_overbought": 75,
        "ai_score_threshold": 4.0,
        "min_confidence": 64,
    },
]


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


async def test_parameters_for_symbol(
    symbol: str,
    df: pd.DataFrame,
    btc_df: pd.DataFrame,
    eth_df: pd.DataFrame,
    sol_df: pd.DataFrame,
    params: Dict[str, Any],
    days: int = 365,
) -> Dict[str, Any]:
    """Тестирует монету с заданными параметрами"""
    try:
        from src.core.config import SYMBOL_SPECIFIC_CONFIG

        original_params = SYMBOL_SPECIFIC_CONFIG.get(symbol, {}).copy()

        test_params = {
            "optimal_rsi_oversold": int(params["rsi_oversold"]),
            "optimal_rsi_overbought": int(params["rsi_overbought"]),
            "ai_score_threshold": params["ai_score_threshold"],
            "min_confidence": int(params["min_confidence"]),
            "soft_volume_ratio": 1.2,
            "position_size_multiplier": 1.0,
            "filter_mode": "soft",
        }

        SYMBOL_SPECIFIC_CONFIG[symbol] = test_params.copy()

        backtest = AdvancedBacktest(initial_balance=10000.0, risk_per_trade=2.0, leverage=2.0)

        backtest.btc_df = btc_df
        backtest.eth_df = eth_df
        backtest.sol_df = sol_df

        if hasattr(backtest, "_symbol_params_cache"):
            backtest._symbol_params_cache.clear()

        original_get_params = backtest.get_symbol_params

        def get_test_params(sym):
            if sym == symbol:
                return test_params.copy()
            return original_get_params(sym)

        backtest.get_symbol_params = get_test_params

        await backtest.run_backtest(symbol, df, btc_df, days)

        metrics = backtest.calculate_metrics()

        if original_params:
            SYMBOL_SPECIFIC_CONFIG[symbol] = original_params
        elif symbol in SYMBOL_SPECIFIC_CONFIG:
            del SYMBOL_SPECIFIC_CONFIG[symbol]

        return {
            "symbol": symbol,
            "variant": params["name"],
            "total_trades": metrics.get("total_trades", 0),
            "win_rate": metrics.get("win_rate", 0.0),
            "profit_factor": metrics.get("profit_factor", 0.0),
            "total_pnl": metrics.get("total_pnl", 0.0),
            "total_pnl_pct": metrics.get("total_pnl_pct", 0.0),
            "max_drawdown": metrics.get("max_drawdown", 0.0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
            "sortino_ratio": metrics.get("sortino_ratio", 0.0),
            "parameters": params,
        }

    except Exception as e:
        logger.error("❌ Ошибка тестирования %s: %s", symbol, e)
        return {
            "symbol": symbol,
            "variant": params["name"],
            "error": str(e),
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_pnl": 0.0,
        }


async def optimize_all_symbols(days: int = 365) -> Dict[str, Any]:
    """Оптимизирует параметры для всех монет портфеля"""
    data_dir = PROJECT_ROOT / "data" / "backtest_data"

    btc_df = load_csv_data("BTCUSDT", data_dir)
    eth_df = load_csv_data("ETHUSDT", data_dir)
    sol_df = load_csv_data("SOLUSDT", data_dir)

    if btc_df is None or eth_df is None or sol_df is None:
        logger.error("❌ Не удалось загрузить данные BTC/ETH/SOL")
        return {}

    all_results = []
    best_params_by_symbol = {}

    total_tests = len(PORTFOLIO_SYMBOLS) * len(PARAMETER_VARIANTS)
    current_test = 0

    logger.info("🚀 DATA-DRIVEN BOTTOM-UP: Оптимизация всех %d монет", len(PORTFOLIO_SYMBOLS))
    logger.info(
        "📊 Всего тестов: %d (%d вариантов × %d монет)",
        total_tests,
        len(PARAMETER_VARIANTS),
        len(PORTFOLIO_SYMBOLS),
    )
    logger.info("=" * 80)

    for symbol in PORTFOLIO_SYMBOLS:
        df = load_csv_data(symbol, data_dir)
        if df is None:
            logger.warning("⚠️ Данные для %s не найдены, пропускаем", symbol)
            continue

        logger.info(
            "🔍 [%d/%d] Оптимизируем %s...",
            PORTFOLIO_SYMBOLS.index(symbol) + 1,
            len(PORTFOLIO_SYMBOLS),
            symbol,
        )

        symbol_results = []

        for variant in PARAMETER_VARIANTS:
            current_test += 1
            logger.info("  [%d/%d] Тестируем: %s", current_test, total_tests, variant["name"])

            result = await test_parameters_for_symbol(
                symbol, df, btc_df, eth_df, sol_df, variant, days=days
            )

            all_results.append(result)
            symbol_results.append(result)

            if result.get("total_trades", 0) > 0:
                logger.info(
                    "    ✅ %s: %d сделок, WR: %.2f%%, PF: %.2f, PnL: %.2f USDT",
                    variant["name"],
                    result["total_trades"],
                    result["win_rate"],
                    result["profit_factor"],
                    result["total_pnl"],
                )

        # Находим лучший вариант
        symbol_results.sort(key=lambda x: x.get("total_pnl", 0), reverse=True)
        best = symbol_results[0]
        best_params_by_symbol[symbol] = best

        if best.get("total_pnl", 0) > 0:
            logger.info(
                "  ✅ Лучший для %s: %s (PnL: %.2f USDT)",
                symbol,
                best["variant"],
                best["total_pnl"],
            )
        else:
            logger.warning(
                "  ⚠️ Все варианты убыточны для %s, лучший: %s (PnL: %.2f USDT)",
                symbol,
                best["variant"],
                best["total_pnl"],
            )

    return {
        "all_results": all_results,
        "best_params_by_symbol": best_params_by_symbol,
        "optimization_date": datetime.now().isoformat(),
        "total_symbols": len(PORTFOLIO_SYMBOLS),
        "total_tests": total_tests,
    }


async def compare_with_current(results: Dict[str, Any]) -> Dict[str, Any]:
    """Сравнивает результаты оптимизации с текущими параметрами"""
    from src.core.config import SYMBOL_SPECIFIC_CONFIG

    comparison = {}

    for symbol in PORTFOLIO_SYMBOLS:
        optimized = results["best_params_by_symbol"].get(symbol)
        current = SYMBOL_SPECIFIC_CONFIG.get(symbol, {})

        if optimized:
            comparison[symbol] = {
                "optimized": {
                    "rsi_oversold": optimized["parameters"]["rsi_oversold"],
                    "rsi_overbought": optimized["parameters"]["rsi_overbought"],
                    "ai_score_threshold": optimized["parameters"]["ai_score_threshold"],
                    "min_confidence": optimized["parameters"]["min_confidence"],
                    "pnl": optimized.get("total_pnl", 0),
                    "trades": optimized.get("total_trades", 0),
                    "win_rate": optimized.get("win_rate", 0),
                },
                "current": {
                    "rsi_oversold": current.get("optimal_rsi_oversold", 25),
                    "rsi_overbought": current.get("optimal_rsi_overbought", 75),
                    "ai_score_threshold": current.get("ai_score_threshold", 5.0),
                    "min_confidence": current.get("min_confidence", 65),
                },
                "improvement": optimized.get(
                    "total_pnl", 0
                ),  # Будет сравнено с текущими результатами
            }

    return comparison


async def main():
    """Главная функция"""
    logger.info("🎯 DATA-DRIVEN BOTTOM-UP: Полная оптимизация портфеля")
    logger.info("=" * 80)

    # Оптимизируем все монеты
    results = await optimize_all_symbols(days=365)

    if not results:
        logger.error("❌ Оптимизация не дала результатов")
        return

    # Сохраняем результаты
    output_file = (
        PROJECT_ROOT
        / "data"
        / "reports"
        / f"bottom_up_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info("💾 Результаты сохранены в %s", output_file)

    # Сравниваем с текущими параметрами
    comparison = await compare_with_current(results)

    comparison_file = (
        PROJECT_ROOT
        / "data"
        / "reports"
        / f"bottom_up_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(comparison_file, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)

    # Выводим результаты
    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ DATA-DRIVEN BOTTOM-UP ОПТИМИЗАЦИИ:")
    print("=" * 80)

    profitable_count = 0
    total_pnl = 0.0

    for symbol in sorted(PORTFOLIO_SYMBOLS):
        best = results["best_params_by_symbol"].get(symbol)
        if not best:
            continue

        pnl = best.get("total_pnl", 0)
        if pnl > 0:
            profitable_count += 1
            total_pnl += pnl

        params = best.get("parameters", {})
        print(f"\n{symbol}:")
        print(f"  Лучший вариант: {best.get('variant', 'N/A')}")
        print(
            f"  Параметры: RSI {params.get('rsi_oversold', 0):.0f}-{params.get('rsi_overbought', 0):.0f}, "
            f"AI {params.get('ai_score_threshold', 0):.2f}, Conf {params.get('min_confidence', 0):.0f}"
        )
        print(
            f"  Результаты: PnL {pnl:8.2f} USDT | Сделок {best.get('total_trades', 0):3d} | "
            f"WR {best.get('win_rate', 0):5.2f}% | PF {best.get('profit_factor', 0):5.2f}"
        )

    print("\n" + "=" * 80)
    print(f"📈 ИТОГО: {profitable_count}/{len(PORTFOLIO_SYMBOLS)} прибыльных монет")
    print(f"💰 Общий PnL: {total_pnl:.2f} USDT")
    print("=" * 80)

    # Сохраняем лучшие параметры для применения
    best_params_file = (
        PROJECT_ROOT
        / "data"
        / "reports"
        / f"best_params_bottom_up_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(best_params_file, "w", encoding="utf-8") as f:
        json.dump(results["best_params_by_symbol"], f, indent=2, ensure_ascii=False)

    logger.info("💾 Лучшие параметры сохранены в %s", best_params_file)
    logger.info("✅ Оптимизация завершена! Готово к сравнению с текущими результатами.")


if __name__ == "__main__":
    asyncio.run(main())
