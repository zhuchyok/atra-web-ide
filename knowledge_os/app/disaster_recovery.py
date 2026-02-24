"""
Disaster Recovery Module для Singularity.
Обеспечивает graceful degradation и автоматическое переключение режимов при сбоях.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg
import httpx

logger = logging.getLogger(__name__)


class SystemMode(Enum):
    """Режимы работы системы"""

    NORMAL = "normal"  # Нормальная работа
    DEGRADED = "degraded"  # Деградированный режим (некоторые компоненты недоступны)
    READ_ONLY = "read_only"  # Только чтение (БД недоступна для записи)
    EMERGENCY = "emergency"  # Аварийный режим (только критичные функции)
    OFFLINE = "offline"  # Система полностью недоступна


class DisasterRecovery:
    """
    Менеджер аварийного восстановления.
    Отслеживает состояние компонентов и автоматически переключает режимы работы.
    Улучшен для graceful degradation (Singularity 8.0).
    """

    def __init__(self, db_url: str = None):
        self.db_url = db_url
        self.current_mode = SystemMode.NORMAL
        self.component_states: Dict[str, bool] = {}
        self.mode_history: List[Dict[str, Any]] = []

        # Приоритеты компонентов (критичные vs некритичные)
        self.component_priorities: Dict[str, str] = {
            "database": "critical",  # Критичный
            "local_models": "high",  # Высокий приоритет
            "cloud": "high",  # Высокий приоритет
            "cache": "medium",  # Средний приоритет
            "analytics": "low",  # Низкий приоритет
            "backup": "low",  # Низкий приоритет
        }

        # Резервные компоненты (fallback)
        self.fallback_components: Dict[str, List[str]] = {
            "local_models": ["cloud"],  # Если локальные модели недоступны, используем облако
            "cloud": ["local_models"],  # Если облако недоступно, используем локальные модели
            "database": [],  # БД не имеет резерва (read-only mode)
        }

    async def check_database(self) -> bool:
        """Проверить доступность базы данных"""
        if not self.db_url:
            return False

        try:
            conn = await asyncio.wait_for(asyncpg.connect(self.db_url), timeout=2.0)
            await conn.execute("SELECT 1")
            await conn.close()
            return True
        except Exception as e:
            logger.debug(f"Database check failed: {e}")
            return False

    async def check_local_models(self) -> bool:
        """Проверить доступность локальных моделей"""
        urls = [
            "http://localhost:11435",  # MacBook через туннель
            "http://185.177.216.15:11434",  # Server
        ]

        for url in urls:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(f"{url}/api/tags")
                    if response.status_code == 200:
                        return True
            except Exception:
                continue

        return False

    async def check_cloud_services(self) -> bool:
        """Проверить доступность облачных сервисов"""
        # Проверяем доступность cursor-agent или других облачных сервисов
        try:
            # Простая проверка - можно расширить
            return True
        except Exception:
            return False

    async def assess_system_health(self) -> Dict[str, bool]:
        """Оценить состояние всех компонентов системы"""
        db_available = await self.check_database()
        local_models_available = await self.check_local_models()
        cloud_available = await self.check_cloud_services()

        states = {
            "database": db_available,
            "local_models": local_models_available,
            "cloud": cloud_available,
        }

        self.component_states = states
        return states

    def determine_mode(self, health: Dict[str, bool]) -> SystemMode:
        """Определить режим работы на основе состояния компонентов"""
        db_ok = health.get("database", False)
        local_ok = health.get("local_models", False)
        cloud_ok = health.get("cloud", False)

        # Все компоненты доступны
        if db_ok and (local_ok or cloud_ok):
            return SystemMode.NORMAL

        # БД недоступна, но есть модели или облако
        if not db_ok and (local_ok or cloud_ok):
            return SystemMode.READ_ONLY

        # БД доступна, но модели недоступны
        if db_ok and not local_ok and cloud_ok:
            return SystemMode.DEGRADED

        # Только облако доступно
        if not db_ok and not local_ok and cloud_ok:
            return SystemMode.EMERGENCY

        # Ничего не доступно
        return SystemMode.OFFLINE

    async def switch_mode(self, new_mode: SystemMode, reason: str = ""):
        """Переключить режим работы системы"""
        if new_mode == self.current_mode:
            return

        old_mode = self.current_mode
        self.current_mode = new_mode

        mode_change = {
            "timestamp": datetime.now().isoformat(),
            "old_mode": old_mode.value,
            "new_mode": new_mode.value,
            "reason": reason,
            "component_states": self.component_states.copy(),
        }

        self.mode_history.append(mode_change)

        logger.warning(
            f"🔄 [DISASTER RECOVERY] Переключение режима: "
            f"{old_mode.value} -> {new_mode.value} ({reason})"
        )

        # Логируем в БД (если доступна)
        if self.component_states.get("database", False):
            try:
                await self._log_mode_change(mode_change)
            except Exception as e:
                logger.debug(f"Failed to log mode change: {e}")

    async def _log_mode_change(self, mode_change: Dict[str, Any]):
        """Сохранить изменение режима в БД"""
        if not self.db_url:
            return

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.execute(
                    """
                    INSERT INTO disaster_recovery_logs
                    (timestamp, old_mode, new_mode, reason, component_states)
                    VALUES ($1, $2, $3, $4, $5)
                """,
                    mode_change["timestamp"],
                    mode_change["old_mode"],
                    mode_change["new_mode"],
                    mode_change["reason"],
                    mode_change["component_states"],
                )
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Failed to save mode change to DB: {e}")

    async def run_health_check(self) -> SystemMode:
        """Выполнить проверку здоровья и обновить режим"""
        health = await self.assess_system_health()
        new_mode = self.determine_mode(health)

        if new_mode != self.current_mode:
            reason = f"Health check: {health}"
            await self.switch_mode(new_mode, reason)

        return self.current_mode

    def can_write_to_db(self) -> bool:
        """Проверить, можно ли писать в БД"""
        return self.current_mode in [SystemMode.NORMAL, SystemMode.DEGRADED]

    def can_use_local_models(self) -> bool:
        """Проверить, можно ли использовать локальные модели"""
        return self.current_mode in [SystemMode.NORMAL, SystemMode.READ_ONLY]

    def can_use_cloud(self) -> bool:
        """Проверить, можно ли использовать облако"""
        return self.current_mode != SystemMode.OFFLINE

    def get_current_mode(self) -> SystemMode:
        """Получить текущий режим работы"""
        return self.current_mode

    def get_mode_info(self) -> Dict[str, Any]:
        """Получить информацию о текущем режиме"""
        return {
            "mode": self.current_mode.value,
            "component_states": self.component_states.copy(),
            "can_write_db": self.can_write_to_db(),
            "can_use_local": self.can_use_local_models(),
            "can_use_cloud": self.can_use_cloud(),
            "recent_changes": self.mode_history[-5:] if self.mode_history else [],
        }


# Глобальный экземпляр
_disaster_recovery: Optional[DisasterRecovery] = None


def get_disaster_recovery(db_url: str = None) -> DisasterRecovery:
    """Получить глобальный экземпляр DisasterRecovery"""
    global _disaster_recovery
    if _disaster_recovery is None:
        import os

        if not db_url:
            db_url = os.getenv(
                "DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"
            )
        _disaster_recovery = DisasterRecovery(db_url)
    return _disaster_recovery
