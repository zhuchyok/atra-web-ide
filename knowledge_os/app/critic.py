import asyncpg
from datetime import datetime

class CriticCore:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def apply_feedback(self, interaction_id: str, score: int):
        """
        Применяет фидбек пользователя к знанию.
        score: 1 (like), -1 (dislike)
        """
        async with self.pool.acquire() as conn:
            # 1. Записываем фидбек в логи
            await conn.execute(
                "UPDATE interaction_logs SET feedback_score = $1 WHERE id = $2",
                score, interaction_id
            )
            
            # 2. Находим знание, которое было использовано в этом ответе
            # (Предполагаем, что метаданные лога хранят ID узла знаний)
            log = await conn.fetchrow("SELECT metadata FROM interaction_logs WHERE id = $1", interaction_id)
            if log and 'knowledge_node_id' in log['metadata']:
                node_id = log['metadata']['knowledge_node_id']
                
                # 3. Обновляем confidence_score узла знаний
                adjustment = 0.1 if score > 0 else -0.2
                await conn.execute(
                    "UPDATE knowledge_nodes SET confidence_score = GREATEST(0, LEAST(1.0, confidence_score + $1)) WHERE id = $2",
                    adjustment, node_id
                )

    async def extract_patterns(self, interaction_id: str):
        """
        Фоновый анализ: если ответ был успешным, закрепить его как знание.
        """
        # В будущем здесь будет вызов LLM для 'осознания' нового опыта
        pass

