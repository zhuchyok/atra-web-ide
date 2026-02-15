"""
Isolated Context Heaps - Изолированные контексты для агентов
На основе практики Anthropic: изолированные контексты для sub-agents
"""

import os
import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

# Лимиты для предотвращения утечки памяти (56+ ГБ: неограниченный рост contexts и размера message)
MAX_CONTEXTS = int(os.getenv('ISOLATED_CONTEXT_MAX_CONTEXTS', '200'))
MAX_MESSAGE_CONTENT_CHARS = int(os.getenv('ISOLATED_CONTEXT_MAX_MESSAGE_CHARS', '2000'))


class ContextType(Enum):
    """Тип контекста"""
    AGENT = "agent"  # Контекст агента
    PROJECT = "project"  # Контекст проекта
    SESSION = "session"  # Контекст сессии
    TASK = "task"  # Контекст задачи


@dataclass
class IsolatedContext:
    """
    Изолированный контекст для агента/проекта
    
    Предотвращает смешивание контекстов между агентами
    """
    agent_name: str
    project_context: str
    context_type: ContextType = ContextType.AGENT
    
    # Изолированная память
    memory: List[Dict[str, str]] = field(default_factory=list)
    
    # Доступные инструменты
    tools: List[str] = field(default_factory=list)
    
    # Метаданные
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Временные метки
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Лимит сообщений в памяти (предотвращение утечки при долгой работе)
    MAX_MEMORY_ENTRIES = 100

    def add_memory(self, role: str, content: str):
        """Добавить запись в память (храним последние MAX_MEMORY_ENTRIES; content обрезается до MAX_MESSAGE_CONTENT_CHARS)."""
        content_stored = content
        if isinstance(content_stored, str) and len(content_stored) > MAX_MESSAGE_CONTENT_CHARS:
            content_stored = content_stored[:MAX_MESSAGE_CONTENT_CHARS] + "..."
        self.memory.append({
            "role": role,
            "content": content_stored,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        if len(self.memory) > self.MAX_MEMORY_ENTRIES:
            self.memory = self.memory[-self.MAX_MEMORY_ENTRIES:]
        self.last_accessed = datetime.now(timezone.utc)
    
    def get_memory(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Получить память (с лимитом)"""
        self.last_accessed = datetime.now(timezone.utc)
        if limit:
            return self.memory[-limit:]
        return self.memory
    
    def clear_memory(self):
        """Очистить память"""
        self.memory = []
        self.last_accessed = datetime.now(timezone.utc)
    
    def update_metadata(self, key: str, value: Any):
        """Обновить метаданные"""
        self.metadata[key] = value
        self.last_accessed = datetime.now(timezone.utc)

    def prune_context(self, task_description: str, max_chars: int = 4000):
        """
        [ADAPTIVE PRUNING] Адаптивная обрезка контекста (Anthropic Pattern).
        Оставляет только те сообщения из памяти, которые релевантны текущей задаче.
        """
        if not self.memory or len(str(self.memory)) <= max_chars:
            return

        logger.info(f"✂️ [PRUNING] Обрезка контекста для задачи: '{task_description[:50]}...'")
        
        # Извлекаем ключевые слова из задачи
        keywords = set(re.findall(r'\w{4,}', task_description.lower()))
        
        # Оцениваем релевантность каждого сообщения
        scored_memory = []
        for msg in self.memory:
            content = msg.get("content", "").lower()
            score = sum(1 for kw in keywords if kw in content)
            # Бонус за свежесть (последние сообщения важнее)
            # Бонус за роль (ответы ассистента часто важнее)
            scored_memory.append((score, msg))
        
        # Сортируем по релевантности (score) и сохраняем хронологию для топ-сообщений
        # Но для простоты: берем последние 3 сообщения ВСЕГДА + топ релевантных
        keep_always = self.memory[-3:]
        others = self.memory[:-3]
        
        # Сортируем остальных по score
        scored_others = sorted([(sum(1 for kw in keywords if kw in m.get("content", "").lower()), m) for m in others], 
                               key=lambda x: x[0], reverse=True)
        
        pruned = []
        current_len = len(str(keep_always))
        
        for score, msg in scored_others:
            msg_len = len(str(msg))
            if current_len + msg_len < max_chars:
                pruned.append(msg)
                current_len += msg_len
            else:
                break
        
        # Объединяем и восстанавливаем хронологию
        final_memory = pruned + keep_always
        self.memory = sorted(final_memory, key=lambda x: x.get("timestamp", ""))
        logger.info(f"✅ [PRUNING] Контекст обрезан: {len(final_memory)} сообщений оставлено")


class ContextManager:
    """
    Менеджер изолированных контекстов
    
    Управляет контекстами для всех агентов и проектов.
    Лимит MAX_CONTEXTS: при превышении удаляется контекст с самым старым last_accessed (причина 56 ГБ).
    """
    
    def __init__(self):
        self.contexts: Dict[str, IsolatedContext] = {}  # key -> IsolatedContext
    
    def _get_key(self, agent_name: str, project_context: str) -> str:
        """Получить ключ для контекста"""
        return f"{agent_name}:{project_context}"
    
    def _evict_lru_context(self) -> None:
        """Удалить контекст с самым старым last_accessed (если достигнут лимит)."""
        if len(self.contexts) < MAX_CONTEXTS:
            return
        oldest_key = min(self.contexts.keys(), key=lambda k: self.contexts[k].last_accessed)
        del self.contexts[oldest_key]
        logger.debug(f"🗑️ [MEMORY] Evicted context {oldest_key} (max {MAX_CONTEXTS})")
    
    def get_context(
        self,
        agent_name: str,
        project_context: str,
        context_type: ContextType = ContextType.AGENT
    ) -> IsolatedContext:
        """
        Получить или создать изолированный контекст
        
        Args:
            agent_name: Имя агента
            project_context: Контекст проекта
            context_type: Тип контекста
        
        Returns:
            IsolatedContext
        """
        key = self._get_key(agent_name, project_context)
        
        if key not in self.contexts:
            self._evict_lru_context()
            self.contexts[key] = IsolatedContext(
                agent_name=agent_name,
                project_context=project_context,
                context_type=context_type
            )
            logger.debug(f"✅ Создан изолированный контекст: {key}")
        
        return self.contexts[key]
    
    def clear_context(self, agent_name: str, project_context: str):
        """Очистить контекст"""
        key = self._get_key(agent_name, project_context)
        if key in self.contexts:
            del self.contexts[key]
            logger.debug(f"🗑️ Удален контекст: {key}")
    
    def clear_all_contexts(self, agent_name: Optional[str] = None, project_context: Optional[str] = None):
        """Очистить все контексты (с фильтрами)"""
        if agent_name and project_context:
            self.clear_context(agent_name, project_context)
        elif agent_name:
            # Очистить все контексты агента
            keys_to_delete = [k for k in self.contexts.keys() if k.startswith(f"{agent_name}:")]
            for key in keys_to_delete:
                del self.contexts[key]
            logger.debug(f"🗑️ Удалены все контексты агента: {agent_name}")
        elif project_context:
            # Очистить все контексты проекта
            keys_to_delete = [k for k in self.contexts.keys() if k.endswith(f":{project_context}")]
            for key in keys_to_delete:
                del self.contexts[key]
            logger.debug(f"🗑️ Удалены все контексты проекта: {project_context}")
        else:
            # Очистить все
            self.contexts = {}
            logger.debug("🗑️ Очищены все контексты")

    def prune_all_contexts(self, task_description: str, max_chars: int = 4000):
        """Обрезать все активные контексты для текущей задачи"""
        for context in self.contexts.values():
            context.prune_context(task_description, max_chars)
            logger.debug("🗑️ Удалены все контексты")
    
    def get_all_contexts(
        self,
        agent_name: Optional[str] = None,
        project_context: Optional[str] = None
    ) -> List[IsolatedContext]:
        """Получить все контексты (с фильтрами)"""
        contexts = list(self.contexts.values())
        
        if agent_name:
            contexts = [c for c in contexts if c.agent_name == agent_name]
        
        if project_context:
            contexts = [c for c in contexts if c.project_context == project_context]
        
        return contexts
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику контекстов"""
        return {
            "total_contexts": len(self.contexts),
            "by_agent": {
                agent: len([c for c in self.contexts.values() if c.agent_name == agent])
                for agent in set(c.agent_name for c in self.contexts.values())
            },
            "by_project": {
                project: len([c for c in self.contexts.values() if c.project_context == project])
                for project in set(c.project_context for c in self.contexts.values())
            }
        }


# Глобальный менеджер контекстов
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """Получить глобальный менеджер контекстов"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
