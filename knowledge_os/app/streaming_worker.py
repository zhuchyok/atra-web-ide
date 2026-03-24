"""
Streaming Worker - event-driven обработка задач через Redis Streams.

Заменяет polling-based worker на реактивную архитектуру:
- Мгновенная реакция на новые задачи
- Consumer Groups для масштабирования
- At-least-once доставка
- Автоматическое восстановление при сбоях
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, Optional

# Добавляем путь к src
sys.path.insert(0, "/root/knowledge_os/src")

import asyncpg

from infrastructure.streaming import (
    EventConsumer,
    EventProducer,
    EventType,
    KnowledgeEvent,
    StreamManager,
    TaskEvent,
)
from infrastructure.streaming.consumer import ConsumerConfig

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("streaming_worker")

# Конфигурация
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Connection pool
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Получает или создаёт connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DB_URL,
            min_size=1,
            max_size=5,  # Уменьшено для предотвращения перегрузки БД
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )
    return _pool


def run_cursor_agent(prompt: str, timeout: int = 600) -> Optional[str]:
    """Вызывает cursor-agent для выполнения AI задач."""
    try:
        env = os.environ.copy()
        result = subprocess.run(
            ["/root/.local/bin/cursor-agent", "--print", prompt],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
            env=env,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error(f"Cursor agent timeout after {timeout}s")
        return None
    except Exception as e:
        logger.error(f"Cursor agent error: {e}")
        return None


class StreamingWorker:
    """
    Event-driven worker для обработки задач из Redis Streams.

    Подписывается на:
    - task_stream: Новые задачи для выполнения
    - knowledge_stream: События знаний для обработки
    """

    def __init__(self, worker_id: str = "worker-1"):
        self.worker_id = worker_id
        self.producer: Optional[EventProducer] = None
        self.stream_manager: Optional[StreamManager] = None

        # Task consumer
        self.task_consumer = EventConsumer(
            redis_url=REDIS_URL,
            config=ConsumerConfig(
                stream_name="task_stream",
                group_name="task_workers",
                consumer_name=f"task-worker-{worker_id}",
                batch_size=5,
                block_ms=5000,
                claim_idle_ms=120000,  # 2 минуты для claim
            ),
        )

        # Knowledge consumer (для реакции на новые знания)
        self.knowledge_consumer = EventConsumer(
            redis_url=REDIS_URL,
            config=ConsumerConfig(
                stream_name="knowledge_stream",
                group_name="knowledge_processors",
                consumer_name=f"knowledge-worker-{worker_id}",
                batch_size=10,
                block_ms=3000,
            ),
        )

        # Регистрируем обработчики
        self._register_handlers()

    def _register_handlers(self):
        """Регистрирует обработчики событий."""

        # Task handlers
        @self.task_consumer.on_event(EventType.TASK_CREATED)
        async def handle_task_created(event: TaskEvent, raw_data: Dict) -> bool:
            return await self._process_task(event)

        @self.task_consumer.on_event(EventType.TASK_ASSIGNED)
        async def handle_task_assigned(event: TaskEvent, raw_data: Dict) -> bool:
            logger.info(f"📋 Task assigned: {event.title} -> {event.assignee_name}")
            return True  # Just acknowledge

        # Knowledge handlers
        @self.knowledge_consumer.on_event(EventType.KNOWLEDGE_CREATED)
        async def handle_knowledge_created(event: KnowledgeEvent, raw_data: Dict) -> bool:
            return await self._process_new_knowledge(event)

        @self.knowledge_consumer.on_event(EventType.INSIGHT_CROSS_DOMAIN)
        async def handle_insight(event: KnowledgeEvent, raw_data: Dict) -> bool:
            logger.info(f"💡 New cross-domain insight received: {event.content[:100]}...")
            return True

    async def _process_task(self, event: TaskEvent) -> bool:
        """Обрабатывает задачу из stream."""
        task_id = event.task_id
        logger.info(f"🔄 Processing task: {event.title} (ID: {task_id})")

        try:
            pool = await get_pool()

            # Получаем полную информацию о задаче из БД
            task = await pool.fetchrow(
                """
                SELECT t.id, t.title, t.description, t.status,
                       e.name as assignee, e.system_prompt
                FROM tasks t
                JOIN experts e ON t.assignee_expert_id = e.id
                WHERE t.id = $1
            """,
                int(task_id) if task_id else None,
            )

            if not task:
                logger.warning(f"Task {task_id} not found in database")
                return True  # ACK anyway - task may have been deleted

            if task["status"] != "pending":
                logger.info(f"Task {task_id} already processed (status: {task['status']})")
                return True

            # Обновляем статус на in_progress
            await pool.execute(
                "UPDATE tasks SET status = 'in_progress', updated_at = NOW() WHERE id = $1",
                task["id"],
            )

            # Публикуем событие о начале обработки
            if self.producer:
                await self.producer.publish(
                    TaskEvent(
                        event_type=EventType.TASK_STARTED,
                        task_id=str(task["id"]),
                        title=task["title"],
                        assignee_name=task["assignee"],
                    )
                )

            # Формируем промпт и вызываем AI
            prompt = f"""{task["system_prompt"]}

