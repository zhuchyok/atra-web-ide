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
        return 0

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    avg = data.get("avg_metrics", data.get("avg", {}))
    thresholds = {}
    for part in args.threshold.split(","):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            thresholds[k.strip()] = float(v.strip())

    alerts = []
    for name, th in thresholds.items():
        val = avg.get(name)
        if val is not None and val < th:
            alerts.append(f"{name}={val:.3f} < {th}")

    if alerts:
        print("ALERTS: " + "; ".join(alerts), file=sys.stderr)
        return 1
    print("No alerts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
