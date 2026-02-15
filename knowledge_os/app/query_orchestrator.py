"""
Query & Prompt Orchestrator - автоматическое преобразование запросов в оптимизированные промпты
Концепция из agent.md: Query Orchestrator для role-aware промптов и оптимизации контекста
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Импорты для оптимизации контекста
try:
    from context_compressor import ContextCompressor
    from context_analyzer import ContextAnalyzer
except ImportError:
    ContextCompressor = None
    ContextAnalyzer = None

try:
    from optimizers import FrugalPrompt, PromptOptimizer
except ImportError:
    FrugalPrompt = None
    PromptOptimizer = None


class QueryType(Enum):
    """Типы запросов для классификации"""
    STRATEGY = "strategy"  # Торговая стратегия
    RISK = "risk"  # Риск-менеджмент
    ANALYSIS = "analysis"  # Анализ данных
    OPTIMIZATION = "optimization"  # Оптимизация параметров
    CODE = "code"  # Разработка кода
    ARCHITECTURE = "architecture"  # Архитектура системы
    GENERAL = "general"  # Общий запрос


@dataclass
class NormalizedQuery:
    """Нормализованный запрос пользователя"""
    original: str
    query_type: QueryType
    goal: str  # Что нужно сделать
    context: str  # Где (проект/файлы/планы)
    constraints: List[str]  # Ограничения (безопасность, скорость, ресурсы)
    preferences: List[str]  # Предпочтения (стиль, стек, подход)
    domain: str  # Домен: trading/code/infrastructure/general


@dataclass
class PromptContext:
    """Контекст для сборки промпта"""
    session_summary: Optional[str] = None  # Summary из сессии
    relevant_plans: List[Dict[str, Any]] = None  # Релевантные планы
    relevant_code: List[str] = None  # Релевантные файлы кода
    relevant_knowledge: List[str] = None  # Релевантные знания из БД
    previous_actions: List[Dict[str, Any]] = None  # Предыдущие действия


class QueryOrchestrator:
    """
    Query & Prompt Orchestrator - централизованная нормализация запросов и сборка промптов
    
    Функции:
    1. Классификация запросов
    2. Нормализация запросов
    3. Подбор роли эксперта
    4. Подбор релевантного контекста
    5. Сборка финального промпта по шаблону роли
    6. Оптимизация контекста (сжатие до лимита 60-70% окна)
    """
    
    # Матрица ролей для типов запросов
    ROLE_MATRIX: Dict[QueryType, List[str]] = {
        QueryType.STRATEGY: ["Павел", "Максим", "Мария"],  # Trading Strategy Developer, Data Analyst, Risk Manager
        QueryType.RISK: ["Мария", "Павел", "Екатерина"],  # Risk Manager, Trading Strategy, Financial Analyst
        QueryType.ANALYSIS: ["Максим", "Павел", "Дмитрий"],  # Data Analyst, Trading Strategy, ML Engineer
        QueryType.OPTIMIZATION: ["Павел", "Максим", "Ольга"],  # Trading Strategy, Data Analyst, Performance Engineer
        QueryType.CODE: ["Игорь", "Павел", "Анна"],  # Backend Developer, Trading Strategy, QA Engineer
        QueryType.ARCHITECTURE: ["Виктория", "Игорь", "Павел"],  # Team Lead, Backend Developer, Trading Strategy
        QueryType.GENERAL: ["Виктория", "Максим"],  # Team Lead, Data Analyst
    }
    
    # Ключевые слова для классификации
    STRATEGY_KEYWORDS = [
        "стратегия", "strategy", "сигнал", "signal", "индикатор", "indicator",
        "фильтр", "filter", "бэктест", "backtest", "торговля", "trading"
    ]
    
    RISK_KEYWORDS = [
        "риск", "risk", "stop loss", "take profit", "position sizing", "размер позиции",
        "максимальный просадка", "max drawdown", "VaR", "CVaR"
    ]
    
    ANALYSIS_KEYWORDS = [
        "анализ", "analysis", "метрика", "metric", "статистика", "statistics",
        "результат", "result", "производительность", "performance", "прибыль", "profit"
    ]
    
    OPTIMIZATION_KEYWORDS = [
        "оптимизация", "optimization", "улучшить", "improve", "ускорить", "speed up",
        "оптимизировать", "optimize", "параметр", "parameter"
    ]
    
    CODE_KEYWORDS = [
        "код", "code", "функция", "function", "класс", "class", "модуль", "module",
        "рефакторинг", "refactoring", "баг", "bug", "исправить", "fix"
    ]
    
    ARCHITECTURE_KEYWORDS = [
        "архитектура", "architecture", "структура", "structure", "дизайн", "design",
        "система", "system", "модульность", "modularity"
    ]
    
    def __init__(self, session_manager=None):
        """
        Инициализация Query Orchestrator
        
        Args:
            session_manager: Опциональный StrategySessionManager для восстановления контекста
        """
        self.session_manager = session_manager
    
    def classify_query(self, query: str) -> QueryType:
        """
        Классифицирует запрос по типу
        
        Args:
            query: Сырой запрос пользователя
        
        Returns:
            QueryType: Тип запроса
        """
        query_lower = query.lower()
        
        # Подсчитываем совпадения по ключевым словам
        scores = {
            QueryType.STRATEGY: sum(1 for kw in self.STRATEGY_KEYWORDS if kw in query_lower),
            QueryType.RISK: sum(1 for kw in self.RISK_KEYWORDS if kw in query_lower),
            QueryType.ANALYSIS: sum(1 for kw in self.ANALYSIS_KEYWORDS if kw in query_lower),
            QueryType.OPTIMIZATION: sum(1 for kw in self.OPTIMIZATION_KEYWORDS if kw in query_lower),
            QueryType.CODE: sum(1 for kw in self.CODE_KEYWORDS if kw in query_lower),
            QueryType.ARCHITECTURE: sum(1 for kw in self.ARCHITECTURE_KEYWORDS if kw in query_lower),
        }
        
        # Находим тип с максимальным счетом
        max_score = max(scores.values()) if scores.values() else 0
        
        if max_score > 0:
            query_type = max(scores, key=scores.get)
            logger.debug(f"🔍 [QUERY ORCHESTRATOR] Запрос классифицирован как: {query_type.value} (score: {max_score})")
            return query_type
        
        # Если нет совпадений, возвращаем GENERAL
        return QueryType.GENERAL
    
    def normalize_query(self, query: str) -> NormalizedQuery:
        """
        Нормализует запрос: извлекает цель, контекст, ограничения, предпочтения
        
        Args:
            query: Сырой запрос пользователя
        
        Returns:
            NormalizedQuery: Нормализованный запрос
        """
        query_type = self.classify_query(query)
        
        # Извлекаем цель (что нужно сделать)
        goal = self._extract_goal(query)
        
        # Извлекаем контекст (где)
        context = self._extract_context(query)
        
        # Извлекаем ограничения
        constraints = self._extract_constraints(query)
        
        # Извлекаем предпочтения
        preferences = self._extract_preferences(query)
        
        # Определяем домен
        domain = self._determine_domain(query_type, query)
        
        normalized = NormalizedQuery(
            original=query,
            query_type=query_type,
            goal=goal,
            context=context,
            constraints=constraints,
            preferences=preferences,
            domain=domain
        )
        
        logger.debug(f"📝 [QUERY ORCHESTRATOR] Запрос нормализован: goal={goal[:50]}..., constraints={len(constraints)}, preferences={len(preferences)}")
        
        return normalized
    
    def _extract_goal(self, query: str) -> str:
        """Извлекает цель из запроса"""
        # Удаляем приветствия и обрамления
        query = re.sub(r'^(здравствуйте|привет|добрый\s+(?:день|вечер|утро))[,\s]*', '', query, flags=re.IGNORECASE)
        query = re.sub(r'[,\s]*(спасибо|благодарю|благодарность)[,\s]*$', '', query, flags=re.IGNORECASE)
        
        # Извлекаем основную часть запроса
        goal_match = re.search(r'(?:сделай|создай|напиши|реализуй|разработай|оптимизируй|улучши|исправь|проверь|проанализируй)\s+(.+?)(?:\.|$|при|с|для|в)', query, re.IGNORECASE)
        if goal_match:
            return goal_match.group(1).strip()
        
        # Если не найдено, возвращаем первые 200 символов
        return query[:200].strip()
    
    def _extract_context(self, query: str) -> str:
        """Извлекает контекст (где) из запроса"""
        context_patterns = [
            r'(?:в|для|по)\s+(?:проекту|файлу|модулю|стратегии|фильтру)\s+(.+?)(?:\.|$|,)',
            r'(?:проект|файл|модуль|стратегия|фильтр)\s+(.+?)(?:\.|$|,)',
        ]
        
        for pattern in context_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _extract_constraints(self, query: str) -> List[str]:
        """Извлекает ограничения из запроса"""
        constraints = []
        
        constraint_patterns = [
            r'(?:безопасность|security)\s+(.+?)(?:\.|$|,)',
            r'(?:скорость|speed|performance)\s+(.+?)(?:\.|$|,)',
            r'(?:ресурс|resource|memory|cpu)\s+(.+?)(?:\.|$|,)',
            r'(?:депозит|deposit|баланс|balance)\s+(.+?)(?:\.|$|,)',
            r'(?:плечо|leverage)\s+(.+?)(?:\.|$|,)',
            r'(?:риск|risk)\s+(.+?)(?:\.|$|,)',
        ]
        
        for pattern in constraint_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            constraints.extend(matches)
        
        return constraints
    
    def _extract_preferences(self, query: str) -> List[str]:
        """Извлекает предпочтения из запроса"""
        preferences = []
        
        preference_patterns = [
            r'(?:предпочтительно|preferably|желательно|желательно)\s+(.+?)(?:\.|$|,)',
            r'(?:стиль|style|подход|approach)\s+(.+?)(?:\.|$|,)',
            r'(?:стек|stack|технология|technology)\s+(.+?)(?:\.|$|,)',
        ]
        
        for pattern in preference_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            preferences.extend(matches)
        
        return preferences
    
    def _determine_domain(self, query_type: QueryType, query: str) -> str:
        """Определяет домен запроса"""
        query_lower = query.lower()
        
        if query_type == QueryType.STRATEGY or query_type == QueryType.RISK:
            return "trading"
        elif query_type == QueryType.CODE or query_type == QueryType.ARCHITECTURE:
            return "code"
        elif query_type == QueryType.OPTIMIZATION:
            return "performance"
        else:
            return "general"
    
    def select_role(self, query_type: QueryType, context: Optional[Dict] = None) -> str:
        """
        Выбирает роль эксперта на основе типа задачи
        
        Args:
            query_type: Тип запроса
            context: Дополнительный контекст (опционально)
        
        Returns:
            str: Имя эксперта (Павел/Мария/Максим/Дмитрий/Виктория/...)
        """
        candidates = self.ROLE_MATRIX.get(query_type, [QueryType.GENERAL])
        
        if candidates:
            selected = candidates[0]  # Берем первого кандидата
            logger.debug(f"👤 [QUERY ORCHESTRATOR] Выбрана роль: {selected} для типа {query_type.value}")
            return selected
        
        return "Виктория"  # Fallback на Team Lead
    
    async def select_context(
        self,
        session_id: Optional[str] = None,
        role: Optional[str] = None,
        normalized_query: Optional[NormalizedQuery] = None
    ) -> PromptContext:
        """
        Подбирает релевантный контекст из БД/планов/знаний
        
        Args:
            session_id: ID сессии для восстановления контекста
            role: Роль эксперта
            normalized_query: Нормализованный запрос
        
        Returns:
            PromptContext: Контекст для сборки промпта
        """
        context = PromptContext()
        
        # Если есть session_id, восстанавливаем контекст из сессии
        if session_id and self.session_manager:
            try:
                # get_session_summary - синхронный метод
                context.session_summary = self.session_manager.get_session_summary(session_id)
                logger.debug(f"📋 [QUERY ORCHESTRATOR] Восстановлен контекст сессии: {session_id}")
            except Exception as e:
                logger.debug(f"⚠️ [QUERY ORCHESTRATOR] Ошибка восстановления контекста сессии: {e}")
        
        if context.relevant_knowledge is None:
            context.relevant_knowledge = []
        # Подбор релевантных планов/знаний из БД (knowledge_nodes) по запросу
        if normalized_query and normalized_query.goal:
            await self.enrich_context_from_db_async(context, normalized_query.goal, limit=5)
        
        return context
    
    async def enrich_context_from_db_async(
        self,
        context: PromptContext,
        query_text: str,
        limit: int = 5,
    ) -> None:
        """
        Подбор релевантных планов/знаний из БД (knowledge_nodes) по запросу.
        Вызывать из async-кода после gather_context для заполнения context.relevant_knowledge.
        """
        if not query_text or len(query_text.strip()) < 2:
            return
        try:
            import os
            import asyncpg
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                return
            conn = await asyncpg.connect(db_url)
            try:
                table_exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'knowledge_nodes')"
                )
                if not table_exists:
                    return
                q = query_text.strip()[:200].replace("%", "\\%")
                rows = await conn.fetch(
                    """
                    SELECT LEFT(content, 500) AS snippet
                    FROM knowledge_nodes
                    WHERE content IS NOT NULL AND content ILIKE $1
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT $2
                    """,
                    f"%{q}%",
                    limit,
                )
                if context.relevant_knowledge is None:
                    context.relevant_knowledge = []
                for r in rows:
                    if r["snippet"]:
                        context.relevant_knowledge.append(r["snippet"])
                if rows:
                    logger.debug("QueryOrchestrator: подобрано %s фрагментов из knowledge_nodes", len(rows))
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("QueryOrchestrator enrich_context_from_db: %s", e)
    
    def build_prompt(
        self,
        normalized_query: NormalizedQuery,
        role: str,
        context: PromptContext,
        template_func: Optional[callable] = None
    ) -> str:
        """
        Собирает финальный промпт по шаблону роли
        
        Args:
            normalized_query: Нормализованный запрос
            role: Роль эксперта
            context: Контекст для промпта
            template_func: Функция для получения шаблона роли (опционально)
        
        Returns:
            str: Финальный промпт
        """
        # Если передан template_func, используем его
        if template_func:
            template = template_func(role)
        else:
            # Используем базовый шаблон
            template = self._get_default_template(role)
        
        # Формируем структурированный запрос
        structured_task = self.format_structured_task(normalized_query)
        
        # Формируем контекст
        context_str = self.format_context(context)
        
        # Подставляем в шаблон
        prompt = template.format(
            task=structured_task,
            context=context_str,
            constraints=", ".join(normalized_query.constraints) if normalized_query.constraints else "Нет",
            preferences=", ".join(normalized_query.preferences) if normalized_query.preferences else "Нет"
        )
        
        logger.debug(f"📝 [QUERY ORCHESTRATOR] Промпт собран: длина={len(prompt)}, роль={role}")
        
        return prompt
    
    def _get_default_template(self, role: str) -> str:
        """Получает базовый шаблон промпта для роли"""
        # Базовый шаблон
        base_template = """Ты {role}.
