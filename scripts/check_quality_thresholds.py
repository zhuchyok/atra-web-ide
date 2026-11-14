#!/usr/bin/env python3
"""
Фаза 4: проверка порогов качества по JSON-отчёту (для CI).

Использование:
  python scripts/check_quality_thresholds.py backend/validation_report.json
  python scripts/check_quality_thresholds.py validation_report.json --threshold faithfulness:0.7,relevance:0.75

При нарушении порогов — exit 1.
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Check quality report against thresholds")
    parser.add_argument("report", help="Path to validation_report.json")
    parser.add_argument(
        "--threshold",
        default="faithfulness:0.8,relevance:0.85,coherence:0.7",
        help="Comma-separated metric:value (QA: faithfulness≥0.8, relevance≥0.85, coherence≥0.7)",
    )
    args = parser.parse_args()

    path = Path(args.report)
    if not path.exists():
        print(f"Report not found: {path}", file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("skipped") is True:
        print("Report marked skipped=true; refusing to green-pass thresholds", file=sys.stderr)
        return 1

    avg = data.get("avg_metrics", data.get("avg", {}))
    if not avg:
        print("No avg_metrics in report", file=sys.stderr)
        return 1

    # Fail-closed on empty/stub runs (total_queries=0 must not green-pass)
    if "total_queries" in data:
        try:
            n = int(data.get("total_queries") or 0)
        except (TypeError, ValueError):
            n = 0
        if n < 1:
            print(f"total_queries={n} — refusing empty validation report", file=sys.stderr)
            return 1

    thresholds = {}
    for part in args.threshold.split(","):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            thresholds[k.strip()] = float(v.strip())

    failed = []
    for name, th in thresholds.items():
        if name not in avg or avg.get(name) is None:
            failed.append(f"{name}=missing (required >= {th})")
            continue
        try:
            val = float(avg[name])
        except (TypeError, ValueError):
            failed.append(f"{name}=non-numeric ({avg[name]!r})")
            continue
        if val != val:  # NaN
            failed.append(f"{name}=nan (required >= {th})")
            continue
        if val < th:
            failed.append(f"{name}={val:.3f} < {th}")

    if failed:
        print("Thresholds failed: " + ", ".join(failed), file=sys.stderr)
        return 1
    print("All thresholds passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
