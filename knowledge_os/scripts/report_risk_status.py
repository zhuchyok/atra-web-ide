#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Оперативный отчёт по рискам и live-статусу.

Выводит:
  - Активные risk_flags
  - Текущие метрики (MaxDD, дневной убыток, weak_setup streak)
  - Наличие live сигналов/депозитов пользователей
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from risk_flags_manager import RiskFlagsManager

CAPITAL_BASE = 1_000.0


def read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fp:
        return json.load(fp)


def format_bool(value: bool) -> str:
    return "ON " if value else "off"


def get_live_signal_stats(conn: sqlite3.Connection) -> Dict[str, Optional[str]]:
    total = conn.execute(
        "SELECT COUNT(*) FROM signals_log WHERE trade_mode = 'live'"
    ).fetchone()[0]
    last = conn.execute(
        """
        SELECT entry_time, symbol
        FROM signals_log
        WHERE trade_mode = 'live'
        ORDER BY datetime(entry_time) DESC
        LIMIT 1
        """
    ).fetchone()
    return {
        "total_live_signals": total,
        "last_live_entry": last[0] if last else None,
        "last_live_symbol": last[1] if last else None,
    }


def get_users_deposits(conn: sqlite3.Connection) -> Dict[str, float]:
    rows = conn.execute("SELECT user_id, data FROM users_data").fetchall()
    deposits = {}
    for user_id, data in rows:
        try:
            payload = json.loads(data)
            deposits[user_id] = float(payload.get("deposit") or 0.0)
        except (TypeError, json.JSONDecodeError):
            deposits[user_id] = 0.0
    return deposits


def get_daily_loss_pct(conn: sqlite3.Connection, hours: int = 24) -> float:
    since = datetime.utcnow() - timedelta(hours=hours)
    pnl = conn.execute(
        """
        SELECT COALESCE(SUM(net_pnl_usd), 0)
        FROM trades
        WHERE exit_time IS NOT NULL
          AND datetime(exit_time) >= ?
        """,
        (since.isoformat(),),
    ).fetchone()[0]
    pnl = pnl or 0.0
    return (-pnl / CAPITAL_BASE) * 100 if pnl < 0 else 0.0


def weak_setup_recent(conn: sqlite3.Connection, limit: int = 10) -> bool:
    rows = conn.execute(
        """
        SELECT final_amount_usd, adaptive_reason
        FROM position_sizing_events
        ORDER BY datetime(created_at) DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    if len(rows) < limit:
        return False
    return all(
        (row[0] == 0 or row[0] is None)
        and row[1]
        and row[1].startswith("WEAK_SETUP")
        for row in rows
    )


def collect_risk_status(
    db_path: str,
    performance_report: Path,
    hours: int,
    weak_limit: int,
) -> Dict[str, Any]:
    manager = RiskFlagsManager(db_path=db_path)
    flags = manager.get_flags()

    report = read_json(performance_report)
    max_dd = None
    if report:
        try:
            max_dd = report["metrics"]["all"]["max_drawdown_pct"]
        except KeyError:
            max_dd = None

    with sqlite3.connect(db_path) as conn:
        daily_loss = get_daily_loss_pct(conn, hours=hours)
        weak_series = weak_setup_recent(conn, limit=weak_limit)
        live_stats = get_live_signal_stats(conn)
        deposits = get_users_deposits(conn)

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "flags": flags,
        "max_drawdown_pct": max_dd,
        "daily_loss_pct": daily_loss,
        "weak_setup_streak": weak_series,
        "live_stats": live_stats,
        "deposits": deposits,
        "hours": hours,
        "weak_limit": weak_limit,
    }


def format_risk_status(data: Dict[str, Any]) -> str:
    lines = []
    lines.append("=== Risk Status Report ===")
    lines.append(f"Generated at: {data['generated_at']}")
    lines.append("")
    lines.append("Risk Flags:")
    flags: Dict[str, Any] = data["flags"]
    if not flags:
        lines.append("  - none")
    else:
        for flag, info in flags.items():
            lines.append(
                f"  - {flag}: {format_bool(info.value)} "
                f"(updated {info.updated_at.isoformat()}, reason={info.reason})"
            )
    lines.append("")
    lines.append("Metrics:")
    max_dd = data["max_drawdown_pct"]
    lines.append(
        f"  - Max drawdown: {max_dd:.2f}%" if max_dd is not None else "  - Max drawdown: n/a"
    )
    lines.append(f"  - Daily loss (last {data['hours']}h): {data['daily_loss_pct']:.2f}%")
    lines.append(
        f"  - Weak setup streak >= {data['weak_limit']}: {data['weak_setup_streak']}"
    )
    lines.append("")
    lines.append("Live Signals:")
    live_stats = data["live_stats"]
    lines.append(f"  - Total live signals: {live_stats['total_live_signals']}")
    lines.append(
        f"  - Last live entry: {live_stats['last_live_entry']} ({live_stats['last_live_symbol']})"
    )
    lines.append("")
    lines.append("User Deposits:")
    for user_id, deposit in data["deposits"].items():
        warning = " ⚠" if deposit <= 0 else ""
        lines.append(f"  - {user_id}: {deposit} USDT{warning}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Оперативный отчёт по рискам/live статусу")
    parser.add_argument("--db", default="trading.db")
    parser.add_argument(
        "--performance-report",
        default="data/reports/performance_live_vs_backfill.json",
    )
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--weak-limit", type=int, default=10)
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Формат вывода (text/json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = collect_risk_status(
        db_path=args.db,
        performance_report=Path(args.performance_report),
        hours=args.hours,
        weak_limit=args.weak_limit,
    )

    if args.format == "json":
        serializable = {
            "generated_at": data["generated_at"],
            "max_drawdown_pct": data["max_drawdown_pct"],
            "daily_loss_pct": data["daily_loss_pct"],
            "weak_setup_streak": data["weak_setup_streak"],
            "hours": data["hours"],
            "weak_limit": data["weak_limit"],
            "live_stats": data["live_stats"],
            "deposits": data["deposits"],
            "flags": {
                name: {
                    "value": info.value,
                    "updated_at": info.updated_at.isoformat(),
                    "reason": info.reason,
                }
                for name, info in data["flags"].items()
            },
        }
        print(json.dumps(serializable, ensure_ascii=False, indent=2))
    else:
        print(format_risk_status(data))


if __name__ == "__main__":
    main()

