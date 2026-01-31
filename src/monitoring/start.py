#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 СКРИПТ ЗАПУСКА МОНИТОРИНГА
Запускает мониторинг dashboard для системы сигналов
"""

import asyncio
import logging
import sys
from signal_monitoring_dashboard import run_monitoring_dashboard

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Главная функция запуска мониторинга"""
    logger.info("🚀 Запуск мониторинг dashboard для ATRA...")
    
    try:
        # Запускаем dashboard
        run_monitoring_dashboard(
            host='0.0.0.0',
            port=8080,
            debug=False
        )
    except KeyboardInterrupt:
        logger.info("🛑 Мониторинг остановлен пользователем")
    except Exception as e:
        logger.error("❌ Ошибка запуска мониторинга: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
