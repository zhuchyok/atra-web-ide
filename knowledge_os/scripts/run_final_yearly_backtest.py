#!/usr/bin/env python3
"""
Финальный годовой бектест на выбранном портфеле (15 монет: 5 BTC_HIGH + 5 ETH_HIGH + 5 SOL_HIGH)
С новыми исправлениями: TP1 trailing SL, breakeven SL
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

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
        elif df.index.name == "timestamp" or df.index.dtype == "object":
            df.index = pd.to_datetime(df.index)

        required_cols = ["open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_cols):
            logger.warning("⚠️ Не все необходимые колонки найдены для %s", symbol)
            return None

        return df

    except Exception as e:
        logger.error("❌ Ошибка загрузки данных для %s: %s", symbol, e)
        return None


async def run_portfolio_backtest(portfolio_symbols: List[str], days: int = 365) -> Dict[str, Any]:
    """
    Запускает годовой бектест для портфеля монет

    Args:
        portfolio_symbols: Список символов для портфеля (15 монет)
        days: Количество дней для тестирования (365 для годового)

    Returns:
        Результаты бектеста портфеля
    """
    data_dir = PROJECT_ROOT / "data" / "backtest_data"

    logger.info("🚀 Запуск годового бектеста для портфеля из %d монет...", len(portfolio_symbols))
    logger.info("📊 Период: %d дней (годовой бектест)", days)
    logger.info("📋 Портфель: %s", ", ".join(portfolio_symbols))

    # Загружаем данные BTC, ETH, SOL для фильтров
    logger.info("📥 Загрузка данных BTC, ETH, SOL для фильтров...")
    btc_df = load_csv_data("BTCUSDT", data_dir)
    eth_df = load_csv_data("ETHUSDT", data_dir)
    sol_df = load_csv_data("SOLUSDT", data_dir)

    if btc_df is None or eth_df is None or sol_df is None:
        logger.error("❌ Не удалось загрузить данные BTC/ETH/SOL для фильтров")
        return {}

    # Инициализируем бектест для портфеля
    backtest = AdvancedBacktest(initial_balance=10000.0, risk_per_trade=2.0, leverage=2.0)

    backtest.btc_df = btc_df
    backtest.eth_df = eth_df
    backtest.sol_df = sol_df

    # Запускаем бектесты для каждой монеты в портфеле
    all_trades = []
    portfolio_results = []

    for symbol in portfolio_symbols:
        logger.info("📊 Тестируем %s...", symbol)

        df = load_csv_data(symbol, data_dir)
        if df is None or df.empty:
            logger.warning("⚠️ Пропускаем %s - нет данных", symbol)
            continue

        try:
            # Создаем отдельный бектест для каждой монеты
            symbol_backtest = AdvancedBacktest(
                initial_balance=10000.0, risk_per_trade=2.0, leverage=2.0
            )

            symbol_backtest.btc_df = btc_df
            symbol_backtest.eth_df = eth_df
            symbol_backtest.sol_df = sol_df

            await symbol_backtest.run_backtest(symbol, df, btc_df, days)

            metrics = symbol_backtest.calculate_metrics()

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
            }

            portfolio_results.append(result)
            all_trades.extend(symbol_backtest.trades)

            logger.info(
                "✅ %s: %d сделок, Win Rate: %.2f%%, PF: %.2f, PnL: %.2f%%",
                symbol,
                result["total_trades"],
                result["win_rate"],
                result["profit_factor"],
                result["total_pnl_pct"],
            )

        except Exception as e:
            logger.error("❌ Ошибка бектеста для %s: %s", symbol, e)
            import traceback

            logger.error(traceback.format_exc())

    # Агрегируем результаты портфеля
    total_trades = sum(r["total_trades"] for r in portfolio_results)
    total_pnl = sum(r["total_pnl"] for r in portfolio_results)
    total_pnl_pct = sum(r["total_pnl_pct"] for r in portfolio_results)

    winning_trades = sum(1 for t in all_trades if t.get("pnl", 0) > 0)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

    total_wins = sum(t.get("pnl", 0) for t in all_trades if t.get("pnl", 0) > 0)
    total_losses = abs(sum(t.get("pnl", 0) for t in all_trades if t.get("pnl", 0) < 0))
    profit_factor = (total_wins / total_losses) if total_losses > 0 else 0.0

    portfolio_summary = {
        "portfolio_symbols": portfolio_symbols,
        "period_days": days,
        "total_symbols": len(portfolio_results),
        "total_trades": total_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "symbol_results": portfolio_results,
        "timestamp": datetime.now().isoformat(),
    }

    return portfolio_summary


def save_results(results: Dict[str, Any], output_dir: Path = None):
    """Сохраняет результаты бектеста"""
    if output_dir is None:
        output_dir = PROJECT_ROOT / "data" / "reports"

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Сохраняем JSON
    json_file = output_dir / f"final_yearly_backtest_{timestamp}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("💾 JSON сохранен в %s", json_file)

    return json_file


def print_summary(results: Dict[str, Any]):
    """Выводит сводку результатов"""
    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ ГОДОВОГО БЕКТЕСТА ПОРТФЕЛЯ")
    print("=" * 80)

    print(f"\n📋 Портфель: {len(results.get('portfolio_symbols', []))} монет")
    print(f"📊 Период: {results.get('period_days', 0)} дней")
    print(f"📈 Всего сделок: {results.get('total_trades', 0)}")
    print(f"✅ Win Rate: {results.get('win_rate', 0.0):.2f}%")
    print(f"💰 Profit Factor: {results.get('profit_factor', 0.0):.2f}")
    print(
        f"💵 Total PnL: {results.get('total_pnl', 0.0):.2f} USDT ({results.get('total_pnl_pct', 0.0):.2f}%)"
    )

    print("\n📊 Результаты по монетам:")
    print("-" * 80)
    for result in results.get("symbol_results", []):
        print(
            f"  {result['symbol']:12s} | "
            f"Сделок: {result['total_trades']:3d} | "
            f"Win Rate: {result['win_rate']:5.2f}% | "
            f"PF: {result['profit_factor']:5.2f} | "
            f"PnL: {result['total_pnl_pct']:7.2f}%"
        )

    print("\n" + "=" * 80)


async def main():
    """Главная функция"""
    # TODO: Загрузить топ-5 монет из каждой группы из результатов скрининга
    # Пока используем примерный портфель
    portfolio = [
        # BTC_HIGH (5 монет)
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "ADAUSDT",
        "DOTUSDT",
        # ETH_HIGH (5 монет)
        "LINKUSDT",
        "UNIUSDT",
        "AAVEUSDT",
        "MATICUSDT",
        "ARBUSDT",
        # SOL_HIGH (5 монет)
        "SOLUSDT",
        "AVAXUSDT",
        "SUIUSDT",
        "DOGEUSDT",
        "WIFUSDT",
    ]

    logger.info("🚀 Запуск финального годового бектеста...")

    results = await run_portfolio_backtest(portfolio, days=365)

    if results:
        save_results(results)
        print_summary(results)
    else:
        logger.error("❌ Не удалось получить результаты бектеста")


if __name__ == "__main__":
    asyncio.run(main())
