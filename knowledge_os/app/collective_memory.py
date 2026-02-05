"""
Collective Memory - Коллективная память через stigmergy
Основано на исследовании 2025: +68.7% performance improvement
"""

import os
import asyncio
import logging
import json
import asyncpg
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')


@dataclass
class EnvironmentalTrace:
    """Экологический след (stigmergy)"""
    trace_id: str
    agent_name: str
    action: str
    result: Any
    location: str  # "Место" в системе (файл, задача, домен)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strength: float = 1.0  # Сила следа (убывает со временем)
    metadata: Dict = field(default_factory=dict)


@dataclass
class CollectiveMemory:
    """Коллективная память агента"""
    agent_name: str
    individual_memory: List[Dict] = field(default_factory=list)
    environmental_traces: List[EnvironmentalTrace] = field(default_factory=list)
    aggregated_knowledge: Dict = field(default_factory=dict)


# Лимиты для предотвращения утечки памяти (56+ ГБ при долгой работе Victoria)
MAX_TRACES_PER_LOCATION = int(os.getenv('COLLECTIVE_MEMORY_MAX_TRACES_PER_LOCATION', '200'))
MAX_TRACE_RESULT_CHARS = int(os.getenv('COLLECTIVE_MEMORY_MAX_RESULT_CHARS', '2000'))
MAX_TRACE_LOCATIONS = int(os.getenv('COLLECTIVE_MEMORY_MAX_LOCATIONS', '500'))
# Лимит числа агентов в памяти и размера одного experience (причина 56 ГБ: неограниченный рост agent_memories)
MAX_AGENT_MEMORIES = int(os.getenv('COLLECTIVE_MEMORY_MAX_AGENTS', '100'))
MAX_EXPERIENCE_VALUE_CHARS = int(os.getenv('COLLECTIVE_MEMORY_MAX_EXPERIENCE_CHARS', '2000'))


def _truncate_experience(experience: Dict, depth: int = 0) -> Dict:
    """Обрезать строковые значения в experience до MAX_EXPERIENCE_VALUE_CHARS (предотвращение роста памяти)."""
    if depth > 5:
        return experience
    out = {}
    for k, v in experience.items():
        if isinstance(v, str) and len(v) > MAX_EXPERIENCE_VALUE_CHARS:
            out[k] = v[:MAX_EXPERIENCE_VALUE_CHARS] + "..."
        elif isinstance(v, dict):
            out[k] = _truncate_experience(v, depth + 1)
        else:
            out[k] = v
    return out


