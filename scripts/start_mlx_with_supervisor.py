#!/usr/bin/env python3
"""
Запуск MLX API Server с Supervisor (автоматический перезапуск)
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем путь к knowledge_os
knowledge_os_path = str(Path(__file__).parent.parent / "knowledge_os" / "app")
sys.path.insert(0, knowledge_os_path)

from mlx_server_supervisor import get_mlx_supervisor


async def main():
    """Запуск supervisor"""
    supervisor = get_mlx_supervisor()

    print("🚀 Запуск MLX API Server с Supervisor...")
    print("   - Автоматический перезапуск при падении")
    print("   - Health monitoring каждые 10 секунд")
    print("   - Exponential backoff при перезапусках")
    print("   - Circuit Breaker для защиты от каскадных сбоев")
    print()

    try:
        success = await supervisor.start()

        if success:
            print("✅ Supervisor запущен успешно")
            print("   Нажмите Ctrl+C для остановки")
            print()

            # Ждем сигнала завершения
            try:
                while True:
                    status = supervisor.get_status()
                    print(f"📊 Статус: {status['state']}, PID: {status['process_pid']}, "
                          f"Перезапусков: {status['restart_count']}")
                    await asyncio.sleep(30)
            except KeyboardInterrupt:
                print("\n🛑 Получен сигнал завершения...")
        else:
            print("❌ Не удалось запустить supervisor")
            sys.exit(1)

    finally:
        await supervisor.stop()
        print("✅ Supervisor остановлен")


if __name__ == "__main__":
    asyncio.run(main())
