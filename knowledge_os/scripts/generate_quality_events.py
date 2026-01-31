#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генерация событий FalseBreakout/MTF на исторических данных Binance.

Позволяет быстро наполнить таблицы `false_breakout_events` и
`mtf_confirmation_events` для анализа pass-rate. Поддерживаются
несколько символов и выбор режима тестирования (test_run=1).
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.db import Database  # noqa: E402
from false_breakout_detector import get_false_breakout_detector  # noqa: E402
from market_regime_detector import get_regime_detector  # noqa: E402
from ohlc_utils import get_ohlc_binance_sync  # noqa: E402
from signal_live import _run_mtf_confirmation_with_logging  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Генерация событий FBD/MTF для контроля качества")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTCUSDT"],
        help="Список символов (Binance spot, формата BTCUSDT)",
    )
    parser.add_argument("--interval", default="1h", help="Интервал свечей Binance (по умолчанию 1h)")
    parser.add_argument(
        "--limit",
        type=int,
        default=240,
        help="Количество свечей на символ (по умолчанию 240 ≈ 10 дней для 1h)",
    )
    parser.add_argument(
        "--directions",
        nargs="+",
        default=["BUY"],
        help="Список направлений для FBD (BUY/SELL/LONG/SHORT)",
    )
    parser.add_argument(
        "--test-run",
        type=int,
        choices=(0, 1),
        default=1,
        help="Помечать события как тестовые (1) или как реальные (0)",
    )
    parser.add_argument(
        "--mtf-directions",
        nargs="+",
        default=["BUY", "SELL"],
        help="Направления для запуска MTF Confirmation",
    )
    return parser


async def process_symbol(
    symbol: str,
    interval: str,
    limit: int,
    directions: Iterable[str],
    mtf_directions: Iterable[str],
    test_run: int,
) -> tuple[int, int]:
    raw = get_ohlc_binance_sync(symbol, interval=interval, limit=limit)
    if not raw:
        print(f"⚠️ Не удалось получить OHLC данные для {symbol}")
        return 0, 0

    df = pd.DataFrame(raw)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df[["datetime", "open", "high", "low", "close", "volume"]].set_index("datetime")

    regime_detector = get_regime_detector()
    regime_info = regime_detector.detect_regime(df.reset_index())
    regime_context = {
        "regime": regime_info.get("regime"),
        "regime_confidence": regime_info.get("confidence"),
    }

    detector = get_false_breakout_detector()
    fbd_windows = 0
    for i in range(40, len(df)):
        window = df.iloc[i - 40 : i].copy()
        if len(window) < 40:
            continue
        for direction in directions:
            await detector.analyze_breakout_quality(
                window.reset_index(drop=True),
                symbol,
                direction.upper(),
                regime_context,
            )
            fbd_windows += 1

    mtf_events = 0
    for direction in mtf_directions:
        await _run_mtf_confirmation_with_logging(symbol, direction.upper(), regime_context)
        mtf_events += 1

    db = Database()
    with db.get_lock():
        db.cursor.execute(
            """
            UPDATE false_breakout_events
            SET test_run = ?
            WHERE datetime(created_at) >= datetime('now', '-10 minutes')
              AND symbol = ?
            """,
            (test_run, symbol),
        )
        db.cursor.execute(
            """
            UPDATE mtf_confirmation_events
            SET test_run = ?
            WHERE datetime(created_at) >= datetime('now', '-10 minutes')
              AND symbol = ?
            """,
            (test_run, symbol),
        )
        db.conn.commit()

    return fbd_windows, mtf_events


async def main() -> None:
    args = build_arg_parser().parse_args()
    total_fbd = total_mtf = 0
    for symbol in args.symbols:
        fbd_windows, mtf_events = await process_symbol(
            symbol,
            args.interval,
            args.limit,
            args.directions,
            args.mtf_directions,
            args.test_run,
        )
        total_fbd += fbd_windows
        total_mtf += mtf_events
        print(f"✅ {symbol}: добавлено FBD окон={fbd_windows}, MTF вызовов={mtf_events}, test_run={args.test_run}")

    print(f"Итого: FBD окон={total_fbd}, MTF событий={total_mtf}")


if __name__ == "__main__":
    asyncio.run(main())