class CollectiveMemorySystem:
    """
    Collective Memory System - коллективная память через stigmergy
    
    Механизм:
    1. Individual memory - личная память агента
    2. Environmental traces - следы в среде (stigmergy)
    3. Aggregated knowledge - агрегированное знание
    
    Результаты исследований: +68.7% performance improvement
    """
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.traces: Dict[str, List[EnvironmentalTrace]] = {}  # location -> traces
        self.agent_memories: Dict[str, CollectiveMemory] = {}
        self.decay_rate = 0.1  # Скорость убывания силы следов
    
    async def record_action(
        self,
        agent_name: str,
        action: str,
        result: Any,
        location: str,
        metadata: Dict = None
    ):
        """
        Записать действие агента (создает environmental trace)
        
        Args:
            agent_name: Имя агента
            action: Действие
            result: Результат действия
            location: Место действия (файл, задача, домен)
            metadata: Дополнительные метаданные
        """
        # Ограничиваем размер result в памяти (полный ответ LLM может быть 100KB+)
        result_stored = result
        if isinstance(result_stored, str) and len(result_stored) > MAX_TRACE_RESULT_CHARS:
            result_stored = result_stored[:MAX_TRACE_RESULT_CHARS] + "..."
        elif result_stored is not None and not isinstance(result_stored, (str, int, float, bool)):
            result_stored = str(result_stored)[:MAX_TRACE_RESULT_CHARS] + ("..." if len(str(result_stored)) > MAX_TRACE_RESULT_CHARS else "")
        
        trace = EnvironmentalTrace(
            trace_id=f"{agent_name}_{datetime.now(timezone.utc).isoformat()}",
            agent_name=agent_name,
            action=action,
            result=result_stored,
            location=location,
            metadata=metadata or {}
        )
        
        # Сохраняем trace с лимитом на количество (предотвращение утечки памяти)
        if location not in self.traces:
            if len(self.traces) >= MAX_TRACE_LOCATIONS:
                # Удаляем самую старую location (первый ключ в порядке вставки)
                oldest_key = next(iter(self.traces))
                del self.traces[oldest_key]
            self.traces[location] = []
        self.traces[location].append(trace)
        if len(self.traces[location]) > MAX_TRACES_PER_LOCATION:
            self.traces[location] = self.traces[location][-MAX_TRACES_PER_LOCATION:]
        
        # Сохраняем в БД полный result (без обрезки) — мысль не теряется; в памяти только обрезка
        await self._save_trace_to_db(trace, full_result=result)
        
        logger.debug(f"📝 Записан trace: {agent_name} → {location}")
    
    async def get_environmental_context(self, location: str, agent_name: str) -> Dict:
        """
        Получить контекст из environmental traces (stigmergy)
        
        Args:
            location: Место для получения контекста
            agent_name: Имя агента (для фильтрации своих следов)
        
        Returns:
            Контекст из следов других агентов
        """
        # Получаем traces для location
        traces = self.traces.get(location, [])
        
        # Фильтруем: только следы других агентов, свежие следы
        relevant_traces = [
            trace for trace in traces
            if trace.agent_name != agent_name
            and (datetime.now(timezone.utc) - trace.timestamp) < timedelta(hours=24)
        ]
        
        # Применяем decay к силе следов
        current_time = datetime.now(timezone.utc)
        for trace in relevant_traces:
            age_hours = (current_time - trace.timestamp).total_seconds() / 3600
            trace.strength = max(0.0, trace.strength * (1 - self.decay_rate) ** age_hours)
        
        # Сортируем по силе (самые сильные первыми)
        relevant_traces.sort(reverse=True, key=lambda t: t.strength)
        
        # Формируем контекст
        context = {
            "location": location,
            "traces_count": len(relevant_traces),
            "recent_actions": [
                {
                    "agent": trace.agent_name,
                    "action": trace.action,
                    "result": str(trace.result)[:200],
                    "timestamp": trace.timestamp.isoformat(),
                    "strength": trace.strength
                }
                for trace in relevant_traces[:10]  # Топ 10
            ],
            "aggregated_patterns": await self._aggregate_patterns(relevant_traces)
        }
        
        logger.debug(f"🔍 Контекст для {location}: {len(relevant_traces)} следов")
        
        return context
    
    async def update_individual_memory(
        self,
        agent_name: str,
        experience: Dict
    ):
        """
        Обновить индивидуальную память агента
        
        Args:
            agent_name: Имя агента
            experience: Опыт для сохранения
        """
        # Ограничиваем число агентов в памяти (причина 56 ГБ: неограниченный рост agent_memories)
        if agent_name not in self.agent_memories:
            if len(self.agent_memories) >= MAX_AGENT_MEMORIES:
                oldest_agent = next(iter(self.agent_memories))
                del self.agent_memories[oldest_agent]
                logger.debug(f"🗑️ [MEMORY] Evicted agent {oldest_agent} (max {MAX_AGENT_MEMORIES})")
            self.agent_memories[agent_name] = CollectiveMemory(agent_name=agent_name)
        
        memory = self.agent_memories[agent_name]
        exp_truncated = _truncate_experience(experience)
        memory.individual_memory.append({
            **exp_truncated,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Ограничиваем размер памяти (последние 100 опытов)
        if len(memory.individual_memory) > 100:
            memory.individual_memory = memory.individual_memory[-100:]
        
        logger.debug(f"💾 Обновлена индивидуальная память: {agent_name}")
    
    async def get_enhanced_context(
        self,
        agent_name: str,
        location: str,
        query: Optional[str] = None
    ) -> Dict:
        """
        Получить улучшенный контекст (individual + environmental)
        
        Args:
            agent_name: Имя агента
            location: Место действия
            query: Запрос (опционально)
        
        Returns:
            Улучшенный контекст
        """
        # 1. Индивидуальная память
        individual_context = self._get_individual_context(agent_name, location)
        
        # 2. Environmental traces (stigmergy)
        environmental_context = await self.get_environmental_context(location, agent_name)
        
        # 3. Агрегированное знание
        aggregated = await self._get_aggregated_knowledge(location)
        
        return {
            "individual": individual_context,
            "environmental": environmental_context,
            "aggregated": aggregated,
            "enhancement_factor": self._calculate_enhancement_factor(
                individual_context, environmental_context
            )
        }
    
    def _get_individual_context(self, agent_name: str, location: str) -> Dict:
        """Получить индивидуальный контекст"""
        if agent_name not in self.agent_memories:
            return {"experiences": [], "count": 0}
        
        memory = self.agent_memories[agent_name]
        
        # Фильтруем опыты связанные с location
        relevant_experiences = [
            exp for exp in memory.individual_memory
            if exp.get("location") == location
        ]
        
        return {
            "experiences": relevant_experiences[-10:],  # Последние 10
            "count": len(relevant_experiences)
        }
    
    async def _aggregate_patterns(self, traces: List[EnvironmentalTrace]) -> Dict:
        """Агрегировать паттерны из traces"""
        if not traces:
            return {}
        
        # Группируем по действиям
        action_groups = {}
        for trace in traces:
            action = trace.action
            if action not in action_groups:
                action_groups[action] = []
            action_groups[action].append(trace)
        
        # Находим наиболее частые действия
        patterns = {
            "most_common_actions": [
                {
                    "action": action,
                    "count": len(group),
                    "avg_strength": sum(t.strength for t in group) / len(group)
                }
                for action, group in sorted(
                    action_groups.items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )[:5]
            ],
            "successful_patterns": [
                {
                    "action": trace.action,
                    "result": str(trace.result)[:100]
                }
                for trace in sorted(traces, key=lambda t: t.strength, reverse=True)[:3]
            ]
        }
        
        return patterns
    
    async def _get_aggregated_knowledge(self, location: str) -> Dict:
        """Получить агрегированное знание для location"""
        traces = self.traces.get(location, [])
        
        if not traces:
            return {}
        
        # Агрегируем знания
        return {
            "total_traces": len(traces),
            "unique_agents": len(set(t.agent_name for t in traces)),
            "time_span": {
                "first": min(t.timestamp for t in traces).isoformat(),
                "last": max(t.timestamp for t in traces).isoformat()
            },
            "knowledge_density": len(traces) / max(
                (max(t.timestamp for t in traces) - min(t.timestamp for t in traces)).total_seconds() / 3600,
                1.0
            )
        }
    
    def _calculate_enhancement_factor(self, individual: Dict, environmental: Dict) -> float:
        """Рассчитать фактор улучшения (research: +68.7%)"""
        base_factor = 1.0
        
        # Бонус за индивидуальную память
        if individual.get("count", 0) > 0:
            base_factor += 0.2
        
        # Бонус за environmental traces
        if environmental.get("traces_count", 0) > 0:
            base_factor += 0.3 * min(environmental["traces_count"] / 10, 1.0)
        
        # Бонус за агрегированные паттерны
        if environmental.get("aggregated_patterns"):
            base_factor += 0.2
        
        return min(base_factor, 1.687)  # Максимум +68.7%
    
    async def _save_trace_to_db(self, trace: EnvironmentalTrace, full_result: Any = None):
        """
        Сохранить trace в БД.
        full_result: полный текст результата (без обрезки) — пишем в БД целиком;
        в памяти в trace хранится только обрезка (см. record_action).
        """
        result_for_db = full_result if full_result is not None else trace.result
        if result_for_db is not None and not isinstance(result_for_db, str):
            result_for_db = str(result_for_db)
        try:
            from db_pool import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                # Проверяем наличие таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'environmental_traces'
                    )
                """)
                
                if not table_exists:
                    await self._create_traces_table(conn)
                
                await conn.execute("""
                    INSERT INTO environmental_traces
                    (trace_id, agent_name, action, result, location, timestamp, strength, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (trace_id) DO UPDATE SET
                        strength = EXCLUDED.strength,
                        timestamp = EXCLUDED.timestamp,
                        result = EXCLUDED.result
                """, trace.trace_id, trace.agent_name, trace.action,
                    result_for_db or "", trace.location, trace.timestamp,
                    trace.strength, json.dumps(trace.metadata) if trace.metadata else None)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения trace: {e}")
    
    async def _create_traces_table(self, conn: asyncpg.Connection):
        """Создать таблицу для traces"""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS environmental_traces (
                trace_id VARCHAR(255) PRIMARY KEY,
                agent_name VARCHAR(255) NOT NULL,
                action VARCHAR(255) NOT NULL,
                result TEXT,
                location VARCHAR(255) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                strength FLOAT DEFAULT 1.0,
                metadata JSONB
            );
            
            CREATE INDEX IF NOT EXISTS idx_traces_location 
            ON environmental_traces(location);
            
            CREATE INDEX IF NOT EXISTS idx_traces_agent 
            ON environmental_traces(agent_name);
            
            CREATE INDEX IF NOT EXISTS idx_traces_timestamp 
            ON environmental_traces(timestamp);
        """)
        logger.info("✅ Таблица environmental_traces создана")


async def main():
    """Пример использования"""
    system = CollectiveMemorySystem()
    
    # Записываем действия
    await system.record_action(
        agent_name="Виктория",
        action="analyzed_performance",
        result="Found bottleneck in database queries",
        location="database_optimization"
    )
    
    await system.record_action(
        agent_name="Вероника",
        action="implemented_index",
        result="Created index on user_id column",
        location="database_optimization"
    )
    
    # Получаем контекст
    context = await system.get_enhanced_context(
        agent_name="Игорь",
        location="database_optimization"
    )
    
    print("Улучшенный контекст:")
    print(f"  Environmental traces: {context['environmental']['traces_count']}")
    print(f"  Enhancement factor: {context['enhancement_factor']:.2f}x")
    print(f"  Patterns: {len(context['environmental']['aggregated_patterns'])}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
