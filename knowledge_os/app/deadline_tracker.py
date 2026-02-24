"""
Deadline Tracker - Отслеживание дедлайнов из БД
Публикует события в Event Bus при приближении дедлайнов
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.event_bus import Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


@dataclass
class TaskDeadline:
    """Информация о дедлайне задачи"""

    task_id: str
    task_title: str
    deadline: datetime
    time_until: timedelta
    hours_until: float
    notified_at: List[datetime]  # Времена, когда уже было уведомление


class DeadlineTracker:
    """
    Deadline Tracker - отслеживание дедлайнов задач

    Источники дедлайнов:
    - metadata JSONB в таблице tasks (поле "deadline" или "due_date")
    - Парсинг из описания задачи (даты в тексте)

    Публикует события:
    - DEADLINE_APPROACHING (за 24ч, 12ч, 6ч, 1ч до дедлайна)
    - DEADLINE_PASSED (когда дедлайн прошел)
    """

    def __init__(
        self,
        check_interval: int = 300,  # Интервал проверки в секундах (5 минут)
        notification_thresholds: Optional[List[int]] = None,  # Часы до дедлайна для уведомлений
    ):
        """
        Инициализация Deadline Tracker

        Args:
            check_interval: Интервал проверки в секундах
            notification_thresholds: Список часов до дедлайна для уведомлений (по умолчанию [24, 12, 6, 1])
        """
        self.check_interval = check_interval
        self.notification_thresholds = notification_thresholds or [24, 12, 6, 1]
        self.event_bus = get_event_bus()
        self.running = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self.tracked_deadlines: Dict[str, TaskDeadline] = {}
        self.db_connection = None

        logger.info(
            f"✅ Deadline Tracker инициализирован (пороги: {self.notification_thresholds} часов)"
        )

    async def _get_db_connection(self):
        """Получить подключение к БД"""
        import os

        if self.db_connection is None:
            try:
                import asyncpg

                db_url = os.getenv(
                    "DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"
                )
                self.db_connection = await asyncpg.connect(db_url)
            except ImportError:
                logger.error("❌ asyncpg не установлен, Deadline Tracker не может работать с БД")
                return None
            except Exception as e:
                logger.error(f"❌ Ошибка подключения к БД: {e}")
                return None

        return self.db_connection

    async def _parse_deadline_from_text(self, text: str) -> Optional[datetime]:
        """Парсить дедлайн из текста задачи"""
        if not text:
            return None

        # Паттерны для поиска дат
        patterns = [
            # "дедлайн: 2026-01-27 18:00"
            r"дедлайн[:\s]+(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?)",
            # "due: 2026-01-27"
            r"due[:\s]+(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?)",
            # "до 27.01.2026"
            r"до\s+(\d{1,2}\.\d{1,2}\.\d{4}(?:\s+\d{2}:\d{2})?)",
            # "deadline: 2026-01-27T18:00:00Z"
            r"deadline[:\s]+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    # Пробуем разные форматы
                    for fmt in [
                        "%Y-%m-%d %H:%M",
                        "%Y-%m-%d",
                        "%d.%m.%Y %H:%M",
                        "%d.%m.%Y",
                        "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%dT%H:%M:%S",
                    ]:
                        try:
                            dt = datetime.strptime(date_str, fmt)
                            # Если нет времени, устанавливаем конец дня
                            if fmt.endswith("%Y"):
                                dt = dt.replace(hour=23, minute=59, second=59)
                            # Устанавливаем timezone
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            return dt
                        except ValueError:
                            continue
                except Exception as e:
                    logger.debug(f"Не удалось распарсить дату '{date_str}': {e}")
                    continue

        return None

    async def _fetch_tasks_with_deadlines(self) -> List[Dict[str, Any]]:
        """Получить задачи с дедлайнами из БД"""
        conn = await self._get_db_connection()
        if not conn:
            return []

        try:
            # Получаем все активные задачи (pending, in_progress)
            query = """
                SELECT
                    id,
                    title,
                    description,
                    status,
                    metadata,
                    created_at
                FROM tasks
                WHERE status IN ('pending', 'in_progress')
                ORDER BY created_at DESC
            """

            rows = await conn.fetch(query)
            tasks = []

            for row in rows:
                task = {
                    "id": str(row["id"]),
                    "title": row["title"],
                    "description": row["description"] or "",
                    "status": row["status"],
                    "metadata": row["metadata"] or {},
                    "created_at": row["created_at"],
                }

                # Ищем дедлайн в metadata
                deadline = None
                if isinstance(task["metadata"], dict):
                    deadline_str = task["metadata"].get("deadline") or task["metadata"].get(
                        "due_date"
                    )
                    if deadline_str:
                        try:
                            if isinstance(deadline_str, str):
                                # Парсим строку
                                deadline = await self._parse_deadline_from_text(deadline_str)
                            elif isinstance(deadline_str, (int, float)):
                                # Unix timestamp
                                deadline = datetime.fromtimestamp(deadline_str, tz=timezone.utc)
                        except Exception as e:
                            logger.debug(f"Ошибка парсинга дедлайна из metadata: {e}")

                # Если не нашли в metadata, парсим из описания
                if not deadline:
                    deadline = await self._parse_deadline_from_text(task["description"])

                if deadline:
                    task["deadline"] = deadline
                    tasks.append(task)

            return tasks
        except Exception as e:
            logger.error(f"❌ Ошибка получения задач из БД: {e}")
            return []

    def _should_notify(self, deadline: TaskDeadline, threshold_hours: int) -> bool:
        """Проверить, нужно ли отправлять уведомление для данного порога"""
        # Проверяем, не уведомляли ли уже для этого порога
        now = datetime.now(timezone.utc)
        threshold_time = deadline.deadline - timedelta(hours=threshold_hours)

        # Если порог уже прошел, не уведомляем
        if now > threshold_time:
            return False

        # Проверяем, не уведомляли ли уже в последние 30 минут для этого порога
        for notified_at in deadline.notified_at:
            if abs((notified_at - threshold_time).total_seconds()) < 1800:  # 30 минут
                return False

        return True

    async def _check_deadlines(self):
        """Проверить все дедлайны и опубликовать события"""
        tasks = await self._fetch_tasks_with_deadlines()
        now = datetime.now(timezone.utc)

        # Обновляем отслеживаемые дедлайны
        current_task_ids = set()

        for task in tasks:
            task_id = task["id"]
            deadline_dt = task["deadline"]
            current_task_ids.add(task_id)

            # Вычисляем время до дедлайна
            time_until = deadline_dt - now
            hours_until = time_until.total_seconds() / 3600

            # Создаем или обновляем TaskDeadline
            if task_id not in self.tracked_deadlines:
                self.tracked_deadlines[task_id] = TaskDeadline(
                    task_id=task_id,
                    task_title=task["title"],
                    deadline=deadline_dt,
                    time_until=time_until,
                    hours_until=hours_until,
                    notified_at=[],
                )
            else:
                # Обновляем время
                self.tracked_deadlines[task_id].time_until = time_until
                self.tracked_deadlines[task_id].hours_until = hours_until

            deadline = self.tracked_deadlines[task_id]

            # Проверяем, прошел ли дедлайн
            if hours_until < 0:
                # Дедлайн прошел
                if not deadline.notified_at or deadline.notified_at[-1] < deadline.deadline:
                    await self._publish_deadline_passed(deadline)
                    deadline.notified_at.append(now)
            else:
                # Проверяем пороги уведомлений
                for threshold_hours in self.notification_thresholds:
                    if hours_until <= threshold_hours and self._should_notify(
                        deadline, threshold_hours
                    ):
                        await self._publish_deadline_approaching(deadline, threshold_hours)
                        deadline.notified_at.append(now)

        # Удаляем дедлайны для задач, которые больше не активны
        tasks_to_remove = set(self.tracked_deadlines.keys()) - current_task_ids
        for task_id in tasks_to_remove:
            del self.tracked_deadlines[task_id]

    async def _publish_deadline_approaching(self, deadline: TaskDeadline, hours_until: int):
        """Опубликовать событие о приближении дедлайна"""
        event = Event(
            event_id=f"deadline_approaching_{deadline.task_id}_{hours_until}h",
            event_type=EventType.DEADLINE_APPROACHING,
            payload={
                "task_id": deadline.task_id,
                "task_title": deadline.task_title,
                "deadline": deadline.deadline.isoformat(),
                "hours_until": hours_until,
                "time_until": deadline.time_until.total_seconds(),
            },
            source="deadline_tracker",
        )

        await self.event_bus.publish(event)
        logger.info(f"⏰ Дедлайн приближается: {deadline.task_title} (через {hours_until}ч)")

    async def _publish_deadline_passed(self, deadline: TaskDeadline):
        """Опубликовать событие о прохождении дедлайна"""
        event = Event(
            event_id=f"deadline_passed_{deadline.task_id}",
            event_type=EventType.DEADLINE_PASSED,
            payload={
                "task_id": deadline.task_id,
                "task_title": deadline.task_title,
                "deadline": deadline.deadline.isoformat(),
                "hours_passed": abs(deadline.hours_until),
            },
            source="deadline_tracker",
        )

        await self.event_bus.publish(event)
        logger.warning(f"⚠️ Дедлайн прошел: {deadline.task_title}")

    async def _monitoring_loop(self):
        """Основной цикл мониторинга дедлайнов"""
        logger.info("🔄 Запуск цикла мониторинга дедлайнов")

        while self.running:
            try:
                await self._check_deadlines()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле мониторинга дедлайнов: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)

    async def start(self):
        """Запустить мониторинг дедлайнов"""
        if self.running:
            logger.warning("⚠️ Deadline Tracker уже запущен")
            return

        self.running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("🚀 Deadline Tracker запущен")

    async def stop(self):
        """Остановить мониторинг дедлайнов"""
        if not self.running:
            return

        self.running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        # Закрываем подключение к БД
        if self.db_connection:
            await self.db_connection.close()
            self.db_connection = None

        logger.info("🛑 Deadline Tracker остановлен")

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику мониторинга"""
        now = datetime.now(timezone.utc)
        approaching = []
        passed = []

        for deadline in self.tracked_deadlines.values():
            if deadline.hours_until < 0:
                passed.append(
                    {
                        "task_id": deadline.task_id,
                        "task_title": deadline.task_title,
                        "hours_passed": abs(deadline.hours_until),
                    }
                )
            elif deadline.hours_until <= 24:
                approaching.append(
                    {
                        "task_id": deadline.task_id,
                        "task_title": deadline.task_title,
                        "hours_until": deadline.hours_until,
                    }
                )

        return {
            "running": self.running,
            "total_tracked": len(self.tracked_deadlines),
            "approaching": approaching,
            "passed": passed,
            "check_interval": self.check_interval,
        }


