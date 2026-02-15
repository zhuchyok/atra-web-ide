#!/usr/bin/env python3
"""
Совет экспертов - обсуждение новых мировых практик с 58 сотрудниками.
Выдвижение гипотез, обработка и применение.
"""
import asyncio
import os
import json
import asyncpg
from datetime import datetime, timezone
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

# Импорты для работы с моделями
try:
    from ai_core import run_smart_agent_async
    AI_CORE_AVAILABLE = True
except ImportError:
    AI_CORE_AVAILABLE = False
    logger.warning("ai_core not available, using fallback")

try:
    from local_router import LocalAIRouter
    LOCAL_ROUTER_AVAILABLE = True
except ImportError:
    LOCAL_ROUTER_AVAILABLE = False


class ExpertCouncil:
    """Совет экспертов для обсуждения новых практик"""
    
    def __init__(self, db_url: str = None):
        self.db_url = db_url or DB_URL
        self.router = LocalAIRouter() if LOCAL_ROUTER_AVAILABLE else None
    
    async def get_experts_by_department(self, department: str = None, limit: int = 10) -> List[Dict]:
        """Получить экспертов по департаменту"""
        pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=3)
        async with pool.acquire() as conn:
            query = """
                SELECT id, name, role, department, system_prompt
                FROM experts
                WHERE is_active = TRUE OR is_active IS NULL
            """
            params = []
            if department:
                query += " AND department = $1"
                params.append(department)
            query += " ORDER BY RANDOM() LIMIT $2"
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def get_all_experts(self) -> List[Dict]:
        """Получить всех активных экспертов"""
        pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=3)
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, name, role, department, system_prompt
                FROM experts
                WHERE is_active = TRUE OR is_active IS NULL
                ORDER BY name
            """)
            return [dict(row) for row in rows]
    
    async def get_relevant_experts(self, topic: str, count: int = 5) -> List[Dict]:
        """Выбрать релевантных экспертов для темы"""
        all_experts = await self.get_all_experts()
        
        # Ключевые слова для выбора экспертов
        topic_lower = topic.lower()
        
        relevant = []
        for expert in all_experts:
            role = (expert.get('role') or '').lower()
            dept = (expert.get('department') or '').lower()
            prompt = (expert.get('system_prompt') or '').lower()
            
            # Проверяем релевантность
            score = 0
            if 'ai' in topic_lower or 'agent' in topic_lower or 'neural' in topic_lower:
                if 'ml' in role or 'ai' in role or 'engineer' in role or 'developer' in role:
                    score += 2
            if 'security' in topic_lower:
                if 'security' in role or 'security' in dept:
                    score += 2
            if 'devops' in topic_lower or 'infrastructure' in topic_lower:
                if 'devops' in role or 'devops' in dept:
                    score += 2
            if 'learning' in topic_lower or 'self' in topic_lower:
                if 'ml' in role or 'ai' in role or 'researcher' in role:
                    score += 2
            if 'architecture' in topic_lower:
                if 'architect' in role or 'engineer' in role:
                    score += 1
            
            if score > 0:
                expert['relevance_score'] = score
                relevant.append(expert)
        
        # Сортируем по score и берем топ
        relevant.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        return relevant[:count]
    
    async def ask_expert(self, expert: Dict, question: str) -> Optional[str]:
        """Спросить эксперта"""
        name = expert.get('name', 'Эксперт')
        role = expert.get('role', '')
        system_prompt = expert.get('system_prompt', '')
        
        full_prompt = f"""Вы {name}, {role}.

{system_prompt}

ВОПРОС ДЛЯ ОБСУЖДЕНИЯ:
{question}

Пожалуйста, дайте ваше экспертное мнение:
1. Что вы думаете об этом?
2. Какие преимущества и риски?
3. Как это можно применить в нашей корпорации?
4. Что нам не хватает для реализации?

