"""
Менеджер системы ИИ для торгового бота ATRA.

Содержит функции для управления инициализацией и запуском
компонентов системы искусственного интеллекта.

⚠️ MIGRATION TO STATELESS ARCHITECTURE:
Module-level variable _ai_instances has been replaced with AISystemManager class
for explicit state management.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

# Импорты ИИ системы
try:
    from src.ai.auto_learning import AutoLearningSystem
    from src.ai.historical_analysis import run_historical_analysis
    from src.ai.integration import start_ai_learning_integration
    from src.ai.learning import AILearningSystem
    from src.ai.monitor import AIMonitor
    from src.ai.signal_generator import AISignalGenerator

    print("✅ ИИ системы загружены (с lazy initialization)")
    AI_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ ИИ система недоступна: {e}")
    AI_AVAILABLE = False

logger = logging.getLogger(__name__)

# =============================================================================
# STATELESS AI SYSTEM MANAGER
# =============================================================================


class AISystemManager:
    """
    Менеджер экземпляров ИИ системы (stateless architecture).

    Управляет экземплярами ИИ компонентов через явное состояние,
    заменяя модульную переменную _ai_instances.

    Example:
        ```python
        manager = AISystemManager()
        instance = manager.get_instance('ai_learning')
        manager.set_instance('ai_learning', AILearningSystem())
        ```
    """

    def __init__(self):
        """Initialize empty AI instances dictionary"""
        self._instances: Dict[str, Any] = {}

    def get_instance(self, key: str) -> Optional[Any]:
        """
        Get AI instance by key.

        Args:
            key: Instance key (e.g., 'ai_learning', 'ai_monitor')

        Returns:
            AI instance or None if not found
        """
        return self._instances.get(key)

    def set_instance(self, key: str, instance: Any) -> None:
        """
        Set AI instance.

        Args:
            key: Instance key
            instance: AI instance object
        """
        self._instances[key] = instance

    def has_instance(self, key: str) -> bool:
        """
        Check if instance exists.

        Args:
            key: Instance key

        Returns:
            True if instance exists
        """
        return key in self._instances

    def clear_all(self) -> None:
        """Clear all AI instances"""
        self._instances.clear()

    def get_all_keys(self) -> list:
        """Get all instance keys"""
        return list(self._instances.keys())


# Singleton instance for application-wide AI management
_ai_manager: Optional[AISystemManager] = None


def get_ai_manager() -> AISystemManager:
    """
    Get singleton AI system manager instance.

    Returns:
        AISystemManager instance
    """
    global _ai_manager
    if _ai_manager is None:
        _ai_manager = AISystemManager()
    return _ai_manager


def reset_ai_manager() -> None:
    """Reset AI manager (useful for testing)"""
    global _ai_manager
    _ai_manager = None


def cleanup_ai_instances():
    """
    Очищает экземпляры ИИ системы (stateless).

    Uses AISystemManager for explicit state management.
    """
    manager = get_ai_manager()
    if manager.get_all_keys():
        print("🧹 Очистка ИИ экземпляров...")
        manager.clear_all()
        print("✅ ИИ экземпляры очищены")
    else:
        print("ℹ️ ИИ экземпляры уже очищены или не были инициализированы")


async def run_ai_learning_system(ai_manager: Optional[AISystemManager] = None):
    """
    Запускает систему обучения ИИ (stateless architecture).

    Args:
        ai_manager: Optional AI system manager instance (uses singleton if None)
    """
    if not AI_AVAILABLE:
        print("⚠️ ИИ система недоступна, пропускаем...")
        return

    # Use singleton instance if not provided (backward compatibility)
    if ai_manager is None:
        ai_manager = get_ai_manager()

    try:
        print("🤖 Запуск системы обучения ИИ...")

        # Проверяем, не инициализированы ли уже компоненты
        if ai_manager.has_instance("ai_learning"):
            print("⚠️ ИИ система уже инициализирована, пропускаем дублирование...")
            return

        # Инициализируем ИИ компоненты ОДИН РАЗ
        print("🔧 Инициализация ИИ компонентов...")
        ai_manager.set_instance("ai_learning", AILearningSystem())
        ai_manager.set_instance("ai_monitor", AIMonitor())
        ai_manager.set_instance("auto_learning", AutoLearningSystem())
        ai_manager.set_instance("ai_signal_generator", AISignalGenerator())

        # Запускаем задачи ОДИН РАЗ
        print("🚀 Запуск ИИ задач...")
        asyncio.create_task(ai_manager.get_instance("ai_monitor").start_monitoring())
        asyncio.create_task(ai_manager.get_instance("auto_learning").start_auto_learning())
        asyncio.create_task(
            ai_manager.get_instance("ai_signal_generator").start_signal_generation()
        )
        asyncio.create_task(ai_manager.get_instance("ai_learning").continuous_learning())
        asyncio.create_task(start_ai_learning_integration())
        asyncio.create_task(run_historical_analysis())

        # 🆕 Запускаем оптимизатор фильтров (с lazy initialization ВНУТРИ task)
        async def run_filter_optimizer():
            """
            Задача оптимизатора фильтров с ленивой инициализацией.
            """
            try:
                from src.ai.filter_optimizer import (
                    get_filter_optimizer,  # pylint: disable=import-outside-toplevel
                )

                optimizer = get_filter_optimizer()
                logger.info("🤖 Оптимизатор фильтров инициализирован")
                await optimizer.start_auto_optimization()
            except (ValueError, TypeError, KeyError, ConnectionError) as e:
                logger.error(
                    "❌ Ошибка в оптимизаторе фильтров: %s",
                    e,
                    extra={
                        "error_type": type(e).__name__,
                        "module": "filter_optimizer",
                        "trace_id": "main_loop",
                    },
                )
            except Exception as e:
                logger.critical(
                    "❌ Критическая ошибка в оптимизаторе фильтров: %s", e, exc_info=True
                )
                # Алерт админу и fallback
                try:
                    # Алерт админу через логирование
                    logger.critical(
                        "🚨 КРИТИЧЕСКАЯ ОШИБКА В ОПТИМИЗАТОРЕ - ТРЕБУЕТСЯ ВМЕШАТЕЛЬСТВО АДМИНА!"
                    )
                except Exception:
                    pass

        print("🤖 Запуск оптимизатора фильтров...")
        asyncio.create_task(run_filter_optimizer())

        # Принудительно запускаем анализ исторических данных при старте (неблокирующий)
        print("📊 Анализ исторических данных при запуске...")
        asyncio.create_task(ai_manager.get_instance("auto_learning").force_historical_analysis())

        print("✅ ИИ система запущена с автоматическим обучением и генерацией сигналов")
        print("✅ Оптимизатор фильтров запущен (обновление каждые 6 часов)")

    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
        print(f"❌ Ошибка запуска ИИ системы: {e}")
