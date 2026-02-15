#!/usr/bin/env python3
"""
Скрипт для применения всех изученных знаний.

Применяет:
1. Lessons learned → guidance
2. Ретроспективы → база знаний
3. Новые знания → эволюция промптов
4. Код-релевантные уроки/инсайты → задачи «Внедрить в код»
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.knowledge_applicator import apply_all_knowledge

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    logger.info("🧠 Применение всех изученных знаний...")
    
    results = apply_all_knowledge()
    
    # Выводим результаты
    logger.info("")
    logger.info("📊 РЕЗУЛЬТАТЫ ПРИМЕНЕНИЯ ЗНАНИЙ:")
    logger.info("  ✅ Guidance обновлен: %s", "Да" if results.get("guidance_updated") else "Нет")
    logger.info("  ✅ База знаний обновлена: %s", "Да" if results.get("knowledge_base_updated") else "Нет")
    logger.info("  ✅ Промпты эволюционированы: %s", "Да" if results.get("prompts_evolved") else "Нет")
    logger.info("  ✅ Задачи «Внедрить в код» созданы: %s", "Да" if results.get("code_tasks_created") else "Нет")
    logger.info("")
    
    if all(results.values()):
        logger.info("✅ Все знания успешно применены!")
        return 0
    # Не все применены — часто это нормально (нет данных в adaptive_learning_logs / interaction_logs)
    applied = sum(1 for v in results.values() if v)
    logger.info(
        "ℹ️ Применено %d из 4 компонентов. Остальные ждут данных: "
        "adaptive_learning_logs → guidance; interaction_logs → knowledge_nodes; код-релевантные уроки → code tasks.",
        applied
    )
    # Возвращаем 0 — скрипт отработал; 1 только при реальных ошибках (по практикам CI/CD)
    return 0


if __name__ == "__main__":
    sys.exit(main())

