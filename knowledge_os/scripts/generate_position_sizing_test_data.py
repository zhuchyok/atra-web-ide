#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генерация тестовых событий position_sizing и связанных сделок.

Скрипт создаёт синтетические записи в таблицах `position_sizing_events`
и `trades`, чтобы можно было протестировать отчётность adaptive vs baseline
без ожидания живых сигналов.
"""

from __future__ import annotations

import argparse
import logging
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from src.shared.utils.datetime_utils import get_utc_now

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.db import Database  # noqa: E402

logger = logging.getLogger(__name__)


def _parse_symbols(value: str) -> List[str]:
    parts = [item.strip().upper() for item in value.split(",") if item.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("Не задан список символов")
    return parts


def _simulate_event(
    db: Database,
    symbol: str,
    user_id: str,
    trade_mode: str,
    filter_mode: str,
    base_amount: float,
    base_risk_pct: float,
    leverage: float,
    entry_dt: datetime,
) -> None:
    direction = random.choice(["LONG", "SHORT"])
    baseline_amount_usd = base_amount

    # ИИ и адаптивные множители
    ai_multiplier = random.uniform(0.85, 1.35)
    regime_multiplier = random.uniform(0.80, 1.20)
    correlation_multiplier = random.uniform(0.85, 1.10)
    adaptive_multiplier = random.uniform(0.80, 1.15)
    risk_adjustment_multiplier = random.uniform(0.85, 1.05)

    ai_amount_usd = baseline_amount_usd * ai_multiplier
    after_regime = ai_amount_usd * regime_multiplier
    after_correlation = after_regime * correlation_multiplier
    final_amount_usd = after_correlation * adaptive_multiplier * risk_adjustment_multiplier

    ai_risk_pct = base_risk_pct * ai_multiplier

    # Сохраняем событие position_sizing
    signal_token = f"TESTSIZE_{symbol}_{entry_dt.strftime('%Y%m%d%H%M%S')}"
    entry_time_iso = entry_dt.isoformat(timespec="seconds")

    db.cursor.execute(
        """
        INSERT INTO position_sizing_events(
            symbol, direction, entry_time, signal_token, user_id,
            trade_mode, signal_price, baseline_amount_usd, ai_amount_usd,
            regime_multiplier, after_regime_amount_usd,
            correlation_multiplier, after_correlation_amount_usd,
            adaptive_multiplier, after_adaptive_amount_usd,
            risk_adjustment_multiplier, final_amount_usd,
            base_risk_pct, ai_risk_pct, leverage,
            regime, regime_confidence, quality_score, composite_score,
            pattern_confidence, adaptive_reason, adaptive_components
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            symbol,
            direction,
            entry_time_iso,
            signal_token,
            user_id,
            trade_mode,
            100.0,
            baseline_amount_usd,
            ai_amount_usd,
            regime_multiplier,
            after_regime,
            correlation_multiplier,
            after_correlation,
            adaptive_multiplier,
            after_correlation * adaptive_multiplier,
            risk_adjustment_multiplier,
            final_amount_usd,
            base_risk_pct,
            ai_risk_pct,
            leverage,
            random.choice(["BULL_TREND", "BEAR_TREND", "LOW_VOL_RANGE"]),
            random.uniform(0.4, 0.8),
            random.uniform(0.5, 0.9),
            random.uniform(0.4, 0.8),
            random.uniform(0.4, 0.8),
            "adaptive-test",
            None,
        ),
    )

    # Симулируем сделку под это событие
    entry_price = random.uniform(0.8, 1.2) * 100.0
    profit_pct = random.uniform(-0.02, 0.05)

    if direction == "LONG":
        exit_price = entry_price * (1 + profit_pct)
        sl_price = entry_price * (1 - base_risk_pct / 100)
    else:
        exit_price = entry_price * (1 - profit_pct)
        sl_price = entry_price * (1 + base_risk_pct / 100)

    quantity = final_amount_usd / entry_price if entry_price else 0.0
    pnl_usd = final_amount_usd * profit_pct
    fees_usd = final_amount_usd * 0.0008
    net_pnl_usd = pnl_usd - fees_usd

    tp1_hit = 1 if net_pnl_usd > 0 else 0
    tp2_hit = 1 if net_pnl_usd > 0.5 * final_amount_usd * 0.01 else 0
    sl_hit = 1 if net_pnl_usd < 0 else 0
    exit_reason = "TP" if net_pnl_usd >= 0 else "SL"

    exit_dt = entry_dt + timedelta(minutes=random.randint(30, 180))
    exit_time_iso = exit_dt.isoformat(timespec="seconds")

    db.cursor.execute(
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
            entry_price,
            exit_price,
            entry_time_iso,
            exit_time_iso,
            (exit_dt - entry_dt).total_seconds() / 60.0,
            quantity,
            final_amount_usd,
            leverage,
            ai_risk_pct,
            pnl_usd,
            profit_pct * 100,
            fees_usd,
            net_pnl_usd,
            exit_reason,
            entry_price * (1 + 0.01) if direction == "LONG" else entry_price * (1 - 0.01),
            entry_price * (1 + 0.02) if direction == "LONG" else entry_price * (1 - 0.02),
            sl_price,
            tp1_hit,
            tp2_hit,
            sl_hit,
            signal_token,
            user_id,
            trade_mode,
            filter_mode,
            None,
            0,
        ),
    )


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        logger.debug("Не удалось распарсить timestamp: %s", value)
        return None


