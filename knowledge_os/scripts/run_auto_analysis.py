#!/usr/bin/env python3
"""Автоматический анализ результатов сделок и обновление уроков.

Система автоматически:
1. Анализирует закрытые сделки из БД
2. Определяет паттерны успешных/неуспешных сигналов
3. Генерирует уроки для агентов
4. Применяет улучшения через GuidanceStore
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.auto_analyzer import AutoTradeAnalyzer
from observability.feedback import FeedbackAggregator
from observability.guidance import GuidanceStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description="Автоматический анализ сделок и обновление уроков")
    parser.add_argument("--db", default="trading.db", help="Путь к БД SQLite")
    parser.add_argument("--lookback-days", type=int, default=30, help="Период анализа (дни)")
    parser.add_argument(
        "--apply-guidance", action="store_true", help="Применить уроки как guidance"
    )
    parser.add_argument(
        "--output", default="observability/lessons.json", help="Путь для сохранения уроков"
    )
    args = parser.parse_args()

    logger.info("🔍 Запуск автоматического анализа сделок...")

    # 1. Анализ сделок
    analyzer = AutoTradeAnalyzer(db_path=args.db, lookback_days=args.lookback_days)
    lessons = analyzer.run_analysis()

    if not lessons:
        logger.warning("⚠️ Недостаточно данных для анализа")
        return

    logger.info("📚 Сгенерировано %d уроков", len(lessons))

    # 2. Сохранение уроков
    output_path = Path(args.output)
    analyzer.save_lessons(lessons, output_path)

    # 3. Агрегация с другими источниками (trace events, audit failures)
    logger.info("🔄 Агрегация всех источников обратной связи...")
    aggregator = FeedbackAggregator(db_path=args.db)
    all_lessons = aggregator.collect_lessons()
    aggregator.save_lessons()

    logger.info("📊 Всего уроков после агрегации: %d", len(all_lessons))

    # 4. Применение guidance (если запрошено)
    if args.apply_guidance:
        logger.info("📝 Применение уроков как guidance...")
        guidance_store = GuidanceStore()
        for lesson in all_lessons:
            agent_name = lesson.agent
            lessons_list = [
                lesson.to_dict() for lesson in all_lessons if lesson.agent == agent_name
            ]
            if lessons_list:
                # Берем топ-5 уроков для каждого агента
                top_lessons = sorted(lessons_list, key=lambda x: x.get("count", 0), reverse=True)[
                    :5
                ]
                guidance_store.update_guidance(agent_name, top_lessons)
        logger.info("✅ Guidance применён для всех агентов")

    logger.info("✅ Автоматический анализ завершён")


if __name__ == "__main__":
    main()
