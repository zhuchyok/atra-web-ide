#!/usr/bin/env python3
"""
Автоматический сбор ретроспектив и обновление базы знаний.

Запускается после завершения задач для:
1. Сбора ретроспектив
2. Обновления базы знаний
3. Интеграции lessons learned
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.retrospective import collect_retrospective, get_retrospective_collector
from observability.knowledge_base import update_knowledge_base
from observability.feedback import FeedbackAggregator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Автоматический сбор ретроспектив и обновление базы знаний"
    )
    parser.add_argument(
        "--task-id",
        type=str,
        required=True,
        help="Уникальный ID задачи"
    )
    parser.add_argument(
        "--task-name",
        type=str,
        required=True,
        help="Название задачи"
    )
    parser.add_argument(
        "--task-description",
        type=str,
        default="",
        help="Описание задачи"
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        help="Длительность выполнения в минутах"
    )
    parser.add_argument(
        "--skip-retrospective",
        action="store_true",
        help="Пропустить сбор ретроспективы (только обновление базы знаний)"
    )
    parser.add_argument(
        "--skip-knowledge-update",
        action="store_true",
        help="Пропустить обновление базы знаний (только ретроспектива)"
    )
    
    args = parser.parse_args()
    
    logger.info("🚀 Запуск автоматического сбора ретроспектив и обновления базы знаний")
    
    # 1. Сбор ретроспективы
    if not args.skip_retrospective:
        logger.info("📋 Сбор ретроспективы для задачи: %s", args.task_name)
        try:
            retrospective = collect_retrospective(
                task_id=args.task_id,
                task_name=args.task_name,
                task_description=args.task_description,
                duration_minutes=args.duration_minutes,
            )
            logger.info("✅ Ретроспектива собрана: %s", retrospective.task_id)
            
            # Генерируем Markdown отчет
            collector = get_retrospective_collector()
            markdown_report = collector.generate_markdown_report(retrospective)
            
            # Сохраняем Markdown отчет
            report_file = Path("retrospectives") / f"{retrospective.task_id}_report.md"
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(markdown_report, encoding='utf-8')
            logger.info("📄 Markdown отчет сохранен: %s", report_file)
            
        except Exception as e:
            logger.error("❌ Ошибка сбора ретроспективы: %s", e, exc_info=True)
    else:
        logger.info("⏭️ Пропущен сбор ретроспективы")
    
    # 2. Обновление базы знаний
    if not args.skip_knowledge_update:
        logger.info("📚 Обновление базы знаний...")
        try:
            success = update_knowledge_base()
            if success:
                logger.info("✅ База знаний обновлена")
            else:
                logger.warning("⚠️ Не удалось обновить базу знаний")
        except Exception as e:
            logger.error("❌ Ошибка обновления базы знаний: %s", e, exc_info=True)
    else:
        logger.info("⏭️ Пропущено обновление базы знаний")
    
    # 3. Сбор lessons learned (опционально)
    logger.info("🔍 Сбор lessons learned...")
    try:
        aggregator = FeedbackAggregator()
        lessons = aggregator.collect_lessons()
        logger.info("📊 Собрано %d lessons learned", len(lessons))
    except Exception as e:
        logger.warning("⚠️ Ошибка сбора lessons learned: %s", e)
    
    logger.info("✅ Автоматический сбор завершен")


if __name__ == "__main__":
    main()

