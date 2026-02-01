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

    failed = []
    for name, th in thresholds.items():
        val = avg.get(name)
        if val is not None and val < th:
            failed.append(f"{name}={val:.3f} < {th}")

    if failed:
        print("Thresholds failed: " + ", ".join(failed), file=sys.stderr)
        return 1
    print("All thresholds passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
