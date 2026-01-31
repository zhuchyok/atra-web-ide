#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Экспорт датасета для backtest replay (baseline vs adaptive).

Собирает события `position_sizing_events`, подбирает к ним ближайшие записи
из `signals_log` и `trades`, рассчитывает вспомогательные метрики и сохраняет
результаты в CSV для последующего сравнения baseline/adaptive.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.db import Database  # noqa: E402

# =============================================================================
# Вспомогательные функции
# =============================================================================


def _load_events(conn: sqlite3.Connection, hours: int) -> pd.DataFrame:
    query = """
        SELECT
            id AS event_id,
            created_at AS event_created_at,
            entry_time AS event_entry_time,
            symbol,
            direction,
            trade_mode AS event_trade_mode,
            baseline_amount_usd,
            ai_amount_usd,
            final_amount_usd,
            base_risk_pct,
            ai_risk_pct,
            leverage,
            regime,
            regime_confidence,
            correlation_multiplier,
            adaptive_multiplier,
            risk_adjustment_multiplier
        FROM position_sizing_events
        WHERE datetime(created_at) >= datetime('now', ?)
        ORDER BY symbol ASC, event_entry_time ASC
    """
    df = pd.read_sql_query(query, conn, params=[f"-{hours} hours"])
    if df.empty:
        return df
    df["event_entry_dt"] = pd.to_datetime(df["event_entry_time"], errors="coerce", utc=True).dt.tz_convert(None)
    df["event_created_dt"] = pd.to_datetime(df["event_created_at"], errors="coerce", utc=True).dt.tz_convert(None)
    df = df.dropna(subset=["event_entry_dt"])
    return df.sort_values(["symbol", "event_entry_dt"]).reset_index(drop=True)


