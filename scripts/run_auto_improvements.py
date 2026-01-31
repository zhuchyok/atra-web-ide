#!/usr/bin/env python3
"""
Фаза 4: запуск автоулучшений на основе обратной связи (для пайплайна качества).

Использование:
  python scripts/run_auto_improvements.py
"""

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))


async def main() -> int:
    try:
        from app.services.feedback_collector import FeedbackCollector
        from app.services.auto_improver import AutoImprover
        from app.services.rag_light import get_rag_light_service
    except ImportError as e:
        print(f"Import error: {e}", file=sys.stderr)
        return 0

    collector = FeedbackCollector()
    rag = get_rag_light_service()
    improver = AutoImprover(collector, rag)

    result = await improver.analyze_and_improve()
    print(f"Analyzed feedback: {result['analyzed_feedback']}")
    print(f"Satisfaction rate: {result['satisfaction_rate']:.2%}")
    print(f"Improvements applied: {result['improvements_applied']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
