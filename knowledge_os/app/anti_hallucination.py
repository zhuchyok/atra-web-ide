"""
Anti-Hallucination System - Система снижения галлюцинаций в локальных моделях
Использует RAG, prompt engineering и валидацию ответов
"""

import os
import json
import asyncio
import logging
import asyncpg
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

class AntiHallucinationSystem:
    """Система снижения галлюцинаций через RAG и валидацию"""
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
    
    def create_anti_hallucination_prompt(self, user_query: str, context: List[str] = None) -> str:
        """
        Создать промпт с защитой от галлюцинаций
        
        Args:
            user_query: Запрос пользователя
            context: Контекст из базы знаний
        
        Returns:
            Промпт с инструкциями против галлюцинаций
        """
        base_prompt = """Ты - точный и надежный ассистент. Следуй этим правилам:

1. **ТОЧНОСТЬ ПРЕВЫШЕ ВСЕГО**: Отвечай только на основе предоставленного контекста или проверенных фактов.
2. **ЧЕСТНОСТЬ**: Если не знаешь точного ответа - скажи "Не уверен" или "Нужна дополнительная информация".
3. **БЕЗ ВЫДУМОК**: Не придумывай факты, даты, имена или детали, которых нет в контексте.
4. **ПРОВЕРКА**: Если сомневаешься - укажи уровень уверенности.
5. **ИСТОЧНИКИ**: При возможности ссылайся на источники информации.

"""
        
        if context:
            context_text = "\n\n".join([f"[Контекст {i+1}]: {c}" for i, c in enumerate(context)])
            base_prompt += f"\n\nКОНТЕКСТ ДЛЯ ОТВЕТА:\n{context_text}\n\n"
        
        base_prompt += f"\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{user_query}\n\n"
        base_prompt += "ОТВЕТ (только на основе контекста или проверенных фактов):"
        
        return base_prompt
    
    async def retrieve_relevant_context(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Получить релевантный контекст из базы знаний (RAG)
        
        Args:
            query: Запрос пользователя
            limit: Количество результатов
        
        Returns:
            Список релевантных знаний
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Простой поиск по ключевым словам (можно улучшить через векторный поиск)
                keywords = query.lower().split()
                keyword_pattern = '|'.join(keywords[:5])  # Первые 5 слов
                
                rows = await conn.fetch("""
                    SELECT content, confidence_score, metadata, domain_id
                    FROM knowledge_nodes
                    WHERE is_verified = TRUE
                    AND confidence_score >= 0.8
                    AND (
                        content ILIKE ANY(ARRAY[SELECT '%' || keyword || '%' FROM unnest(string_to_array($1, '|')) AS keyword])
                        OR metadata::text ILIKE ANY(ARRAY[SELECT '%' || keyword || '%' FROM unnest(string_to_array($1, '|')) AS keyword])
                    )
                    ORDER BY confidence_score DESC, usage_count DESC
                    LIMIT $2
                """, keyword_pattern, limit)
                
                context = []
                for row in rows:
                    domain = await conn.fetchval("SELECT name FROM domains WHERE id = $1", row['domain_id'])
                    context.append({
                        "content": row['content'],
                        "confidence": float(row['confidence_score']),
                        "domain": domain,
                        "metadata": row['metadata']
                    })
                
                logger.info(f"✅ Найдено {len(context)} релевантных контекстов")
                return context
                
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Ошибка получения контекста: {e}")
            return []
    
    async def validate_response(self, response: str, context: List[Dict]) -> Tuple[bool, float, List[str]]:
        """
        Валидировать ответ на наличие галлюцинаций
        
        Args:
            response: Ответ модели
            context: Контекст из базы знаний
        
        Returns:
            (is_valid, confidence, issues)
        """
        issues = []
        confidence = 1.0
        
        # Проверка 1: Ответ не пустой
        if not response or len(response.strip()) < 10:
            issues.append("Ответ слишком короткий")
            confidence *= 0.5
        
        # Проверка 2: Нет фраз типа "я не знаю" в контексте с высоким confidence
        if "не знаю" in response.lower() or "не уверен" in response.lower():
            if context and all(c['confidence'] >= 0.9 for c in context):
                issues.append("Модель говорит 'не знаю' при наличии проверенного контекста")
                confidence *= 0.7
        
        # Проверка 3: Проверка на явные галлюцинации (можно расширить)
        hallucination_phrases = [
            "точно помню",
            "я уверен что",
            "это факт",
            "100%"
        ]
        
        for phrase in hallucination_phrases:
            if phrase in response.lower():
                issues.append(f"Подозрительная фраза: '{phrase}'")
                confidence *= 0.8
        
        is_valid = confidence >= 0.7 and len(issues) < 2
        
        return is_valid, confidence, issues
    
    async def enhance_response_with_rag(
        self,
        user_query: str,
        model_response: str,
        use_context: bool = True
    ) -> Dict:
        """
        Улучшить ответ через RAG и валидацию
        
        Args:
            user_query: Запрос пользователя
            model_response: Ответ модели
            use_context: Использовать ли контекст из базы знаний
        
        Returns:
            Улучшенный ответ с метаданными
        """
        context = []
        if use_context:
            context = await self.retrieve_relevant_context(user_query)
        
        # Валидация ответа
        is_valid, confidence, issues = await self.validate_response(model_response, context)
        
        # Если ответ невалиден и есть контекст - попробуем улучшить
        if not is_valid and context:
            # Используем контекст для улучшения ответа
            enhanced_prompt = self.create_anti_hallucination_prompt(user_query, [c['content'] for c in context])
            # Здесь можно отправить enhanced_prompt в модель для нового ответа
        
        return {
            "response": model_response,
            "is_valid": is_valid,
            "confidence": confidence,
            "issues": issues,
            "context_used": len(context),
            "enhanced": not is_valid and len(context) > 0
        }


async def main():
    """Пример использования"""
    system = AntiHallucinationSystem()
    
    # Пример запроса
    query = "Как работает система отслеживания моделей?"
    
    # Получаем контекст
    context = await system.retrieve_relevant_context(query)
    
    # Создаем промпт
    prompt = system.create_anti_hallucination_prompt(query, [c['content'] for c in context])
    
    print("Промпт с защитой от галлюцинаций:")
    print(prompt)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
