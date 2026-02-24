#!/usr/bin/env python3
"""
Тестирование разных комбинаций параметров для BTC/ETH монет
Цель: Найти оптимальные параметры, которые улучшат результаты
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


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


# Варианты параметров для тестирования
PARAMETER_VARIANTS = [
    {
        "name": "Вариант 1: Умеренно консервативные",
        "rsi_oversold": 27,
        "rsi_overbought": 73,
        "ai_score_threshold": 5.5,
        "min_confidence": 67,
    },
    {
        "name": "Вариант 2: Средние",
        "rsi_oversold": 28,
        "rsi_overbought": 72,
        "ai_score_threshold": 6.0,
        "min_confidence": 68,
    },
    {
        "name": "Вариант 3: Более консервативные",
        "rsi_oversold": 29,
        "rsi_overbought": 71,
        "ai_score_threshold": 6.5,
        "min_confidence": 69,
    },
    {
        "name": "Вариант 4: Ближе к SOL, но строже",
        "rsi_oversold": 26,
        "rsi_overbought": 74,
        "ai_score_threshold": 5.0,
        "min_confidence": 66,
    },
    {
        "name": "Вариант 5: Очень умеренные",
        "rsi_oversold": 26.5,
        "rsi_overbought": 73.5,
        "ai_score_threshold": 5.25,
        "min_confidence": 66.5,
    },
    {
        "name": "Вариант 6: Текущие (оптимизированные)",
        "rsi_oversold": 25,
        "rsi_overbought": 75,
        "ai_score_threshold": 5.0,
        "min_confidence": 65,
    },
    {
        "name": "Вариант 7: Оригинальные (строгие)",
        "rsi_oversold": 30,  # Для BTC, будет переопределено для ETH
        "rsi_overbought": 70,
        "ai_score_threshold": 6.5,
        "min_confidence": 70,
    },
]


async def test_parameters_for_symbol(
    symbol: str,
    df: pd.DataFrame,
    btc_df: pd.DataFrame,
    eth_df: pd.DataFrame,
    sol_df: pd.DataFrame,
    params: Dict[str, Any],
    days: int = 365,
) -> Dict[str, Any]:
    """
    Тестирует монету с заданными параметрами
    """
    try:
        # Временно обновляем параметры в конфиге
        from src.core.config import SYMBOL_SPECIFIC_CONFIG

        # Сохраняем оригинальные параметры
        original_params = SYMBOL_SPECIFIC_CONFIG.get(symbol, {}).copy()

        # Устанавливаем тестовые параметры
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

        # Очищаем кэш параметров, чтобы применить новые
        if hasattr(backtest, "_symbol_params_cache"):
            backtest._symbol_params_cache.clear()

        # Переопределяем метод get_symbol_params для этого экземпляра
        original_get_params = backtest.get_symbol_params

        def get_test_params(sym):
            if sym == symbol:
                return test_params.copy()
            return original_get_params(sym)

        backtest.get_symbol_params = get_test_params

        await backtest.run_backtest(symbol, df, btc_df, days)

        metrics = backtest.calculate_metrics()

        # Восстанавливаем оригинальные параметры
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
            "parameters": params,
        }

    except Exception as e:
        logger.error("❌ Ошибка тестирования %s с параметрами %s: %s", symbol, params["name"], e)
        return {
            "symbol": symbol,
            "variant": params["name"],
            "error": str(e),
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_pnl": 0.0,
        }


async def main():
    """Главная функция"""
    data_dir = PROJECT_ROOT / "data" / "backtest_data"

    # Тестируем на основных монетах
    test_symbols = ["BTCUSDT", "ETHUSDT"]

    # Загружаем данные BTC, ETH, SOL для фильтров
    btc_df = load_csv_data("BTCUSDT", data_dir)
    eth_df = load_csv_data("ETHUSDT", data_dir)
    sol_df = load_csv_data("SOLUSDT", data_dir)

    if btc_df is None or eth_df is None or sol_df is None:
        logger.error("❌ Не удалось загрузить данные BTC/ETH/SOL")
        return

    all_results = []

    for symbol in test_symbols:
        df = load_csv_data(symbol, data_dir)
        if df is None:
            logger.warning("⚠️ Данные для %s не найдены, пропускаем", symbol)
            continue

        logger.info(
            "🔍 Тестируем %s с %d вариантами параметров...", symbol, len(PARAMETER_VARIANTS)
        )

        # Для ETH используем оригинальные параметры из варианта 7
        if symbol == "ETHUSDT":
            PARAMETER_VARIANTS[6]["rsi_oversold"] = 28
            PARAMETER_VARIANTS[6]["rsi_overbought"] = 72
            PARAMETER_VARIANTS[6]["ai_score_threshold"] = 7.0

        for variant in PARAMETER_VARIANTS:
            logger.info("  📊 Тестируем: %s", variant["name"])

            result = await test_parameters_for_symbol(
                symbol, df, btc_df, eth_df, sol_df, variant, days=365
            )

            all_results.append(result)

            logger.info(
                "    ✅ %s: %d сделок, WR: %.2f%%, PF: %.2f, PnL: %.2f USDT",
                variant["name"],
                result["total_trades"],
                result["win_rate"],
                result["profit_factor"],
                result["total_pnl"],
            )

    # Сохраняем результаты
    output_file = PROJECT_ROOT / "data" / "reports" / "btc_eth_parameter_optimization.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    logger.info("💾 Результаты сохранены в %s", output_file)

    # Анализируем результаты
    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ ОПТИМИЗАЦИИ ПАРАМЕТРОВ:")
    print("=" * 80)

    for symbol in test_symbols:
        symbol_results = [r for r in all_results if r["symbol"] == symbol]
        if not symbol_results:
            continue

        print(f"\n📈 {symbol}:")
        print("-" * 80)

        # Сортируем по PnL
        symbol_results.sort(key=lambda x: x["total_pnl"], reverse=True)

        for i, result in enumerate(symbol_results, 1):
            print(
                f"{i}. {result['variant']:40s} | "
                f"Сделок: {result['total_trades']:3d} | "
                f"WR: {result['win_rate']:5.2f}% | "
                f"PF: {result['profit_factor']:5.2f} | "
                f"PnL: {result['total_pnl']:8.2f} USDT"
            )

        # Находим лучший вариант
        best = symbol_results[0]
        if best["total_pnl"] > 0:
            print(f"\n✅ Лучший вариант для {symbol}: {best['variant']}")
            print(
                f"   Параметры: RSI {best['parameters']['rsi_oversold']}-{best['parameters']['rsi_overbought']}, "
                f"AI Score {best['parameters']['ai_score_threshold']}, "
                f"Confidence {best['parameters']['min_confidence']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
