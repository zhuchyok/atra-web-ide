#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сводный ежедневный отчёт по качеству фильтров и адаптивного сайзинга.

В отчёт входят:
1. False Breakout Detector (pass-rate, средние метрики, разбивка по режимам)
2. MTF Confirmation (confirmation rate, ошибки, разбивка по режимам)
3. Adaptive vs baseline sizing (соответствия событий сайзинга и сделок)

Результат выводится в stdout (JSON) и при указании каталога сохраняется в файл.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.db import Database  # noqa: E402
from scripts.compare_sizing_performance import (  # noqa: E402
    _load_position_events,
    _load_trades,
    _match_trades,
)
from sources_hub import SourcesHub  # noqa: E402


def _build_sizing_summary(conn: sqlite3.Connection, hours: int) -> Dict[str, Any]:
    events = _load_position_events(conn, hours)
    trades = _load_trades(conn, hours)

    summary: Dict[str, Any] = {
        "window_hours": hours,
        "events_total": len(events),
        "matched_events": 0,
        "uplift_vs_baseline": None,
        "mean_final_vs_base": None,
        "mean_ai_vs_base": None,
        "mean_actual_pnl": None,
        "mean_baseline_pnl": None,
        "total_actual_pnl": None,
        "total_baseline_pnl": None,
        "regime_stats": {},
        "direction_stats": {},
    }

    if events.empty:
        return summary

    merged = _match_trades(events, trades)
    if merged.empty:
        summary["matched_events"] = 0
        return summary

    summary["matched_events"] = int(len(merged))
    summary["mean_final_vs_base"] = float(merged["final_vs_base"].mean())
    summary["mean_ai_vs_base"] = float(merged["ai_vs_base"].mean())
    summary["mean_actual_pnl"] = float(merged["actual_pnl_usd"].mean())
    summary["mean_baseline_pnl"] = float(merged["baseline_pnl_usd"].mean())
    total_actual = float(merged["actual_pnl_usd"].sum())
    total_baseline = float(merged["baseline_pnl_usd"].sum())
    summary["total_actual_pnl"] = total_actual
    summary["total_baseline_pnl"] = total_baseline
    summary["uplift_vs_baseline"] = total_actual - total_baseline

    regime_stats = []
    for regime, group in merged.groupby("regime"):
        regime_stats.append(
            {
                "regime": regime,
                "events": int(len(group)),
                "final_vs_base_mean": float(group["final_vs_base"].mean()),
                "actual_pnl_sum": float(group["actual_pnl_usd"].sum()),
                "baseline_pnl_sum": float(group["baseline_pnl_usd"].sum()),
            }
        )
    summary["regime_stats"] = regime_stats

    direction_stats = []
    for direction, group in merged.groupby("direction"):
        direction_stats.append(
            {
                "direction": direction,
                "events": int(len(group)),
                "final_vs_base_mean": float(group["final_vs_base"].mean()),
                "actual_pnl_sum": float(group["actual_pnl_usd"].sum()),
                "baseline_pnl_sum": float(group["baseline_pnl_usd"].sum()),
            }
        )
    summary["direction_stats"] = direction_stats

    return summary


def _purge_cache(db: Database, keys: Dict[str, str]) -> None:
    with db.conn:
        for cache_key in keys.values():
            db.conn.execute(
                "DELETE FROM app_cache WHERE cache_type = ? AND cache_key = ?",
                ("sources_hub", cache_key),
            )


async def _collect_sources_metrics(symbol: str = "BTCUSDT") -> Dict[str, Any]:
    hub = SourcesHub()
    cache_keys = {
        "market_cap": hub.build_cache_key("market_cap", symbol),
        "price": hub.build_cache_key("price", symbol),
        "volume": hub.build_cache_key("volume", symbol),
    }
    _purge_cache(hub.db, cache_keys)

    await hub.get_market_cap_data(symbol)
    await hub.get_price_data(symbol)
    await hub.get_volume_data(symbol)
    return {
        "symbol": symbol,
        "metrics": hub.get_metrics_snapshot(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Сводный отчёт (False Breakout + MTF + sizing)")
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Период анализа в часах (по умолчанию 24)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Каталог для сохранения JSON-отчёта (например, data/reports). Если не задан, файл не создаётся.",
    )
    args = parser.parse_args()

    hours = max(1, int(args.hours))
    db = Database()

    fb_summary = db.get_false_breakout_summary(hours=hours)
    mtf_summary = db.get_mtf_confirmation_summary(hours=hours)
    sizing_summary = _build_sizing_summary(db.conn, hours)
    sources_metrics = asyncio.run(_collect_sources_metrics())

    report: Dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "window_hours": hours,
        "false_breakout": fb_summary,
        "mtf_confirmation": mtf_summary,
        "position_sizing": sizing_summary,
        "sources_metrics": sources_metrics,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_path = output_dir / f"daily_quality_report_{ts}.json"
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ Отчёт сохранён: {out_path}")


if __name__ == "__main__":
    main()

