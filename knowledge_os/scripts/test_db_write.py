#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import sys
import os
import logging

# Добавляем путь к проекту
sys.path.append(os.getcwd())

from src.utils.filter_logger import log_filter_check_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DB_TEST")

async def test_write():
    logger.info("🚀 Запуск теста записи в БД...")
    result = await log_filter_check_async(
        symbol="TESTUSDT",
        filter_type="manual_test",
        passed=False,
        reason="Test rejection entry",
        signal_data={"price": 1.23, "test": True}
    )
    if result:
        logger.info("✅ Тестовая запись успешно отправлена (проверьте таблицу)")
    else:
        logger.error("❌ Тестовая запись провалилась")

if __name__ == "__main__":
    asyncio.run(test_write())

