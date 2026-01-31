#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сравнение результатов adaptive sizing против baseline.

На основе таблицы position_sizing_events и trades оценивает,
как изменилась прибыль относительно базового размера позиции.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# Допустимая погрешность по времени при сопоставлении сигналов и сделок
ENTRY_TIME_TOLERANCE_MINUTES = 15


def _load_position_events(conn: sqlite3.Connection, hours: Optional[int]) -> pd.DataFrame:
    where_clauses = []
    params = []
    if hours:
        where_clauses.append("datetime(created_at) >= datetime('now', ?)")
        params.append(f"-{hours} hours")

    query = """
        SELECT
            id,
            created_at,
            symbol,
            direction,
            entry_time,
            signal_token,
            user_id,
            baseline_amount_usd,
            ai_amount_usd,
            final_amount_usd,
            ai_risk_pct,
            base_risk_pct,
            regime,
            regime_confidence
        FROM position_sizing_events
    """
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY created_at DESC"

    try:
        df = pd.read_sql_query(
            query,
            conn,
            params=params or None,
            parse_dates=["created_at"],
        )
    except (sqlite3.OperationalError, pd.errors.DatabaseError):
        return pd.DataFrame()

    if not df.empty:
        df["entry_time"] = pd.to_datetime(df["entry_time"], errors="coerce")
    return df


def _load_trades(conn: sqlite3.Connection, hours: Optional[int]) -> pd.DataFrame:
    where_clauses = []
    params = []
    if hours:
        where_clauses.append("datetime(entry_time) >= datetime('now', ?)")
        params.append(f"-{hours} hours")

    query = """
        SELECT
            id,
            symbol,
            entry_time,
            exit_time,
            net_pnl_usd,
            pnl_percent,
            position_size_usdt,
            trade_mode,
            user_id
        FROM trades
    """
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    trades = pd.read_sql_query(
        query,
        conn,
        params=params or None,
        parse_dates=["entry_time", "exit_time"],
    )
    return trades


