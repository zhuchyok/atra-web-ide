"""
Self-Check System - система самопроверки всех компонентов корпорации.

Обеспечивает:
- Автоматическую проверку всех критических компонентов
- Диагностику проблем
- Автоматическое исправление
- Отчетность и алерты
- АВТОНОМНЫЙ ЗАПУСК - система проверяет сама себя
"""

import asyncio
import logging
import subprocess
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ComponentStatus(Enum):
    """Статус компонента"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentCheck:
    """Результат проверки компонента"""
    name: str
    status: ComponentStatus
    message: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    auto_fixed: bool = False
    fix_attempts: int = 0


class SelfCheckSystem:
    """
    Система самопроверки всех компонентов корпорации.
    
    ✅ САМОПРОВЕРЯЮЩАЯСЯ: Система проверяет сама себя и запускается автономно.
    """
    
    def __init__(
        self,
        check_interval: int = 60,  # Интервал проверки (секунды)
        auto_fix_enabled: bool = True,
        alert_on_critical: bool = True
    ):
        self.check_interval = check_interval
        self.auto_fix_enabled = auto_fix_enabled
        self.alert_on_critical = alert_on_critical
        self.monitoring_active = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self.check_history: List[ComponentCheck] = []
        self.component_statuses: Dict[str, ComponentStatus] = {}
        self.self_check_enabled = True  # Проверка самой себя
    
    async def check_self(self) -> ComponentCheck:
        """Проверка самой системы самопроверки"""
        try:
            # Проверяем, что мониторинг активен
            if not self.monitoring_active:
                return ComponentCheck(
                    name="Self-Check System",
                    status=ComponentStatus.DEGRADED,
                    message="Мониторинг не активен",
                    timestamp=datetime.now()
                )
            
            # Проверяем, что задача мониторинга работает
            if self._monitoring_task and self._monitoring_task.done():
                return ComponentCheck(
                    name="Self-Check System",
                    status=ComponentStatus.UNHEALTHY,
                    message="Задача мониторинга завершена",
                    timestamp=datetime.now()
                )
            
            # Проверяем последнюю проверку
            if self.check_history:
                last_check = self.check_history[-1]
                time_since_check = (datetime.now() - last_check.timestamp).total_seconds()
                if time_since_check > self.check_interval * 2:
                    return ComponentCheck(
                        name="Self-Check System",
                        status=ComponentStatus.DEGRADED,
                        message=f"Последняя проверка была {time_since_check:.0f} секунд назад",
                        timestamp=datetime.now()
                    )
            
            return ComponentCheck(
                name="Self-Check System",
                status=ComponentStatus.HEALTHY,
                message="Система работает нормально",
                timestamp=datetime.now(),
                details={
                    "monitoring_active": self.monitoring_active,
                    "check_history_count": len(self.check_history),
                    "components_monitored": len(self.component_statuses)
                }
            )
        except Exception as e:
            return ComponentCheck(
                name="Self-Check System",
                status=ComponentStatus.UNHEALTHY,
                message=f"Ошибка самопроверки: {e}",
                timestamp=datetime.now()
            )
    
    async def check_victoria(self) -> ComponentCheck:
        """Проверка Victoria Agent"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:8010/health")
                if response.status_code == 200:
                    data = response.json()
                    status = ComponentStatus.HEALTHY if data.get("status") == "ok" else ComponentStatus.DEGRADED
                    return ComponentCheck(
                        name="Victoria Agent",
                        status=status,
                        message=f"Status: {data.get('status')}",
                        timestamp=datetime.now(),
                        details=data
                    )
                else:
                    return ComponentCheck(
                        name="Victoria Agent",
                        status=ComponentStatus.UNHEALTHY,
                        message=f"HTTP {response.status_code}",
                        timestamp=datetime.now()
                    )
        except Exception as e:
            return ComponentCheck(
                name="Victoria Agent",
                status=ComponentStatus.UNHEALTHY,
                message=f"Ошибка подключения: {e}",
                timestamp=datetime.now()
            )
    
    async def check_veronica(self) -> ComponentCheck:
        """Проверка Veronica Agent"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:8011/health")
                if response.status_code == 200:
                    data = response.json()
                    status = ComponentStatus.HEALTHY if data.get("status") == "ok" else ComponentStatus.DEGRADED
                    return ComponentCheck(
                        name="Veronica Agent",
                        status=status,
                        message=f"Status: {data.get('status')}",
                        timestamp=datetime.now(),
                        details=data
                    )
                else:
                    return ComponentCheck(
                        name="Veronica Agent",
                        status=ComponentStatus.UNHEALTHY,
                        message=f"HTTP {response.status_code}",
                        timestamp=datetime.now()
                    )
        except Exception as e:
            return ComponentCheck(
                name="Veronica Agent",
                status=ComponentStatus.UNHEALTHY,
                message=f"Ошибка подключения: {e}",
                timestamp=datetime.now()
            )
    
    async def check_database(self) -> ComponentCheck:
        """Проверка Knowledge OS Database"""
        try:
            import asyncpg
            db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
            conn = await asyncpg.connect(db_url)
            try:
                result = await conn.fetchval("SELECT 1")
                if result == 1:
                    tables = await conn.fetch("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                        AND table_name IN ('tasks', 'knowledge_nodes', 'experts', 'domains')
                    """)
                    missing_tables = {"tasks", "knowledge_nodes", "experts", "domains"} - {t["table_name"] for t in tables}
                    
                    if missing_tables:
                        return ComponentCheck(
                            name="Knowledge OS Database",
                            status=ComponentStatus.DEGRADED,
                            message=f"Отсутствуют таблицы: {', '.join(missing_tables)}",
                            timestamp=datetime.now()
                        )
                    
                    return ComponentCheck(
                        name="Knowledge OS Database",
                        status=ComponentStatus.HEALTHY,
                        message="Подключение успешно, все таблицы на месте",
                        timestamp=datetime.now()
                    )
            finally:
                await conn.close()
        except Exception as e:
            return ComponentCheck(
                name="Knowledge OS Database",
                status=ComponentStatus.UNHEALTHY,
                message=f"Ошибка подключения: {e}",
                timestamp=datetime.now()
            )
    
    async def check_ollama(self) -> ComponentCheck:
        """Проверка Ollama"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    if models:
                        return ComponentCheck(
                            name="Ollama",
                            status=ComponentStatus.HEALTHY,
                            message=f"Доступно моделей: {len(models)}",
                            timestamp=datetime.now(),
                            details={"model_count": len(models)}
                        )
                    else:
                        return ComponentCheck(
                            name="Ollama",
                            status=ComponentStatus.DEGRADED,
                            message="Нет доступных моделей",
                            timestamp=datetime.now()
                        )
                else:
                    return ComponentCheck(
                        name="Ollama",
                        status=ComponentStatus.UNHEALTHY,
                        message=f"HTTP {response.status_code}",
                        timestamp=datetime.now()
                    )
        except Exception as e:
            return ComponentCheck(
                name="Ollama",
                status=ComponentStatus.UNHEALTHY,
                message=f"Ошибка подключения: {e}",
                timestamp=datetime.now()
            )
    
    async def check_redis(self) -> ComponentCheck:
        """Проверка Redis"""
        try:
            import redis.asyncio as redis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            r = redis.from_url(redis_url)
            await r.ping()
            await r.close()
            return ComponentCheck(
                name="Redis",
                status=ComponentStatus.HEALTHY,
                message="Подключение успешно",
                timestamp=datetime.now()
            )
        except Exception as e:
            return ComponentCheck(
                name="Redis",
                status=ComponentStatus.UNHEALTHY,
                message=f"Ошибка подключения: {e}",
                timestamp=datetime.now()
            )
    
    async def check_autonomous_systems(self) -> List[ComponentCheck]:
        """Проверка автономных систем"""
        checks = []
        
        systems = [
            ("Nightly Learner", "nightly_learner.py"),
            ("Debate Processor", "debate_processor.py"),
            ("Smart Worker", "smart_worker_autonomous.py")
        ]
        
        for name, script_name in systems:
            try:
                result = subprocess.run(
                    ["docker", "exec", "knowledge_os_api", "pgrep", "-f", script_name],
                    capture_output=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    checks.append(ComponentCheck(
                        name=name,
                        status=ComponentStatus.HEALTHY,
                        message="Процесс запущен",
                        timestamp=datetime.now()
                    ))
                else:
                    checks.append(ComponentCheck(
                        name=name,
                        status=ComponentStatus.UNHEALTHY,
                        message="Процесс не найден",
                        timestamp=datetime.now()
                    ))
            except Exception as e:
                checks.append(ComponentCheck(
                    name=name,
                    status=ComponentStatus.UNKNOWN,
                    message=f"Ошибка проверки: {e}",
                    timestamp=datetime.now()
                ))
        
        return checks
    
    async def auto_fix_component(self, check: ComponentCheck) -> bool:
        """Автоматическое исправление компонента"""
        if not self.auto_fix_enabled:
            return False
        
        check.fix_attempts += 1
        
        try:
            if check.name == "Victoria Agent":
                subprocess.run(["docker", "restart", "victoria-agent"], timeout=30)
                await asyncio.sleep(5)
                new_check = await self.check_victoria()
                if new_check.status == ComponentStatus.HEALTHY:
                    check.auto_fixed = True
                    check.status = ComponentStatus.HEALTHY
                    check.message = "Автоматически исправлено (перезапуск)"
                    return True
            
            elif check.name == "Veronica Agent":
                subprocess.run(["docker", "restart", "veronica-agent"], timeout=30)
                await asyncio.sleep(5)
                new_check = await self.check_veronica()
                if new_check.status == ComponentStatus.HEALTHY:
                    check.auto_fixed = True
                    check.status = ComponentStatus.HEALTHY
                    check.message = "Автоматически исправлено (перезапуск)"
                    return True
            
            elif check.name == "Self-Check System":
                # Если система самопроверки упала, перезапускаем мониторинг
                if not self.monitoring_active:
                    await self.start_monitoring()
                    check.auto_fixed = True
                    check.status = ComponentStatus.HEALTHY
                    check.message = "Автоматически исправлено (перезапуск мониторинга)"
                    return True
            
        except Exception as e:
            logger.error(f"❌ [SELF-CHECK] Ошибка автоматического исправления {check.name}: {e}")
        
        return False

    async def _create_recovery_task(self, check: ComponentCheck) -> None:
        """Создать задачу в БД при деградации компонента (если auto_fix не сработал)."""
        try:
            import asyncpg
            db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
            conn = await asyncpg.connect(db_url)
            try:
                full_title = f"🔧 Self-Check: восстановить {check.name}"
                # Избегаем дублирования: не создаём если такая задача уже есть за последние 24ч
                existing = await conn.fetchval("""
                    SELECT 1 FROM tasks
                    WHERE title = $1 AND created_at > NOW() - INTERVAL '24 hours'
                    LIMIT 1
                """, full_title)
                if existing:
                    return
                description = f"Компонент {check.name}: {check.status.value}. {check.message}"
                metadata = json.dumps({
                    "source": "self_check_system",
                    "assignee_hint": "SRE",
                    "component": check.name,
                    "status": check.status.value,
                })
                await conn.execute("""
                    INSERT INTO tasks (title, description, status, priority, metadata)
                    VALUES ($1, $2, 'pending', 'high', $3::jsonb)
                """, full_title, description, metadata)
                logger.info(f"📋 [SELF-CHECK] Создана задача на восстановление: {check.name}")
            finally:
                await conn.close()
        except ImportError:
            logger.debug("asyncpg не доступен, пропускаем создание задачи self_check")
        except Exception as e:
            logger.warning("Ошибка создания задачи self_check: %s", e)

    async def run_full_check(self) -> Dict[str, Any]:
        """Запуск полной проверки всех компонентов"""
        logger.info("🔍 [SELF-CHECK] Запуск полной проверки системы...")
        
        checks = []
        
        # Проверяем все компоненты
        checks.append(await self.check_victoria())
        checks.append(await self.check_veronica())
        checks.append(await self.check_database())
        checks.append(await self.check_ollama())
        checks.append(await self.check_redis())
        checks.extend(await self.check_autonomous_systems())
        
        # ✅ ВАЖНО: Проверяем саму систему самопроверки
        if self.self_check_enabled:
            checks.append(await self.check_self())

        # Предиктивный мониторинг (Living Organism §6) — тренды, пороги → задачи
        try:
            from app.predictive_monitor import run_predictive_check
            pred = await run_predictive_check()
            if pred.get("tasks_created", 0) > 0:
                logger.info("📊 [PREDICTIVE] Создано %s задач (stuck=%s, old_pending=%s)",
                            pred["tasks_created"], pred.get("stuck_count"), pred.get("old_pending_count"))
        except Exception as e:
            logger.debug("Predictive check failed: %s", e)
        
        # Обновляем статусы
        for check in checks:
            self.component_statuses[check.name] = check.status
            
            # Автоматическое исправление
            if check.status in [ComponentStatus.UNHEALTHY, ComponentStatus.DEGRADED]:
                if check.fix_attempts < 3:
                    fixed = await self.auto_fix_component(check)
                    if fixed:
                        logger.info(f"✅ [SELF-CHECK] {check.name} автоматически исправлен")
                # Если auto_fix не сработал — создаём задачу в БД для SRE
                if not check.auto_fixed and check.status in [ComponentStatus.UNHEALTHY, ComponentStatus.DEGRADED]:
                    await self._create_recovery_task(check)
        
        # Сохраняем в историю
        self.check_history.extend(checks)
        if len(self.check_history) > 100:
            self.check_history = self.check_history[-100:]
        
        # Формируем отчет
        healthy_count = sum(1 for c in checks if c.status == ComponentStatus.HEALTHY)
        degraded_count = sum(1 for c in checks if c.status == ComponentStatus.DEGRADED)
        unhealthy_count = sum(1 for c in checks if c.status == ComponentStatus.UNHEALTHY)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(checks),
                "healthy": healthy_count,
                "degraded": degraded_count,
                "unhealthy": unhealthy_count
            },
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "auto_fixed": c.auto_fixed,
                    "fix_attempts": c.fix_attempts
                }
                for c in checks
            ]
        }
        
        if unhealthy_count > 0 and self.alert_on_critical:
            logger.error(f"🚨 [SELF-CHECK] КРИТИЧНО: {unhealthy_count} компонентов нездоровы!")
        
        logger.info(f"✅ [SELF-CHECK] Проверка завершена: {healthy_count} здоровых, {degraded_count} деградированных, {unhealthy_count} нездоровых")
        
        return report
    
    async def start_monitoring(self):
        """Запуск фонового мониторинга"""
        if self.monitoring_active:
            logger.warning("⚠️ [SELF-CHECK] Мониторинг уже запущен")
            return
        
        self.monitoring_active = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("✅ [SELF-CHECK] Мониторинг запущен (САМОПРОВЕРЯЮЩАЯСЯ СИСТЕМА)")
    
    async def stop_monitoring(self):
        """Остановка мониторинга"""
        self.monitoring_active = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ [SELF-CHECK] Мониторинг остановлен")
    
    async def _monitoring_loop(self):
        """Основной цикл мониторинга - работает АВТОНОМНО"""
        logger.info("🔄 [SELF-CHECK] Цикл мониторинга запущен (автономный режим)")
        
        while self.monitoring_active:
            try:
                await self.run_full_check()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ [SELF-CHECK] Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(10)


# Глобальный экземпляр
_self_check_system: Optional[SelfCheckSystem] = None


def get_self_check_system() -> SelfCheckSystem:
    """Получить глобальный экземпляр SelfCheckSystem"""
    global _self_check_system
    if _self_check_system is None:
        _self_check_system = SelfCheckSystem()
    return _self_check_system


# ✅ АВТОНОМНЫЙ ЗАПУСК - система запускается сама при импорте
async def start_autonomous_self_check():
    """Автономный запуск системы самопроверки"""
    system = get_self_check_system()
    await system.start_monitoring()
    logger.info("✅ [SELF-CHECK] Автономная система самопроверки запущена")


# Запуск при импорте модуля (если запущен как скрипт)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_autonomous_self_check())
    # Держим процесс живым
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        logger.info("⏹️ [SELF-CHECK] Остановка по запросу пользователя")
