#!/usr/bin/env python3
"""
🔧 SINGLETON REGISTRY ДЛЯ ИИ СИСТЕМЫ
Централизованное управление экземплярами ИИ компонентов
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AISingletonRegistry:
    """Реестр singleton экземпляров ИИ системы"""
    
    _instances: Dict[str, Any] = {}
    _initialized = False
    
    @classmethod
    def get_instance(cls, instance_type: str, factory_func=None, *args, **kwargs):
        """Получает или создает singleton экземпляр"""
        if not cls._initialized:
            cls._instances = {}
            cls._initialized = True
        
        if instance_type not in cls._instances:
            if factory_func:
                logger.info("🤖 Создаем новый экземпляр %s", instance_type)
                cls._instances[instance_type] = factory_func(*args, **kwargs)
            else:
                logger.warning("⚠️ Фабричная функция не предоставлена для %s", instance_type)
                return None
        else:
            logger.debug("✅ Используем существующий экземпляр %s", instance_type)
        
        return cls._instances[instance_type]
    
    @classmethod
    def register_instance(cls, instance_type: str, instance: Any):
        """Регистрирует экземпляр в реестре"""
        if not cls._initialized:
            cls._instances = {}
            cls._initialized = True
        
        cls._instances[instance_type] = instance
        logger.info("📝 Зарегистрирован экземпляр %s", instance_type)
    
    @classmethod
    def has_instance(cls, instance_type: str) -> bool:
        """Проверяет, есть ли экземпляр в реестре"""
        return instance_type in cls._instances
    
    @classmethod
    def clear_all(cls):
        """Очищает все экземпляры"""
        cls._instances.clear()
        cls._initialized = False
        logger.info("🧹 Все экземпляры очищены")
    
    @classmethod
    def get_all_instances(cls) -> Dict[str, Any]:
        """Возвращает все экземпляры"""
        return cls._instances.copy()
    
    @classmethod
    def get_instance_count(cls) -> int:
        """Возвращает количество экземпляров"""
        return len(cls._instances)

# Глобальный реестр
ai_registry = AISingletonRegistry()

def get_ai_learning_system():
    """Получает singleton экземпляр AILearningSystem"""
    from src.ai.learning import AILearningSystem
    return ai_registry.get_instance('ai_learning', AILearningSystem)

def get_ai_integration():
    """Получает singleton экземпляр AIIntegration"""
    from src.ai.integration import AIIntegration
    return ai_registry.get_instance('ai_integration', AIIntegration)

def get_ai_monitor():
    """Получает singleton экземпляр AIMonitor"""
    from src.ai.monitor import AIMonitor
    return ai_registry.get_instance('ai_monitor', AIMonitor)

def get_auto_learning_system():
    """Получает singleton экземпляр AutoLearningSystem"""
    from ai_auto_learning import AutoLearningSystem
    return ai_registry.get_instance('auto_learning', AutoLearningSystem)

def get_ai_signal_generator():
    """Получает singleton экземпляр AISignalGenerator"""
    from ai_signal_generator import AISignalGenerator
    return ai_registry.get_instance('ai_signal_generator', AISignalGenerator)

def get_historical_analyzer():
    """Получает singleton экземпляр HistoricalDataAnalyzer"""
    try:
        from src.ai.historical_analysis import HistoricalDataAnalyzer
    except ImportError:
        try:
            from ai_historical_analysis import HistoricalDataAnalyzer
        except ImportError:
            class HistoricalDataAnalyzer: pass
    return ai_registry.get_instance('historical_analyzer', HistoricalDataAnalyzer)

# Функции для тестирования
def test_singleton():
    """Тестирует singleton pattern"""
    print("🧪 Тестирование singleton registry...")
    
    # Получаем экземпляры
    ai1 = get_ai_learning_system()
    ai2 = get_ai_learning_system()
    
    integration1 = get_ai_integration()
    integration2 = get_ai_integration()
    
    print(f"AI Learning 1: {id(ai1)}")
    print(f"AI Learning 2: {id(ai2)}")
    print(f"Same AI Learning: {ai1 is ai2}")
    
    print(f"Integration 1: {id(integration1)}")
    print(f"Integration 2: {id(integration2)}")
    print(f"Same Integration: {integration1 is integration2}")
    
    print(f"AI Learning in Integration 1: {id(integration1.ai_learning)}")
    print(f"AI Learning in Integration 2: {id(integration2.ai_learning)}")
    print(f"Same AI Learning in Integration: {integration1.ai_learning is integration2.ai_learning}")
    
    if ai1 is ai2 and integration1 is integration2 and integration1.ai_learning is integration2.ai_learning:
        print("✅ SUCCESS: Singleton pattern работает!")
    else:
        print("❌ FAIL: Singleton pattern не работает")
    
    print(f"Всего экземпляров в реестре: {ai_registry.get_instance_count()}")

if __name__ == "__main__":
    test_singleton()