def _generate_from_real_signals(
    db: Database,
    days: int,
    user_id: str,
    fallback_trade_mode: str,
    default_amount: float,
    base_risk_pct: float,
    leverage: float,
) -> tuple[int, int]:
    """Генерирует события на основе реальных сигналов из БД."""
    since_dt = get_utc_now() - timedelta(days=max(1, days))
    inserted_events = 0

    with db.get_lock():
        try:
            db.conn.execute("BEGIN")
            rows = db.conn.execute(
                """
                SELECT
                    symbol,
                    entry,
                    tp1,
                    tp2,
                    entry_time,
                    entry_amount_usd,
                    trade_mode,
                    risk_pct_used,
                    leverage_used
                FROM signals_log
                WHERE entry_time IS NOT NULL
                """
            ).fetchall()
        except sqlite3.Error as exc:
            logger.error("Не удалось прочитать signals_log: %s", exc)
            return 0, 0

        for row in rows:
            symbol = (row[0] or "").upper()
            if not symbol:
                continue

            entry_dt = _parse_timestamp(row[4])
            if entry_dt is None:
                continue
            if entry_dt.tzinfo:
                entry_dt = entry_dt.astimezone(timezone.utc).replace(tzinfo=None)
            if entry_dt < since_dt:
                continue

            entry_price = float(row[1] or 0.0)
            tp1_price = float(row[2] or 0.0)
            direction = "LONG"
            try:
                if entry_price and tp1_price and tp1_price < entry_price:
                    direction = "SHORT"
            except (TypeError, ValueError):
                pass

            entry_amount = float(row[5] or default_amount or 0.0) or default_amount
            trade_mode = (row[6] or fallback_trade_mode or "futures").lower()
            risk_pct = float(row[7] or base_risk_pct)
            leverage_val = float(row[8] or leverage)

            signal_token = f"REAL_{symbol}_{entry_dt.strftime('%Y%m%d%H%M%S')}"
            entry_time_iso = entry_dt.isoformat(timespec="seconds")

            try:
                db.cursor.execute(
                    """
                    INSERT INTO position_sizing_events(
                        symbol, direction, entry_time, signal_token, user_id,
                        trade_mode, signal_price, baseline_amount_usd, ai_amount_usd,
                        regime_multiplier, after_regime_amount_usd,
                        correlation_multiplier, after_correlation_amount_usd,
                        adaptive_multiplier, after_adaptive_amount_usd,
                        risk_adjustment_multiplier, final_amount_usd,
                        base_risk_pct, ai_risk_pct, leverage,
                        regime, regime_confidence, quality_score, composite_score,
                        pattern_confidence, adaptive_reason, adaptive_components
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        direction,
                        entry_time_iso,
                        signal_token,
                        user_id,
                        trade_mode,
                        entry_price,
                        entry_amount,
                        entry_amount,
                        1.0,
                        entry_amount,
                        1.0,
                        entry_amount,
                        1.0,
                        entry_amount,
                        1.0,
                        entry_amount,
                        risk_pct,
                        risk_pct,
                        leverage_val,
                        None,
                        None,
                        None,
                        None,
                        None,
                        "real-signal",
                        None,
                    ),
                )
                inserted_events += 1
            except sqlite3.Error as exc:
                logger.debug("Не удалось вставить позиционное событие (%s): %s", signal_token, exc)
                continue

        try:
            db.conn.commit()
        except sqlite3.Error as exc:
            logger.error("Ошибка фиксации транзакции: %s", exc)
            db.conn.rollback()
            return inserted_events, 0

    return inserted_events, 0
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Генерация тестовых событий position sizing и связанных сделок"
    )
    parser.add_argument(
        "--symbols",
        type=_parse_symbols,
        default="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,AVAXUSDT",
        help="Список символов через запятую (по умолчанию 5 USDT пар)",
    )
    parser.add_argument(
        "--user-id",
        default="test_sizing",
        help="Идентификатор пользователя для тестовых записей (по умолчанию test_sizing)",
    )
    parser.add_argument(
        "--trade-mode",
        default="futures",
        help="Режим торговли для тестовых записей (по умолчанию futures)",
    )
    parser.add_argument(
        "--filter-mode",
        default="soft",
        help="Filter mode для сделок (по умолчанию soft)",
    )
    parser.add_argument(
        "--base-amount",
        type=float,
        default=25.0,
        help="Базовый размер позиции в USD (по умолчанию 25)",
    )
    parser.add_argument(
        "--base-risk-pct",
        type=float,
        default=2.0,
        help="Базовый риск на сделку в %% (по умолчанию 2.0)",
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=5.0,
        help="Леверидж для тестовых сделок (по умолчанию 5.0)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Период (в днях) для выборки реальных сигналов (по умолчанию 7)",
    )
    parser.add_argument(
        "--real-signals",
        action="store_true",
        help="Использовать реальные сигналы из БД вместо синтетических данных",
    )

    args = parser.parse_args()

    db = Database()
    now = get_utc_now()

    inserted_events = 0
    inserted_trades = 0

    symbols = args.symbols
    if isinstance(symbols, str):
        symbols = _parse_symbols(symbols)

    if args.real_signals:
        inserted_events, inserted_trades = _generate_from_real_signals(
            db=db,
            days=args.days,
            user_id=args.user_id,
            fallback_trade_mode=args.trade_mode,
            default_amount=args.base_amount,
            base_risk_pct=args.base_risk_pct,
            leverage=args.leverage,
        )
    else:
        with db.get_lock():
            for idx, symbol in enumerate(symbols):
                entry_dt = now - timedelta(minutes=idx * 7)
                _simulate_event(
                    db=db,
                    symbol=symbol,
                    user_id=args.user_id,
                    trade_mode=args.trade_mode,
                    filter_mode=args.filter_mode,
                    base_amount=args.base_amount,
                    base_risk_pct=args.base_risk_pct,
                    leverage=args.leverage,
                    entry_dt=entry_dt,
                )
                inserted_events += 1
                inserted_trades += 1

            db.conn.commit()

    print(f"✅ Добавлено событий сайзинга: {inserted_events}")
    print(f"✅ Добавлено связанных сделок: {inserted_trades}")
    print(f"ℹ️ user_id='{args.user_id}', режим={args.trade_mode}, база={args.base_amount} USD")


if __name__ == "__main__":
    main()

