#!/usr/bin/env python3
"""
Централизованное логирование использования токенов для всех AI операций
"""
import asyncio
import json
import os
import asyncpg
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def get_pool():
    """Получить пул подключений к БД"""
    from evaluator import get_pool as get_evaluator_pool
    return await get_evaluator_pool()

async def estimate_tokens(text: str) -> int:
    """
    Оценивает количество токенов в тексте.
    Примерная оценка: 1 токен ≈ 4 символа для английского текста,
    но может быть меньше для русского (более длинные слова).
    """
    if not text:
        return 0
    # Упрощенная оценка: учитываем пробелы и знаки препинания
    # Для более точной оценки можно использовать tiktoken или аналоги
    return len(text) // 3  # Более консервативная оценка

async def estimate_cost(prompt_tokens: int, completion_tokens: int, model_type: str = "gpt-4o-mini") -> float:
    """
    Оценивает стоимость токенов в USD.
    
    Цены (примерные, на январь 2026):
    - gpt-4o-mini: input $0.15/1M, output $0.60/1M
    - gpt-4o: input $2.50/1M, output $10.00/1M
    - local models: $0.00 (бесплатно)
    """
    pricing = {
        "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
        "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
        "local": {"input": 0.0, "output": 0.0},
        "cursor-agent": {"input": 0.0, "output": 0.0},  # Cursor-agent может быть локальным или облачным
    }
    
    prices = pricing.get(model_type, pricing["gpt-4o-mini"])
    cost = (prompt_tokens * prices["input"]) + (completion_tokens * prices["output"])
    return round(cost, 6)

async def log_ai_interaction(
    prompt: str,
    response: str,
    expert_id: Optional[str] = None,
    expert_name: Optional[str] = None,
    model_type: str = "gpt-4o-mini",
    source: str = "ai_core",
    knowledge_ids: Optional[List[str]] = None,
    knowledge_applied: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
    trace: Optional[List] = None,
    reasoning_trace: Optional[str] = None
) -> Optional[str]:
    """
    Логирует использование AI с подсчетом токенов и стоимости.
    
    Args:
        prompt: Промпт, отправленный в AI
        response: Ответ от AI
        expert_id: ID эксперта (UUID)
        expert_name: Имя эксперта (для поиска ID если expert_id не указан)
        model_type: Тип модели (gpt-4o-mini, gpt-4o, local, cursor-agent)
        source: Источник запроса (ai_core, telegram, mcp, nightly_learner, etc.)
        knowledge_ids: Список ID узлов знаний, использованных в ответе
        knowledge_applied: Использовались ли знания из базы
        metadata: Дополнительные метаданные
        trace: Трассировка выполнения
        reasoning_trace: Трассировка рассуждений (CoT)
    
    Returns:
        ID созданной записи в interaction_logs или None при ошибке
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Находим expert_id если не указан
            if not expert_id and expert_name:
                try:
                    from app.expert_aliases import resolve_expert_name_for_db
                    resolved_name = resolve_expert_name_for_db(expert_name)
                except ImportError:
                    resolved_name = expert_name
                expert_id = await conn.fetchval("SELECT id FROM experts WHERE name = $1", resolved_name)
            
            # Оцениваем токены
            prompt_tokens = await estimate_tokens(prompt)
            completion_tokens = await estimate_tokens(response)
            total_tokens = prompt_tokens + completion_tokens
            
            # Оцениваем стоимость
            cost_usd = await estimate_cost(prompt_tokens, completion_tokens, model_type)
            
            # Формируем метаданные
            log_metadata = {
                "source": source,
                "model_type": model_type,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "knowledge_node_ids": knowledge_ids or [],
                "knowledge_applied": knowledge_applied,
                "trace": trace or [],
                "reasoning_trace": reasoning_trace or "",
                **(metadata or {})
            }
            
            # Вставляем запись
            log_id = await conn.fetchval("""
                INSERT INTO interaction_logs (
                    expert_id, user_query, assistant_response, 
                    metadata, token_usage, cost_usd, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                RETURNING id
            """, 
                expert_id,
                prompt[:1000],  # Ограничиваем длину для производительности
                response[:2000],
                json.dumps(log_metadata),
                total_tokens,
                cost_usd
            )
            
            # Обновляем usage_count для использованных знаний
            if knowledge_ids:
                await conn.execute("""
                    UPDATE knowledge_nodes 
                    SET usage_count = usage_count + 1 
                    WHERE id = ANY($1)
                """, knowledge_ids)
            
            logger.debug(f"✅ Logged AI interaction: {total_tokens} tokens, ${cost_usd:.6f} (source: {source})")
            return str(log_id)
            
    except Exception as e:
        logger.error(f"❌ Error logging AI interaction: {e}")
        import traceback
        traceback.print_exc()
        return None

async def log_ai_interaction_sync(
    prompt: str,
    response: str,
    **kwargs
) -> Optional[str]:
    """
    Синхронная обертка для log_ai_interaction (для использования в не-async контексте)
    """
    loop = asyncio.get_event_loop()
    return await log_ai_interaction(prompt, response, **kwargs)

def log_ai_interaction_fire_and_forget(
    prompt: str,
    response: str,
    **kwargs
) -> None:
    """
    Асинхронное логирование "fire and forget" - не блокирует выполнение
    """
    try:
        loop = None
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            # Если event loop уже запущен, создаем задачу
            asyncio.create_task(log_ai_interaction(prompt, response, **kwargs))
        else:
            # Если event loop не запущен, запускаем синхронно
            loop.run_until_complete(log_ai_interaction(prompt, response, **kwargs))
    except Exception as e:
        logger.debug(f"Could not log interaction: {e}")

