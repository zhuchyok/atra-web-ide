#!/usr/bin/env python3
"""
Фаза 4: проверка алертов по отчёту качества (для пайплайна качества).

Использование:
  python scripts/check_quality_alerts.py --report backend/validation_report.json --threshold faithfulness:0.7,relevance:0.75
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Check quality report for alerts")
    parser.add_argument("--report", default="backend/validation_report.json")
    parser.add_argument(
        "--threshold",
        default="faithfulness:0.7,relevance:0.75",
        help="Comma-separated metric:value",
    )
    args = parser.parse_args()

    path = REPO_ROOT / args.report
    if not path.exists():
        print(f"Report not found: {path}", file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("skipped") is True:
        print("Report marked skipped=true; refusing to green-pass alerts", file=sys.stderr)
        return 1

    avg = data.get("avg_metrics", data.get("avg", {}))
    if not avg:
        print("No avg_metrics in report", file=sys.stderr)
        return 1

    thresholds = {}
    for part in args.threshold.split(","):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            thresholds[k.strip()] = float(v.strip())

    alerts = []
    for name, th in thresholds.items():
        val = avg.get(name)
        if val is None:
            alerts.append(f"{name}=missing")
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            alerts.append(f"{name}=non-numeric")
            continue
        if fval != fval:  # NaN
            alerts.append(f"{name}=nan")
            continue
        if fval < th:
            alerts.append(f"{name}={fval:.3f} < {th}")

    if alerts:
        print("ALERTS: " + "; ".join(alerts), file=sys.stderr)
        return 1
    print("No alerts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
