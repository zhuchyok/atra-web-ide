"""
Adaptive Prompter - Динамическая оптимизация промптов на основе обратной связи
Улучшает промпты на основе успешности предыдущих ответов
"""

import os
import json
import asyncio
import logging
import asyncpg
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')


class AdaptivePrompter:
    """Адаптивная оптимизация промптов на основе обратной связи"""
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.prompt_templates = {}
        self.success_patterns = defaultdict(list)  # Паттерны успешных промптов
        self.failure_patterns = defaultdict(list)  # Паттерны неудачных промптов
    
    async def optimize_prompt(
        self,
        base_prompt: str,
        task_type: str,
        model_name: str,
        use_feedback: bool = True
    ) -> str:
        """
        Оптимизировать промпт на основе истории
        
        Args:
            base_prompt: Базовый промпт
            task_type: Тип задачи (coding, reasoning, general)
            model_name: Имя модели
            use_feedback: Использовать ли обратную связь
        
        Returns:
            Оптимизированный промпт
        """
        if not use_feedback:
            return self._apply_basic_optimization(base_prompt, task_type)
        
        # Получаем историю успешных/неудачных промптов
        success_patterns = await self._get_success_patterns(task_type, model_name)
        failure_patterns = await self._get_failure_patterns(task_type, model_name)
        
        # Применяем оптимизации
        optimized = base_prompt
        
        # 1. Добавляем успешные паттерны
        if success_patterns:
            optimized = self._inject_success_patterns(optimized, success_patterns)
        
        # 2. Избегаем неудачных паттернов
        if failure_patterns:
            optimized = self._avoid_failure_patterns(optimized, failure_patterns)
        
        # 3. Базовые оптимизации
        optimized = self._apply_basic_optimization(optimized, task_type)
        
        return optimized
    
    def _apply_basic_optimization(self, prompt: str, task_type: str) -> str:
        """Применить базовые оптимизации"""
        if task_type == "coding":
            return f"""Ты - эксперт по программированию. Отвечай точно и структурированно.

{prompt}

Требования:
- Код должен быть рабочим и протестированным
- Используй лучшие практики
- Добавь комментарии где необходимо
- Укажи зависимости если нужны

Ответ:"""
        
        elif task_type == "reasoning":
            return f"""Реши задачу пошагово, показывая все рассуждения.

{prompt}

Шаги решения:
1. Анализ проблемы
2. Поиск подхода
3. Решение
4. Проверка

Решение:"""
        
        elif task_type == "general":
            return f"""Ответь на вопрос структурированно и подробно.

{prompt}

Ответ:"""
        
        return prompt
    
    def _inject_success_patterns(self, prompt: str, patterns: List[str]) -> str:
        """Внедрить успешные паттерны"""
        if not patterns:
            return prompt
        
        # Добавляем инструкции из успешных паттернов
        pattern_text = "\n".join([f"- {p}" for p in patterns[:3]])  # Первые 3
        return f"{prompt}\n\n[Успешные подходы из истории]:\n{pattern_text}\n"
    
    def _avoid_failure_patterns(self, prompt: str, patterns: List[str]) -> str:
        """Избегать неудачных паттернов"""
        if not patterns:
            return prompt
        
        # Добавляем предупреждения
        avoid_text = "\n".join([f"- Избегай: {p}" for p in patterns[:2]])  # Первые 2
        return f"{prompt}\n\n[Избегай следующих подходов]:\n{avoid_text}\n"
    
    async def _get_success_patterns(self, task_type: str, model_name: str) -> List[str]:
        """Получить успешные паттерны из истории"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Ищем успешные ответы за последние 7 дней
                rows = await conn.fetch("""
                    SELECT prompt_template, performance_score
                    FROM prompt_feedback
                    WHERE task_type = $1
                    AND model_name = $2
                    AND performance_score >= 0.8
                    AND created_at > NOW() - INTERVAL '7 days'
                    ORDER BY performance_score DESC, created_at DESC
                    LIMIT 10
                """, task_type, model_name)
                
                patterns = [row['prompt_template'] for row in rows if row['prompt_template']]
                return patterns[:5]  # Топ 5
                
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения успешных паттернов: {e}")
            return []
    
    async def _get_failure_patterns(self, task_type: str, model_name: str) -> List[str]:
        """Получить неудачные паттерны из истории"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                rows = await conn.fetch("""
                    SELECT prompt_template, performance_score
                    FROM prompt_feedback
                    WHERE task_type = $1
                    AND model_name = $2
                    AND performance_score < 0.5
                    AND created_at > NOW() - INTERVAL '7 days'
                    ORDER BY performance_score ASC, created_at DESC
                    LIMIT 10
                """, task_type, model_name)
                
                patterns = [row['prompt_template'] for row in rows if row['prompt_template']]
                return patterns[:5]  # Топ 5 неудачных
                
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения неудачных паттернов: {e}")
            return []
    
    async def record_feedback(
        self,
        prompt: str,
        response: str,
        task_type: str,
        model_name: str,
        performance_score: float,
        user_feedback: Optional[str] = None
    ):
        """
        Записать обратную связь о промпте
        
        Args:
            prompt: Промпт
            response: Ответ модели
            task_type: Тип задачи
            model_name: Имя модели
            performance_score: Оценка производительности (0.0-1.0)
            user_feedback: Обратная связь пользователя
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'prompt_feedback'
                    )
                """)
                
                if not table_exists:
                    await self._create_feedback_table(conn)
                
                # Извлекаем шаблон промпта (без конкретных данных)
                prompt_template = self._extract_template(prompt)
                
                await conn.execute("""
                    INSERT INTO prompt_feedback (
                        prompt_template, prompt_full, response,
                        task_type, model_name, performance_score,
                        user_feedback, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                """, prompt_template, prompt[:2000], response[:5000], 
                    task_type, model_name, performance_score, user_feedback)
                
                logger.info(f"✅ Записана обратная связь: {performance_score:.2f}")
                
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка записи обратной связи: {e}")
    
    def _extract_template(self, prompt: str) -> str:
        """Извлечь шаблон из промпта (убрать конкретные данные)"""
        # Простая замена конкретных данных на плейсхолдеры
        template = prompt
        # Можно улучшить через более сложную обработку
        return template[:500]  # Ограничиваем размер
    
    async def _create_feedback_table(self, conn: asyncpg.Connection):
        """Создать таблицу для обратной связи"""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS prompt_feedback (
                id SERIAL PRIMARY KEY,
                prompt_template TEXT NOT NULL,
                prompt_full TEXT,
                response TEXT,
                task_type VARCHAR(50),
                model_name VARCHAR(255),
                performance_score FLOAT,
                user_feedback TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_prompt_feedback_task_model 
            ON prompt_feedback(task_type, model_name);
            
            CREATE INDEX IF NOT EXISTS idx_prompt_feedback_score 
            ON prompt_feedback(performance_score);
            
            CREATE INDEX IF NOT EXISTS idx_prompt_feedback_created 
            ON prompt_feedback(created_at);
        """)
        logger.info("✅ Таблица prompt_feedback создана")


async def main():
    """Пример использования"""
    prompter = AdaptivePrompter()
    
    # Оптимизируем промпт
    optimized = await prompter.optimize_prompt(
        "Напиши функцию для сортировки",
        "coding",
        "qwen2.5-coder:32b",
        use_feedback=True
    )
    print("Оптимизированный промпт:")
    print(optimized)
    
    # Записываем обратную связь
    await prompter.record_feedback(
        optimized,
        "def sort_list(items): ...",
        "coding",
        "qwen2.5-coder:32b",
        performance_score=0.9
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
