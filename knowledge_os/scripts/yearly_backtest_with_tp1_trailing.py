#!/usr/bin/env python3
"""
Годовой бектест с новыми исправлениями:
- Подтягивание SL к TP1
- Автоматический перенос SL в безубыток после TP1
- Интеграция с TrailingStopManager
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# pylint: disable=wrong-import-position
from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_csv_data(symbol: str, data_dir: Path = None) -> Optional[pd.DataFrame]:
    """Загружает данные из CSV файла"""
    if data_dir is None:
        data_dir = PROJECT_ROOT / "data" / "backtest_data"

    csv_file = data_dir / f"{symbol}.csv"

    if not csv_file.exists():
        logger.warning("⚠️ Файл не найден: %s", csv_file)
        return None

    try:
        df = pd.read_csv(csv_file)

        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        elif df.index.name == 'timestamp' or df.index.dtype == 'object':
            df.index = pd.to_datetime(df.index)

        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.warning("⚠️ Не все необходимые колонки найдены для %s", symbol)
            return None

        return df

    except Exception as e:
        logger.error("❌ Ошибка загрузки данных для %s: %s", symbol, e)
        return None


async def run_yearly_backtest_for_symbol(
    symbol: str,
    df: pd.DataFrame,
    btc_df: pd.DataFrame,
    eth_df: pd.DataFrame,
    sol_df: pd.DataFrame,
    days: int = 365
) -> Dict[str, Any]:
    """
    Запускает годовой бектест для одной монеты с новыми исправлениями
    """
    try:
        logger.info("📊 Запуск годового бектеста для %s (%d дней)...", symbol, days)

        # Инициализируем бектест
        backtest = AdvancedBacktest(
            initial_balance=10000.0,
            risk_per_trade=2.0,
            leverage=2.0
        )

        # Загружаем данные BTC, ETH, SOL для фильтров
        backtest.btc_df = btc_df
        backtest.eth_df = eth_df
        backtest.sol_df = sol_df

        # Запускаем бектест
        await backtest.run_backtest(symbol, df, btc_df, days)

        # Получаем метрики
        metrics = backtest.calculate_metrics()

        result = {
            "symbol": symbol,
            "total_trades": metrics.get("total_trades", 0),
            "win_rate": metrics.get("win_rate", 0.0),
            "profit_factor": metrics.get("profit_factor", 0.0),
            "total_pnl": metrics.get("total_pnl", 0.0),
            "total_pnl_pct": metrics.get("total_pnl_pct", 0.0),
            "max_drawdown": metrics.get("max_drawdown", 0.0),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
            "sortino_ratio": metrics.get("sortino_ratio", 0.0),
            "avg_win": metrics.get("avg_win", 0.0),
            "avg_loss": metrics.get("avg_loss", 0.0),
            "largest_win": metrics.get("largest_win", 0.0),
            "largest_loss": metrics.get("largest_loss", 0.0),
            "trades_per_month": metrics.get("trades_per_month", 0.0),
        }

        logger.info(
            "✅ %s: %d сделок, Win Rate: %.2f%%, PF: %.2f, PnL: %.2f%%",
            symbol,
            result["total_trades"],
            result["win_rate"],
            result["profit_factor"],
            result["total_pnl_pct"]
        )

        return result

    except Exception as e:
        logger.error("❌ Ошибка бектеста для %s: %s", symbol, e)
        # pylint: disable=import-outside-toplevel
        import traceback
        logger.error(traceback.format_exc())
        return {
            "symbol": symbol,
            "error": str(e),
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_pnl": 0.0,
            "total_pnl_pct": 0.0,
        }


async def run_yearly_backtest_for_portfolio(
    symbols: List[str],
    days: int = 365
) -> List[Dict[str, Any]]:
    """
    Запускает годовой бектест для портфеля монет
    """
    data_dir = PROJECT_ROOT / "data" / "backtest_data"

    # Загружаем данные BTC, ETH, SOL для фильтров
    logger.info("📥 Загрузка данных BTC, ETH, SOL для фильтров...")
    btc_df = load_csv_data("BTCUSDT", data_dir)
    eth_df = load_csv_data("ETHUSDT", data_dir)
    sol_df = load_csv_data("SOLUSDT", data_dir)

    if btc_df is None or eth_df is None or sol_df is None:
        logger.error("❌ Не удалось загрузить данные BTC/ETH/SOL для фильтров")
        return []

    results = []

    for symbol in symbols:
        df = load_csv_data(symbol, data_dir)
        if df is None or df.empty:
            logger.warning("⚠️ Пропускаем %s - нет данных", symbol)
            continue

        result = await run_yearly_backtest_for_symbol(
            symbol, df, btc_df, eth_df, sol_df, days=days
        )
        results.append(result)

    return results


if __name__ == "__main__":
    # Пример использования
    test_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "LINKUSDT"]

    asyncio.run(run_yearly_backtest_for_portfolio(test_symbols, days=365))
