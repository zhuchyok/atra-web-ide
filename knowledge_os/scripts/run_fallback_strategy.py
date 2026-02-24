#!/usr/bin/env python3
"""
Запуск fallback 15m стратегии и вывод сигналов в консоль.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fallback_strategy import FallbackConfig, FallbackMomentumStrategy  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Запуск fallback стратегии Momentum+Liquidity (15m)"
    )
    parser.add_argument(
        "--symbols", nargs="*", default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT"]
    )
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--json", action="store_true", help="Выводить результаты в формате JSON")
    parser.add_argument("--save", action="store_true", help="Сохранить сигналы в БД (signals_log)")
    parser.add_argument("--user-id", type=int, default=0, help="ID пользователя (по умолчанию 0)")
    parser.add_argument(
        "--entry-amount-usd", type=float, default=100.0, help="Размер позиции для записи в БД (USD)"
    )
    parser.add_argument(
        "--trade-mode",
        default="backfill",
        help="Режим торговли для записи в БД (spot/futures/backfill)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = FallbackConfig(symbols=[s.upper() for s in args.symbols], days=args.days)
    strategy = FallbackMomentumStrategy(config)

    signals = strategy.run()
    saved_count = 0
    if args.save and signals:
        saved_count = strategy.save_signals(
            signals,
            user_id=args.user_id,
            entry_amount_usd=args.entry_amount_usd,
            trade_mode=args.trade_mode,
        )
    if args.json:
        print(
            json.dumps(
                {
                    "generated_at": datetime.utcnow().isoformat(),
                    "signals": signals,
                    "saved": saved_count,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if not signals:
            print("⚠️ Нет сигналов по заданным условиям.")
        for sig in signals:
            print(
                f"✅ {sig['symbol']} LONG @ {sig['entry_price']:.4f} | "
                f"TP1 {sig['tp1_price']:.4f} | TP2 {sig['tp2_price']:.4f} | "
                f"SL {sig['sl_price']:.4f} | volume_ratio={sig['volume_ratio']:.2f}"
            )
        if args.save:
            print(f"💾 Сохранено записей: {saved_count}")


if __name__ == "__main__":
    main()
