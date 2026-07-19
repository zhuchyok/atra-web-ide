"""
Streaming Orchestrator - event-driven оркестрация Knowledge OS.

Полностью переработанный orchestrator на базе Redis Streams:
- Публикация событий через EventProducer
- Реакция на события через EventConsumer
- Типизированные события
- Масштабируемая архитектура
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Добавляем путь к src
sys.path.insert(0, "/root/knowledge_os/src")

import asyncpg

try:
    from task_dedup import same_task_for_expert_in_last_n_days
except ImportError:
    try:
        from app.task_dedup import same_task_for_expert_in_last_n_days
    except ImportError:
        same_task_for_expert_in_last_n_days = None

from infrastructure.streaming import (
    EventConsumer,
    EventProducer,
    EventType,
    InsightEvent,
    KnowledgeEvent,
    StreamManager,
    TaskEvent,
)
from infrastructure.streaming.consumer import ConsumerConfig

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("streaming_orchestrator")

# Конфигурация
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Canonical domains (план Этап 2): маппинг для recruit_expert
CANONICAL_DOMAINS = {
    "Machine Learning": "ML/AI",
    "AI Systems": "ML/AI",
    "AI": "ML/AI",
    "Backend": "Backend",
    "Frontend": "Frontend",
    "DevOps": "DevOps/Infra",
    "Infrastructure": "DevOps/Infra",
}


def _canonical_domain(name: str) -> str:
    """Возвращает каноническое имя домена."""
    return CANONICAL_DOMAINS.get(name, name)


# Resource lock (простая реализация через Redis)
_lock_key = "orchestrator:lock"

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


def run_cursor_agent(prompt: str, timeout: int = 300) -> Optional[str]:
    """Вызывает cursor-agent для AI операций."""
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
    except Exception as e:
        logger.error(f"Cursor agent error: {e}")
        return None


class StreamingOrchestrator:
    """
    Event-driven оркестратор Knowledge OS.

    Обеспечивает:
    - Кросс-доменное связывание знаний
    - Автономный рекрутинг экспертов
    - Управление "интеллектуальными пустынями"
    - Генерацию синтетических гипотез
    """

    def __init__(self):
        self.producer: Optional[EventProducer] = None
        self.stream_manager: Optional[StreamManager] = None

        # Consumer для реакции на события
        self.insight_consumer = EventConsumer(
            redis_url=REDIS_URL,
            config=ConsumerConfig(
                stream_name="insight_stream",
                group_name="orchestrator",
                consumer_name="orchestrator-insight-processor",
                batch_size=5,
                block_ms=2000,
            ),
        )

        self._register_handlers()

    def _register_handlers(self):
        """Регистрирует обработчики событий."""

        @self.insight_consumer.on_event(EventType.INSIGHT_HYPOTHESIS)
        async def handle_hypothesis(event: InsightEvent, raw_data: Dict) -> bool:
            """Обрабатывает новые гипотезы - может создавать задачи для валидации."""
            logger.info(f"🔬 New hypothesis to validate: {event.hypothesis[:100]}...")

            # Создаём задачу на валидацию гипотезы
            pool = await get_pool()

            # Находим эксперта по домену
            expert = await pool.fetchrow(
                """
                SELECT e.id, e.name FROM experts e
                JOIN domains d ON e.domain_id = d.id
                WHERE d.name = $1
                ORDER BY RANDOM() LIMIT 1
            """,
                event.source_domain,
            )

            if expert:
                victoria_id = await pool.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")

                task_id = await pool.fetchval(
                    """
                    INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
                    VALUES ($1, $2, 'pending', $3, $4, $5)
                    ON CONFLICT (title, COALESCE(project_context, 'default'::character varying))
                    WHERE (status = ANY (ARRAY['pending'::text, 'in_progress'::text]))
                    DO NOTHING
                    RETURNING id
                """,
                    f"🔬 Валидация гипотезы: {event.source_domain} ↔ {event.target_domain}",
                    f"Проверь гипотезу: {event.hypothesis}\n\nОцени её применимость и предложи эксперимент для валидации.",
                    expert["id"],
                    victoria_id,
                    json.dumps({"source": "hypothesis_validation", "insight_id": event.insight_id}),
                )

                # Публикуем событие создания задачи
                if self.producer and task_id:
                    await self.producer.publish_task_created(
                        task_id=str(task_id),
                        title=f"Валидация гипотезы: {event.source_domain} ↔ {event.target_domain}",
                        description=f"Проверить гипотезу: {event.hypothesis[:200]}",
                        assignee_expert_id=str(expert["id"]),
                        assignee_name=expert["name"],
                        priority="high",
                    )
                    logger.info(f"📋 Created validation task {task_id} for {expert['name']}")

            return True

    async def initialize(self):
        """Инициализирует оркестратор."""
        self.stream_manager = StreamManager(REDIS_URL)
        await self.stream_manager.initialize()

        self.producer = EventProducer(REDIS_URL)
        await self.producer.connect()

        logger.info("✅ StreamingOrchestrator initialized")

    async def run_orchestration_cycle(self):
        """Выполняет один цикл оркестрации."""
        logger.info(f"[{datetime.now()}] 🚀 STREAMING ORCHESTRATOR v4.0 starting cycle...")

        pool = await get_pool()

        # === ФАЗА 1: СБОР НОВЫХ ЗНАНИЙ ===
        new_knowledge = await pool.fetch("""
            SELECT k.id, k.content, d.name as domain, k.metadata, k.domain_id
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.created_at > NOW() - INTERVAL '6 hours'
            AND (k.metadata->>'orchestrated' IS NULL OR k.metadata->>'orchestrated' = 'false')
            LIMIT 50
        """)

        logger.info(f"📚 Found {len(new_knowledge)} new knowledge nodes to process")

        # === ФАЗА 2: КРОСС-ДОМЕННОЕ СВЯЗЫВАНИЕ ===
        for node in new_knowledge:
            await self._process_knowledge_node(pool, node)

        # === ФАЗА 3: ДВИГАТЕЛЬ ЛЮБОПЫТСТВА ===
        await self._run_curiosity_engine(pool)

        # === ФАЗА 4: HEALTH CHECK ===
        if self.stream_manager:
            health = await self.stream_manager.health_check()
            logger.info(f"📊 Streams health: {health['status']}")

        logger.info(f"[{datetime.now()}] ✅ Orchestration cycle completed")

    async def _process_knowledge_node(self, pool: asyncpg.Pool, node: Dict[str, Any]):
        """Обрабатывает узел знаний - создаёт кросс-доменные связи."""
        logger.info(f"🧩 Processing: {node['content'][:50]}...")

        # Находим случайный узел из другого домена
        random_node = await pool.fetchrow(
            """
            SELECT k.id, k.content, d.name as domain
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.domain_id != $1
            ORDER BY RANDOM() LIMIT 1
        """,
            node["domain_id"],
        )

        if not random_node:
            return

        # Генерируем кросс-доменную гипотезу
        link_prompt = f"""
        Вы - Виктория (Team Lead). Найдите неочевидную связь между двумя фактами из разных отделов:

        ФАКТ А ({node["domain"]}): {node["content"]}
        ФАКТ Б ({random_node["domain"]}): {random_node["content"]}

        ЗАДАЧА: Сформулируйте одну инновационную гипотезу (Synthetic Hypothesis) на стыке этих знаний.
        Верните ТОЛЬКО текст гипотезы (1-3 предложения).
        """

        hypothesis = run_cursor_agent(link_prompt)

        if hypothesis:
            # Сохраняем в БД (по возможности с embedding — VERIFICATION §5)
            content_kn = f"🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА: {hypothesis}"
            meta_kn = json.dumps(
                {
                    "source": "cross_domain_linker",
                    "parents": [str(node["id"]), str(random_node["id"])],
                    "source_domain": node["domain"],
                    "target_domain": random_node["domain"],
                }
            )
            embedding = None
            try:
                from semantic_cache import get_embedding

                embedding = await get_embedding(content_kn[:8000])
            except Exception:
                pass
            if embedding is not None:
                knowledge_id = await pool.fetchval(
                    """
                    INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                    VALUES ($1, $2, 0.95, $3, true, $4::vector)
                    RETURNING id
                """,
                    node["domain_id"],
                    content_kn,
                    meta_kn,
                    str(embedding),
                )
            else:
                knowledge_id = await pool.fetchval(
                    """
                    INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                    VALUES ($1, $2, 0.95, $3, true)
                    RETURNING id
                """,
                    node["domain_id"],
                    content_kn,
                    meta_kn,
                )

            # Публикуем событие через streaming инфраструктуру
            if self.producer:
                await self.producer.publish_insight(
                    content=hypothesis,
                    source_domain=node["domain"],
                    target_domain=random_node["domain"],
                    hypothesis=hypothesis,
                    confidence=0.95,
                    parent_knowledge_ids=[str(node["id"]), str(random_node["id"])],
                    metadata={"knowledge_id": str(knowledge_id)},
                )

            logger.info(
                f"💡 Created cross-domain insight: {node['domain']} ↔ {random_node['domain']}"
            )

            # Отправка гипотезы в дебаты для обсуждения экспертами
            try:
                from nightly_learner import create_debate_for_hypothesis

                async with pool.acquire() as conn:
                    await create_debate_for_hypothesis(
                        conn,
                        knowledge_id,
                        f"🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА: {hypothesis}",
                        node["domain_id"],
                    )
            except Exception as db_err:
                logger.debug("Hypothesis debate skip: %s", db_err)

        # Помечаем как обработанный
        await pool.execute(
            """
            UPDATE knowledge_nodes
            SET metadata = metadata || '{"orchestrated": "true"}'::jsonb
            WHERE id = $1
        """,
            node["id"],
        )

    async def _run_curiosity_engine(self, pool: asyncpg.Pool):
        """Находит 'интеллектуальные пустыни' и генерирует исследовательские задачи."""

        # Ищем домены с малым количеством знаний
        deserts = await pool.fetch("""
            SELECT d.id, d.name, count(k.id) as node_count
            FROM domains d
            LEFT JOIN knowledge_nodes k ON d.id = k.domain_id
            GROUP BY d.id, d.name
            HAVING count(k.id) < 50
               OR max(k.created_at) < NOW() - INTERVAL '48 hours'
        """)

        victoria_id = await pool.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")

        # Лимит автономных экспертов (план: не более 25)
        autonomous_count = await pool.fetchval(
            "SELECT count(*) FROM experts WHERE (metadata->>'is_autonomous')::text = 'true'"
        )
        autonomous_limit = int(os.getenv("AUTONOMOUS_EXPERT_LIMIT", "25"))

        for desert in deserts:
            canonical = _canonical_domain(desert["name"])
            logger.info(
                f"🏜️ Curiosity Engine: Domain '{desert['name']}' (canonical: {canonical}) needs attention"
            )

            # Проверяем наличие экспертов (в каноническом домене)
            expert_count = await pool.fetchval(
                "SELECT count(*) FROM experts WHERE department = $1 OR department = $2",
                desert["name"],
                canonical,
            )

            if expert_count == 0 and (autonomous_count or 0) < autonomous_limit:
                logger.info(f"👤 Recruiting expert for {canonical}...")
                try:
                    subprocess.run(
                        [
                            "/root/knowledge_os/venv/bin/python",
                            "/root/knowledge_os/app/expert_generator.py",
                            canonical,
                        ],
                        timeout=60,
                    )
                except Exception as e:
                    logger.warning(f"Expert generation failed: {e}")
                autonomous_count = (autonomous_count or 0) + 1
                continue

            # Создаём исследовательскую задачу
            curiosity_task = (
                f"Проведи глубокое исследование новых технологий и трендов 2026 "
                f"в области {desert['name']}. Найди 3 прорывных инсайта."
            )
            title_curiosity = f"🔥 СРОЧНОЕ ИССЛЕДОВАНИЕ: {desert['name']}"
            cooldown_min = int(os.getenv("ORCHESTRATOR_CURIOSITY_RETRY_COOLDOWN_MIN", "30"))
            recent_curiosity_failure = await pool.fetchval(
                """
                SELECT 1
                FROM tasks
                WHERE title = $1
                  AND status = 'failed'
                  AND updated_at > NOW() - ($2::text || ' minutes')::interval
                  AND COALESCE(metadata->>'auto_fallback_reason', '') IN (
                      'curiosity_no_llm_progress_timeout',
                      'pending_curiosity_starvation_timeout'
                  )
                LIMIT 1
                """,
                title_curiosity,
                str(cooldown_min),
            )
            if recent_curiosity_failure:
                logger.info(
                    "⏭️ Curiosity cooldown active for %s (%s min)",
                    desert["name"],
                    cooldown_min,
                )
                continue

            # Находим эксперта
            assignee = await pool.fetchrow(
                "SELECT id, name FROM experts WHERE department = $1 ORDER BY RANDOM() LIMIT 1",
                desert["name"],
            )

            if assignee and victoria_id:
                # Дедупликация: та же задача (title+description) для того же эксперта не чаще раза в 30 дней
                if same_task_for_expert_in_last_n_days:
                    async with pool.acquire() as conn:
                        if await same_task_for_expert_in_last_n_days(
                            conn, title_curiosity, curiosity_task, assignee["id"], days=30
                        ):
                            logger.info(
                                "⏭️ Skip duplicate: same research task for %s (%s) in last 30 days",
                                assignee["name"],
                                desert["name"],
                            )
                            continue
                task_id = await pool.fetchval(
                    """
                    INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
                    VALUES ($1, $2, 'pending', $3, $4, $5)
                    ON CONFLICT (title, COALESCE(project_context, 'default'::character varying))
                    WHERE (status = ANY (ARRAY['pending'::text, 'in_progress'::text]))
                    DO NOTHING
                    RETURNING id
                """,
                    title_curiosity,
                    curiosity_task,
                    assignee["id"],
                    victoria_id,
                    json.dumps({"reason": "curiosity_engine_starvation", "domain": desert["name"]}),
                )

                # Публикуем событие
                if self.producer and task_id:
                    await self.producer.publish_task_created(
                        task_id=str(task_id),
                        title=f"СРОЧНОЕ ИССЛЕДОВАНИЕ: {desert['name']}",
                        description=curiosity_task,
                        assignee_expert_id=str(assignee["id"]),
                        assignee_name=assignee["name"],
                        creator_expert_id=str(victoria_id) if victoria_id else None,
                        priority="high",
                        metadata={"source": "curiosity_engine"},
                    )

                    logger.info(f"📋 Created research task {task_id} for {assignee['name']}")

    async def start_continuous(self, interval_seconds: int = 300):
        """Запускает непрерывную оркестрацию."""
        logger.info(f"🚀 Starting continuous orchestration (interval: {interval_seconds}s)")

        # Запускаем consumer для обработки insight событий
        consumer_task = asyncio.create_task(self.insight_consumer.start())

        try:
            while True:
                try:
                    await self.run_orchestration_cycle()
                except Exception as e:
                    logger.error(f"Orchestration cycle error: {e}")

                await asyncio.sleep(interval_seconds)
        finally:
            consumer_task.cancel()
            await self.insight_consumer.stop()

    async def close(self):
        """Закрывает соединения."""
        if self.producer:
            await self.producer.close()

        if self.stream_manager:
            await self.stream_manager.close()

        global _pool
        if _pool:
            await _pool.close()
            _pool = None

        logger.info("StreamingOrchestrator closed")


async def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Streaming Orchestrator for Knowledge OS")
    parser.add_argument("--once", action="store_true", help="Run single cycle and exit")
    parser.add_argument(
        "--interval", type=int, default=300, help="Interval between cycles (seconds)"
    )
    args = parser.parse_args()

    orchestrator = StreamingOrchestrator()

    try:
        await orchestrator.initialize()

        if args.once:
            await orchestrator.run_orchestration_cycle()
        else:
            await orchestrator.start_continuous(interval_seconds=args.interval)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await orchestrator.close()


if __name__ == "__main__":
    asyncio.run(main())
