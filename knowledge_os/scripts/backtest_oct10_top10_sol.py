#!/usr/bin/env python3
"""
Бектест TOP-10 SOL_HIGH портфеля на окне вокруг 10 октября.

Цель:
- Поднять реальные исторические данные по монетам и BTC/ETH/SOL
- Прогнать текущую стратегию (AdvancedBacktest) на окне дат
  и оценить, насколько она успешна на этом участке.

Важно:
- Тестируется ТЕКУЩАЯ логика стратегии на прошедшем участке рынка.
- Это не идеально точная реконструкция старой версии кода от 10.10,
  но даёт честную оценку, как сегодняшняя стратегия ведёт себя на тех данных.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# pylint: disable=wrong-import-position
from data.historical_data_loader import HistoricalDataLoader
from scripts.run_advanced_backtest import AdvancedBacktest

# Уменьшаем шум в логах, чтобы бектест нормально отрабатывал в среде
logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Тот же TOP-10 портфель, что используется в config.COINS и грид-поиске
TOP10_SOL_PORTFOLIO: List[str] = [
    "BONKUSDT",
    "NEIROUSDT",
    "SUIUSDT",
    "POLUSDT",
    "WIFUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "CRVUSDT",
    "OPUSDT",
]


async def load_window_data(
    symbols: List[str],
    start: datetime,
    end: datetime,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, pd.DataFrame]]:
    """
    Загружает данные BTC/ETH/SOL и портфеля монет на заданном окне.

    Возвращает:
      - btc_df, eth_df, sol_df
      - dict символ -> df
    """
    async with HistoricalDataLoader(exchange="binance") as loader:
        # BTC / ETH / SOL для трендов и фильтров
        btc_df = await loader.fetch_ohlcv("BTCUSDT", interval="1h", start_time=start, end_time=end)
        eth_df = await loader.fetch_ohlcv("ETHUSDT", interval="1h", start_time=start, end_time=end)
        sol_df = await loader.fetch_ohlcv("SOLUSDT", interval="1h", start_time=start, end_time=end)

        symbol_data: Dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            df = await loader.fetch_ohlcv(symbol, interval="1h", start_time=start, end_time=end)
            symbol_data[symbol] = df

    return btc_df, eth_df, sol_df, symbol_data


async def run_oct_window_backtest() -> Dict[str, Any]:
    """
    Запускает бектест TOP-10 портфеля на окне вокруг 10 октября.

    Окно: с 1 октября до 15 октября (UTC), таймфрейм 1h.
    """
    # Окно вокруг 10 октября (можно легко подвинуть при необходимости)
    end = datetime(2025, 10, 15, 0, 0, tzinfo=timezone.utc)
    start = datetime(2025, 10, 1, 0, 0, tzinfo=timezone.utc)
    days = (end - start).days

    logger.warning("📅 Бектест TOP-10 SOL портфеля на окне %s — %s (дней: %d)", start, end, days)

    btc_df, eth_df, sol_df, symbol_data = await load_window_data(TOP10_SOL_PORTFOLIO, start, end)

    if btc_df.empty:
        logger.error("❌ Не удалось загрузить BTCUSDT, бектест невозможен")
        return {}

    portfolio_results: List[Dict[str, Any]] = []
    total_trades = 0
    total_pnl = 0.0
    total_winning_trades = 0
    total_losing_trades = 0

    for symbol in TOP10_SOL_PORTFOLIO:
        df = symbol_data.get(symbol)
        if df is None or df.empty:
            logger.warning("⚠️ Пропускаем %s — нет данных в окне", symbol)
            continue

        try:
            backtest = AdvancedBacktest(
                initial_balance=10000.0,
                risk_per_trade=2.0,
                leverage=2.0,
            )

            # Подкладываем уже загруженные ETH/SOL, чтобы run_backtest не подтягивал текущий рынок
            backtest.eth_df = eth_df
            backtest.sol_df = sol_df

            await backtest.run_backtest(symbol, df, btc_df, days=days)
            metrics = backtest.calculate_metrics()

            result = {
                "symbol": symbol,
                "total_trades": metrics.get("total_trades", 0),
                "win_rate": metrics.get("win_rate", 0.0),
                "profit_factor": metrics.get("profit_factor", 0.0),
                "total_pnl": metrics.get("total_pnl", 0.0),
                "total_pnl_pct": metrics.get("total_return", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 0.0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                "sortino_ratio": metrics.get("sortino_ratio", 0.0),
            }
            portfolio_results.append(result)

            total_trades += result["total_trades"]
            total_pnl += result["total_pnl"]
            if result["total_trades"] > 0:
                wins = int(result["total_trades"] * result["win_rate"] / 100.0)
                total_winning_trades += wins
                total_losing_trades += result["total_trades"] - wins
        except Exception as exc:
            logger.error("❌ Ошибка бектеста для %s: %s", symbol, exc)
            portfolio_results.append(
                {
                    "symbol": symbol,
                    "error": str(exc),
                    "total_trades": 0,
                    "win_rate": 0.0,
                    "profit_factor": 0.0,
                    "total_pnl": 0.0,
                }
            )

    if not portfolio_results:
        logger.error("❌ Нет результатов бектеста по портфелю")
        return {}

    portfolio_win_rate = (total_winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0
    capital = 10000.0 * max(len(TOP10_SOL_PORTFOLIO), 1)
    total_pnl_pct = (total_pnl / capital * 100.0) if capital > 0 else 0.0

    summary: Dict[str, Any] = {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "symbols": TOP10_SOL_PORTFOLIO,
        "total_symbols": len(TOP10_SOL_PORTFOLIO),
        "total_trades": total_trades,
        "total_winning_trades": total_winning_trades,
        "total_losing_trades": total_losing_trades,
        "portfolio_win_rate": portfolio_win_rate,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "results_by_symbol": portfolio_results,
    }

    # Сохраняем отчёт
    output_file = (
        PROJECT_ROOT
        / "data"
        / "reports"
        / f"oct10_window_backtest_top10_sol_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.warning("💾 Отчёт по окну 10 октября сохранён: %s", output_file)
    return summary


async def main() -> None:
    """Точка входа скрипта."""
    summary = await run_oct_window_backtest()
    if not summary:
        print("❌ Не удалось выполнить бектест по окну 10 октября")
        return

    print("================================================================================")
    print("📊 РЕЗУЛЬТАТЫ БЕКТЕСТА (ОКНО ОКОЛО 10 ОКТЯБРЯ)")
    print("================================================================================")
    print(f"Окно: {summary['window_start']} — {summary['window_end']}")
    print(f"Монет в портфеле: {summary['total_symbols']}")
    print(f"Всего сделок: {summary['total_trades']}")
    print(f"Win Rate портфеля: {summary['portfolio_win_rate']:.2f}%")
    print(f"Общий PnL: {summary['total_pnl']:.2f} USDT")
    print(f"Общий PnL % (на портфель 10×10k): {summary['total_pnl_pct']:.2f}%")
    print("--------------------------------------------------------------------------------")
    print("По монетам:")
    print("--------------------------------------------------------------------------------")
    for res in sorted(summary["results_by_symbol"], key=lambda r: r.get("total_pnl", 0), reverse=True):
        if "error" in res:
            print(f"{res['symbol']:10s} | ❌ Ошибка: {res['error']}")
        else:
            print(
                f"{res['symbol']:10s} | "
                f"Сделок: {res['total_trades']:3d} | "
                f"WR: {res['win_rate']:5.2f}% | "
                f"PF: {res['profit_factor']:5.2f} | "
                f"PnL: {res['total_pnl']:8.2f} USDT"
            )


if __name__ == "__main__":
    asyncio.run(main())