def _load_signals(conn: sqlite3.Connection, hours: int, tolerance_minutes: int) -> pd.DataFrame:
    # Берём чуть больше окна, чтобы охватить сигналы, попадающие в допуск
    extra_hours = hours + max(1, tolerance_minutes // 60 + 1)
    query = """
        SELECT
            id AS signal_id,
            symbol,
            entry_time AS signal_entry_time,
            entry AS signal_entry_price,
            stop AS signal_stop_price,
            tp1 AS signal_tp1_price,
            tp2 AS signal_tp2_price,
            result AS signal_result,
            net_profit AS signal_net_profit,
            entry_amount_usd AS signal_entry_amount_usd,
            risk_pct_used AS signal_risk_pct,
            leverage_used AS signal_leverage,
            trade_mode AS signal_trade_mode,
            created_at AS signal_created_at
        FROM signals_log
        WHERE datetime(entry_time) >= datetime('now', ?)
        ORDER BY symbol ASC, signal_entry_time ASC
    """
    df = pd.read_sql_query(query, conn, params=[f"-{extra_hours} hours"])
    if df.empty:
        return df
    df["signal_entry_dt"] = pd.to_datetime(df["signal_entry_time"], errors="coerce", utc=True).dt.tz_convert(None)
    df["signal_created_dt"] = pd.to_datetime(df["signal_created_at"], errors="coerce", utc=True).dt.tz_convert(None)
    df = df.dropna(subset=["signal_entry_dt"])
    return df.sort_values(["symbol", "signal_entry_dt"]).reset_index(drop=True)


def _load_trades(conn: sqlite3.Connection, hours: int, tolerance_minutes: int) -> pd.DataFrame:
    extra_hours = hours + max(1, tolerance_minutes // 60 + 1)
    query = """
        SELECT
            id AS trade_id,
            symbol,
            direction AS trade_direction,
            entry_time AS trade_entry_time,
            exit_time AS trade_exit_time,
            entry_price AS trade_entry_price,
            exit_price AS trade_exit_price,
            net_pnl_usd,
            pnl_percent,
            position_size_usdt,
            risk_percent AS trade_risk_pct,
            leverage,
            trade_mode AS trade_trade_mode
        FROM trades
        WHERE datetime(entry_time) >= datetime('now', ?)
        ORDER BY symbol ASC, trade_entry_time ASC
    """
    df = pd.read_sql_query(query, conn, params=[f"-{extra_hours} hours"])
    if df.empty:
        return df
    df["trade_entry_dt"] = pd.to_datetime(df["trade_entry_time"], errors="coerce", utc=True).dt.tz_convert(None)
    df["trade_exit_dt"] = pd.to_datetime(df["trade_exit_time"], errors="coerce", utc=True).dt.tz_convert(None)
    df = df.dropna(subset=["trade_entry_dt"])
    return df.sort_values(["symbol", "trade_entry_dt"]).reset_index(drop=True)


def _merge_nearest(
    left: pd.DataFrame,
    right: pd.DataFrame,
    left_on: str,
    right_on: str,
    tolerance: pd.Timedelta,
    suffix: str,
) -> pd.DataFrame:
    if right.empty:
        for col in right.columns:
            if col == right_on or col == "symbol":
                continue
            left[f"{col}{suffix}"] = pd.NA
        return left

    merged = pd.merge_asof(
        left.sort_values([left_on]),
        right.sort_values([right_on]),
        left_on=left_on,
        right_on=right_on,
        by="symbol",
        direction="nearest",
        tolerance=tolerance,
        suffixes=("", suffix),
    )
    return merged


def _compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df["final_vs_baseline"] = df["final_amount_usd"] / df["baseline_amount_usd"].replace({0.0: pd.NA})
    df["ai_vs_baseline"] = df["ai_amount_usd"] / df["baseline_amount_usd"].replace({0.0: pd.NA})

    df["trade_return_pct"] = pd.NA
    mask_trade = df["net_pnl_usd"].notna() & df["final_amount_usd"].notna() & (df["final_amount_usd"] != 0)
    df.loc[mask_trade, "trade_return_pct"] = df.loc[mask_trade, "net_pnl_usd"] / df.loc[mask_trade, "final_amount_usd"] * 100.0

    df["baseline_pnl_usd"] = pd.NA
    df.loc[mask_trade, "baseline_pnl_usd"] = (
        df.loc[mask_trade, "trade_return_pct"] / 100.0 * df.loc[mask_trade, "baseline_amount_usd"]
    )

    return df


def export_dataset(hours: int, tolerance_minutes: int, output_dir: Path) -> Optional[Path]:
    tolerance = pd.Timedelta(minutes=tolerance_minutes)

    db = Database()
    conn = db.conn

    events = _load_events(conn, hours)
    if events.empty:
        print(f"⚠️ Нет событий position_sizing за последние {hours} ч.")
        return None

    signals = _load_signals(conn, hours, tolerance_minutes)
    trades = _load_trades(conn, hours, tolerance_minutes)

    merged = _merge_nearest(events, signals, "event_entry_dt", "signal_entry_dt", tolerance, "_sig")
    merged = _merge_nearest(merged, trades, "event_entry_dt", "trade_entry_dt", tolerance, "_trade")

    merged["signal_time_diff_sec"] = (
        (merged["event_entry_dt"] - merged["signal_entry_dt"]).abs().dt.total_seconds()
        if "signal_entry_dt" in merged
        else pd.NA
    )
    merged["trade_time_diff_sec"] = (
        (merged["event_entry_dt"] - merged["trade_entry_dt"]).abs().dt.total_seconds()
        if "trade_entry_dt" in merged
        else pd.NA
    )

    merged = _compute_metrics(merged)

    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"backtest_dataset_{ts}.csv"
    merged.to_csv(out_path, index=False)

    print(f"✅ Экспортировано записей: {len(merged)} (символов: {merged['symbol'].nunique()})")
    print(f"📁 Файл: {out_path}")
    if "event_entry_dt" in merged:
        print(
            f"🕒 Охват по времени: {merged['event_entry_dt'].min()} → {merged['event_entry_dt'].max()}"
        )
    matches = merged["signal_id"].notna().sum() if "signal_id" in merged else 0
    trade_matches = merged["trade_id"].notna().sum() if "trade_id" in merged else 0
    print(f"🔗 Совпадений с signals_log: {matches} | с trades: {trade_matches}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Экспорт датасета для backtest replay baseline/adaptive")
    parser.add_argument("--hours", type=int, default=168, help="Период выборки в часах (по умолчанию 168)")
    parser.add_argument(
        "--tolerance-minutes",
        type=int,
        default=10,
        help="Макс. расхождение по времени между событиями и сигналами в минутах (по умолчанию 10)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/backtest",
        help="Каталог для сохранения CSV (по умолчанию data/backtest)",
    )
    args = parser.parse_args()

    output = export_dataset(int(args.hours), int(args.tolerance_minutes), Path(args.output_dir))
    if output is None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