Ответьте кратко, но по делу (3-5 предложений)."""

        try:
            if LOCAL_ROUTER_AVAILABLE and self.router:
                # Используем локальную модель
                response = await self.router.run_local_llm_async(
                    full_prompt,
                    category="reasoning",
                    model="phi3.5:3.8b"
                )
                if response:
                    return response
            # Fallback к облачной модели
            if AI_CORE_AVAILABLE:
                response = await run_smart_agent_async(
                    full_prompt,
                    expert_name=name,
                    category="reasoning"
                )
                return response
        except Exception as e:
            logger.error(f"Error asking expert {name}: {e}")
        
        return None
    
    async def conduct_discussion(self, topic: str, question: str, expert_count: int = 5) -> Dict:
        """Провести обсуждение с экспертами"""
        logger.info(f"🎯 Начинаем обсуждение темы: {topic}")
        
        # Выбираем релевантных экспертов
        experts = await self.get_relevant_experts(topic, count=expert_count)
        if not experts:
            # Если не нашли релевантных, берем случайных
            experts = await self.get_experts_by_department(limit=expert_count)
        
        logger.info(f"👥 Выбрано {len(experts)} экспертов для обсуждения")
        
        # Задаем вопрос каждому эксперту
        discussions = []
        for expert in experts:
            name = expert.get('name', 'Unknown')
            logger.info(f"   💬 Спрашиваем {name}...")
            
            response = await self.ask_expert(expert, question)
            if response:
                discussions.append({
                    'expert': name,
                    'role': expert.get('role', ''),
                    'department': expert.get('department', ''),
                    'response': response
                })
                logger.info(f"   ✅ {name} ответил ({len(response)} символов)")
            else:
                logger.warning(f"   ⚠️ {name} не ответил")
        
        # Формируем сводку
        summary = {
            'topic': topic,
            'question': question,
            'experts_count': len(experts),
            'responses_count': len(discussions),
            'discussions': discussions,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return summary
    
    async def generate_hypotheses(self, discussion_summary: Dict) -> List[Dict]:
        """Генерировать гипотезы на основе обсуждения"""
        logger.info("💡 Генерируем гипотезы на основе обсуждения...")
        
        # Формируем промпт для генерации гипотез
        discussions_text = "\n\n".join([
            f"**{d['expert']}** ({d['role']}):\n{d['response']}"
            for d in discussion_summary['discussions']
        ])
        
        hypothesis_prompt = f"""На основе обсуждения экспертов, сформулируйте конкретные гипотезы для внедрения.

ТЕМА: {discussion_summary['topic']}

ОБСУЖДЕНИЕ ЭКСПЕРТОВ:
{discussions_text}

ЗАДАЧА:
Сформулируйте 3-5 конкретных гипотез для внедрения. Каждая гипотеза должна:
1. Быть конкретной и измеримой
2. Описывать что внедрить
3. Указывать ожидаемый эффект
4. Быть приоритизирована (high/medium/low)

Верните JSON массив:
[
  {{
    "title": "Название гипотезы",
    "description": "Описание что внедрить",
    "expected_effect": "Ожидаемый эффект",
    "priority": "high|medium|low",
    "components_needed": ["компонент1", "компонент2"]
  }}
]"""

        try:
            if AI_CORE_AVAILABLE:
                response = await run_smart_agent_async(
                    hypothesis_prompt,
                    expert_name="Виктория",
                    category="reasoning",
                    require_cot=True
                )
                
                # Пытаемся извлечь JSON из ответа
                if response:
                    # Ищем JSON в ответе
                    import re
                    json_match = re.search(r'\[.*\]', response, re.DOTALL)
                    if json_match:
                        try:
                            hypotheses = json.loads(json_match.group())
                            logger.info(f"✅ Сгенерировано {len(hypotheses)} гипотез")
                            return hypotheses
                        except json.JSONDecodeError:
                            logger.warning("Не удалось распарсить JSON из ответа")
        except Exception as e:
            logger.error(f"Ошибка генерации гипотез: {e}")
        
        # Fallback: создаем простые гипотезы
        return [
            {
                "title": f"Внедрить практики из {discussion_summary['topic']}",
                "description": "Внедрить найденные практики",
                "expected_effect": "Улучшение системы",
                "priority": "medium",
                "components_needed": []
            }
        ]
    
    async def save_hypotheses(self, hypotheses: List[Dict], discussion_id: str = None):
        """Сохранить гипотезы в БД и отправить в дебаты для обсуждения."""
        pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=3)
        async with pool.acquire() as conn:
            for hyp in hypotheses:
                content = hyp.get('description', '')
                domain_id = hyp.get('domain_id')
                meta_kn = json.dumps({
                    'type': 'hypothesis',
                    'title': hyp.get('title'),
                    'priority': hyp.get('priority', 'medium'),
                    'expected_effect': hyp.get('expected_effect'),
                    'components_needed': hyp.get('components_needed', []),
                    'discussion_id': discussion_id,
                    'source': 'expert_council'
                })
                created = datetime.now(timezone.utc)
                embedding = None
                try:
                    from semantic_cache import get_embedding
                    embedding = await get_embedding(content[:8000])
                except Exception:
                    pass
                if embedding is not None:
                    kn_id = await conn.fetchval("""
                        INSERT INTO knowledge_nodes (content, domain_id, confidence_score, metadata, created_at, embedding)
                        VALUES ($1, $2, 0.8, $3, $4, $5::vector)
                        RETURNING id
                    """, content, domain_id, meta_kn, created, str(embedding))
                else:
                    kn_id = await conn.fetchval("""
                        INSERT INTO knowledge_nodes (content, domain_id, confidence_score, metadata, created_at)
                        VALUES ($1, $2, 0.8, $3, $4)
                        RETURNING id
                    """, content, domain_id, meta_kn, created)
                # Отправка гипотезы в дебаты для обсуждения экспертами
                if kn_id and content:
                    try:
                        from nightly_learner import create_debate_for_hypothesis
                        await create_debate_for_hypothesis(conn, kn_id, content[:800], domain_id)
                    except Exception as e:
                        logger.debug("Hypothesis debate skip: %s", e)
        logger.info(f"✅ Сохранено {len(hypotheses)} гипотез в БД")


async def main():
    """Главная функция для обсуждения новых практик"""
    
    # Новые практики из веб-поиска
    new_practices = [
        {
            "topic": "Self-Evolving Agents с метакогнитивным обучением",
            "question": """Обсудите практики самоэволюционирующих агентов с метакогнитивным обучением:
            
