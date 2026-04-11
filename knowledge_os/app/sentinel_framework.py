import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

try:
    from app.event_bus import Event, EventType, get_event_bus
except ImportError:
    from event_bus import Event, EventType, get_event_bus
from app.redis_manager import redis_manager

logger = logging.getLogger("ExpertSentinel")


class ExpertSentinel:
    """
    Универсальный страж эксперта (Sentinel).
    Следит за событиями и автоматически инициирует действия.
    """

    def __init__(self, expert_name: str, department: str, triggers: List[EventType]):
        self.expert_name = expert_name
        self.department = department
        self.triggers = triggers
        self.event_bus = get_event_bus()
        self.is_running = False

    async def start(self):
        """Запуск стража и подписка на события."""
        if self.is_running:
            return

        for event_type in self.triggers:
            self.event_bus.subscribe(event_type, self.handle_event)

        self.is_running = True
        logger.info(f"🛡️ Sentinel [{self.expert_name}] запущен (Dept: {self.department})")

    async def handle_event(self, event: Event):
        """Диспетчер обработки событий."""
        logger.debug(f"🔔 Sentinel {self.expert_name} получил событие: {event.event_type.value}")

        # Логика принятия решения (Reflexive Layer - 1.2B model logic simulation)
        should_act = await self._decide_to_act(event)

        if should_act:
            await self._initiate_action(event)

    async def _decide_to_act(self, event: Event) -> bool:
        """Рефлекторный уровень: нужно ли реагировать?"""
        # Анна реагирует на изменения кода
        if self.expert_name == "Анна" and event.event_type in [
            EventType.FILE_CREATED,
            EventType.FILE_MODIFIED,
        ]:
            path = event.payload.get("file_path", "")
            return any(ext in path for ext in [".py", ".js", ".svelte", ".ts"])

        # Роман реагирует на события БД
        if self.expert_name == "Роман" and event.event_type == EventType.PERFORMANCE_DEGRADED:
            return event.payload.get("metric") in ["db_connections", "slow_queries"]

        # Максим реагирует на ошибки безопасности
        if self.expert_name == "Максим" and event.event_type == EventType.ERROR_DETECTED:
            return (
                "security" in str(event.payload).lower()
                or "injection" in str(event.payload).lower()
            )

        return False

    async def _initiate_action(self, event: Event):
        """Когнитивный уровень: постановка задачи в Task Queue v2."""
        task_id = str(uuid.uuid4())
        description = self._generate_task_description(event)

        task_data = {
            "task_id": task_id,
            "expert_name": self.expert_name,
            "description": description,
            "category": "autonomous",
            "metadata": {
                "sentinel": True,
                "source_event": event.event_id,
                "priority": "high" if event.event_type == EventType.ERROR_DETECTED else "medium",
            },
        }

        try:
            await redis_manager.push_to_stream("expert_tasks", task_data)
            logger.info(
                f"🚀 [SENTINEL] {self.expert_name} инициировал задачу {task_id}: {description[:50]}..."
            )

            # Публикуем событие о начале автономной работы
            await self.event_bus.publish(
                Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.TASK_CREATED,
                    payload=task_data,
                    source=f"sentinel_{self.expert_name}",
                )
            )
        except Exception as e:
            logger.error(f"❌ [SENTINEL] Ошибка постановки задачи для {self.expert_name}: {e}")

    def _generate_task_description(self, event: Event) -> str:
        """Генерация промпта для воркера на основе события."""
        if self.expert_name == "Анна":
            return f"АВТО-ТЕСТ: Обнаружены изменения в {event.payload.get('file_path')}. Запусти тесты в Песочнице и проверь регрессию."
        if self.expert_name == "Роман":
            return f"АВТО-ОПТИМИЗАЦИЯ БД: Метрика {event.payload.get('metric')} = {event.payload.get('value')}. Проверь индексы и нагрузку."
        if self.expert_name == "Максим":
            return f"АВТО-АУДИТ БЕЗОПАСНОСТИ: Зафиксирована аномалия: {event.payload}. Проверь логи на предмет атаки."
        return f"Автономная задача по событию {event.event_type.value}"


async def init_all_sentinels():
    """Инициализация роя стражей."""
    sentinels = [
        ExpertSentinel("Анна", "QA", [EventType.FILE_CREATED, EventType.FILE_MODIFIED]),
        ExpertSentinel("Роман", "Database", [EventType.PERFORMANCE_DEGRADED]),
        ExpertSentinel("Максим", "Security", [EventType.ERROR_DETECTED, EventType.SYSTEM_EVENT]),
        ExpertSentinel("Елена", "Docs", [EventType.KNOWLEDGE_UPDATED]),
    ]

    for s in sentinels:
        await s.start()

    return sentinels
