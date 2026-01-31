"""
System Initialization - Инициализация всех компонентов Self-Validating Code

Централизованная инициализация всех принципов Self-Validating Code при старте системы
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def initialize_self_validating_system() -> bool:
    """
    Инициализация всех компонентов Self-Validating Code
    
    Returns:
        True если инициализация успешна, False иначе
    """
    try:
        # 1. Регистрация инвариантов
        try:
            from src.core.invariants import register_all_invariants
            register_all_invariants()
            logger.info("✅ Инварианты зарегистрированы")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка регистрации инвариантов: {e}")
        
        # 2. Регистрация health checks
        try:
            from src.core.health_checks import register_system_health_checks
            register_system_health_checks()
            logger.info("✅ Health checks зарегистрированы")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка регистрации health checks: {e}")
        
        # 3. Регистрация state machines
        try:
            from src.core.state_machine_rules import register_state_machines
            register_state_machines()
            logger.info("✅ State machines зарегистрированы")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка регистрации state machines: {e}")
        
        # 4. Регистрация валидации конфигурации
        try:
            from src.core.config_validations import register_config_validations
            register_config_validations()
            logger.info("✅ Валидация конфигурации зарегистрирована")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка регистрации валидации конфигурации: {e}")
        
        logger.info("✅ Система Self-Validating Code инициализирована")
        return True
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка инициализации Self-Validating Code: {e}")
        return False


async def check_system_health() -> dict:
    """
    Проверка здоровья системы
    
    Returns:
        Словарь со статусом здоровья системы
    """
    try:
        from src.core.health import get_health_manager
        
        manager = get_health_manager()
        status = await manager.check_all()
        
        return {
            "healthy": status.is_healthy(),
            "overall_status": status.overall_status.value,
            "checks": [
                {
                    "name": check.name,
                    "status": check.status.value,
                    "message": check.message,
                    "critical": check.critical,
                    "response_time_ms": check.response_time_ms
                }
                for check in status.checks
            ],
            "critical_failures": len(status.get_critical_failures()),
            "unhealthy_checks": len(status.get_unhealthy_checks())
        }
    except Exception as e:
        logger.error(f"Ошибка проверки здоровья системы: {e}")
        return {
            "healthy": False,
            "overall_status": "unknown",
            "error": str(e)
        }