Задача: {task}
Контекст: {context}
Ограничения: {constraints}
Предпочтения: {preferences}

Формат ответа: Чёткий, структурированный ответ с конкретными шагами.
"""
        
        role_name = role  # Будет заменено в prompt_templates.py
        return base_template.replace("{role}", role_name)
    
    def format_structured_task(self, normalized_query: NormalizedQuery) -> str:
        """Форматирует структурированную задачу (публичный метод для использования извне)"""
        task_parts = [normalized_query.goal]
        
        if normalized_query.context:
            task_parts.append(f"Контекст: {normalized_query.context}")
        
        return "\n".join(task_parts)
    
    def format_context(self, context: PromptContext) -> str:
        """Форматирует контекст для промпта. Включает блок «услуги сотрудников» для точного делегирования."""
        context_parts = []
        
        if context.session_summary:
            context_parts.append(f"История сессии: {context.session_summary}")
        
        if context.relevant_plans:
            plans_str = ", ".join([p.get('title', '') for p in context.relevant_plans[:3]])
            context_parts.append(f"Релевантные планы: {plans_str}")
        
        if context.relevant_code:
            code_str = ", ".join(context.relevant_code[:3])
            context_parts.append(f"Релевантный код: {code_str}")
        
        # Услуги сотрудников: оркестратор/Виктория/Вероника могут опираться на экспертов при составлении промптов и планов
        try:
            from expert_services import get_expert_services_text
            context_parts.append("Доступные эксперты и услуги (при необходимости делегируй): " + get_expert_services_text(18))
        except ImportError:
            pass
        
        if not context_parts:
            return "Нет дополнительного контекста"
        
        return "\n".join(context_parts)
    
    def optimize_context(self, context: PromptContext, max_length: int, max_window_percent: float = 0.7) -> PromptContext:
        """
        Оптимизирует контекст: сжимает до лимита (60-70% окна)
        
        Args:
            context: Контекст для оптимизации
            max_length: Максимальная длина контекста
            max_window_percent: Процент от окна модели (по умолчанию 0.7 = 70%)
        
        Returns:
            PromptContext: Оптимизированный контекст
        """
        # Вычисляем реальный лимит (70% от max_length)
        actual_max_length = int(max_length * max_window_percent)
        
        # Сжимаем session_summary
        if context.session_summary and len(context.session_summary) > actual_max_length // 2:
            if ContextCompressor:
                context.session_summary = ContextCompressor.compress_all(context.session_summary[:actual_max_length // 2])
            else:
                context.session_summary = context.session_summary[:actual_max_length // 2] + "..."
        
        # Ограничиваем количество релевантных планов/кода/знаний
        if context.relevant_plans:
            context.relevant_plans = context.relevant_plans[:3]  # Максимум 3 плана
        
        if context.relevant_code:
            context.relevant_code = context.relevant_code[:3]  # Максимум 3 файла
        
        if context.relevant_knowledge:
            context.relevant_knowledge = context.relevant_knowledge[:2]  # Максимум 2 знания
        
        logger.debug(f"📉 [QUERY ORCHESTRATOR] Контекст оптимизирован: max_length={actual_max_length}")
        
        return context

