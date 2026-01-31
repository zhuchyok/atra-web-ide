#!/usr/bin/env python3
"""
Скрипт для применения всех изученных знаний.

Применяет:
1. Lessons learned → guidance
2. Ретроспективы → база знаний
3. Новые знания → эволюция промптов
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
    logger.info("")
    
    if all(results.values()):
        logger.info("✅ Все знания успешно применены!")
        return 0
    else:
        logger.warning("⚠️ Некоторые знания не были применены")
        return 1


if __name__ == "__main__":
    sys.exit(main())

