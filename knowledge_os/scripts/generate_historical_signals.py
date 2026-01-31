#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генерация исторических сигналов и сделок на основе простого пересечения EMA
для расширения таблиц signals_log и trades.

Использование:
    python scripts/generate_historical_signals.py --days 90 --symbols BTCUSDT ETHUSDT SOLUSDT
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import ccxt  # noqa: E402
from src.database.db import Database  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Генерация исторических сигналов (EMA-cross) для backfill")
    parser.add_argument("--days", type=int, default=120, help="Глубина истории в днях (по умолчанию 120)")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "AVAX/USDT"],
        help="Список символов Binance (формат SYMBOL/USDT)",
    )
    parser.add_argument("--amount", type=float, default=1000.0, help="Размер позиции в USDT (по умолчанию 1000)")
    parser.add_argument("--max-hold", type=int, default=12, help="Максимальное количество баров в сделке (по умолчанию 12)")
    parser.add_argument("--fee-pct", type=float, default=0.0004, help="Комиссия (по умолчанию 0.04%)")
    return parser.parse_args()


def fetch_ohlc(exchange: ccxt.Exchange, symbol: str, days: int) -> pd.DataFrame:
    since_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    all_data: List[List[float]] = []
    timeframe = "1h"
    limit = 1000
    while True:
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=limit)
        if not batch:
            break
        all_data.extend(batch)
        if len(batch) < limit:
            break
        since_ms = batch[-1][0] + 1
    if not all_data:
        raise RuntimeError(f"Не удалось получить OHLC для {symbol}")
    df = pd.DataFrame(all_data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime")
    df = df.astype(float)
    return df


def ema_cross_signals(ema_fast: pd.Series, ema_slow: pd.Series) -> Iterable[Tuple[pd.Timestamp, str]]:
    df_index = ema_fast.index
    start_idx = max(ema_fast.first_valid_index(), ema_slow.first_valid_index())
    if start_idx is None:
        return
    start_pos = df_index.get_loc(start_idx)
    prev_state = None
    for ts in df_index[start_pos:]:
        fast_val = ema_fast.loc[ts]
        slow_val = ema_slow.loc[ts]
        state = "LONG" if fast_val > slow_val else "SHORT"
        if prev_state is None:
            prev_state = state
            continue
        if state != prev_state:
            yield ts, state
        prev_state = state


def main() -> None:
    args = parse_args()
    exchange = ccxt.binance({"enableRateLimit": True})
    amount_usd = float(args.amount)
    fee_pct = float(args.fee_pct)
    max_hold = max(1, int(args.max_hold))

    db = Database()
    inserted_signals = inserted_trades = 0
    skipped = 0

    with db.get_lock():
        for symbol in args.symbols:
            try:
                df = fetch_ohlc(exchange, symbol, args.days)
            except Exception as exc:  # noqa: BLE001
                print(f"⚠️ Не удалось получить данные для {symbol}: {exc}")
                continue

            ema_fast = df["close"].ewm(span=21, adjust=False).mean()
            ema_slow = df["close"].ewm(span=55, adjust=False).mean()
            crosses = list(ema_cross_signals(ema_fast, ema_slow))
            if not crosses:
                print(f"ℹ️ Нет пересечений EMA для {symbol}")
                continue

            for entry_ts, direction in crosses:
                entry_price = float(df.loc[entry_ts]["close"])
                entry_time_iso = entry_ts.isoformat()

                entry_idx = df.index.get_loc(entry_ts)
                exit_idx = None
                for future_idx in range(entry_idx + 1, min(entry_idx + 1 + max_hold, len(df))):
                    future_ts = df.index[future_idx]
                    future_price = float(df.iloc[future_idx]["close"])

                    fast_val = ema_fast.loc[future_ts]
                    slow_val = ema_slow.loc[future_ts]
                    if direction == "LONG":
                        # выход если fast < slow или достигнута минимальная прибыль 0.5%
                        if fast_val < slow_val:
                            exit_idx = future_idx
                            break
                        if (future_price - entry_price) / entry_price >= 0.005:
                            exit_idx = future_idx
                            break
                    else:
                        if fast_val > slow_val:
                            exit_idx = future_idx
                            break
                        if (entry_price - future_price) / entry_price >= 0.005:
                            exit_idx = future_idx
                            break

                if exit_idx is None:
                    continue

                exit_ts = df.index[exit_idx]
                exit_price = float(df.iloc[exit_idx]["close"])
                exit_time_iso = exit_ts.isoformat()

                if direction == "LONG":
                    gross_pct = (exit_price - entry_price) / entry_price * 100.0
                    stop_price = entry_price * 0.98
                else:
                    gross_pct = (entry_price - exit_price) / entry_price * 100.0
                    stop_price = entry_price * 1.02

                pnl_usd = amount_usd * gross_pct / 100.0
                fees_usd = amount_usd * fee_pct * 2  # вход + выход
                net_pnl_usd = pnl_usd - fees_usd
                pnl_percent = gross_pct - fee_pct * 200.0
                qty = amount_usd / entry_price if entry_price else 0.0

                if net_pnl_usd > 0:
                    result_label = "TP2"
                    exit_reason = "TP2"
                    tp1_hit = tp2_hit = 1
                    sl_hit = 0
                elif net_pnl_usd < 0:
                    result_label = "SL"
                    exit_reason = "SL"
                    tp1_hit = tp2_hit = 0
                    sl_hit = 1
                else:
                    result_label = "BE"
                    exit_reason = "BREAKEVEN"
                    tp1_hit = tp2_hit = sl_hit = 0

                tp_price = entry_price * (1 + 0.01 if direction == "LONG" else 1 - 0.01)

                try:
                    db.conn.execute(
                        """
                        INSERT INTO signals_log(
                            symbol, entry, stop, tp1, tp2,
                            entry_time, exit_time, result, net_profit,
                            qty_added, qty_closed, user_id,
                            trade_mode, entry_amount_usd, leverage_used, risk_pct_used,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            symbol.replace("/", ""),
                            entry_price,
                            stop_price,
                            tp_price,
                            tp_price,
                            entry_time_iso,
                            exit_time_iso,
                            result_label,
                            net_pnl_usd,
                            qty,
                            qty,
                            "backfill_ma",
                            "backfill",
                            amount_usd,
                            1.0,
                            2.0,
                            entry_time_iso,
                        ),
                    )
                    inserted_signals += 1
                except Exception as exc:  # noqa: BLE001
                    print(f"⚠️ signals_log skip ({symbol} {entry_time_iso}): {exc}")
                    skipped += 1
                    continue

                try:
                    signal_key = f"EMA_{symbol.replace('/', '')}_{entry_time_iso}"
                    db.conn.execute(
                        """
                        INSERT INTO trades(
                            symbol, direction, entry_price, exit_price,
                            entry_time, exit_time, duration_minutes,
                            quantity, position_size_usdt, leverage, risk_percent,
                            pnl_usd, pnl_percent, fees_usd, net_pnl_usd,
                            exit_reason, tp1_price, tp2_price, sl_price,
                            tp1_hit, tp2_hit, sl_hit,
                            signal_key, user_id, trade_mode, filter_mode,
                            confidence, dca_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            symbol.replace("/", ""),
                            direction,
                            entry_price,
                            exit_price,
                            entry_time_iso,
                            exit_time_iso,
                            (exit_idx - entry_idx) * 60.0,
                            qty,
                            amount_usd,
                            1.0,
                            2.0,
                            pnl_usd,
                            pnl_percent,
                            fees_usd,
                            net_pnl_usd,
                            exit_reason,
                            tp_price,
                            tp_price,
                            stop_price,
                            tp1_hit,
                            tp2_hit,
                            sl_hit,
                            signal_key,
                            "backfill_ma",
                            "backfill",
                            "soft",
                            None,
                            0,
                        ),
                    )
                    inserted_trades += 1
                except Exception as exc:  # noqa: BLE001
                    print(f"⚠️ trades skip ({symbol} {entry_time_iso}): {exc}")
                    skipped += 1
                    continue

    db.conn.commit()

    print(f"✅ Добавлено сигналов: {inserted_signals}, сделок: {inserted_trades}")
    print(f"↩️ Пропущено (ошибки): {skipped}")


if __name__ == "__main__":
    main()

