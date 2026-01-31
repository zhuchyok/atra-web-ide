#!/usr/bin/env python3
"""
Скрипт запуска Moondream Station как сервис
Moondream 3 Preview с MLX поддержкой для Mac Studio
"""

import subprocess
import sys
import os
import signal
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Запуск Moondream Station"""
    logger.info("🚀 Запуск Moondream Station (Moondream 3 Preview с MLX)...")
    logger.info("📡 API будет доступен на: http://localhost:2020")
    
    try:
        # Проверяем, установлен ли moondream-station
        result = subprocess.run(
            ["moondream-station", "--help"],
            capture_output=True,
            timeout=5
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.error("❌ moondream-station не найден!")
        logger.info("💡 Установите: pip install moondream-station")
        sys.exit(1)
    
    # Запускаем Moondream Station
    try:
        logger.info("✅ Запуск Moondream Station...")
        process = subprocess.Popen(
            ["moondream-station"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Обработка сигналов для корректного завершения
        def signal_handler(sig, frame):
            logger.info("\n🛑 Остановка Moondream Station...")
            process.terminate()
            process.wait()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Выводим логи
        for line in process.stdout:
            print(line, end='')
        
        process.wait()
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Остановка Moondream Station...")
        process.terminate()
        process.wait()
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
