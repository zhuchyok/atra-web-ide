#!/usr/bin/env python3
"""
Фаза 4, Неделя 3: запись Human Preference Score (1–5) для калибровки.

Использование:
  python scripts/record_human_preference.py "запрос пользователя" "ответ ассистента" 4
  python scripts/record_human_preference.py "как настроить Victoria" "Запустите docker-compose..." 5 --comment "понятно"
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

try:
    from app.services.feedback_collector import FeedbackCollector
except ImportError:
    FeedbackCollector = None


def main() -> int:
    parser = argparse.ArgumentParser(description="Record Human Preference Score (1-5) for a response")
    parser.add_argument("query", help="User query (or query_id)")
    parser.add_argument("answer", help="Assistant response")
    parser.add_argument("score", type=int, choices=[1, 2, 3, 4, 5], help="Rating 1-5 (5 = best)")
    parser.add_argument("--session-id", default="manual", help="Session identifier")
    parser.add_argument("--comment", help="Optional comment")
    args = parser.parse_args()

    if not FeedbackCollector:
        print("FeedbackCollector not available (run from repo root with PYTHONPATH=backend)", file=sys.stderr)
        return 1

    collector = FeedbackCollector()
    fid = collector.add_feedback(
        session_id=args.session_id,
        query=args.query[:2000],
        answer=args.answer[:5000],
        rating=args.score,
        comment=args.comment,
    )
    print(f"Recorded feedback id={fid} score={args.score}")
    stats = collector.get_feedback_stats(days=30)
    if stats.get("total_feedback"):
        print(f"Human Preference Score (30d): {stats.get('avg_rating', 0):.2f} (n={stats['total_feedback']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
