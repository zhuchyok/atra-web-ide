#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Импорт исторических данных из ai_learning_data/trading_patterns.json
в таблицы signals_log и trades.

Использование:
    python scripts/backfill_from_patterns.py --days 90 --amount 1000

Параметры:
    --days      Количество дней истории от текущего момента (по умолчанию 90)
    --amount    Базовый размер позиции в USDT (по умолчанию 1000)
    --limit     Максимальное число записей для импорта (по умолчанию 5000)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from db import Database
except ModuleNotFoundError:  # pragma: no cover - fallback for CLI invocation
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from db import Database


def parse_args() -> argparse.Namespace:
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(description="Backfill signals_log/trades из паттернов ИИ")
    parser.add_argument("--days", type=int, default=90, help="Глубина истории в днях (по умолчанию 90)")
    parser.add_argument(
        "--amount",
        type=float,
        default=1000.0,
        help="Базовый размер позиции в USDT (по умолчанию 1000)",
    )
    parser.add_argument("--limit", type=int, default=5000, help="Максимальное число записей для импорта")
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("ai_learning_data/trading_patterns.json"),
        help="Путь к JSON с паттернами",
    )
    return parser.parse_args()


def map_result(result: Optional[str], profit_pct: float) -> tuple[str, str, int, int, int]:
    """
    Возвращает (result_label, exit_reason, tp1_hit, tp2_hit, sl_hit)
    """
    result = (result or "").upper()
    if profit_pct > 0:
        return ("TP2", "TP2", 1, 1, 0)
    if profit_pct < 0:
        return ("SL", "SL", 0, 0, 1)
    if result == "WIN":
        return ("TP2", "TP2", 1, 1, 0)
    if result == "LOSS":
        return ("SL", "SL", 0, 0, 1)
    return ("MANUAL", "MANUAL", 0, 0, 0)


def map_direction(signal_type: Optional[str]) -> str:
    """Преобразует тип сигнала к направлению LONG/SHORT."""
    st = (signal_type or "").upper()
    if st in ("SHORT", "SELL"):
        return "SHORT"
    return "LONG"


def parse_timestamp(ts: str) -> Optional[datetime]:
    """Преобразует строку временной метки в объект datetime."""
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def main() -> None:
    """Импортирует данные паттернов в таблицы signals_log и trades."""
    args = parse_args()
    if not args.file.exists():
        raise SystemExit(f"Файл {args.file} не найден")

    with args.file.open("r", encoding="utf-8") as fh:
        patterns = json.load(fh)

    since_dt = datetime.utcnow() - timedelta(days=max(1, args.days))

    db = Database()
    inserted_signals = inserted_trades = skipped = 0
    duplicate_warnings = 0

    with db.get_lock():
        for pattern in patterns:
            if inserted_signals >= args.limit:
                break

            ts_raw = pattern.get("timestamp")
            timestamp = parse_timestamp(ts_raw)
            if not timestamp or timestamp < since_dt:
                skipped += 1
                continue

            entry_price = float(pattern.get("entry_price") or 0.0)
            if entry_price <= 0:
                skipped += 1
                continue

            profit_pct = float(pattern.get("profit_pct") or 0.0)
            risk_pct = float(pattern.get("risk_pct") or 2.0)
            leverage = float(pattern.get("leverage") or 1.0)
            symbol = (pattern.get("symbol") or "").upper()
            if not symbol:
                skipped += 1
                continue

            direction = map_direction(pattern.get("signal_type"))
            result_label, exit_reason, tp1_hit, tp2_hit, sl_hit = map_result(pattern.get("result"), profit_pct)

            entry_amount = float(args.amount)
            quantity = entry_amount / entry_price if entry_price else 0.0
            pnl_usd = entry_amount * (profit_pct / 100.0)
            fees_usd = entry_amount * 0.0004  # условные 0.04%
            net_pnl_usd = pnl_usd - fees_usd

            duration = 60.0  # 1 час
            exit_time = timestamp + timedelta(minutes=duration)

            if direction == "LONG":
                exit_price = entry_price * (1 + profit_pct / 100.0)
                stop_price = entry_price * (1 - risk_pct / 100.0)
            else:
                exit_price = entry_price * (1 - profit_pct / 100.0)
                stop_price = entry_price * (1 + risk_pct / 100.0)

            tp2_price = (
                entry_price * (1 + profit_pct / 100.0)
                if direction == "LONG"
                else entry_price * (1 - profit_pct / 100.0)
            )
            tp1_price = tp2_price

            signal_key = f"PATTERN_{symbol}_{timestamp.isoformat()}"

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
                        symbol,
                        entry_price,
                        stop_price,
                        tp1_price,
                        tp2_price,
                        timestamp.isoformat(timespec="seconds"),
                        exit_time.isoformat(timespec="seconds"),
                        result_label,
                        net_pnl_usd,
                        quantity,
                        quantity,
                        "backfill_patterns",
                        "backfill",
                        entry_amount,
                        leverage,
                        risk_pct,
                        timestamp.isoformat(timespec="seconds"),
                    ),
                )
                inserted_signals += 1
            except Exception as exc:
                if "UNIQUE constraint failed" in str(exc):
                    duplicate_warnings += 1
                    if duplicate_warnings <= 20:
                        print(f"↩️ signals_log duplicate ({symbol} {timestamp}): {exc}")
                else:
                    print(f"⚠️ signals_log skip ({symbol} {timestamp}): {exc}")
                skipped += 1
                continue

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
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        direction,
                        entry_price,
                        exit_price,
                        timestamp.isoformat(timespec="seconds"),
                        exit_time.isoformat(timespec="seconds"),
                        duration,
                        quantity,
                        entry_amount,
                        leverage,
                        risk_pct,
                        pnl_usd,
                        profit_pct,
                        fees_usd,
                        net_pnl_usd,
                        exit_reason,
                        tp1_price,
                        tp2_price,
                        stop_price,
                        tp1_hit,
                        tp2_hit,
                        sl_hit,
                        signal_key,
                        "backfill_patterns",
                        "backfill",
                        "soft",
                        None,
                        0,
                    ),
                )
                inserted_trades += 1
            except Exception as exc:
                print(f"⚠️ trades skip ({symbol} {timestamp}): {exc}")
                skipped += 1
                continue

        db.conn.commit()

    print(f"✅ Добавлено записей: signals_log={inserted_signals}, trades={inserted_trades}")
    print(f"↩️ Пропущено (ошибки/фильтр) : {skipped}")


if __name__ == "__main__":
    main()
