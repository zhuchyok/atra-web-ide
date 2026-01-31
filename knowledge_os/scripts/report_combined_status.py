#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Комбинированный отчёт качества и рисков.

Сводит данные из:
  - latest daily_quality_report_*.json
  - report_risk_status (через collect_risk_status)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from report_infra_status import (  # noqa: E402
    collect_infra_status,
    format_infra_status,
)
from report_risk_status import collect_risk_status, format_risk_status  # noqa: E402

REPORT_DIR = PROJECT_ROOT / "data" / "reports"


def find_latest_quality_report() -> Optional[Path]:
    if not REPORT_DIR.exists():
        return None
    reports = sorted(REPORT_DIR.glob("daily_quality_report_*.json"))
    return reports[-1] if reports else None


def load_quality_summary(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    fb = data.get("false_breakout", {})
    mtf = data.get("mtf_confirmation", {})
    sizing = data.get("position_sizing", {})
    return {
        "generated_at": data.get("generated_at"),
        "window_hours": data.get("window_hours", 24),
        "false_breakout": {
            "total_events": fb.get("total_events", 0),
            "pass_rate": fb.get("pass_rate"),
        },
        "mtf_confirmation": {
            "total_events": mtf.get("total_events", 0),
            "confirmation_rate": mtf.get("confirmation_rate"),
        },
        "position_sizing": {
            "events_total": sizing.get("events_total", 0),
            "matched_events": sizing.get("matched_events", 0),
            "uplift_vs_baseline": sizing.get("uplift_vs_baseline"),
        },
        "raw": data,
        "file": path.name,
    }


def format_quality_summary(summary: Dict[str, Any]) -> str:
    def fmt_pct(value: Optional[float]) -> str:
        if value is None:
            return "—"
        try:
            return f"{value * 100:.1f}%"
        except (TypeError, ValueError):
            return "—"

    lines = []
    lines.append("=== Quality Report ===")
    lines.append(f"Generated at: {summary.get('generated_at')}")
    lines.append(f"Window: {summary.get('window_hours')}h")
    lines.append("")
    fb = summary["false_breakout"]
    lines.append("False Breakout:")
    lines.append(f"  - Events: {fb['total_events']}")
    lines.append(f"  - Pass rate: {fmt_pct(fb['pass_rate'])}")
    lines.append("")
    mtf = summary["mtf_confirmation"]
    lines.append("MTF Confirmation:")
    lines.append(f"  - Events: {mtf['total_events']}")
    lines.append(f"  - Confirmation: {fmt_pct(mtf['confirmation_rate'])}")
    lines.append("")
    sizing = summary["position_sizing"]
    lines.append("Adaptive Sizing:")
    lines.append(f"  - Events: {sizing['events_total']}")
    lines.append(f"  - Matched trades: {sizing['matched_events']}")
    uplift = sizing["uplift_vs_baseline"]
    lines.append(
        f"  - Uplift: {uplift:+.2f} USDT" if uplift is not None else "  - Uplift: —"
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Комбинированный отчёт risk + quality")
    parser.add_argument("--db", default="trading.db")
    parser.add_argument(
        "--performance-report",
        default="data/reports/performance_live_vs_backfill.json",
    )
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--weak-limit", type=int, default=10)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--backups-dir", default=str(PROJECT_ROOT / "backups"))
    parser.add_argument("--bot-pid", default=str(PROJECT_ROOT / "bot.pid"))
    parser.add_argument("--bot-log", default=str(PROJECT_ROOT / "bot.log"))
    parser.add_argument("--lock-file", default=str(PROJECT_ROOT / "atra.lock"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    risk_data = collect_risk_status(
        db_path=args.db,
        performance_report=Path(args.performance_report),
        hours=args.hours,
        weak_limit=args.weak_limit,
    )
    infra_data = collect_infra_status(
        db_path=Path(args.db),
        backups_dir=Path(args.backups_dir),
        bot_pid_file=Path(args.bot_pid),
        bot_log_path=Path(args.bot_log),
        lock_file=Path(args.lock_file),
    )
    quality_path = find_latest_quality_report()
    if quality_path is None:
        raise SystemExit("Не найден daily_quality_report_*.json в data/reports")
    quality_summary = load_quality_summary(quality_path)

    if args.format == "json":
        combined = {
            "risk": {
                "generated_at": risk_data["generated_at"],
                "max_drawdown_pct": risk_data["max_drawdown_pct"],
                "daily_loss_pct": risk_data["daily_loss_pct"],
                "weak_setup_streak": risk_data["weak_setup_streak"],
                "hours": risk_data["hours"],
                "weak_limit": risk_data["weak_limit"],
                "live_stats": risk_data["live_stats"],
                "deposits": risk_data["deposits"],
                "flags": {
                    name: {
                        "value": info.value,
                        "updated_at": info.updated_at.isoformat(),
                        "reason": info.reason,
                    }
                    for name, info in risk_data["flags"].items()
                },
            },
            "quality": quality_summary,
            "infra": infra_data,
        }
        print(json.dumps(combined, ensure_ascii=False, indent=2))
    else:
        print("==== Combined Status ====")
        print(format_quality_summary(quality_summary))
        print("")
        print(format_risk_status(risk_data))
        print("")
        print(format_infra_status(infra_data))


if __name__ == "__main__":
    main()

