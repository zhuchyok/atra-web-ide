#!/usr/bin/env python3
"""
Скрипт для ручного обновления базы знаний.

Использование:
    python scripts/update_knowledge_base.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.knowledge_base import update_knowledge_base

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    logger.info("📚 Обновление базы знаний команды...")

    success = update_knowledge_base()

    if success:
        logger.info("✅ База знаний успешно обновлена!")
        return 0
    else:
        logger.error("❌ Не удалось обновить базу знаний")
        return 1


if __name__ == "__main__":
    sys.exit(main())
