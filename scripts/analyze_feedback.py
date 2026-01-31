#!/usr/bin/env python3
"""
Фаза 4: анализ обратной связи за период (для пайплайна качества).

Использование:
  python scripts/analyze_feedback.py --days 7
  python scripts/analyze_feedback.py --days 30 --output feedback_analysis.json
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

try:
    from app.services.feedback_collector import FeedbackCollector
except ImportError:
    FeedbackCollector = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze RAG feedback")
    parser.add_argument("--days", type=int, default=7, help="Days to analyze")
    parser.add_argument("--output", "-o", help="Write JSON to file")
    args = parser.parse_args()

    if not FeedbackCollector:
        print("FeedbackCollector not available", file=sys.stderr)
        return 0

    collector = FeedbackCollector()
    stats = collector.get_feedback_stats(days=args.days)
    issues = collector.get_quality_issues(unresolved_only=True)

    result = {
        "days": args.days,
        "stats": stats,
        "quality_issues_count": len(issues),
        "quality_issues_sample": issues[:10],
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.output:
        out = Path(args.output)
        if not out.is_absolute():
            out = REPO_ROOT / args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Written to {out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