1. Intrinsic Metacognitive Learning - способность агента оценивать, планировать и адаптировать свой процесс обучения
2. Self-Assessment - самооценка знаний и способностей
3. Metacognitive Planning - планирование что изучать дальше
4. Metacognitive Evaluation - рефлексия над опытом обучения

Что нам нужно для внедрения? Какие компоненты создать?"""
        },
        {
            "topic": "Agent Lifecycle Governance и Registration",
            "question": """Обсудите практики управления жизненным циклом агентов:
            
1. Agent Registration - явная регистрация и версионирование агентов
2. Lifecycle Governance - управление версиями, валидация перед деплоем
3. Agent Versioning - отслеживание версий агентов
4. Pre-deployment Validation - проверка перед продакшеном

Как это применить в нашей корпорации? Что нужно создать?"""
        },
        {
            "topic": "Separation of Concerns и Secure by Design",
            "question": """Обсудите архитектурные практики:
            
1. Separation of Concerns - четкое разделение ответственности агентов
2. Secure by Design - безопасность с самого начала
3. Context Management Policies - политики управления контекстом между агентами
4. Failure Isolation - изоляция сбоев, graceful degradation

Как улучшить нашу архитектуру? Какие компоненты добавить?"""
        },
        {
            "topic": "AgentEvolver: Self-Questioning, Self-Navigating, Self-Attributing",
            "question": """Обсудите механизмы самоэволюции агентов:
            
1. Self-Questioning - генерация вопросов для любопытства
2. Self-Navigating - улучшенное исследование пространства задач
3. Self-Attributing - улучшенная эффективность выборки

Как внедрить эти механизмы? Что создать?"""
        },
        {
            "topic": "Multi-Agent Reference Architecture (Microsoft)",
            "question": """Обсудите референсную архитектуру мультиагентных систем:
            
1. Workflow Agents - централизованная координация
2. Multi-Agent Collaboration - децентрализованная координация
3. Observability & Traceability - отслеживание действий
4. Distributed Token Processing - параллельная обработка

Как применить в нашей системе? Что улучшить?"""
        }
    ]
    
    council = ExpertCouncil()
    
    all_hypotheses = []
    
    for practice in new_practices:
        logger.info(f"\n{'='*60}")
        logger.info(f"Обсуждаем: {practice['topic']}")
        logger.info(f"{'='*60}\n")
        
        # Проводим обсуждение
        discussion = await council.conduct_discussion(
            topic=practice['topic'],
            question=practice['question'],
            expert_count=5  # 5 экспертов на тему
        )
        
        # Генерируем гипотезы
        hypotheses = await council.generate_hypotheses(discussion)
        
        # Сохраняем гипотезы
        await council.save_hypotheses(hypotheses)
        
        all_hypotheses.extend(hypotheses)
        
        logger.info(f"\n✅ Обсуждение завершено. Создано {len(hypotheses)} гипотез\n")
    
    logger.info(f"\n🎉 Всего создано {len(all_hypotheses)} гипотез для внедрения!")
    
    # Сохраняем сводку
    summary_file = "expert_council_discussion_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'practices_discussed': len(new_practices),
            'total_hypotheses': len(all_hypotheses),
            'hypotheses': all_hypotheses
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"📄 Сводка сохранена в {summary_file}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
