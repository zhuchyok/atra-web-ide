#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Создаёт записи в таблице trades на основе сигналов,
импортированных из паттернов (user_id='backfill_patterns').

Использование:
    python scripts/backfill_trades_from_signals.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.db import Database


def detect_direction(entry: float, stop: Optional[float]) -> str:
    if stop is None:
        return "LONG"
    return "LONG" if stop < entry else "SHORT"


def map_hits(result: str) -> tuple[int, int, int, str]:
    res = (result or "").upper()
    if res.startswith("TP2"):
        return 1, 1, 0, "TP2"
    if res.startswith("TP1"):
        return 1, 0, 0, "TP1"
    if res.startswith("SL"):
        return 0, 0, 1, "SL"
    if res.startswith("BE"):
        return 0, 0, 0, "BREAKEVEN"
    return 0, 0, 0, "MANUAL"


def main() -> None:
    db = Database()
    inserted = skipped = 0
    with db.get_lock():
        rows = db.conn.execute(
            """
            SELECT
                id, symbol, entry, stop, entry_time, exit_time,
                net_profit, entry_amount_usd, trade_mode, result,
                leverage_used, risk_pct_used
            FROM signals_log
            WHERE user_id = 'backfill_patterns'
            """
        ).fetchall()

        for row in rows:
            signal_id, symbol, entry, stop, entry_time, exit_time, net_profit, entry_amount_usd, trade_mode, result, leverage, risk_pct = row

            if not symbol or entry is None or entry_amount_usd is None:
                skipped += 1
                continue

            # Проверяем, существует ли уже trade для этого сигнала
            signal_key = f"PATTERN_SIGNAL_{signal_id}"
            existing = db.conn.execute(
                "SELECT 1 FROM trades WHERE signal_key = ?", (signal_key,)
            ).fetchone()
            if existing:
                skipped += 1
                continue

            direction = detect_direction(entry, stop)
            amount = float(entry_amount_usd)
            quantity = amount / entry if entry else 0.0
            pnl_usd = float(net_profit or 0.0)
            pnl_percent = (pnl_usd / amount * 100.0) if amount else 0.0

            if direction == "LONG":
                exit_price = entry * (1 + pnl_percent / 100.0)
                sl_price = stop or entry * (1 - (risk_pct or 2.0) / 100.0)
            else:
                exit_price = entry * (1 - pnl_percent / 100.0)
                sl_price = stop or entry * (1 + (risk_pct or 2.0) / 100.0)

            tp1_hit, tp2_hit, sl_hit, exit_reason = map_hits(result or "")

            try:
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
                        symbol,
                        direction,
                        entry,
                        exit_price,
                        entry_time,
                        exit_time,
                        60.0,
                        quantity,
                        amount,
                        float(leverage or 1.0),
                        float(risk_pct or 2.0),
                        pnl_usd,
                        pnl_percent,
                        0.0,
                        pnl_usd,
                        exit_reason,
                        None,
                        None,
                        sl_price,
                        tp1_hit,
                        tp2_hit,
                        sl_hit,
                        signal_key,
                        "backfill_patterns",
                        trade_mode or "backfill",
                        "soft",
                        None,
                        0,
                    ),
                )
                inserted += 1
            except Exception as exc:  # noqa: BLE001
                print(f"⚠️ trades skip (signal {signal_id}): {exc}")
                skipped += 1
                continue

        db.conn.commit()

    print(f"✅ Добавлено записей trades: {inserted}")
    print(f"↩️ Пропущено: {skipped}")


if __name__ == "__main__":
    main()

