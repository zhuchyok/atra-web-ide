#!/usr/bin/env python3
import argparse
import asyncio
import logging

from src.agents.implementations.audit_agent import AuditAgent

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("AgentRunner")


async def main():
    parser = argparse.ArgumentParser(description="Запуск автономного агента ATRA")
    parser.add_argument("goal", type=str, help="Цель/задание для агента")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Название модели Ollama (авто-выбор если не указано)",
    )

    args = parser.parse_args()

    logger.info(f"🤖 Инициализация агента AuditAgent (модель: {args.model})...")
    agent = AuditAgent(model_name=args.model)

    logger.info(f"🎯 Задание для агента: {args.goal}")
    result = await agent.run(args.goal)

    print("\n" + "=" * 50)
    print("🏁 ФИНАЛЬНЫЙ ОТЧЕТ АГЕНТА:")
    print("=" * 50)
    print(result)
    print("=" * 50)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Завершение работы по команде пользователя.")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