def _match_trades(events: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    if events.empty or trades.empty:
        return pd.DataFrame()

    # Подготовка ключей для join: символ + округлённое время входа
    events = events.copy()
    trades = trades.copy()

    events["entry_time_rounded"] = events["entry_time"].dt.round("1min")
    trades["entry_time_rounded"] = trades["entry_time"].dt.round("1min")

    merged = events.merge(
        trades,
        on="symbol",
        how="inner",
        suffixes=("_event", "_trade"),
    )

    tolerance = pd.to_timedelta(ENTRY_TIME_TOLERANCE_MINUTES, unit="m")
    merged["time_diff"] = (
        merged["entry_time_trade"] - merged["entry_time_event"]
    ).abs()

    merged = merged[merged["time_diff"] <= tolerance]

    # Оставляем ближайшее совпадение для каждого события
    merged = merged.sort_values("time_diff").drop_duplicates(subset=["id_event"])
    merged = merged.rename(columns={"net_pnl_usd": "actual_pnl_usd"})

    # Расчёт коэффициентов
    merged["final_vs_base"] = merged["final_amount_usd"] / merged["baseline_amount_usd"].replace({0.0: pd.NA})
    merged["ai_vs_base"] = merged["ai_amount_usd"] / merged["baseline_amount_usd"].replace({0.0: pd.NA})
    merged["baseline_pnl_usd"] = merged["actual_pnl_usd"]
    merged.loc[merged["final_vs_base"].notna() & (merged["final_vs_base"] != 0), "baseline_pnl_usd"] = (
        merged["actual_pnl_usd"] / merged["final_vs_base"]
    )
    merged["final_vs_base"] = merged["final_vs_base"].fillna(1.0)
    merged["ai_vs_base"] = merged["ai_vs_base"].fillna(1.0)

    return merged


def summarize(df: pd.DataFrame) -> dict:
    if df.empty:
        print("⚠️ Нет совпавших сделок и событий сайзинга за указанный период.")
        return {}

    summary = {
        "events_matched": int(len(df)),
        "mean_final_vs_base": float(df["final_vs_base"].mean()),
        "median_final_vs_base": float(df["final_vs_base"].median()),
        "mean_ai_vs_base": float(df["ai_vs_base"].mean()),
        "mean_actual_pnl": float(df["actual_pnl_usd"].mean()),
        "mean_baseline_pnl": float(df["baseline_pnl_usd"].mean()),
        "total_actual_pnl": float(df["actual_pnl_usd"].sum()),
        "total_baseline_pnl": float(df["baseline_pnl_usd"].sum()),
    }
    uplift = summary["total_actual_pnl"] - summary["total_baseline_pnl"]

    print("=== Сравнение adaptive vs baseline ===")
    for key, value in summary.items():
        print(f"{key:22s}: {value:,.4f}")
    print(f"{'uplift_vs_baseline':22s}: {uplift:,.4f}")

    regime_stats = []
    print("\n=== Группировка по режиму ===")
    regime_grp = (
        df.groupby("regime")[["final_vs_base", "actual_pnl_usd", "baseline_pnl_usd"]]
        .agg(["mean", "median", "sum", "count"])
        .fillna(0)
    )
    print(regime_grp.to_string(float_format=lambda x: f"{x:,.3f}"))
    for regime, row in regime_grp.iterrows():
        regime_stats.append(
            {
                "regime": regime,
                "mean_final_vs_base": float(row[("final_vs_base", "mean")]),
                "actual_pnl_sum": float(row[("actual_pnl_usd", "sum")]),
                "baseline_pnl_sum": float(row[("baseline_pnl_usd", "sum")]),
                "events": int(row[("final_vs_base", "count")]),
            }
        )

    direction_stats = []
    print("\n=== Группировка по направлению ===")
    direction_grp = (
        df.groupby("direction")[["final_vs_base", "actual_pnl_usd", "baseline_pnl_usd"]]
        .agg(["mean", "median", "sum", "count"])
        .fillna(0)
    )
    print(direction_grp.to_string(float_format=lambda x: f"{x:,.3f}"))
    for direction, row in direction_grp.iterrows():
        direction_stats.append(
            {
                "direction": direction,
                "mean_final_vs_base": float(row[("final_vs_base", "mean")]),
                "actual_pnl_sum": float(row[("actual_pnl_usd", "sum")]),
                "baseline_pnl_sum": float(row[("baseline_pnl_usd", "sum")]),
                "events": int(row[("final_vs_base", "count")]),
            }
        )

    summary["uplift_vs_baseline"] = uplift
    summary["regime_stats"] = regime_stats
    summary["direction_stats"] = direction_stats
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Сравнение adaptive sizing против baseline")
    parser.add_argument("--db", default="trading.db", help="Путь к SQLite базе данных")
    parser.add_argument(
        "--hours",
        type=int,
        default=168,
        help="Интервал анализа в часах (по умолчанию 168, то есть 7 дней). 0 — весь период.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Интервал анализа в днях (перекрывает --hours, 0 — весь период).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Каталог для сохранения отчёта (JSON). По умолчанию не сохраняется.",
    )
    args = parser.parse_args()
    hours = None
    if args.days is not None and args.days > 0:
        hours = args.days * 24
    elif args.hours and args.hours > 0:
        hours = args.hours

    with sqlite3.connect(args.db) as conn:
        events = _load_position_events(conn, hours)
        trades = _load_trades(conn, hours)

    if events.empty:
        scope = f"за последние {hours} ч." if hours else "за весь период"
        print(f"⚠️ В таблице position_sizing_events нет данных {scope}.")
        return

    matched = _match_trades(events, trades)
    summary = summarize(matched)

    if args.output_dir and summary:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_path = output_dir / f"adaptive_vs_baseline_{timestamp}.json"
        payload = {
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "hours": hours,
            "summary": summary,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n💾 Отчёт сохранён в {out_path}")


if __name__ == "__main__":
    main()

