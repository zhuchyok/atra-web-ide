"""
Streaming Orchestrator - event-driven оркестрация Knowledge OS.

Полностью переработанный orchestrator на базе Redis Streams:
- Публикация событий через EventProducer
- Реакция на события через EventConsumer
- Типизированные события
- Масштабируемая архитектура
"""

import asyncio
import os
import sys
import json
import logging
import subprocess
from datetime import datetime
from typing import Optional, List, Dict, Any

# Добавляем путь к src
sys.path.insert(0, '/root/knowledge_os/src')

import asyncpg

from infrastructure.streaming import (
    EventProducer,
    EventConsumer,
    StreamManager,
    EventType,
    KnowledgeEvent,
    TaskEvent,
    InsightEvent,
)
from infrastructure.streaming.consumer import ConsumerConfig

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("streaming_orchestrator")

# Конфигурация
DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

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
            command_timeout=60
        )
    return _pool


def run_cursor_agent(prompt: str, timeout: int = 300) -> Optional[str]:
    """Вызывает cursor-agent для AI операций."""
    try:
        env = os.environ.copy()
        result = subprocess.run(
            ['/root/.local/bin/cursor-agent', '--print', prompt],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
            env=env
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
            )
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
            expert = await pool.fetchrow("""
                SELECT e.id, e.name FROM experts e
                JOIN domains d ON e.domain_id = d.id
                WHERE d.name = $1
                ORDER BY RANDOM() LIMIT 1
            """, event.source_domain)
            
            if expert:
                victoria_id = await pool.fetchval(
                    "SELECT id FROM experts WHERE name = 'Виктория'"
                )
                
                task_id = await pool.fetchval("""
                    INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
                    VALUES ($1, $2, 'pending', $3, $4, $5)
                    RETURNING id
                """,
                    f"🔬 Валидация гипотезы: {event.source_domain} ↔ {event.target_domain}",
                    f"Проверь гипотезу: {event.hypothesis}\n\nОцени её применимость и предложи эксперимент для валидации.",
                    expert['id'],
                    victoria_id,
                    json.dumps({"source": "hypothesis_validation", "insight_id": event.insight_id})
                )
                
                # Публикуем событие создания задачи
                if self.producer and task_id:
                    await self.producer.publish_task_created(
                        task_id=str(task_id),
                        title=f"Валидация гипотезы: {event.source_domain} ↔ {event.target_domain}",
                        description=f"Проверить гипотезу: {event.hypothesis[:200]}",
                        assignee_expert_id=str(expert['id']),
                        assignee_name=expert['name'],
                        priority="high"
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
        random_node = await pool.fetchrow("""
            SELECT k.id, k.content, d.name as domain
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.domain_id != $1
            ORDER BY RANDOM() LIMIT 1
        """, node['domain_id'])
        
        if not random_node:
            return
        
        # Генерируем кросс-доменную гипотезу
        link_prompt = f"""
        Вы - Виктория (Team Lead). Найдите неочевидную связь между двумя фактами из разных отделов:
        
        ФАКТ А ({node['domain']}): {node['content']}
        ФАКТ Б ({random_node['domain']}): {random_node['content']}
        
        ЗАДАЧА: Сформулируйте одну инновационную гипотезу (Synthetic Hypothesis) на стыке этих знаний.
        Верните ТОЛЬКО текст гипотезы (1-3 предложения).
        """
        
        hypothesis = run_cursor_agent(link_prompt)
        
        if hypothesis:
            # Сохраняем в БД
            knowledge_id = await pool.fetchval("""
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                VALUES ($1, $2, 0.95, $3, true)
                RETURNING id
            """, node['domain_id'],
                f"🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА: {hypothesis}",
                json.dumps({
                    "source": "cross_domain_linker",
                    "parents": [str(node['id']), str(random_node['id'])],
                    "source_domain": node['domain'],
                    "target_domain": random_node['domain']
                })
            )
            
            # Публикуем событие через streaming инфраструктуру
            if self.producer:
                await self.producer.publish_insight(
                    content=hypothesis,
                    source_domain=node['domain'],
                    target_domain=random_node['domain'],
                    hypothesis=hypothesis,
                    confidence=0.95,
                    parent_knowledge_ids=[str(node['id']), str(random_node['id'])],
                    metadata={"knowledge_id": str(knowledge_id)}
                )
            
            logger.info(f"💡 Created cross-domain insight: {node['domain']} ↔ {random_node['domain']}")
        
        # Помечаем как обработанный
        await pool.execute("""
            UPDATE knowledge_nodes 
            SET metadata = metadata || '{"orchestrated": "true"}'::jsonb 
            WHERE id = $1
        """, node['id'])
    
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
        
        for desert in deserts:
            logger.info(f"🏜️ Curiosity Engine: Domain '{desert['name']}' needs attention")
            
            # Проверяем наличие экспертов
            expert_count = await pool.fetchval(
                "SELECT count(*) FROM experts WHERE department = $1",
                desert['name']
            )
            
            if expert_count == 0:
                logger.info(f"👤 Recruiting expert for {desert['name']}...")
                try:
                    subprocess.run(
                        ["/root/knowledge_os/venv/bin/python",
                         "/root/knowledge_os/app/expert_generator.py",
                         desert['name']],
                        timeout=60
                    )
                except Exception as e:
                    logger.warning(f"Expert generation failed: {e}")
                continue
            
            # Создаём исследовательскую задачу
            curiosity_task = (
                f"Проведи глубокое исследование новых технологий и трендов 2026 "
                f"в области {desert['name']}. Найди 3 прорывных инсайта."
            )
            
            # Находим эксперта
            assignee = await pool.fetchrow(
                "SELECT id, name FROM experts WHERE department = $1 ORDER BY RANDOM() LIMIT 1",
                desert['name']
            )
            
            if assignee and victoria_id:
                task_id = await pool.fetchval("""
                    INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
                    VALUES ($1, $2, 'pending', $3, $4, $5)
                    RETURNING id
                """,
                    f"🔥 СРОЧНОЕ ИССЛЕДОВАНИЕ: {desert['name']}",
                    curiosity_task,
                    assignee['id'],
                    victoria_id,
                    json.dumps({"reason": "curiosity_engine_starvation", "domain": desert['name']})
                )
                
                # Публикуем событие
                if self.producer and task_id:
                    await self.producer.publish_task_created(
                        task_id=str(task_id),
                        title=f"СРОЧНОЕ ИССЛЕДОВАНИЕ: {desert['name']}",
                        description=curiosity_task,
                        assignee_expert_id=str(assignee['id']),
                        assignee_name=assignee['name'],
                        creator_expert_id=str(victoria_id) if victoria_id else None,
                        priority="high",
                        metadata={"source": "curiosity_engine"}
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
    
    parser = argparse.ArgumentParser(description='Streaming Orchestrator for Knowledge OS')
    parser.add_argument('--once', action='store_true', help='Run single cycle and exit')
    parser.add_argument('--interval', type=int, default=300, help='Interval between cycles (seconds)')
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