ЗАДАЧА: {task["title"]}
ИНСТРУКЦИЯ: {task["description"]}

ТВОЯ ЦЕЛЬ: Выполни задачу максимально глубоко и профессионально.
Сформулируй 3-5 ключевых инсайтов или решений.
Ответь в формате экспертного отчета.
"""

            logger.info(f"🤖 Calling AI for task {task_id}...")
            report = run_cursor_agent(prompt)

            if report:
                # Сохраняем результат
                await pool.execute(
                    "UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW() WHERE id = $1",
                    task["id"],
                    report,
                )

                # Создаём knowledge node из результата
                domain_id = await pool.fetchval(
                    "SELECT domain_id FROM experts WHERE name = $1 LIMIT 1", task["assignee"]
                )

                if domain_id:
                    knowledge_id = await pool.fetchval(
                        """
                        INSERT INTO knowledge_nodes
                        (domain_id, content, metadata, confidence_score, is_verified)
                        VALUES ($1, $2, $3, 0.95, TRUE)
                        RETURNING id
                    """,
                        domain_id,
                        f"📊 ОТЧЕТ ЭКСПЕРТА ({task['assignee']}): {task['title']}\n\n{report}",
                        json.dumps(
                            {
                                "task_id": str(task["id"]),
                                "expert": task["assignee"],
                                "source": "streaming_worker",
                            }
                        ),
                    )

                    # Публикуем событие о новом знании
                    if self.producer and knowledge_id:
                        await self.producer.publish_knowledge_created(
                            knowledge_id=str(knowledge_id),
                            content=report[:500],
                            domain_id=str(domain_id),
                            domain_name=task["assignee"],
                            metadata={"from_task": str(task["id"])},
                        )

                # Публикуем событие о завершении
                if self.producer:
                    await self.producer.publish_task_completed(
                        task_id=str(task["id"]),
                        title=task["title"],
                        assignee_name=task["assignee"],
                        result=report[:500],
                    )

                logger.info(f"✅ Task {task_id} completed by {task['assignee']}")
                return True
            else:
                # Откатываем статус
                await pool.execute(
                    "UPDATE tasks SET status = 'pending', updated_at = NOW() WHERE id = $1",
                    task["id"],
                )

                # Публикуем событие о неудаче
                if self.producer:
                    await self.producer.publish(
                        TaskEvent(
                            event_type=EventType.TASK_FAILED,
                            task_id=str(task["id"]),
                            title=task["title"],
                            assignee_name=task["assignee"],
                            metadata={"reason": "AI agent returned empty response"},
                        )
                    )

                logger.warning(f"❌ Task {task_id} failed, reverted to pending")
                return False  # Не ACKаем - будет retry

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")
            return False

    async def _process_new_knowledge(self, event: KnowledgeEvent) -> bool:
        """Обрабатывает событие создания нового знания."""
        logger.info(f"📚 New knowledge in domain '{event.domain_name}': {event.content[:100]}...")

        # Здесь можно добавить логику:
        # - Индексация в vector store
        # - Уведомление заинтересованных экспертов
        # - Триггер cross-domain анализа

        return True

    async def start(self):
        """Запускает worker."""
        logger.info(f"🚀 StreamingWorker '{self.worker_id}' starting...")

        # Инициализируем инфраструктуру
        self.stream_manager = StreamManager(REDIS_URL)
        await self.stream_manager.initialize()

        self.producer = EventProducer(REDIS_URL)
        await self.producer.connect()

        # Запускаем consumers параллельно
        await asyncio.gather(
            self.task_consumer.start(),
            self.knowledge_consumer.start(),
        )

    async def stop(self):
        """Останавливает worker."""
        logger.info("Stopping StreamingWorker...")

        await self.task_consumer.stop()
        await self.knowledge_consumer.stop()

        if self.producer:
            await self.producer.close()

        if self.stream_manager:
            await self.stream_manager.close()

        global _pool
        if _pool:
            await _pool.close()
            _pool = None

        logger.info("StreamingWorker stopped")


async def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Streaming Worker for Knowledge OS")
    parser.add_argument("--worker-id", default="worker-1", help="Unique worker ID")
    args = parser.parse_args()

    worker = StreamingWorker(worker_id=args.worker_id)

    # Graceful shutdown
    loop = asyncio.get_event_loop()

    def shutdown():
        logger.info("Received shutdown signal")
        asyncio.create_task(worker.stop())

    try:
        import signal

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, shutdown)
    except NotImplementedError:
        pass  # Windows

    try:
        await worker.start()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
