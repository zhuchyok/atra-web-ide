#!/usr/bin/env python3
"""Generate aggregated feedback lessons for agents."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.feedback import FeedbackAggregator  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect agent feedback and generate lessons learned.")
    parser.add_argument(
        "--traces",
        type=Path,
        default=Path("logs/agent_traces.log"),
        help="Путь к JSONL-файлу трассировки Think/Act/Observe.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("trading.db"),
        help="Путь к базе данных (используется для order_audit_log).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("observability/lessons.json"),
        help="Файл для сохранения агрегированных уроков.",
    )
    parser.add_argument(
        "--print",
        dest="print_summary",
        action="store_true",
        help="Печатать краткую сводку поверх сохранения.",
    )
    parser.add_argument(
        "--apply-guidance",
        action="store_true",
        help="Обновить guidance-файлы в configs/guidance.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("process_feedback")

    # 1. Автоматический анализ сделок (основной источник обучения)
    logger.info("🔍 Запуск автоматического анализа сделок...")
    try:
        from observability.auto_analyzer import AutoTradeAnalyzer  # noqa: E402
        
        analyzer = AutoTradeAnalyzer(db_path=str(args.db), lookback_days=30)
        trade_lessons = analyzer.run_analysis()
        if trade_lessons:
            logger.info("📚 Сгенерировано %d уроков из анализа сделок", len(trade_lessons))
    except Exception as e:
        logger.warning("⚠️ Ошибка автоматического анализа сделок: %s", e)
    
    # 2. 🆕 Сбор неявного feedback из результатов сделок
    logger.info("🔍 Запуск сбора неявного feedback...")
    try:
        from observability.implicit_feedback import get_implicit_feedback_collector  # noqa: E402
        
        collector = get_implicit_feedback_collector()
        feedback_list = collector.collect_from_trades_table(lookback_days=7)
        if feedback_list:
            logger.info("📊 Собрано %d неявных feedback (positive: %d, negative: %d)",
                       len(feedback_list),
                       sum(1 for f in feedback_list if f.feedback_type == "positive"),
                       sum(1 for f in feedback_list if f.feedback_type == "negative"))
            # Сохраняем feedback
            collector.save_feedback(feedback_list)
    except Exception as e:
        logger.warning("⚠️ Ошибка сбора неявного feedback: %s", e)

    # 3. Агрегация всех источников (trace events, audit failures, trade analysis, implicit feedback)
    aggregator = FeedbackAggregator(trace_path=args.traces, db_path=args.db)
    data = aggregator.export_lessons(args.output)

    logger.info("Lessons saved to %s (total=%d)", args.output, len(data["lessons"]))

    if args.apply_guidance:
        from observability.guidance import GuidanceStore  # noqa: E402

        store = GuidanceStore()
        # Применяем уроки через новый метод
        for lesson_dict in data["lessons"]:
            agent_name = lesson_dict.get("agent", "unknown")
            # Группируем уроки по агентам
            agent_lessons = [l for l in data["lessons"] if l.get("agent") == agent_name]
            if agent_lessons:
                # Берем топ-5 уроков для каждого агента
                top_lessons = sorted(agent_lessons, key=lambda x: x.get("count", 0), reverse=True)[:5]
                store.update_guidance(agent_name, top_lessons)
        logger.info("✅ Guidance применён для всех агентов")

    if args.print_summary:
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