async def main():
    """Пример использования"""
    import logging
    import os

    logging.basicConfig(level=logging.INFO)

    # Устанавливаем DATABASE_URL если нужно
    if not os.getenv("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "postgresql://admin:secret@localhost:5432/knowledge_os"

    # Инициализируем Event Bus
    event_bus = get_event_bus()
    await event_bus.start()

    # Подписываемся на события дедлайнов
    async def handle_deadline_approaching(event: Event):
        payload = event.payload
        print(
            f"⏰ Дедлайн приближается: {payload.get('task_title')} (через {payload.get('hours_until')}ч)"
        )

    async def handle_deadline_passed(event: Event):
        payload = event.payload
        print(f"⚠️ Дедлайн прошел: {payload.get('task_title')}")

    event_bus.subscribe(EventType.DEADLINE_APPROACHING, handle_deadline_approaching)
    event_bus.subscribe(EventType.DEADLINE_PASSED, handle_deadline_passed)

    # Создаем Deadline Tracker
    tracker = DeadlineTracker(check_interval=60)

    await tracker.start()

    # Ждем события
    print("⏳ Мониторинг дедлайнов (нажмите Ctrl+C для остановки)...")
    try:
        await asyncio.sleep(300)
    except KeyboardInterrupt:
        pass

    print(f"\n📊 Статистика: {tracker.get_stats()}")

    await tracker.stop()
    await event_bus.stop()


if __name__ == "__main__":
    asyncio.run(main())
