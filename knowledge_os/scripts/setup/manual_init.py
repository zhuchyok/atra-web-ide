#!/usr/bin/env python3
"""
Ручная инициализация системы принятия сигналов
"""

import asyncio
import logging
from src.signals.acceptance_manager import SignalAcceptanceManager
from acceptance_database import AcceptanceDatabase
from telegram_message_updater import TelegramMessageUpdater
from src.execution.position_manager import ImprovedPositionManager

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger('manual_init')

async def manual_initialize_acceptance_system():
    """Ручная инициализация системы принятия сигналов"""
    
    try:
        logger.info("🔧 РУЧНАЯ ИНИЦИАЛИЗАЦИЯ СИСТЕМЫ ПРИНЯТИЯ СИГНАЛОВ...")
        
        # Инициализируем компоненты
        acceptance_db = AcceptanceDatabase()
        telegram_updater = TelegramMessageUpdater()
        position_manager = ImprovedPositionManager(acceptance_db, telegram_updater)
        
        signal_acceptance = SignalAcceptanceManager(
            acceptance_db, 
            telegram_updater, 
            position_manager
        )
        
        # Инициализируем систему (загружаем pending сигналы)
        await signal_acceptance.initialize()
        
        logger.info("✅ Система принятия сигналов инициализирована")
        
        # Проверяем работу
        test_signals = acceptance_db.get_pending_signals()
        logger.info(f"📋 Найдено ожидающих сигналов: {len(test_signals)}")
        
        # Проверяем загруженные сигналы в pending_signals
        logger.info(f"📊 Загружено в pending_signals: {len(signal_acceptance.pending_signals)}")
        
        if signal_acceptance.pending_signals:
            logger.info("📋 Первые несколько pending сигналов:")
            for i, (key, signal_data) in enumerate(list(signal_acceptance.pending_signals.items())[:3]):
                logger.info(f"   {i+1}. {key}: {signal_data.symbol} {signal_data.direction}")
        
        # Тестируем принятие сигнала
        if signal_acceptance.pending_signals:
            test_key = list(signal_acceptance.pending_signals.keys())[0]
            test_signal = signal_acceptance.pending_signals[test_key]
            
            logger.info(f"🧪 Тестируем принятие сигнала: {test_signal.symbol}")
            
            # Получаем timestamp из signal_data
            signal_timestamp = test_signal.signal_time.timestamp()
            user_id = "556251171"
            
            result = await signal_acceptance.accept_signal(
                test_signal.symbol, 
                signal_timestamp, 
                user_id
            )
            
            if result:
                logger.info(f"✅ Сигнал {test_signal.symbol} успешно принят!")
            else:
                logger.error(f"❌ Ошибка принятия сигнала {test_signal.symbol}")
        
        logger.info("🎉 СИСТЕМА ПРИНЯТИЯ СИГНАЛОВ ГОТОВА К РАБОТЕ!")
        return signal_acceptance
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        import traceback
        traceback.print_exc()
        return None

# Глобальная переменная для доступа
SIGNAL_ACCEPTANCE_SYSTEM = None

async def get_signal_acceptance_system():
    """Получить инициализированную систему принятия сигналов"""
    global SIGNAL_ACCEPTANCE_SYSTEM
    
    if SIGNAL_ACCEPTANCE_SYSTEM is None:
        SIGNAL_ACCEPTANCE_SYSTEM = await manual_initialize_acceptance_system()
    
    return SIGNAL_ACCEPTANCE_SYSTEM

if __name__ == "__main__":
    print("🚀 ЗАПУСК РУЧНОЙ ИНИЦИАЛИЗАЦИИ СИСТЕМЫ ПРИНЯТИЯ СИГНАЛОВ")
    print("=" * 70)
    
    system = asyncio.run(manual_initialize_acceptance_system())
    
    if system:
        print("\n✅ СИСТЕМА УСПЕШНО ИНИЦИАЛИЗИРОВАНА!")
        print("📋 Используйте SIGNAL_ACCEPTANCE_SYSTEM в основном коде")
        
        # Показываем статистику
        print(f"\n📊 СТАТИСТИКА:")
        print(f"   - Ожидающих сигналов: {len(system.pending_signals)}")
        print(f"   - Активных позиций: {len(system.active_positions)}")
        
    else:
        print("\n❌ НЕ УДАЛОСЬ ИНИЦИАЛИЗИРОВАТЬ СИСТЕМУ!")
