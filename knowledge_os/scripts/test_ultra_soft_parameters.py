#!/usr/bin/env python3
"""
Тестирование ультра-мягких параметров для 12 монет
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROBLEM_SYMBOLS = [
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

# Ультра-мягкие варианты параметров
ULTRA_SOFT_VARIANTS = [
    {
        "name": "Ультра-мягкий 1",
        "rsi_oversold": 15,
        "rsi_overbought": 85,
        "ai_score_threshold": 2.0,
        "min_confidence": 55,
    },
    {
        "name": "Ультра-мягкий 2",
        "rsi_oversold": 18,
        "rsi_overbought": 82,
        "ai_score_threshold": 2.5,
        "min_confidence": 57,
    },
    {
        "name": "Ультра-мягкий 3",
        "rsi_oversold": 20,
        "rsi_overbought": 80,
        "ai_score_threshold": 3.0,
        "min_confidence": 60,
    },
    {
        "name": "Ультра-мягкий 4",
        "rsi_oversold": 12,
        "rsi_overbought": 88,
        "ai_score_threshold": 1.5,
        "min_confidence": 50,
    },
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


async def test_ultra_soft_params(
    symbol: str, df: pd.DataFrame, btc_df: pd.DataFrame, params: Dict[str, Any], days: int = 365
) -> Dict[str, Any]:
    """Тестирует монету с ультра-мягкими параметрами"""
    from src.core.config import SYMBOL_SPECIFIC_CONFIG

    original_params = SYMBOL_SPECIFIC_CONFIG.get(symbol, {}).copy()

    test_params = {
        "optimal_rsi_oversold": int(params["rsi_oversold"]),
        "optimal_rsi_overbought": int(params["rsi_overbought"]),
        "ai_score_threshold": params["ai_score_threshold"],
        "min_confidence": int(params["min_confidence"]),
        "soft_volume_ratio": 1.0,  # Ослабляем volume фильтр
        "position_size_multiplier": 1.0,
        "filter_mode": "soft",
    }

    SYMBOL_SPECIFIC_CONFIG[symbol] = test_params.copy()

    backtest = AdvancedBacktest(initial_balance=10000.0, risk_per_trade=2.0, leverage=2.0)

    backtest.btc_df = btc_df
    backtest.eth_df = load_csv_data("ETHUSDT")
    backtest.sol_df = load_csv_data("SOLUSDT")

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
        "parameters": params,
    }


async def main():
    """Главная функция"""
    logger.info("🚀 ТЕСТИРОВАНИЕ УЛЬТРА-МЯГКИХ ПАРАМЕТРОВ")
    logger.info("=" * 80)

    data_dir = PROJECT_ROOT / "data" / "backtest_data"
    btc_df = load_csv_data("BTCUSDT", data_dir)

    all_results = []
    best_params_by_symbol = {}

    total_tests = len(PROBLEM_SYMBOLS) * len(ULTRA_SOFT_VARIANTS)
    current_test = 0

    for symbol in PROBLEM_SYMBOLS:
        df = load_csv_data(symbol, data_dir)
        if df is None:
            logger.warning("⚠️ Данные для %s не найдены", symbol)
            continue

        logger.info(
            "🔍 [%d/%d] Тестируем %s...",
            PROBLEM_SYMBOLS.index(symbol) + 1,
            len(PROBLEM_SYMBOLS),
            symbol,
        )

        symbol_results = []

        for variant in ULTRA_SOFT_VARIANTS:
            current_test += 1
            logger.info("  [%d/%d] %s", current_test, total_tests, variant["name"])

            result = await test_ultra_soft_params(symbol, df, btc_df, variant, days=365)

            all_results.append(result)
            symbol_results.append(result)

            if result["total_trades"] > 0:
                logger.info(
                    "    ✅ %s: %d сделок, PnL: %.2f USDT",
                    variant["name"],
                    result["total_trades"],
                    result["total_pnl"],
                )

        # Находим лучший вариант
        symbol_results.sort(key=lambda x: x["total_pnl"], reverse=True)
        best = symbol_results[0]
        best_params_by_symbol[symbol] = best

        if best["total_trades"] > 0:
            logger.info(
                "  ✅ Лучший для %s: %s (%d сделок, PnL: %.2f USDT)",
                symbol,
                best["variant"],
                best["total_trades"],
                best["total_pnl"],
            )
        else:
            logger.warning("  ❌ Все варианты дали 0 сделок для %s", symbol)

    # Сохраняем результаты
    output_file = (
        PROJECT_ROOT
        / "data"
        / "reports"
        / f"ultra_soft_params_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {"all_results": all_results, "best_params_by_symbol": best_params_by_symbol},
            f,
            indent=2,
            ensure_ascii=False,
        )

    # Выводим результаты
    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ УЛЬТРА-МЯГКИХ ПАРАМЕТРОВ:")
    print("=" * 80)

    unlocked_count = 0
    total_pnl = 0.0

    for symbol in PROBLEM_SYMBOLS:
        best = best_params_by_symbol.get(symbol)
        if not best:
            continue

        trades = best.get("total_trades", 0)
        if trades > 0:
            unlocked_count += 1
            pnl = best.get("total_pnl", 0)
            total_pnl += pnl

            params = best.get("parameters", {})
            print(f"\n✅ {symbol}:")
            print(f"  Вариант: {best.get('variant', 'N/A')}")
            print(
                f"  Параметры: RSI {params.get('rsi_oversold', 0):.0f}-{params.get('rsi_overbought', 0):.0f}, "
                f"AI {params.get('ai_score_threshold', 0):.2f}, Conf {params.get('min_confidence', 0):.0f}"
            )
            print(
                f"  Результаты: PnL {pnl:8.2f} USDT | Сделок {trades:3d} | "
                f"WR {best.get('win_rate', 0):5.2f}% | PF {best.get('profit_factor', 0):5.2f}"
            )
        else:
            print(f"\n❌ {symbol}: Все варианты дали 0 сделок")

    print("\n" + "=" * 80)
    print(f"📈 Разблокировано: {unlocked_count}/{len(PROBLEM_SYMBOLS)} монет")
    print(f"💰 Общий PnL: {total_pnl:.2f} USDT")
    print("=" * 80)

    logger.info("💾 Результаты сохранены в %s", output_file)


if __name__ == "__main__":
    asyncio.run(main())
