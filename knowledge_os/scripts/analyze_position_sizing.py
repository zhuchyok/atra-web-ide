#!/usr/bin/env python3
"""
Аналитика по таблице position_sizing_events.

Сравнивает базовый объём позиции с финальным после всех корректировок
(режим, корреляции, адаптивный сайзинг, портфельные ограничения).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd


def _load_events(db_path: str, hours: Optional[int]) -> pd.DataFrame:
    where_clauses: List[str] = []
    params: List[str] = []

    if hours is not None and hours > 0:
        where_clauses.append("datetime(created_at) >= datetime('now', ?)")
        params.append(f"-{hours} hours")

    query = """
        SELECT
            created_at,
            symbol,
            direction,
            entry_time,
            signal_token,
            user_id,
            trade_mode,
            signal_price,
            baseline_amount_usd,
            ai_amount_usd,
            regime_multiplier,
            after_regime_amount_usd,
            correlation_multiplier,
            after_correlation_amount_usd,
            adaptive_multiplier,
            after_adaptive_amount_usd,
            risk_adjustment_multiplier,
            final_amount_usd,
            base_risk_pct,
            ai_risk_pct,
            leverage,
            regime,
            regime_confidence,
            quality_score,
            composite_score,
            pattern_confidence,
            adaptive_reason
        FROM position_sizing_events
    """
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY created_at DESC"

    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql_query(
                query,
                conn,
                params=params or None,
                parse_dates=["created_at"],
            )
        except (sqlite3.OperationalError, pd.errors.DatabaseError) as exc:
            if "no such table" in str(exc).lower():
                return pd.DataFrame()
            raise
    return df


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.divide(denominator.replace({0.0: pd.NA}))


def analyze(db_path: str, hours: Optional[int]) -> Optional[dict]:
    df = _load_events(db_path, hours)
    if df.empty:
        scope = f"за последние {hours} ч." if hours else "за всё время"
        print(f"⚠️ Нет данных в position_sizing_events {scope}")
        return None

    df["baseline_amount_usd"] = df["baseline_amount_usd"].astype(float)
    df["final_amount_usd"] = df["final_amount_usd"].astype(float)
    df["ai_amount_usd"] = df["ai_amount_usd"].astype(float)

    df["ai_vs_base"] = _safe_ratio(df["ai_amount_usd"], df["baseline_amount_usd"])
    df["final_vs_base"] = _safe_ratio(df["final_amount_usd"], df["baseline_amount_usd"])
    df["final_vs_ai"] = _safe_ratio(df["final_amount_usd"], df["ai_amount_usd"])

    total_events = len(df)
    summary = {
        "events_total": total_events,
        "mean_baseline": df["baseline_amount_usd"].mean(),
        "mean_ai_amount": df["ai_amount_usd"].mean(),
        "mean_final_amount": df["final_amount_usd"].mean(),
        "mean_final_vs_base": df["final_vs_base"].mean(),
        "median_final_vs_base": df["final_vs_base"].median(),
        "share_final_above_base": (df["final_vs_base"] > 1.01).mean(),
        "share_final_below_base": (df["final_vs_base"] < 0.99).mean(),
    }

    print("=== Сводка position sizing ===")
    for key, value in summary.items():
        if key.startswith("share_"):
            print(f"{key:25s}: {value * 100:6.2f}%")
        else:
            print(f"{key:25s}: {value:,.4f}")

    print("\n=== Группировка по режиму ===")
    regime_group = (
        df.groupby("regime")[["final_vs_base", "final_vs_ai"]]
        .agg(["mean", "median", "count"])
        .fillna(0)
    )
    print(regime_group.to_string(float_format=lambda x: f"{x:,.3f}"))

    print("\n=== Группировка по направлению ===")
    direction_group = (
        df.groupby("direction")[["final_vs_base", "final_vs_ai"]]
        .agg(["mean", "median", "count"])
        .fillna(0)
    )
    print(direction_group.to_string(float_format=lambda x: f"{x:,.3f}"))

    def _flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
        flattened = frame.reset_index()
        flattened.columns = [
            "_".join([part for part in map(str, col) if part and part != ""])
            for col in flattened.columns.values
        ]
        return flattened

    return {
        "summary": summary,
        "regime_group": _flatten_columns(regime_group).to_dict(orient="records"),
        "direction_group": _flatten_columns(direction_group).to_dict(orient="records"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Аналитика позиционного сайзинга")
    parser.add_argument(
        "--db", default="trading.db", help="Путь к базе данных (по умолчанию trading.db)"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=168,
        help="Интервал анализа в часах (по умолчанию 168 = 7 дней). 0 — весь период.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Интервал анализа в днях (перекрывает --hours). 0 — весь период.",
    )
    parser.add_argument(
        "--final-report",
        action="store_true",
        help="Сохранить финальный отчёт (JSON) в data/reports",
    )
    args = parser.parse_args()

    hours = None
    if args.days is not None and args.days > 0:
        hours = args.days * 24
    elif args.hours and args.hours > 0:
        hours = args.hours

    result = analyze(args.db, hours)

    if args.final_report and result:
        output_dir = Path("data/reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_path = output_dir / f"position_sizing_report_{ts}.json"
        payload = {
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "hours": hours,
            **result,
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n💾 Отчёт сохранён в {out_path}")


if __name__ == "__main__":
    main()
