#!/usr/bin/env python3
"""
Автоматический скрипт для исправления всех позиций
Выполняет все шаги последовательно
"""

import asyncio
import logging
import os
import sys

# Добавляем путь к корню проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("auto_fix_all")


async def run_sync_positions():
    """Шаг 1: Синхронизация позиций"""
    logger.info("📋 ШАГ 1: Синхронизация позиций с биржи")
    logger.info("=" * 70)

    try:
        from scripts.sync_positions_with_exchange import main_async

        await main_async()
        logger.info("✅ Синхронизация завершена")
        return True
    except Exception as e:
        logger.error("❌ Ошибка синхронизации: %s", e, exc_info=True)
        return False


async def run_emergency_fix_pumpusdt():
    """Шаг 2: Экстренное исправление PUMPUSDT"""
    logger.info("📋 ШАГ 2: Экстренное исправление PUMPUSDT")
    logger.info("=" * 70)

    try:
        from scripts.emergency_fix_pumpusdt import main

        await main()
        logger.info("✅ Исправление PUMPUSDT завершено")
        return True
    except Exception as e:
        logger.error("❌ Ошибка исправления PUMPUSDT: %s", e, exc_info=True)
        return False


async def run_fix_all_positions():
    """Шаг 3: Общее исправление всех позиций"""
    logger.info("📋 ШАГ 3: Общее исправление всех позиций")
    logger.info("=" * 70)

    try:
        from scripts.fix_open_positions_tp_sl import main

        await main()
        logger.info("✅ Общее исправление завершено")
        return True
    except Exception as e:
        logger.error("❌ Ошибка общего исправления: %s", e, exc_info=True)
        return False


async def main():
    """Главная функция - выполняет все шаги последовательно"""
    logger.info("🚀 НАЧАЛО АВТОМАТИЧЕСКОГО ИСПРАВЛЕНИЯ ПОЗИЦИЙ")
    logger.info("=" * 70)
    logger.info("")

    results = {}

    # Шаг 1: Синхронизация
    results["sync"] = await run_sync_positions()
    logger.info("")

    # Шаг 2: PUMPUSDT
    results["pumpusdt"] = await run_emergency_fix_pumpusdt()
    logger.info("")

    # Шаг 3: Общее исправление
    results["fix_all"] = await run_fix_all_positions()
    logger.info("")

    # Итоги
    logger.info("=" * 70)
    logger.info("📊 ИТОГИ ВЫПОЛНЕНИЯ:")
    logger.info("  Синхронизация: %s", "✅" if results["sync"] else "❌")
    logger.info("  PUMPUSDT: %s", "✅" if results["pumpusdt"] else "❌")
    logger.info("  Общее исправление: %s", "✅" if results["fix_all"] else "❌")
    logger.info("")

    if all(results.values()):
        logger.info("✅ ВСЕ ИСПРАВЛЕНИЯ ЗАВЕРШЕНЫ УСПЕШНО")
    else:
        logger.warning("⚠️ Некоторые шаги завершились с ошибками")

    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
