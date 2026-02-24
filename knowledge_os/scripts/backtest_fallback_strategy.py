#!/usr/bin/env python3
"""
Бэктест fallback стратегии momentum + liquidity (15m).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if TYPE_CHECKING:
    from fallback_strategy import FallbackConfig, FallbackMomentumStrategy


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки для запуска бэктеста fallback-стратегии."""
    parser = argparse.ArgumentParser(
        description="Бэктест fallback стратегии Momentum+Liquidity (15m)"
    )
    parser.add_argument(
        "--symbols", nargs="*", default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
    )
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument(
        "--horizon", type=int, default=16, help="Количество свечей 15m для оценки исхода сделки"
    )
    parser.add_argument("--entry-amount-usd", type=float, default=100.0)
    parser.add_argument("--json", action="store_true", help="Выводить отчёт в формате JSON")
    return parser.parse_args()


def main() -> None:
    """Запускает бэктест fallback-стратегии и выводит агрегированный отчёт."""
    from fallback_strategy import (  # pylint: disable=import-outside-toplevel
        FallbackConfig,
        FallbackMomentumStrategy,
    )

    args = parse_args()
    config = FallbackConfig(symbols=[s.upper() for s in args.symbols], days=args.days)
    strategy = FallbackMomentumStrategy(config)

    report = strategy.backtest(
        days=args.days,
        max_horizon_bars=args.horizon,
        entry_amount_usd=args.entry_amount_usd,
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    totals = report["totals"]
    print("📊 Бэктест fallback стратегии (Momentum + Liquidity)")
    print(f"Период: {args.days} дней | Сигналов: {totals['signals']}")
    print(
        f"P&L: {totals['pnl_usd']:+.2f} USDT "
        f"(Sharpe≈{totals['sharpe']:.2f}, MaxDD≈{totals['max_drawdown_pct']:.2f}%)"
    )
    print(
        f"TP1: {totals['tp1']} | TP2: {totals['tp2']} | SL: {totals['sl']} | HOLD: {totals['hold']}"
    )

    if report["symbols"]:
        print("\nДетали по символам:")
        for symbol, stats in report["symbols"].items():
            print(
                f"• {symbol}: sig={stats['signals']}, PnL={stats['pnl_usd']:+.2f} USDT, "
                f"WinRate={stats['win_rate']:.1f}%, AvgRet={stats['avg_return_pct'] * 100:.2f}%"
            )


if __name__ == "__main__":
    main()
