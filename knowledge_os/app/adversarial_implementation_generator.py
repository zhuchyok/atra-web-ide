"""
Adversarial Implementation Generator
Автоматическое создание задач для внедрения выдержавших атаку знаний
"""

import asyncio
import os
import json
import asyncpg
import logging
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# Используем get_pool из evaluator для консистентности
sys.path.insert(0, os.path.dirname(__file__))
from evaluator import get_pool
from ai_core import run_smart_agent_async

logger = logging.getLogger(__name__)

# Пороги для создания задач
MIN_CONFIDENCE_FOR_IMPLEMENTATION = 0.75  # Минимальный confidence_score для внедрения
TOP_N_FOR_IMPLEMENTATION = 10  # Топ-N узлов для анализа

class AdversarialImplementationGenerator:
    """
    Генератор задач для внедрения выдержавших adversarial testing знаний.
    """
    
    def __init__(self):
        self.db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
    
    async def get_pool(self):
        return await get_pool()
    
    async def find_survived_knowledge(self, limit: int = TOP_N_FOR_IMPLEMENTATION) -> List[Dict]:
        """
        Находит выдержавшие атаку знания для внедрения.
        
        Returns:
            Список знаний с метриками
        """
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Находим выдержавшие атаку знания, для которых еще не создавались задачи
            # Проверяем наличие 'adversarial_task_created' в metadata
            nodes = await conn.fetch("""
                SELECT 
                    k.id,
                    k.content,
                    k.domain_id,
                    k.metadata,
                    k.confidence_score,
                    k.usage_count,
                    d.name as domain,
                    (k.confidence_score * (CASE WHEN k.usage_count > 0 THEN 1.5 ELSE 1.0 END)) as priority_score
                FROM knowledge_nodes k
                JOIN domains d ON k.domain_id = d.id
                WHERE k.metadata->>'adversarial_tested' = 'true'
                AND k.metadata->>'survived' = 'true'
                AND k.confidence_score >= $1
                AND (k.metadata->>'adversarial_task_created' IS NULL OR k.metadata->>'adversarial_task_created' = 'false')
                ORDER BY priority_score DESC, k.confidence_score DESC
                LIMIT $2
            """, MIN_CONFIDENCE_FOR_IMPLEMENTATION, limit)
            
            candidates = []
            for kn in nodes:
                candidates.append({
                    "id": str(kn['id']),
                    "content": kn['content'],
                    "domain": kn['domain'],
                    "domain_id": str(kn['domain_id']),
                    "confidence_score": float(kn['confidence_score']),
                    "usage_count": kn['usage_count'],
                    "priority_score": float(kn['priority_score']),
                    "metadata": kn['metadata']
                })
            
            await pool.release(conn)
        return candidates
    
    async def create_implementation_task(self, knowledge: Dict) -> Optional[str]:
        """
        Создает задачу для внедрения выдержавшего атаку знания.
        
        Args:
            knowledge: Данные знания с метриками
        
        Returns:
            ID созданной задачи или None
        """
        try:
            pool = await self.get_pool()
        except Exception as e:
            logger.error(f"Error getting pool: {e}")
            return None
        
        async with pool.acquire() as conn:
            try:
                # Проверяем, не создана ли уже задача для этого знания
                existing_task = await conn.fetchval("""
                    SELECT id FROM tasks
                    WHERE metadata->>'knowledge_node_id' = $1
                    AND status IN ('pending', 'in_progress')
                    LIMIT 1
                """, knowledge['id'])
                
                if existing_task:
                    logger.debug(f"Task already exists for knowledge {knowledge['id']}")
                    await pool.release(conn)
                    return None
                
                # Используем AI для анализа знания и генерации actionable tasks
                prompt = f"""
                Вы - стратегический аналитик корпорации ATRA.
                Проанализируйте следующее знание, которое выдержало adversarial testing (стресс-тест),
                и предложите конкретные действия для его внедрения в процессы или создания новых продуктов/сервисов.
                
                Знание (ID: {knowledge['id']}, Домен: {knowledge['domain']}, Confidence: {knowledge['confidence_score']:.2f}):
                "{knowledge['content']}"
                
                Это знание выдержало критическую атаку и доказало свою устойчивость.
                
                Ваша задача:
                1. Определить, как это проверенное знание может быть внедрено в текущие процессы корпорации.
                2. Предложить 1-3 конкретные, измеримые задачи для команды.
                3. Оценить приоритет внедрения (low, medium, high, urgent) на основе важности знания.
                
                Формат ответа: JSON
                ```json
                {{
                    "title": "Краткое название задачи",
                    "description": "Детальное описание задачи, включая контекст знания и предлагаемые шаги.",
                    "priority": "high", // low, medium, high, urgent
                    "actionable_items": ["Пункт 1", "Пункт 2", "Пункт 3"],
                    "implementation_strategy": "Краткая стратегия внедрения"
                }}
                ```
                """
                
                try:
                    # Добавляем таймаут для AI обработки (3 минуты)
                    ai_response = await asyncio.wait_for(
                        run_smart_agent_async(
                            prompt, 
                            expert_name="Виктория", 
                            category="adversarial_implementation",
                            session_id=f"adversarial_task_{knowledge['id']}"
                        ),
                        timeout=180.0  # 3 минуты таймаут
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ AI timeout for adversarial implementation of node {knowledge['id']}. Creating task with fallback.")
                    ai_response = None
                
                if not ai_response:
                    # Fallback: создаем простую задачу без AI анализа
                    logger.info(f"📝 Creating fallback task for knowledge {knowledge['id']}")
                    fallback_title = f"Внедрить проверенное знание (survived adversarial, confidence: {knowledge['confidence_score']:.2f})"
                    fallback_description = f"""
**Исходное знание (ID: {knowledge['id']}, Выдержало adversarial testing):**
{knowledge['content']}

**Статус:** Знание выдержало стресс-тест и доказало свою устойчивость (confidence_score: {knowledge['confidence_score']:.2f}).

**Задача:** Проанализировать и внедрить это проверенное знание в процессы корпорации.

**Домен:** {knowledge['domain']}

**Приоритет:** Высокий (знание проверено adversarial testing)

Источник: Генератор задач по выдержавшим adversarial testing знаниям (fallback режим)
"""
                    priority = "high" if knowledge['confidence_score'] >= 0.8 else "medium"
                
                # Если нет AI ответа, используем fallback
                if not ai_response:
                    analysis = {
                        'title': fallback_title,
                        'description': fallback_description.split('**Задача:**')[0] if '**Задача:**' in fallback_description else 'Требуется анализ и внедрение.',
                        'priority': priority,
                        'actionable_items': ['Проанализировать знание', 'Разработать план внедрения', 'Интегрировать в процессы'],
                        'implementation_strategy': 'Анализ проверенного знания и разработка стратегии внедрения'
                    }
                else:
                    try:
                        # Парсим JSON из ответа
                        clean_json = ai_response.strip()
                        if "```json" in clean_json:
                            clean_json = clean_json.split("```json")[1].split("```")[0]
                        elif "```" in clean_json:
                            clean_json = clean_json.split("```")[1].split("```")[0]
                        
                        analysis = json.loads(clean_json)
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Failed to parse AI response for node {knowledge['id']}. Using fallback.")
                        analysis = {
                            'title': fallback_title,
                            'description': fallback_description.split('**Задача:**')[0] if '**Задача:**' in fallback_description else 'Требуется анализ и внедрение.',
                            'priority': priority,
                            'actionable_items': ['Проанализировать знание', 'Разработать план внедрения'],
                            'implementation_strategy': 'Анализ проверенного знания'
                        }
                
                # Определяем домен
                domain_name = "Knowledge Implementation"
                domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", domain_name)
                if not domain_id:
                    domain_id = await conn.fetchval("INSERT INTO domains (name) VALUES ($1) RETURNING id", domain_name)
                
                # Определяем исполнителя (Виктория)
                assignee = await conn.fetchrow("SELECT id, name FROM experts WHERE name = 'Виктория'")
                assignee_id = assignee['id'] if assignee else None
                if not assignee_id:
                    assignee_id = await conn.fetchval("SELECT id FROM experts LIMIT 1")  # Fallback
                
                creator_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
                if not creator_id:
                    creator_id = assignee_id
                
                actionable_text = "\n".join([f"- {item}" for item in analysis.get('actionable_items', [])])
                
                task_description = f"""
**Исходное знание (ID: {knowledge['id']}, Выдержало adversarial testing):**
{knowledge['content']}

**Стратегия внедрения:**
{analysis.get('implementation_strategy', 'Требуется разработка стратегии внедрения.')}

**Анализ AI и предлагаемые действия:**
{analysis.get('description', 'Нет детального описания.')}

**Конкретные шаги:**
{actionable_text if actionable_text else 'Нет конкретных шагов.'}

**Приоритет AI:** {analysis.get('priority', 'medium')}
**Confidence Score:** {knowledge['confidence_score']:.2f}

Источник: Генератор задач по выдержавшим adversarial testing знаниям
"""
                
                task_id = await conn.fetchval("""
                    INSERT INTO tasks (
                        title, description, status, priority,
                        assignee_expert_id, creator_expert_id, domain_id,
                        metadata
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                """, 
                    analysis.get('title', f"Внедрить проверенное знание {str(knowledge['id'])[:8]}"),
                    task_description,
                    'pending',
                    analysis.get('priority', 'medium'),
                    assignee_id,
                    creator_id,
                    domain_id,
                    json.dumps({
                        "source": "adversarial_implementation_generator",
                        "knowledge_node_id": knowledge['id'],
                        "confidence_score": knowledge['confidence_score'],
                        "survived_adversarial": True,
                        "priority_score": knowledge['priority_score'],
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
                )
                
                logger.info(f"✅ Created task {task_id} for survived knowledge {knowledge['id']} (priority: {analysis.get('priority', 'medium')})")
                
                # Помечаем узел как обработанный
                try:
                    await conn.execute("""
                        UPDATE knowledge_nodes
                        SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('adversarial_task_created', 'true')
                        WHERE id = $1
                    """, knowledge['id'])
                except Exception as e:
                    logger.debug(f"Could not update metadata for knowledge {knowledge['id']}: {e}")
                
                await pool.release(conn)
                return str(task_id)
                
            except Exception as e:
                logger.error(f"❌ Error creating implementation task for knowledge {knowledge['id']}: {e}", exc_info=True)
                try:
                    await pool.release(conn)
                except:
                    pass
                return None
    
    async def process_survived_knowledge(self, limit: int = TOP_N_FOR_IMPLEMENTATION) -> Dict[str, int]:
        """
        Основной цикл обработки выдержавших атаку знаний и создания задач.
        
        Returns:
            Статистика обработки
        """
        logger.info(f"🛡️ Starting adversarial implementation generation cycle (limit: {limit})...")
        
        stats = {
            "analyzed": 0,
            "tasks_created": 0,
            "skipped": 0,
            "errors": 0
        }
        
        try:
            # Находим выдержавшие атаку знания
            candidates = await self.find_survived_knowledge(limit)
            stats["analyzed"] = len(candidates)
            
            logger.info(f"📊 Found {len(candidates)} survived knowledge candidates")
            
            for knowledge in candidates:
                try:
                    task_id = await self.create_implementation_task(knowledge)
                    if task_id:
                        stats["tasks_created"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    logger.error(f"❌ Error processing survived knowledge {knowledge['id']}: {e}", exc_info=True)
                    stats["errors"] += 1
                    # Помечаем узел как ошибочный, чтобы не пытаться его снова бесконечно
                    try:
                        pool = await self.get_pool()
                        async with pool.acquire() as conn:
                            await conn.execute("""
                                UPDATE knowledge_nodes
                                SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('adversarial_task_created', 'error', 'error_message', $1)
                                WHERE id = $2
                            """, str(e), knowledge['id'])
                            await pool.release(conn)
                    except:
                        pass
            
            logger.info(f"✅ Adversarial implementation generation cycle completed. Stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Error in process_survived_knowledge: {e}", exc_info=True)
            stats["errors"] += 1
            return stats


async def run_adversarial_implementation_generation():
    """
    Точка входа для запуска генератора задач по внедрению выдержавших атаку знаний.
    """
    generator = AdversarialImplementationGenerator()
    return await generator.process_survived_knowledge()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    stats = asyncio.run(run_adversarial_implementation_generation())
    print(f"\n📊 Статистика обработки выдержавших атаку знаний:")
    print(f"   Проанализировано: {stats.get('analyzed', 0)}")
    print(f"   Создано задач: {stats.get('tasks_created', 0)}")
    print(f"   Пропущено: {stats.get('skipped', 0)}")
    print(f"   Ошибок: {stats.get('errors', 0)}")

