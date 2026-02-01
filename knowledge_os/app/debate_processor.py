#!/usr/bin/env python3
"""
Модуль для обработки дебатов экспертов и автоматического создания задач для внедрения.
Приоритизация знаний на основе дебатов.
Уведомления о важных консенсусах.
"""
import asyncio
import os
import re
import json
import asyncpg
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

# Пороги для приоритетов
PRIORITY_THRESHOLDS = {
    "urgent": 0.9,  # Если 90% экспертов согласны - срочно
    "high": 0.75,   # 75% согласны - высокий приоритет
    "medium": 0.6,  # 60% согласны - средний приоритет
    "low": 0.4      # 40% согласны - низкий приоритет
}

# Минимальный consensus_score для создания задачи (снижен для более активного создания задач)
MIN_CONSENSUS_FOR_TASK = 0.5

# Минимальный consensus_score для уведомления
MIN_CONSENSUS_FOR_NOTIFICATION = 0.75


class DebateProcessor:
    """Обработчик дебатов экспертов"""
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url
    
    async def get_pool(self):
        """Получить пул подключений к БД (использует тот же метод, что и evaluator)"""
        if self.db_url:
            return await asyncpg.create_pool(self.db_url, min_size=1, max_size=3)
        else:
            # Используем get_pool из evaluator для совместимости
            from evaluator import get_pool
            pool = await get_pool()
            # Убеждаемся, что пул правильно настроен
            return pool
    
    async def analyze_debate_consensus(self, debate_id: str) -> Optional[Dict]:
        """
        Анализирует консенсус в дебате и возвращает метрики.
        
        Returns:
            Dict с метриками: consensus_score, priority, actionable_insights
        """
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            debate = await conn.fetchrow("""
                SELECT id, knowledge_node_id, expert_ids, topic, consensus_summary, created_at
                FROM expert_discussions
                WHERE id = $1
            """, debate_id)
            
            if not debate:
                return None
            
            # Анализируем consensus_summary
            consensus_text = debate['consensus_summary'] or ""
            
            # Простая эвристика: количество экспертов в дебате
            expert_count = len(debate['expert_ids']) if debate['expert_ids'] else 2
            
            # Базовый score от количества экспертов (нормализовано)
            expert_score = min(expert_count / 3.0, 1.0)  # Максимум 3 эксперта = 1.0
            
            # Score от длины консенсуса (чем больше, тем лучше обсуждение)
            consensus_length = len(consensus_text)
            length_score = min(consensus_length / 500.0, 0.4)  # Максимум 0.4 за длину (500+ символов)
            
            # Дополнительный бонус если консенсус содержит позитивные слова
            positive_indicators = ['рекомендуется', 'важно', 'критично', 'необходимо', 'срочно', 'приоритет', 
                                 'реализовать', 'внедрить', 'создать', 'разработать', 'оптимизировать', 'улучшить']
            positive_bonus = 0.0
            if any(indicator in consensus_text.lower() for indicator in positive_indicators):
                positive_bonus = 0.2
            
            # Бонус за структурированность (наличие маркеров экспертов)
            structure_bonus = 0.0
            if '🧐' in consensus_text or '**' in consensus_text or len(consensus_text.split('\n\n')) > 2:
                structure_bonus = 0.1
            
            # Итоговый score (более гибкий)
            base_score = min(expert_score + length_score + positive_bonus + structure_bonus, 1.0)
            
            # Минимальный score для дебатов с хорошим контентом
            if consensus_length > 200 and expert_count >= 2:
                base_score = max(base_score, 0.5)  # Минимум 0.5 для качественных дебатов
            
            # Определяем приоритет
            priority = "low"
            if base_score >= PRIORITY_THRESHOLDS["urgent"]:
                priority = "urgent"
            elif base_score >= PRIORITY_THRESHOLDS["high"]:
                priority = "high"
            elif base_score >= PRIORITY_THRESHOLDS["medium"]:
                priority = "medium"
            
            # Извлекаем actionable insights
            actionable_insights = self._extract_actionable_insights(consensus_text)
            
            return {
                "debate_id": str(debate['id']),
                "knowledge_node_id": str(debate['knowledge_node_id']) if debate['knowledge_node_id'] else None,
                "consensus_score": base_score,
                "priority": priority,
                "expert_count": expert_count,
                "actionable_insights": actionable_insights,
                "topic": debate['topic'],
                "consensus_summary": consensus_text
            }
    
    def _extract_actionable_insights(self, consensus_text: str) -> List[str]:
        """Извлекает actionable insights из консенсуса (Singularity 10.0: расширенный Prompt Engineer)"""
        insights = []
        seen = set()

        # Глаголы действия (русский + английский)
        action_verbs = [
            'реализовать', 'внедрить', 'создать', 'разработать', 'оптимизировать', 'улучшить', 'добавить',
            'внедрять', 'создавать', 'разрабатывать', 'оптимизировать', 'улучшать', 'добавлять',
            'рекомендуется', 'следует', 'необходимо', 'нужно', 'важно',
            'implement', 'create', 'add', 'improve', 'optimize', 'develop', 'recommend'
        ]
        # Паттерны для actionable фраз
        action_patterns = ['→', '->', ':', '—', '•', '- ', '1.', '2.', 'рекомендация', 'action', 'task']

        def normalize(s: str) -> str:
            return s.strip()[:500]

        sentences = re.split(r'[.!?\n]+', consensus_text)
        for sentence in sentences:
            s = sentence.strip()
            if len(s) < 20:
                continue
            s_lower = s.lower()
            # Проверка глаголов действия
            if any(verb in s_lower for verb in action_verbs):
                n = normalize(s)
                if n and n not in seen:
                    seen.add(n)
                    insights.append(n)
            # Проверка паттернов (рекомендации, списки)
            elif any(p in s_lower for p in action_patterns) and len(s) > 30:
                n = normalize(s)
                if n and n not in seen:
                    seen.add(n)
                    insights.append(n)

        return insights[:5]  # Максимум 5 инсайтов (расширено с 3)
    
    async def create_task_from_debate(self, debate_id: str, analysis: Dict) -> Optional[str]:
        """
        Создает задачу для внедрения на основе дебата.
        
        Returns:
            ID созданной задачи или None
        """
        if analysis['consensus_score'] < MIN_CONSENSUS_FOR_TASK:
            logger.info(f"Debate {debate_id} consensus_score too low ({analysis['consensus_score']:.2f}), skipping task creation")
            return None
        
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Получаем знание, связанное с дебатом
            knowledge = None
            if analysis['knowledge_node_id']:
                knowledge = await conn.fetchrow("""
                    SELECT id, content, domain_id, metadata
                    FROM knowledge_nodes
                    WHERE id = $1
                """, analysis['knowledge_node_id'])
            
            # Определяем домен задачи
            domain_id = knowledge['domain_id'] if knowledge else None
            if not domain_id:
                domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'General' LIMIT 1")
                if not domain_id:
                    domain_id = await conn.fetchval("SELECT id FROM domains ORDER BY id LIMIT 1")
            
            # Находим эксперта для назначения задачи
            # Берем первого эксперта из дебата или эксперта, создавшего знание
            assignee_id = None
            if analysis['knowledge_node_id'] and knowledge:
                original_expert = knowledge.get('metadata', {}).get('expert')
                if original_expert:
                    try:
                        from app.expert_aliases import resolve_expert_name_for_db
                        resolved_expert = resolve_expert_name_for_db(original_expert)
                    except ImportError:
                        resolved_expert = original_expert
                    assignee_id = await conn.fetchval("SELECT id FROM experts WHERE name = $1", resolved_expert)
            
            if not assignee_id:
                # Берем эксперта домена
                assignee = await conn.fetchrow("""
                    SELECT id FROM experts 
                    WHERE department = (SELECT name FROM domains WHERE id = $1)
                    ORDER BY RANDOM() 
                    LIMIT 1
                """, domain_id)
                assignee_id = assignee['id'] if assignee else None
            
            if not assignee_id:
                # Берем Викторияию как последний вариант
                assignee_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
            
            # Находим создателя задачи (Виктория)
            creator_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
            if not creator_id:
                creator_id = assignee_id
            
            # Формируем описание задачи
            task_title = f"💡 Внедрить: {analysis['topic'][:60]}"
            
            actionable_text = "\n".join([f"- {insight}" for insight in analysis['actionable_insights']])
            task_description = f"""Консенсус экспертов (score: {analysis['consensus_score']:.2f}, priority: {analysis['priority']})

Консенсус:
{analysis['consensus_summary']}

Действия для внедрения:
{actionable_text if actionable_text else 'Требуется анализ консенсуса и разработка плана внедрения.'}

Источник: Дебат экспертов (debate_id: {debate_id})"""
            
            # Создаем задачу
            task_id = await conn.fetchval("""
                INSERT INTO tasks (
                    title, description, status, priority,
                    assignee_expert_id, creator_expert_id, domain_id,
                    metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, 
                task_title,
                task_description,
                'pending',
                analysis['priority'],
                assignee_id,
                creator_id,
                domain_id,
                json.dumps({
                    "source": "debate_processor",
                    "debate_id": debate_id,
                    "knowledge_node_id": analysis['knowledge_node_id'],
                    "consensus_score": analysis['consensus_score'],
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
            )
            
            logger.info(f"✅ Created task {task_id} from debate {debate_id} (priority: {analysis['priority']})")
            return str(task_id)
    
    async def prioritize_knowledge_from_debate(self, debate_id: str, analysis: Dict) -> bool:
        """
        Приоритизирует знание на основе дебата.
        Обновляет priority в knowledge_nodes.
        
        Returns:
            True если обновление выполнено
        """
        if not analysis['knowledge_node_id']:
            return False
        
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Обновляем метаданные знания с приоритетом из дебата
            await conn.execute("""
                UPDATE knowledge_nodes
                SET metadata = metadata || jsonb_build_object(
                    'debate_priority', $1::text,
                    'debate_consensus_score', $2::numeric,
                    'debate_id', $3::text,
                    'prioritized_at', $4::text
                )
                WHERE id = $5::uuid
            """, 
                str(analysis['priority']),
                float(analysis['consensus_score']),
                str(debate_id),
                datetime.now(timezone.utc).isoformat(),
                str(analysis['knowledge_node_id'])
            )
            
            logger.info(f"✅ Prioritized knowledge {analysis['knowledge_node_id']} from debate {debate_id} (priority: {analysis['priority']})")
            return True
    
    async def send_notification_for_important_consensus(self, debate_id: str, analysis: Dict) -> bool:
        """
        Создает уведомление о важном консенсусе.
        
        Returns:
            True если уведомление создано
        """
        if analysis['consensus_score'] < MIN_CONSENSUS_FOR_NOTIFICATION:
            return False
        
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Проверяем, нет ли уже уведомления для этого дебата
            # Если есть колонка metadata, проверяем по ней
            has_metadata = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'notifications' 
                    AND column_name = 'metadata'
                )
            """)
            
            if has_metadata:
                existing = await conn.fetchval("""
                    SELECT COUNT(*) FROM notifications
                    WHERE metadata->>'debate_id' = $1
                """, debate_id)
            else:
                # Если metadata нет, проверяем по сообщению
                existing = await conn.fetchval("""
                    SELECT COUNT(*) FROM notifications
                    WHERE message LIKE $1
                """, f"%debate_id: {debate_id}%")
            
            if existing > 0:
                return False  # Уведомление уже отправлено
            
            # Создаем уведомление
            notification_message = f"""🎯 ВАЖНЫЙ КОНСЕНСУС ЭКСПЕРТОВ

Тема: {analysis['topic']}

Консенсус (score: {analysis['consensus_score']:.2f}, приоритет: {analysis['priority']}):
{analysis['consensus_summary'][:300]}...

💡 Рекомендуется создать задачу для внедрения."""
            
            # Создаем уведомление (таблица notifications: id, message, sent, created_at)
            await conn.execute("""
                INSERT INTO notifications (message, sent)
                VALUES ($1, FALSE)
            """, notification_message)
            
            logger.info(f"📢 Sent notification for important consensus from debate {debate_id}")
            return True
    
    async def process_new_debates(self) -> Dict[str, int]:
        """
        Обрабатывает все новые дебаты (без обработки).
        
        Returns:
            Статистика обработки
        """
        # Используем один пул для всех операций
        if not hasattr(self, '_pool') or self._pool is None:
            self._pool = await self.get_pool()
        
        pool = self._pool
        stats = {
            "processed": 0,
            "tasks_created": 0,
            "knowledge_prioritized": 0,
            "notifications_sent": 0,
            "errors": 0
        }
        
        try:
            async with pool.acquire() as conn:
                # Находим дебаты без обработки
                # Проверяем наличие колонки metadata
                has_metadata = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'expert_discussions' 
                        AND column_name = 'metadata'
                    )
                """)
            
            if has_metadata:
                # Обрабатываем дебаты, которые не обработаны или обработаны более 7 дней назад
                debates = await conn.fetch("""
                    SELECT id, knowledge_node_id
                    FROM expert_discussions
                    WHERE (metadata->>'processed' IS NULL OR metadata->>'processed' = 'false' 
                           OR (metadata->>'processed_at' IS NOT NULL 
                               AND (metadata->>'processed_at')::timestamp < NOW() - INTERVAL '7 days'))
                    ORDER BY created_at DESC
                    LIMIT 100
                """)
            else:
                # Если metadata нет, обрабатываем все дебаты
                debates = await conn.fetch("""
                    SELECT id, knowledge_node_id
                    FROM expert_discussions
                    ORDER BY created_at DESC
                    LIMIT 100
                """)
            
            logger.info(f"📊 Found {len(debates)} new debates to process")
            
            for debate in debates:
                try:
                    debate_id = str(debate['id'])
                    
                    # Анализируем дебат
                    analysis = await self.analyze_debate_consensus(debate_id)
                    if not analysis:
                        continue
                    
                    stats["processed"] += 1
                    
                    # Приоритизируем знание
                    if analysis['knowledge_node_id']:
                        if await self.prioritize_knowledge_from_debate(debate_id, analysis):
                            stats["knowledge_prioritized"] += 1
                    
                    # Создаем задачу для внедрения
                    task_id = await self.create_task_from_debate(debate_id, analysis)
                    if task_id:
                        stats["tasks_created"] += 1
                    
                    # Отправляем уведомление о важном консенсусе
                    if await self.send_notification_for_important_consensus(debate_id, analysis):
                        stats["notifications_sent"] += 1
                    
                    # Помечаем дебат как обработанный (если есть колонка metadata)
                    if has_metadata:
                        await conn.execute("""
                            UPDATE expert_discussions
                            SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                                'processed', true,
                                'processed_at', $1,
                                'consensus_score', $2,
                                'priority', $3
                            )
                            WHERE id = $4
                        """, 
                            datetime.now(timezone.utc).isoformat(),
                            analysis['consensus_score'],
                            analysis['priority'],
                            debate['id']
                        )
                    
                except Exception as e:
                    logger.error(f"❌ Error processing debate {debate['id']}: {e}")
                    stats["errors"] += 1
                    import traceback
                    traceback.print_exc()
        except Exception as e:
            logger.error(f"❌ Critical error in process_new_debates: {e}")
            stats["errors"] += 1
        
        # Не закрываем пул, так как он может использоваться повторно
        return stats


async def process_all_debates():
    """Главная функция для обработки всех дебатов"""
    processor = DebateProcessor()
    stats = await processor.process_new_debates()
    
    print(f"\n📊 Статистика обработки дебатов:")
    print(f"   Обработано дебатов: {stats['processed']}")
    print(f"   Создано задач: {stats['tasks_created']}")
    print(f"   Приоритизировано знаний: {stats['knowledge_prioritized']}")
    print(f"   Отправлено уведомлений: {stats['notifications_sent']}")
    print(f"   Ошибок: {stats['errors']}")
    
    return stats


if __name__ == "__main__":
    asyncio.run(process_all_debates())

