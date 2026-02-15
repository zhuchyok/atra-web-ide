"""
Victoria Enhanced - Интеграция новых компонентов супер-корпорации с Victoria
Подключает: ReAct, Extended Thinking, Swarm, Consensus, Collective Memory и др.
"""

import os
import asyncio
import logging
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Единый источник «русский + краткость» (план «как я» п.11.3 п.1)
try:
    from configs.victoria_common import PROMPT_RUSSIAN_ONLY, PROMPT_RUSSIAN_AND_BREVITY_LINES
except ImportError:
    PROMPT_RUSSIAN_ONLY = "КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском языке! Все ответы должны быть на русском!"
    PROMPT_RUSSIAN_AND_BREVITY_LINES = (
        "1. ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском языке!\n"
        "2. Ответ должен быть КРАТКИМ - максимум 3-5 предложений!\n"
        "3. НЕ генерируй длинные списки, инструкции или повторяющийся текст!\n"
        "4. НЕ повторяй вопрос, НЕ пиши \"Запрос:\" или \"Ответ:\"!"
    )


def _is_gibberish_output(text: str) -> bool:
    """Проверить, похож ли вывод на мусор (галлюцинации, смешение скриптов, битый текст)."""
    if not text or len(text.strip()) < 20:
        return False  # Пустой — не gibberish, просто нет ответа
    s = text.strip()
    # Смешение CJK с латиницей в хаотичном виде
    import re
    cjk = len(re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', s))
    cyrillic = len(re.findall(r'[а-яёА-ЯЁ]', s))
    latin = len(re.findall(r'[a-zA-Z]', s))
    total_letters = cyrillic + latin + cjk
    if total_letters < 10:
        return False
    # Много CJK при русском запросе — подозрительно
    if cjk > 0 and cyrillic < 20 and cjk + latin > cyrillic:
        return True
    # Переменные/код в ответе: token_0, _text, Instagram_1
    if re.search(r'\b(thoughtful_\d|_0-text|Instagram_\d|token[s]?_\d)\b', s):
        return True
    # Слишком много случайных символов/скобок
    if s.count('[') + s.count('{') > 5 and cyrillic < 30:
        return True
    return False


# Допустимые типы от лёгкой MLX-классификации (гипотеза 1, docs/MLX_STRATEGY_LIGHT_AND_VITALITY.md)
_MLX_LIGHT_CLASSIFY_ALLOWED = frozenset(("greeting", "data_question", "coding", "reasoning", "general"))


async def _try_mlx_light_classify(goal: str, timeout_sec: float = 8.0) -> Tuple[Optional[str], float]:
    """
    Опциональная классификация запроса через лёгкую модель MLX (один короткий промпт).
    Включение: VICTORIA_MLX_LIGHT_CLASSIFY=true. При таймауте/ошибке возвращает (None, duration_sec).
    Возвращает (категория или None, длительность в секундах) для замера.
    """
    import re
    import time
    t0 = time.perf_counter()
    is_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() == "true"
    mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435" if is_docker else "http://localhost:11435")
    prompt = (
        "Определи тип запроса одним словом из списка: greeting, data_question, coding, reasoning, general.\n"
        f"Запрос: {goal[:300]}\nТип:"
    )
    payload = {"prompt": prompt, "category": "fast", "max_tokens": 10, "stream": False}
    try:
        from app.network_resilience import safe_http_request
        response = await safe_http_request(
            f"{mlx_url.rstrip('/')}/api/generate",
            method="POST",
            timeout=timeout_sec,
            json=payload,
        )
        duration = time.perf_counter() - t0
        if response is None or response.status_code != 200:
            return None, duration
        data = response.json()
        text = (data.get("response") or "").strip()
        if not text:
            return None, duration
        first_word = re.sub(r"[^\w]", " ", text).split()
        if not first_word:
            return None, duration
        raw = first_word[0].lower()
        if raw in _MLX_LIGHT_CLASSIFY_ALLOWED:
            if raw == "greeting":
                return "fast", duration
            return raw, duration
        return None, duration
    except Exception as e:
        duration = time.perf_counter() - t0
        logger.debug("MLX light classify: %s", e)
        return None, duration


# Контекст мировых практик для запросов анализа (OpenAI, Anthropic, Meta, Microsoft, LangGraph)
WORLD_PRACTICES_CONTEXT = (
    "Контекст мировых практик (учитывай в ответе): "
    "OpenAI (o1, guardrails, самоисправление), Anthropic (Extended Thinking, CLAUDE.md), "
    "Meta (ReCAP, Model-First Reasoning), Microsoft (AutoGen, Event-Driven, Observability), "
    "LangGraph (State Machines, Checkpoint, HITL), ReAct (Reasoning+Acting). "
)

# Импорт для выбора моделей
try:
    from app.model_selector import select_available_model, check_model_available
    MODEL_SELECTOR_AVAILABLE = True
except ImportError:
    MODEL_SELECTOR_AVAILABLE = False
    logger.debug("Model selector не доступен, используем модели по умолчанию")

# OpenTelemetry для трассировки
try:
    from app.observability import get_observability_manager, trace_span
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False
    logger.debug("Observability не доступен")

# Enhanced Cache для кэширования результатов
try:
    from app.enhanced_cache import get_enhanced_cache
    ENHANCED_CACHE_AVAILABLE = True
except ImportError:
    ENHANCED_CACHE_AVAILABLE = False
    logger.debug("Enhanced Cache не доступен")

# Импорты новых компонентов
try:
    from app.react_agent import ReActAgent
    REACT_AVAILABLE = True
except ImportError:
    REACT_AVAILABLE = False
    logger.warning("⚠️ ReActAgent не доступен")

try:
    from app.extended_thinking import ExtendedThinkingEngine
    EXTENDED_THINKING_AVAILABLE = True
except ImportError:
    EXTENDED_THINKING_AVAILABLE = False
    logger.warning("⚠️ ExtendedThinkingEngine не доступен")

try:
    from app.swarm_intelligence import SwarmIntelligence
    SWARM_AVAILABLE = True
except ImportError:
    SWARM_AVAILABLE = False
    logger.warning("⚠️ SwarmIntelligence не доступен")

try:
    from app.consensus_agent import ConsensusAgent
    CONSENSUS_AVAILABLE = True
except ImportError:
    CONSENSUS_AVAILABLE = False
    logger.warning("⚠️ ConsensusAgent не доступен")

try:
    from app.collective_memory import CollectiveMemorySystem
    COLLECTIVE_MEMORY_AVAILABLE = True
except ImportError:
    COLLECTIVE_MEMORY_AVAILABLE = False
    logger.debug("ℹ️ CollectiveMemorySystem не доступен (опциональный компонент)")

try:
    from app.hierarchical_orchestration import HierarchicalOrchestrator
    HIERARCHICAL_AVAILABLE = True
except ImportError:
    HIERARCHICAL_AVAILABLE = False
    logger.warning("⚠️ HierarchicalOrchestrator не доступен")

try:
    from app.recap_framework import ReCAPFramework
    RECAP_AVAILABLE = True
except ImportError:
    RECAP_AVAILABLE = False
    logger.warning("⚠️ ReCAPFramework не доступен")

try:
    from app.tree_of_thoughts import TreeOfThoughts
    TOT_AVAILABLE = True
except ImportError:
    TOT_AVAILABLE = False
    logger.warning("⚠️ TreeOfThoughts не доступен")

# Новые компоненты 2026
try:
    from app.metacognitive_learning import MetacognitiveLearner
    METACOGNITIVE_AVAILABLE = True
except ImportError:
    METACOGNITIVE_AVAILABLE = False
    logger.warning("⚠️ MetacognitiveLearner не доступен")

try:
    from app.agent_lifecycle_manager import AgentLifecycleManager
    LIFECYCLE_AVAILABLE = True
except ImportError:
    LIFECYCLE_AVAILABLE = False
    logger.warning("⚠️ AgentLifecycleManager не доступен")

try:
    from app.agent_evolver import AgentEvolver
    EVOLVER_AVAILABLE = True
except ImportError:
    EVOLVER_AVAILABLE = False
    logger.warning("⚠️ AgentEvolver не доступен")


class VictoriaEnhanced:
    """
    Victoria Enhanced - Victoria с интеграцией всех новых компонентов
    
    Автоматически выбирает оптимальный метод для задачи:
    - Reasoning → Extended Thinking + ReCAP
    - Planning → Tree of Thoughts + Hierarchical Orchestration
    - Complex → Swarm Intelligence + Consensus
    - Execution → ReAct Framework
    
    Новые компоненты 2026:
    - Metacognitive Learning - самооценка и адаптация обучения (+40-60%)
    - Agent Lifecycle Manager - управление версиями и деплоем
    - AgentEvolver - самоэволюция через вопросы и навигацию (+50-70%)
    """
    
    def __init__(
        self,
        model_name: str = "phi3.5:3.8b",
        use_react: bool = True,
        use_extended_thinking: bool = True,
        use_swarm: bool = True,
        use_consensus: bool = True,
        use_collective_memory: bool = True,
        use_metacognitive: bool = True,
        use_lifecycle: bool = True,
        use_evolver: bool = True
    ):
        self.model_name = model_name
        self.use_react = use_react and REACT_AVAILABLE
        self.use_extended_thinking = use_extended_thinking and EXTENDED_THINKING_AVAILABLE
        self.use_swarm = use_swarm and SWARM_AVAILABLE
        self.use_consensus = use_consensus and CONSENSUS_AVAILABLE
        self.use_collective_memory = use_collective_memory and COLLECTIVE_MEMORY_AVAILABLE
        self.use_metacognitive = use_metacognitive and METACOGNITIVE_AVAILABLE
        self.use_lifecycle = use_lifecycle and LIFECYCLE_AVAILABLE
        self.use_evolver = use_evolver and EVOLVER_AVAILABLE
        
        # Инициализируем компоненты
        self.react_agent = None
        self.extended_thinking = None
        self.swarm = None
        self.consensus = None
        self.collective_memory = None
        self.hierarchical_orch = None
        self.task_delegator = None  # Система делегирования задач
        self.recap = None
        self.tot = None
        # Новые компоненты 2026
        self.metacognitive = None
        self.lifecycle_manager = None
        self.evolver = None
        
        # Инициализация observability
        self.observability = None
        if OBSERVABILITY_AVAILABLE:
            try:
                self.observability = get_observability_manager()  # Не принимает аргументы
                logger.info("✅ Observability инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации Observability: {e}")
        
        # Инициализация кэша
        self.cache = None
        self.use_cache = ENHANCED_CACHE_AVAILABLE
        if self.use_cache:
            try:
                self.cache = get_enhanced_cache()
                logger.info("✅ Enhanced Cache инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации Enhanced Cache: {e}")
                self.use_cache = False
        
        # Инициализация Event-Driven Architecture и Skill Registry
        self.event_bus = None
        self.file_watcher = None
        self.service_monitor = None
        self.deadline_tracker = None
        self.skill_registry = None
        self.skill_loader = None
        self.event_handlers = None
        self.monitoring_started = False
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Инициализировать доступные компоненты"""
        if self.use_react:
            try:
                # Используем модель для coding задач (ReAct часто используется для кода)
                # Но модель будет выбрана динамически при выполнении через fallback
                self.react_agent = ReActAgent(
                    agent_name="Виктория",
                    model_name=self.model_name  # Начальная модель, fallback в _generate_response
                )
                logger.info(f"✅ ReActAgent инициализирован (модель: {self.model_name}, fallback доступен)")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ReActAgent: {e}")
        
        if self.use_extended_thinking:
            try:
                # Используем модель для reasoning задач (по умолчанию)
                # Реальная модель будет выбрана динамически при выполнении
                self.extended_thinking = ExtendedThinkingEngine(
                    model_name=self.model_name
                )
                logger.info(f"✅ ExtendedThinkingEngine инициализирован (модель будет выбрана динамически)")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ExtendedThinkingEngine: {e}")
        
        if self.use_swarm:
            try:
                self.swarm = SwarmIntelligence(
                    swarm_size=16,
                    model_name=self.model_name
                )
                logger.info("✅ SwarmIntelligence инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации SwarmIntelligence: {e}")
        
        if self.use_consensus:
            try:
                self.consensus = ConsensusAgent(model_name=self.model_name)
                logger.info("✅ ConsensusAgent инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ConsensusAgent: {e}")
        
        if self.use_collective_memory:
            try:
                self.collective_memory = CollectiveMemorySystem()
                logger.info("✅ CollectiveMemorySystem инициализирован")
            except Exception as e:
                logger.debug(f"ℹ️ Ошибка инициализации CollectiveMemorySystem: {e} (опциональный компонент)")
        
        if HIERARCHICAL_AVAILABLE:
            try:
                self.hierarchical_orch = HierarchicalOrchestrator(root_agent="Виктория")
                logger.info("✅ HierarchicalOrchestrator инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации HierarchicalOrchestrator: {e}")
        
        # Инициализируем систему делегирования задач
        try:
            from app.task_delegation import TaskDelegator
            self.task_delegator = TaskDelegator()
            logger.info("✅ TaskDelegator инициализирован - Victoria может делегировать задачи Veronica и другим агентам")
        except ImportError as e:
            logger.warning(f"⚠️ TaskDelegator не доступен (ImportError): {e}")
            self.task_delegator = None
        except Exception as e:
            logger.warning(f"⚠️ Ошибка инициализации TaskDelegator: {e}", exc_info=True)
            self.task_delegator = None
        
        if RECAP_AVAILABLE:
            try:
                self.recap = ReCAPFramework(model_name=self.model_name)
                logger.info("✅ ReCAPFramework инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ReCAPFramework: {e}")
        
        if TOT_AVAILABLE:
            try:
                self.tot = TreeOfThoughts(model_name=self.model_name)
                logger.info("✅ TreeOfThoughts инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации TreeOfThoughts: {e}")
        
        # Новые компоненты 2026
        if self.use_metacognitive:
            try:
                self.metacognitive = MetacognitiveLearner(agent_name="Виктория")
                logger.info("✅ MetacognitiveLearner инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации MetacognitiveLearner: {e}")
        
        if self.use_lifecycle:
            try:
                self.lifecycle_manager = AgentLifecycleManager()
                logger.info("✅ AgentLifecycleManager инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации AgentLifecycleManager: {e}")
        
        if self.use_evolver:
            try:
                self.evolver = AgentEvolver(agent_name="Виктория")
                logger.info("✅ AgentEvolver инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации AgentEvolver: {e}")
        
        # Инициализация Event-Driven Architecture
        try:
            from app.event_bus import get_event_bus
            self.event_bus = get_event_bus()
            logger.info("✅ Event Bus инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка инициализации Event Bus: {e}")
        
        # Инициализация Skill Registry
        try:
            from app.skill_registry import get_skill_registry
            self.skill_registry = get_skill_registry()
            logger.info("✅ Skill Registry инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка инициализации Skill Registry: {e}")
        
        # Инициализация Skill Loader
        try:
            from app.skill_loader import SkillLoader
            self.skill_loader = SkillLoader(skill_registry=self.skill_registry)
            logger.info("✅ Skill Loader инициализирован")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка инициализации Skill Loader: {e}")
        
        # Инициализация Victoria Event Handlers
        try:
            from app.victoria_event_handlers import VictoriaEventHandlers
            self.event_handlers = VictoriaEventHandlers(victoria_enhanced=self)
            logger.info("✅ Victoria Event Handlers инициализированы")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка инициализации Event Handlers: {e}")
        
        # Инициализация File Watcher, Service Monitor, Deadline Tracker (ленивая инициализация в start())
    
    async def _get_model_for_category_async(self, category: str) -> Optional[str]:
        """
        Получить модель для категории задачи (динамический выбор из доступных в Ollama/MLX).
        """
        if not MODEL_SELECTOR_AVAILABLE:
            return self.model_name
        
        try:
            # Используем ModelRegistry для динамического выбора
            from app.task_orchestration.model_registry import ModelRegistry
            registry = ModelRegistry()
            
            # Для Mac Studio предпочитаем Ollama (там тяжелые модели)
            model_with_provider = await registry.get_available_model(category, priority="ollama")
            
            if model_with_provider and ":" in model_with_provider:
                provider, model_name = model_with_provider.split(":", 1)
                logger.info(f"✅ Динамически выбрана модель для {category}: {model_name} (через {provider})")
                return model_name
            
            logger.warning(f"⚠️ Ни одна модель не найдена для категории {category}, используем {self.model_name}")
            return self.model_name
        except Exception as e:
            logger.warning(f"⚠️ Ошибка динамического выбора модели для {category}: {e}, используем {self.model_name}")
            return self.model_name
    
    def _get_model_for_category(self, category: str) -> str:
        """Синхронная обертка для выбора модели"""
        try:
            # Пытаемся использовать кэш или быструю проверку
            if MODEL_SELECTOR_AVAILABLE:
                # Для синхронного контекста используем первую доступную модель из списка
                # или возвращаем текущую модель
                return self.model_name
            return self.model_name
        except Exception:
            return self.model_name
    
    def _categorize_task(self, goal: str) -> str:
        """Определить категорию задачи с оптимизацией для быстрых ответов"""
        goal_lower = goal.lower()
        goal_words = goal.split()
        goal_length = len(goal_words)
        
        # 🔍 СЛОЖНЫЕ ЗАДАЧИ - определяем ПЕРВЫМИ (приоритет над простыми)
        # Ключевые слова для сложных задач
        complex_keywords = [
            "полноценное", "веб-приложение", "приложение", "система", "архитектура",
            "интеграция", "база данных", "postgresql", "api", "endpoints",
            "аутентификация", "jwt", "react", "typescript", "fastapi",
            "валидация", "обработка ошибок", "responsive", "дизайн",
            "создай", "разработай", "построй", "реализуй"
        ]
        
        coding_keywords = [
            "html", "css", "javascript", "python", "код", "программируй",
            "напиши код", "создай файл", "страничку", "страницу", "веб-страницу",
            "создай простую", "простая html", "html страничку", "html страницу"
        ]
        
        # Если задача содержит сложные ключевые слова ИЛИ длинная (>15 слов)
        is_complex = (
            any(keyword in goal_lower for keyword in complex_keywords) or
            (goal_length > 15 and any(keyword in goal_lower for keyword in ["с", "и", "состоящее", "включая"]))
        )
        
        is_coding = any(keyword in goal_lower for keyword in coding_keywords)
        
        # Задачи «проанализируй/оптимизируй код» или «команда экспертов» — complex (swarm/команда), не одна Victoria
        team_or_analysis_keywords = [
            "проанализируй", "оптимизируй", "улучшен", "команда", "несколько экспертов",
            "эксперты", "совместно", "консенсус", "коллектив", "архитектур", "стратеги"
        ]
        wants_team = any(kw in goal_lower for kw in team_or_analysis_keywords)
        if is_coding and wants_team:
            return "complex"  # Используем swarm/consensus — команда экспертов
        
        # Приоритет: задачи с кодом определяем первыми (они проще чем complex)
        if is_coding:
            return "coding"  # Используем ReAct или simple с хорошей моделью
        elif is_complex:
            return "complex"  # Используем мощные методы
        
        # 📊 ЗАПРОСЫ О СТАТИСТИКЕ/ДАННЫХ - используем более умные модели
        stats_keywords = [
            "сколько", "количество", "статистик", "задач", "выполнен", "невыполнен",
            "pending", "completed", "в работе", "ожидают", "эксперт", "узлов знаний"
        ]
        is_stats_query = any(keyword in goal_lower for keyword in stats_keywords)
        
        if is_stats_query:
            return "general"  # phi3.5:3.8b, glm-4.7-flash и др.
        
        # 📋 ЗАПРОСЫ О СТАТУСЕ/ПРИОРИТЕТАХ — simple (быстро, без долгого extended thinking)
        status_keywords = ["статус", "приоритет", "приоритеты", "что в работе", "что сейчас"]
        if any(kw in goal_lower for kw in status_keywords):
            return "status_query"  # simple — 1 вызов LLM, без ReAct/extended thinking

        # 🔍 ЗАПРОСЫ О МИРОВЫХ ПРАКТИКАХ/АНАЛИЗЕ - используем reasoning (extended thinking)
        analysis_keywords = [
            "мировые практики", "best practices", "что не хватает", "проанализируй",
            "сравни", "анализ", "пробелы", "что отсутствует", "что нужно добавить"
        ]
        is_analysis_query = any(keyword in goal_lower for keyword in analysis_keywords)
        
        if is_analysis_query:
            return "reasoning"  # extended_thinking — для анализа
        
        # 🚀 БЫСТРЫЕ / ИНФОРМАЦИОННЫЕ ЗАДАЧИ — приветствия, «что умеешь», «кто ты»
        simple_keywords = [
            "привет", "здравствуй", "как дела", "что нового",
            "скажи", "расскажи кратко", "да", "нет",
            "что ты умеешь", "что умеешь", "кто ты", "чем занимаешься",
            "твои возможности", "чем можешь помочь", "расскажи о себе"
        ]
        
        # Информационные вопросы («что умеешь», «кто ты») — simple, без ReAct
        is_informational = any(
            kw in goal_lower for kw in
            ["что ты умеешь", "что умеешь", "кто ты", "чем занимаешься", "твои возможности", "чем можешь помочь", "расскажи о себе"]
        )
        if is_informational:
            return "informational"  # simple (LLM), не ReAct — не нужны инструменты
        
        # Простые: короткие приветствия
        is_simple = (
            goal_length <= 5 and any(keyword in goal_lower for keyword in simple_keywords)
        ) or goal_length <= 3
        if is_simple:
            return "fast"  # Используем быстрые модели
        
        # Остальные категории
        if any(word in goal_lower for word in ["реши", "рассчитай", "вычисли", "reasoning", "логика", "проанализируй"]):
            return "reasoning"
        elif any(word in goal_lower for word in ["спланируй", "организуй", "plan", "планирование", "стратегия"]):
            return "planning"
        elif any(word in goal_lower for word in ["выполни", "сделай", "execute", "действие"]):
            return "execution"
        else:
            return "general"

    async def _get_curator_rag_context(self, goal: str) -> str:
        """
        Подтянуть эталон из RAG (домен curator_standards) для кураторских типов запросов.
        План «умнее быстрее» §3.1: при совпадении с эталонами из standards/ (по ключевым словам)
        подмешивать соответствующий эталон — status_project, what_can_you_do, list_files, greeting, one_line_code.
        """
        if not goal or not goal.strip():
            return ""
        goal_lower = goal.lower().strip()
        # Ключевые слова для всех эталонов куратора (standards/)
        curator_keywords = (
            "статус", "дашборд", "что умеешь", "что ты умеешь", "какой статус", "проект",
            "список файлов", "покажи файлы", "файлы в", "list file", "list dir", "list directory",
            "привет", "здравствуй", "hello", "hi ", "хай",
            "одна строка", "одну строку", "one line", "однострочн",
        )
        if not any(kw in goal_lower for kw in curator_keywords):
            return ""
        try:
            import asyncpg
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                return ""
            conn = await asyncpg.connect(db_url)
            try:
                row = None
                # 1) Статус проекта / дашборд
                if "статус" in goal_lower or "дашборд" in goal_lower or "проект" in goal_lower:
                    row = await conn.fetchrow(
                        """SELECT content FROM knowledge_nodes kn
                           JOIN domains d ON d.id = kn.domain_id
                           WHERE d.name = 'curator_standards'
                             AND (kn.content ILIKE '%статус%' OR kn.content ILIKE '%дашборд%'
                                  OR kn.content ILIKE '%проект%' OR kn.metadata::text ILIKE '%status_project%')
                             AND (kn.confidence_score IS NULL OR kn.confidence_score >= 0.1)
                           ORDER BY (CASE WHEN kn.metadata::text ILIKE '%status_project%' THEN 0 ELSE 1 END),
                                    kn.usage_count DESC NULLS LAST
                           LIMIT 1"""
                    )
                    if not row or not (str(row.get("content") or "").strip()):
                        row = await conn.fetchrow(
                            """SELECT content FROM knowledge_nodes kn
                               JOIN domains d ON d.id = kn.domain_id
                               WHERE d.name = 'curator_standards'
                                 AND kn.metadata::jsonb->>'standard' = 'status_project'
                               LIMIT 1"""
                        )
                # 2) Что умеешь
                elif any(k in goal_lower for k in ("что умеешь", "что ты умеешь", "чем можешь", "возможност", "кто ты")):
                    row = await conn.fetchrow(
                        """SELECT content FROM knowledge_nodes kn
                           JOIN domains d ON d.id = kn.domain_id
                           WHERE d.name = 'curator_standards'
                             AND (kn.content ILIKE '%умею%' OR kn.content ILIKE '%возможност%'
                                  OR kn.metadata::text ILIKE '%what_can_you_do%')
                             AND (kn.confidence_score IS NULL OR kn.confidence_score >= 0.1)
                           ORDER BY kn.usage_count DESC NULLS LAST
                           LIMIT 1"""
                    )
                    if not row or not (str(row.get("content") or "").strip()):
                        row = await conn.fetchrow(
                            """SELECT content FROM knowledge_nodes kn
                               JOIN domains d ON d.id = kn.domain_id
                               WHERE d.name = 'curator_standards'
                                 AND kn.metadata::jsonb->>'standard' = 'what_can_you_do'
                               LIMIT 1"""
                        )
                # 3) Список файлов (план §3.1 — расширение эталонов)
                elif any(k in goal_lower for k in ("список файлов", "покажи файлы", "файлы в", "list file", "list dir", "list directory")):
                    row = await conn.fetchrow(
                        """SELECT content FROM knowledge_nodes kn
                           JOIN domains d ON d.id = kn.domain_id
                           WHERE d.name = 'curator_standards'
                             AND (kn.metadata::jsonb->>'standard' = 'list_files'
                                  OR kn.content ILIKE '%список%файл%' OR kn.content ILIKE '%list%file%')
                             AND (kn.confidence_score IS NULL OR kn.confidence_score >= 0.1)
                           ORDER BY (CASE WHEN kn.metadata::jsonb->>'standard' = 'list_files' THEN 0 ELSE 1 END),
                                    kn.usage_count DESC NULLS LAST
                           LIMIT 1"""
                    )
                # 4) Приветствие
                elif any(k in goal_lower for k in ("привет", "здравствуй", "hello", "hi ", "хай")) and len(goal_lower.split()) <= 5:
                    row = await conn.fetchrow(
                        """SELECT content FROM knowledge_nodes kn
                           JOIN domains d ON d.id = kn.domain_id
                           WHERE d.name = 'curator_standards'
                             AND (kn.metadata::jsonb->>'standard' = 'greeting'
                                  OR kn.content ILIKE '%привет%' OR kn.content ILIKE '%здравствуй%')
                             AND (kn.confidence_score IS NULL OR kn.confidence_score >= 0.1)
                           ORDER BY (CASE WHEN kn.metadata::jsonb->>'standard' = 'greeting' THEN 0 ELSE 1 END)
                           LIMIT 1"""
                    )
                # 5) Одна строка кода
                elif any(k in goal_lower for k in ("одна строка", "одну строку", "one line", "однострочн")):
                    row = await conn.fetchrow(
                        """SELECT content FROM knowledge_nodes kn
                           JOIN domains d ON d.id = kn.domain_id
                           WHERE d.name = 'curator_standards'
                             AND (kn.metadata::jsonb->>'standard' = 'one_line_code'
                                  OR kn.content ILIKE '%одна строка%' OR kn.content ILIKE '%one line%')
                             AND (kn.confidence_score IS NULL OR kn.confidence_score >= 0.1)
                           ORDER BY (CASE WHEN kn.metadata::jsonb->>'standard' = 'one_line_code' THEN 0 ELSE 1 END)
                           LIMIT 1"""
                    )
                if row and row["content"]:
                    return (row["content"] or "").strip()[:2000]
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("RAG curator_standards: %s", e)
        return ""

    async def _get_similar_tasks_context(self, goal: str, max_chars: int = 600) -> str:
        """
        Подтянуть 1–2 похожих успешных решения из домена victoria_tasks (план «умнее, быстрее»).
        _learn_from_task пишет туда результат; при повторной задаче или «сделай как вчера» даём опору.
        """
        if not goal or not goal.strip() or len(goal.strip()) < 4:
            return ""
        try:
            import asyncpg
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                return ""
            conn = await asyncpg.connect(db_url)
            try:
                goal_preview = goal.strip()[:80]
                # Похожие по тексту задачи (metadata->>'task' или content) + приоритет usage_count
                rows = await conn.fetch(
                    """SELECT kn.content, kn.metadata
                       FROM knowledge_nodes kn
                       JOIN domains d ON d.id = kn.domain_id
                       WHERE d.name = 'victoria_tasks'
                         AND (kn.content IS NOT NULL AND length(trim(kn.content)) > 20)
                         AND (kn.metadata::text ILIKE $1 OR kn.content ILIKE $1)
                       ORDER BY kn.usage_count DESC NULLS LAST, kn.created_at DESC
                       LIMIT 2""",
                    f"%{goal_preview}%"
                )
                if not rows:
                    # Fallback: последние 2 по использованию (любая задача)
                    rows = await conn.fetch(
                        """SELECT kn.content, kn.metadata
                           FROM knowledge_nodes kn
                           JOIN domains d ON d.id = kn.domain_id
                           WHERE d.name = 'victoria_tasks'
                             AND (kn.content IS NOT NULL AND length(trim(kn.content)) > 20)
                           ORDER BY kn.usage_count DESC NULLS LAST, kn.created_at DESC
                           LIMIT 2"""
                    )
                if not rows:
                    return ""
                parts = []
                for r in rows:
                    content = (r["content"] or "").strip()[:400]
                    meta = r.get("metadata") or {}
                    task = (meta.get("task") or "")[:80] if isinstance(meta, dict) else ""
                    if content:
                        parts.append(f"- Задача: {task}\n  Результат: {content}" if task else f"- {content}")
                if not parts:
                    return ""
                out = "Похожие успешные решения (из прошлых задач):\n" + "\n".join(parts)
                return out[:max_chars]
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("similar_tasks RAG: %s", e)
        return ""

    async def _get_project_tasks_context(self, project_context: str, limit: int = 5, max_chars: int = 500) -> str:
        """
        Последние задачи по проекту (план «как я» п.12.2): контекст из БД для Victoria.
        Используется при наличии project_context в context при сборке simple-промпта.
        """
        pc = (project_context or "").strip()
        if not pc:
            return ""
        try:
            import asyncpg
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                return ""
            conn = await asyncpg.connect(db_url)
            try:
                # Колонка project_context есть после миграции add_project_context_to_tasks
                rows = await conn.fetch(
                    """SELECT title, status, updated_at
                       FROM tasks
                       WHERE project_context = $1
                       ORDER BY updated_at DESC NULLS LAST
                       LIMIT $2""",
                    pc,
                    limit,
                )
                if not rows:
                    return ""
                parts = []
                for r in rows:
                    title = (r.get("title") or "")[:80]
                    status = r.get("status") or "?"
                    updated = r.get("updated_at")
                    updated_str = updated.strftime("%d.%m %H:%M") if hasattr(updated, "strftime") else str(updated)[:16] if updated else ""
                    parts.append(f"- {title} — {status} ({updated_str})")
                out = "Текущие задачи по проекту (последние):\n" + "\n".join(parts)
                return out[:max_chars]
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("project_tasks context: %s", e)
        return ""

    async def _get_ai_research_context(self, goal: str, max_chars: int = 1500) -> str:
        """
        Сингулярность 10.0: Подтянуть знания о гигантах (AI Research) из БД.
        Используется для вопросов об Anthropic, Google, OpenAI, DeepSeek и др.
        """
        if not goal or not goal.strip():
            return ""
        goal_lower = goal.lower().strip()
        ai_keywords = ["anthropic", "google", "openai", "deepseek", "meta", "llama", "claude", "gemini", "gpt-4", "gpt-5", "research", "исследования"]
        
        if not any(kw in goal_lower for kw in ai_keywords):
            return ""
            
        try:
            import asyncpg
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                return ""
            conn = await asyncpg.connect(db_url)
            try:
                # Поиск по домену 'AI Research' или метатегу 'external_docs_indexer'
                rows = await conn.fetch(
                    """SELECT kn.content, kn.metadata->>'title' as title
                       FROM knowledge_nodes kn
                       JOIN domains d ON d.id = kn.domain_id
                       WHERE (d.name = 'AI Research' OR kn.metadata->>'source' = 'external_docs_indexer')
                         AND (kn.content ILIKE $1 OR kn.metadata::text ILIKE $1)
                       ORDER BY kn.confidence_score DESC NULLS LAST, kn.created_at DESC
                       LIMIT 3""",
                    f"%{goal_lower[:30]}%"
                )
                if not rows:
                    return ""
                
                parts = []
                for r in rows:
                    title = r.get("title") or "Без названия"
                    content = (r["content"] or "").strip()[:800]
                    if content:
                        parts.append(f"### {title}\n{content}")
                
                if not parts:
                    return ""
                
                return "\n---\n**Актуальные знания AI Research:**\n" + "\n\n".join(parts)
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("AI Research RAG: %s", e)
        return ""

    async def _get_semantic_history_context(self, goal: str, session_id: Optional[str] = None) -> str:
        """
        [SEMANTIC HISTORY SEARCH] Поиск по смыслу в прошлых сессиях (Claude Opus 4.6 Pattern)
        """
        goal_lower = goal.lower()
        # Триггеры для поиска по истории
        triggers = ["как мы делали", "как раньше", "помнишь", "вчера", "обсуждали", "прошлый раз"]
        if not any(t in goal_lower for t in triggers):
            return ""

        logger.info(f"🔍 [SEMANTIC HISTORY] Запуск поиска по истории для: '{goal[:50]}...'")
        try:
            from app.semantic_cache import get_embedding
            embedding = await get_embedding(goal)
            if not embedding:
                return ""
            
            db_url = os.getenv('DATABASE_URL')
            import asyncpg
            conn = await asyncpg.connect(db_url)
            try:
                # Ищем в knowledge_nodes по эмбеддингам
                rows = await conn.fetch("""
                    SELECT content, metadata->>'date' as date, (1 - (embedding <=> $1::vector)) as similarity
                    FROM knowledge_nodes
                    WHERE (metadata->>'type' = 'session_exchange' OR metadata->>'source' = 'victoria_enhanced')
                    AND embedding IS NOT NULL
                    AND (1 - (embedding <=> $1::vector)) > 0.8
                    ORDER BY similarity DESC
                    LIMIT 3
                """, str(embedding))
                
                if not rows:
                    return ""
                
                history_parts = []
                for r in rows:
                    date_str = r['date'] or "ранее"
                    history_parts.append(f"[{date_str}] {r['content']}")
                
                return "\n### ИЗ ИСТОРИИ ПРОШЛЫХ ОБСУЖДЕНИЙ:\n" + "\n---\n".join(history_parts)
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"Ошибка семантического поиска по истории: {e}")
            return ""

    async def solve(
        self,
        goal: str,
        method: Optional[str] = None,
        use_enhancements: bool = True,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Решить задачу используя оптимальный метод
        
        Args:
            goal: Цель задачи
            method: Предпочтительный метод (опционально)
            use_enhancements: Использовать ли улучшения
        
        Returns:
            Результат с метаданными
        """
        if not use_enhancements:
            # Fallback на простой метод
            return {"result": "Enhanced methods disabled", "method": "simple"}
        
        # Трассировка через OpenTelemetry
        span_attributes = {"goal": goal[:100], "use_enhancements": use_enhancements}
        span_context = None
        if hasattr(self, 'observability') and self.observability:
            try:
                span_context = self.observability.trace_span("victoria_enhanced.solve", span_attributes)
            except Exception as e:
                logger.debug(f"Observability недоступен: {e}")
                span_context = None
        
        try:
            if span_context:
                span_context.__enter__()
            
            # Сразу при получении задачи: проверить доступность Ollama и MLX, при необходимости поднять их
            await self._ensure_llm_backends_available()
            
            # Определяем категорию задачи (нужно для делегирования)
            category = self._categorize_task(goal)
            # Опционально: для неочевидных general (5–25 слов) — один вызов лёгкой MLX для уточнения категории (docs/MLX_STRATEGY_LIGHT_AND_VITALITY.md §5.1)
            if (
                category == "general"
                and 5 <= len((goal or "").split()) <= 25
                and os.getenv("VICTORIA_MLX_LIGHT_CLASSIFY", "false").lower() in ("true", "1", "yes")
            ):
                new_cat, duration_sec = await _try_mlx_light_classify(goal)
                if new_cat and new_cat != "general":
                    logger.info(
                        "[MLX_LIGHT_CLASSIFY] general -> %s goal_len=%d duration_ms=%.0f",
                        new_cat, len((goal or "").split()), duration_sec * 1000,
                    )
                    category = new_cat
                elif new_cat is None and duration_sec > 0:
                    logger.debug("[MLX_LIGHT_CLASSIFY] no_change_or_error duration_ms=%.0f", duration_sec * 1000)

            # Ранняя проверка: вопросы о данных корпорации и метриках Mac Studio — сразу через corporation_data_tool
            logger.info(f"DEBUG solve: checking early route for goal='{goal[:50]}'")
            try:
                from app.corporation_data_tool import is_data_question, query_corporation_data, _extract_latest_user_message
                goal_for_data = _extract_latest_user_message(goal)
                if is_data_question(goal) or is_data_question(goal_for_data):
                    logger.info(f"📊 [CORP DATA] Ранний маршрут: вопрос о данных/метриках — '{goal_for_data[:80]}...'")
                    corp_result = await query_corporation_data(goal_for_data)
                    if corp_result.get("success") and corp_result.get("answer"):
                        logger.info(f"✅ [CORP DATA] Ответ через corporation_data_tool (метрики/корпорация)")
                        return {
                            "result": corp_result["answer"],
                            "method": "simple",
                            "metadata": {
                                "source": "corporation_data_tool",
                                "sql": corp_result.get("sql"),
                                "count": corp_result.get("count"),
                                "fast_mode": True,
                            },
                        }
                    elif corp_result.get("answer"):
                        # Ответ есть (например текст ошибки) — возвращаем его
                        return {
                            "result": corp_result["answer"],
                            "method": "simple",
                            "metadata": {"source": "corporation_data_tool", "fast_mode": True},
                        }
            except ImportError:
                logger.debug("corporation_data_tool не импортирован")
            except Exception as e:
                logger.warning(f"corporation_data_tool (ранний маршрут): {e}", exc_info=True)
            
            # Проверяем, нужно ли делегировать через Department Heads (мировые практики)
            should_use_department_heads, dept_info = await self._should_use_department_heads(goal, category)
            if should_use_department_heads:
                logger.info(f"🏢 Использую Department Heads System для задачи: {goal[:50]}...")
                try:
                    from app.department_heads_system import get_department_heads_system
                    db_url = os.getenv('DATABASE_URL')
                    
                    # Логируем подключение к БД
                    if db_url:
                        logger.info(f"🔌 Использую DATABASE_URL для подключения к экспертам корпорации")
                        logger.debug(f"🔌 DATABASE_URL: {db_url[:50]}..." if len(db_url) > 50 else f"🔌 DATABASE_URL: {db_url}")
                    else:
                        if not hasattr(self, '_db_url_warning_logged'):
                            logger.debug(f"ℹ️ DATABASE_URL не настроен, эксперты из БД недоступны (используем fallback)")
                            self._db_url_warning_logged = True
                    
                    dept_system = get_department_heads_system(db_url)
                    
                    # Определяем отдел (только если should_use_department_heads вернул True)
                    # Проверка ключевых слов уже была в _should_use_department_heads
                    department = dept_system.determine_department(goal)
                    if department:
                        complexity = dept_system.determine_complexity(goal, department)
                        
                        # Оптимальная архитектура: план (task_plan) от Victoria, при наличии task_plan_struct — без повторного парсинга
                        should_use, coordination_result = await self._should_use_department_heads(goal, category)
                        
                        if should_use and (coordination_result.get("task_plan") or coordination_result.get("veronica_prompt")):
                            # Используем новую систему task_distribution
                            logger.info(f"🔄 [TASK DISTRIBUTION] Использую новую систему распределения задач")
                            execution_result = await self._execute_department_task(goal, coordination_result, department)
                            
                            if execution_result:
                                return execution_result
                        
                        # Fallback на старую систему
                        result = await dept_system.coordinate_department_task(goal, department, complexity)
                        
                        if result.get("success"):
                            logger.info(f"✅ Задача координируется через отдел '{department}' (стратегия: {result.get('strategy')})")
                            
                            # Выполняем задачу через выбранную стратегию
                            execution_result = await self._execute_department_task(goal, result, department)
                            
                            if execution_result:
                                return execution_result
                            
                            # Fallback - возвращаем информацию о координации
                            return {
                                "result": f"Задача координируется через отдел '{department}' (Head: {result.get('head', {}).get('name', 'N/A')})",
                                "method": "department_heads",
                                "department": department,
                                "strategy": result.get("strategy"),
                                "metadata": result
                            }
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка Department Heads System: {e}, продолжаю стандартное делегирование")
            
            # Проверяем, нужно ли делегировать задачу другому агенту
            logger.info(f"🔍 Проверяю делегирование для задачи: {goal[:50]}... (TaskDelegator: {self.task_delegator is not None})")
            if self.task_delegator:
                should_delegate, delegation_info = await self._should_delegate_task(goal, category=category)
                logger.info(f"🔍 Проверка делегирования: should_delegate={should_delegate}, info={delegation_info}")
                if should_delegate:
                    logger.info(f"📋 Делегирую задачу Veronica: {delegation_info.get('agent', 'unknown')} - {delegation_info.get('reason', '')}")
                    try:
                        # Делегируем задачу
                        task = await self.task_delegator.delegate_smart(goal)
                        logger.info(f"✅ Задача делегирована: {task.task_id} → {task.assigned_to}")
                        
                        # Выполняем задачу через назначенного агента
                        from app.multi_agent_collaboration import MultiAgentCollaboration
                        collaboration = MultiAgentCollaboration()
                        result = await collaboration.execute_task(task)
                        
                        if result.success:
                            raw_out = result.result
                            out = (raw_out if isinstance(raw_out, str) else (str(raw_out) if raw_out is not None else "")) or ""
                            out = out.strip()
                            logger.info(f"✅ Задача выполнена через {task.assigned_to}: {(out[:100] + '...') if len(out) > 100 else out or '(пусто)'}")
                            # Мировые практики: в ответе всегда явно статус + что выполнилось + результат
                            steps = getattr(result, "coordination_steps", []) or []
                            status_line = f"✅ Статус: задача выполнена через {task.assigned_to} (task_id: {task.task_id})."
                            steps_block = "\n".join(f"   • {s}" for s in steps) if steps else ""
                            combined = f"{status_line}\n{steps_block}\n\nРезультат:\n{out}" if out else f"{status_line}\n{steps_block}\n\nРезультат: (ответ агента пуст — проверьте логи {task.assigned_to})"
                            return {
                                "result": combined.strip(),
                                "method": "delegation",
                                "delegated_to": task.assigned_to,
                                "task_id": task.task_id,
                                "metadata": {**(result.metadata or {}), "coordination_steps": steps}
                            }
                        else:
                            logger.warning(f"⚠️ Делегированная задача не выполнена ({result.metadata.get('error', 'unknown')}), выполняю сама")
                            # Продолжаем выполнение самостоятельно
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка делегирования: {e}, выполняю сама", exc_info=True)
                        # Продолжаем выполнение самостоятельно
            
            # Выбираем оптимальную модель для категории задачи
            optimal_model = await self._get_model_for_category_async(category)
            if optimal_model and optimal_model != self.model_name:
                logger.info(f"🎯 Выбрана модель для категории '{category}': {optimal_model}")
                # Обновляем модель для компонентов если нужно
                if self.extended_thinking and category == "reasoning":
                    self.extended_thinking.model_name = optimal_model
            
            # Выбираем метод
            if method is None:
                method = self._select_optimal_method(category, goal)
            
            logger.info(f"🎯 Victoria Enhanced: категория={category}, метод={method}, модель={optimal_model or self.model_name}")
            
            # Добавляем атрибуты в span
            if hasattr(self, 'observability') and self.observability:
                try:
                    self.observability.set_attribute("task.category", category)
                    self.observability.set_attribute("task.method", method)
                except Exception as e:
                    logger.debug(f"Не удалось установить атрибуты observability: {e}")
            
            # Получаем контекст из Collective Memory и истории чата
            memory_context = None
            if self.collective_memory:
                try:
                    memory_context = await self.collective_memory.get_enhanced_context(
                        agent_name="Виктория",
                        location="general"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка получения collective memory: {e}")
            
            # Объединяем контексты: переданный контекст (история чата) + collective memory
            if context and memory_context:
                context = {**context, **memory_context}
            elif memory_context:
                context = memory_context
            # Если context передан, используем его (история чата важнее)
            
            # Проверяем кэш
            if self.use_cache and self.cache:
                cached_result = await self.cache.get(method, goal, context)
                if cached_result:
                    logger.info(f"✅ Cache hit для метода {method}")
                    if hasattr(self, 'observability') and self.observability:
                        try:
                            self.observability.set_attribute("cache.hit", True)
                        except Exception:
                            pass
                    return cached_result
                if hasattr(self, 'observability') and self.observability:
                    try:
                        self.observability.set_attribute("cache.hit", False)
                    except Exception:
                        pass
            
            # Выполняем через выбранный метод
            result = await self._execute_method(method, goal, category, context)
            
            # Сохраняем в кэш только успешные ответы (не кэшируем «модели недоступны» и др.)
            if self.use_cache and self.cache and result:
                meta = result.get("metadata") or {}
                skip_cache = (
                    meta.get("note") == "models_unavailable"
                    or (result.get("result") or "").startswith("Сейчас не могу подключиться к моделям")
                    or result.get("error")
                )
                if not skip_cache:
                    try:
                        await self.cache.set(method, goal, result, context)
                        logger.debug(f"💾 Результат сохранен в кэш: {method}")
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка сохранения в кэш: {e}")
            
            # Добавляем метрики в span
            if hasattr(self, 'observability') and self.observability:
                try:
                    self.observability.set_attribute("result.method", result.get("method", ""))
                    self.observability.add_event("task.completed", {
                        "method": result.get("method", ""),
                        "success": True
                    })
                except Exception as e:
                    logger.debug(f"Не удалось добавить метрики observability: {e}")
            
            # Сохраняем в Collective Memory
            if self.collective_memory:
                try:
                    await self.collective_memory.record_action(
                        agent_name="Виктория",
                        action="solve",
                        result=result.get("result", ""),
                        location=category
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка сохранения в collective memory: {e}")
            
            return result
        finally:
            if span_context:
                span_context.__exit__(None, None, None)
    
    def _is_casual_chat(self, goal: str) -> bool:
        """
        Понять, что пользователь хочет просто поболтать (без ключевых слов отдела).
        Тогда не используем Department Heads — отвечаем просто (simple/react).
        """
        goal_lower = goal.lower().strip()
        if len(goal_lower) < 25:
            return True
        chat_phrases = [
            "поболтать", "поболтаем", "просто поболтать", "хочу поболтать",
            "привет", "здравствуй", "хай", "hello", "hi", "hey",
            "как дела", "как ты", "что нового", "как жизнь",
            "кто ты", "что умеешь", "расскажи о себе", "представься",
            "спасибо", "thanks", "пока", "bye", "до свидания",
            "расскажи", "объясни в двух словах", "в двух словах",
        ]
        if any(phrase in goal_lower for phrase in chat_phrases):
            return True
        return False

    async def _ensure_llm_backends_available(self) -> None:
        """
        При получении задачи: проверить доступность Ollama и MLX;
        если недоступны — поднять их, затем обновить кэш роутера.
        Модель из доступных в Ollama и MLX выбирается автоматически (available_models_scanner, local_router).
        """
        try:
            from app.llm_backends_ensure import ensure_llm_backends_available
            await ensure_llm_backends_available(
                start_ollama_if_missing=True,
                refresh_local_router_cache=True,
            )
        except ImportError as e:
            logger.debug("llm_backends_ensure недоступен: %s", e)
        except Exception as e:
            logger.warning("Ошибка при проверке/запуске LLM бэкендов: %s", e)

    async def _should_use_department_heads(self, goal: str, category: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Определить, нужно ли использовать Department Heads System
        
        Returns:
            (should_use, dept_info)
        """
        # Сначала: если пользователь просто хочет поболтать — не используем отделы
        if self._is_casual_chat(goal):
            logger.info(f"💬 [CHAT] Похоже на разговор — не использую Department Heads")
            return False, {}
        # Все задачи (в т.ч. создание файлов) идут через план и разбивку — Victoria сразу план, подзадачи, раздача сотрудникам
        goal_lower = goal.lower()
        try:
            from app.department_heads_system import get_department_heads_system
            db_url = os.getenv('DATABASE_URL')
            dept_system = get_department_heads_system(db_url)
            
            # Определяем отдел (все задачи, в т.ч. создание файлов — через план и разбивку)
            department = dept_system.determine_department(goal)
            if department:
                complexity = dept_system.determine_complexity(goal, department)
                
                logger.info(f"🏢 Определен отдел '{department}' для задачи, сложность: {complexity.value}")
                
            # НОВАЯ АРХИТЕКТУРА: Victoria создает промпт для Veronica, Veronica распределяет
            # Используем Department Heads для всех задач, где определен отдел
            if department:
                # Получаем актуальную структуру организации (корпорация растет!)
                from app.organizational_structure import get_organizational_structure
                db_url = os.getenv('DATABASE_URL')
                org_structure = get_organizational_structure(db_url)
                try:
                    full_structure = await org_structure.get_full_structure(force_refresh=False)
                except RuntimeError as re:
                    # Отсутствуют колонки — нужна миграция; не скрываем, отдаём понятный ответ
                    logger.error("Оргструктура: %s", re)
                    raise re
                # Victoria обдумывает и создает план распределения (task_plan)
                task_plan_text, task_plan_struct = await self._think_and_create_prompt_for_veronica(goal)
                return True, {
                    "department": department,
                    "complexity": complexity.value,
                    "reason": "Задача требует распределения через Task Distribution",
                    "task_plan": task_plan_text,
                    "task_plan_struct": task_plan_struct,
                    "veronica_prompt": task_plan_text,
                    "organizational_structure": full_structure
                }
            return False, {}
        except Exception as e:
            logger.debug(f"Department Heads System недоступен: {e}")
            return False, {}
    
    async def _think_and_create_prompt_for_veronica(self, goal: str):
        """
        Этап 1: Victoria обдумывает задачу и создает план распределения (task_plan).
        Включает структуру организации для правильного распределения.
        Возвращает и текст плана, и структурированный JSON — чтобы Task Distribution
        не вызывал Victoria повторно для парсинга (оптимальная архитектура).
        
        Args:
            goal: Исходная задача
            
        Returns:
            (task_plan_text, task_plan_struct) — текст плана и dict с task_description, subtasks, context, expected_result.
            task_plan_struct может быть None при fallback.
        """
        logger.info(f"🧠 [VICTORIA THINKING] Обдумываю задачу и создаю план распределения (task_plan): {goal[:50]}...")
        
        # Получаем актуальную структуру организации для включения в промпт
        # ВАЖНО: Корпорация растет, структура обновляется автоматически
        structure_summary = ""
        try:
            from app.organizational_structure import get_organizational_structure
            db_url = os.getenv('DATABASE_URL')
            org_structure = get_organizational_structure(db_url)
            # Система автоматически проверит изменения в БД
            full_structure = await org_structure.get_full_structure(force_refresh=False)
            structure_summary = org_structure.get_structure_summary(full_structure)
            logger.info(f"📊 Актуальная структура организации: {full_structure.get('total_departments', 0)} отделов, {full_structure.get('total_employees', 0)} сотрудников (корпорация растет!)")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить структуру организации: {e}")
            structure_summary = "СТРУКТУРА: Используй отделы из базы данных экспертов\n"
        
        thinking_prompt = f"""Ты Victoria, главный стратег корпорации. СРАЗУ составь план и разбей задачу на подзадачи, раздай сотрудникам в виде промпта и рекомендуемой модели.

ИСХОДНАЯ ЗАДАЧА: {goal}

{structure_summary}

ОБЯЗАТЕЛЬНО:
1. СРАЗУ составь план: разбей задачу на конкретные подзадачи (шаги).
2. Для КАЖДОЙ подзадачи укажи: промпт (текст задания для сотрудника), отдел, эксперта (роль/имя из структуры), рекомендуемую модель.
3. Рекомендуемая модель — одна из категорий: "coding" (код, файлы, боты), "reasoning" (анализ, логика, планирование), "fast" (короткие ответы), "general" (общее). Либо имя модели: glm-4.7-flash, phi3.5, qwen2.5 и т.д.

4. ПОДЗАДАЧИ должны быть конкретными и исполняемыми: каждая — один промпт для одного сотрудника с одной рекомендуемой моделью.

Верни ТОЛЬКО валидный JSON:
{{
    "task_description": "Краткое описание задачи",
    "subtasks": [
        {{
            "subtask": "Точный промпт для сотрудника (что сделать)",
            "department": "Название отдела",
            "expert_role": "Имя или роль эксперта из структуры",
            "priority": "high|medium|low",
            "requirements": "Требования к результату",
            "recommended_model": "coding|reasoning|fast|general",
            "recommended_models": ["coding"] или ["glm-4.7-flash", "qwen2.5-coder"]
        }}
    ],
    "context": "Важный контекст",
    "expected_result": "Ожидаемый результат"
}}"""

        try:
            # Логируем промпт для Victoria
            try:
                from app.task_trace_hooks import log_prompt, log_model_selection
                log_prompt(
                    who="Виктория",
                    stage="THINKING_FOR_VERONICA",
                    prompt=thinking_prompt,
                    model="ExtendedThinkingEngine" if EXTENDED_THINKING_AVAILABLE else "run_smart_agent_async"
                )
            except ImportError:
                pass
            
            if EXTENDED_THINKING_AVAILABLE and self.extended_thinking:
                # Исправляем вызов метода - убираем max_iterations если метод его не принимает
                try:
                    # Пробуем с max_iterations
                    thinking_result_obj = await self.extended_thinking.think(
                        prompt=thinking_prompt,
                        max_iterations=3
                    )
                except TypeError:
                    # Если не принимает max_iterations, вызываем без него
                    thinking_result_obj = await self.extended_thinking.think(
                        prompt=thinking_prompt
                    )
                
                # Извлекаем строку из ExtendedThinkingResult
                if hasattr(thinking_result_obj, 'final_answer'):
                    thinking_result = thinking_result_obj.final_answer
                elif isinstance(thinking_result_obj, str):
                    thinking_result = thinking_result_obj
                else:
                    # Пробуем преобразовать в строку
                    thinking_result = str(thinking_result_obj)
                
                try:
                    from app.task_trace_hooks import log_model_selection
                    log_model_selection(
                        who="Виктория",
                        task=goal,
                        selected_model="ExtendedThinkingEngine",
                        reason="Используется для глубокого анализа и планирования",
                        available_models=["ExtendedThinkingEngine"]
                    )
                except ImportError:
                    pass
            else:
                # Fallback
                from app.ai_core import run_smart_agent_async
                thinking_result = await run_smart_agent_async(
                    thinking_prompt,
                    expert_name="Виктория",
                    category="planning"
                )
                try:
                    from app.task_trace_hooks import log_model_selection
                    log_model_selection(
                        who="Виктория",
                        task=goal,
                        selected_model="run_smart_agent_async",
                        reason="Fallback: ExtendedThinkingEngine недоступен",
                        available_models=["run_smart_agent_async"]
                    )
                except ImportError:
                    pass
            
            # Извлекаем JSON промпт (с улучшенной обработкой ошибок)
            # Мировая практика: LLM часто возвращает почти-валидный JSON (trailing comma, \n в строках)
            import json
            import re

            def _try_parse_llm_json(s: str) -> dict | None:
                """Пробуем распарсить JSON из ответа LLM с исправлением типичных ошибок."""
                if not s or not s.strip():
                    return None
                # 1. Базовая попытка
                try:
                    return json.loads(s)
                except json.JSONDecodeError:
                    pass
                # 2. Исправляем trailing comma перед ] или }
                fixed = re.sub(r',\s*([}\]])', r'\1', s)
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass
                # 3. Убираем markdown code fences если есть
                cleaned = re.sub(r'^```(?:json)?\s*', '', s.strip())
                cleaned = re.sub(r'\s*```$', '', cleaned)
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass
                return None

            json_match = re.search(r'\{.*\}', thinking_result, re.DOTALL)
            if json_match:
                try:
                    json_str = json_match.group()
                    prompt_data = _try_parse_llm_json(json_str)
                    if not prompt_data:
                        prompt_data = _try_parse_llm_json(
                            json_str.replace('\n', ' ').replace('\r', ' ').strip()
                        )
                    # Формируем текстовый план (task_plan) для Task Distribution
                    if prompt_data:
                        task_plan_text = f"""ЗАДАЧА ОТ VICTORIA:

{prompt_data.get('task_description', goal)}

{structure_summary}

ПОДЗАДАЧИ:
"""
                    else:
                        logger.warning("⚠️ [VICTORIA THINKING] Не удалось распарсить JSON из ответа LLM")
                        logger.debug(f"   JSON строка (первые 500 символов): {json_str[:500]}")
                        task_plan_text = f"""ЗАДАЧА ОТ VICTORIA:

{goal}

АНАЛИЗ ЗАДАЧИ (от Victoria):
{thinking_result[:2000]}

{structure_summary}

ПОДЗАДАЧИ:
"""
                except Exception as parse_err:
                    logger.warning(f"⚠️ [VICTORIA THINKING] Ошибка парсинга JSON: {parse_err}")
                    prompt_data = None
                    task_plan_text = f"""ЗАДАЧА ОТ VICTORIA:

{goal}

АНАЛИЗ ЗАДАЧИ (от Victoria):
{thinking_result[:2000]}

{structure_summary}

ПОДЗАДАЧИ:
"""

                # Логируем план (task_plan) для Task Distribution
                try:
                    from app.task_trace_hooks import log_prompt
                    log_prompt(
                        who="Виктория → Task Distribution",
                        stage="TASK_DISTRIBUTION",
                        prompt=task_plan_text,
                        model="N/A (план от Victoria)"
                    )
                except ImportError:
                    pass
                for i, subtask in enumerate((prompt_data or {}).get('subtasks', []), 1):
                    recommended_models = subtask.get('recommended_models', [])
                    model_selection = subtask.get('model_selection', 'expert_choice')
                    model_hint = ""
                    if model_selection == "recommended" and recommended_models:
                        model_hint = f"\n   - РЕКОМЕНДУЕМЫЕ МОДЕЛИ: {', '.join(recommended_models)} (используй эти модели)"
                    elif model_selection == "expert_choice":
                        if recommended_models:
                            model_hint = f"\n   - РЕКОМЕНДУЕМЫЕ МОДЕЛИ: {', '.join(recommended_models)} (можешь выбрать сам или использовать рекомендации)"
                        else:
                            model_hint = "\n   - ВЫБОР МОДЕЛИ: выбери сам из доступных моделей"
                    elif model_selection == "auto":
                        model_hint = "\n   - ВЫБОР МОДЕЛИ: система выберет автоматически"
                    
                    task_plan_text += f"""
{i}. {subtask.get('subtask', '')}
   - Отдел: {subtask.get('department', 'General')}
   - Эксперт: {subtask.get('expert_role', 'Expert')}
   - Приоритет: {subtask.get('priority', 'medium')}
   - Требования: {subtask.get('requirements', 'N/A')}{model_hint}
"""
                task_plan_text += f"""
КОНТЕКСТ: {(prompt_data or {}).get('context', 'N/A')}

ОЖИДАЕМЫЙ РЕЗУЛЬТАТ: {(prompt_data or {}).get('expected_result', 'N/A')}

ТВОЯ ЗАДАЧА: Распредели подзадачи по отделам/департаментам/сотрудникам и координируй выполнение.
"""
                has_struct = prompt_data is not None and bool((prompt_data or {}).get('subtasks'))
                logger.info(f"✅ [VICTORIA THINKING] План (task_plan) создан ({len(task_plan_text)} символов, task_plan_struct={has_struct})")
                return task_plan_text, prompt_data
            else:
                # Fallback: простой план
                task_plan_text = f"""ЗАДАЧА ОТ VICTORIA:

{goal}

ТВОЯ ЗАДАЧА: Распредели задачу по отделам/департаментам/сотрудникам и координируй выполнение.
"""
            
            logger.info(f"✅ [VICTORIA THINKING] План (task_plan) создан ({len(task_plan_text)} символов), структура без JSON — fallback")
            return task_plan_text, None
            
        except Exception as e:
            logger.error(f"❌ [VICTORIA THINKING] Ошибка создания плана: {e}")
            fallback = f"""ЗАДАЧА ОТ VICTORIA:

{goal}

ТВОЯ ЗАДАЧА: Распредели задачу по отделам/департаментам/сотрудникам и координируй выполнение.
"""
            return fallback, None
    
    async def _execute_department_task(
        self,
        goal: str,
        coordination_result: Dict,
        department: str
    ) -> Optional[Dict]:
        """
        Выполнить задачу через Department Heads System
        
        Args:
            goal: Цель задачи
            coordination_result: Результат координации от Department Heads System
            department: Название отдела
        
        Returns:
            Результат выполнения или None если не удалось выполнить
        """
        try:
            strategy = coordination_result.get("strategy")
            organizational_structure = coordination_result.get("organizational_structure")
            task_plan = coordination_result.get("task_plan") or coordination_result.get("veronica_prompt")
            task_plan_struct = coordination_result.get("task_plan_struct")
            
            # Оптимальная архитектура: при task_plan_struct — без повторного вызова Victoria для парсинга
            if (task_plan or task_plan_struct) and organizational_structure:
                logger.info(f"🔄 [TASK DISTRIBUTION] Использую систему распределения (task_plan_struct={task_plan_struct is not None})")
                try:
                    result = await self._execute_with_task_distribution(
                        goal,
                        task_plan,
                        organizational_structure,
                        department,
                        task_plan_struct=task_plan_struct
                    )
                    if result:
                        return result
                    else:
                        logger.warning("⚠️ Task Distribution вернул None, используем fallback")
                except Exception as e:
                    logger.error(f"❌ Ошибка в Task Distribution: {e}, используем fallback", exc_info=True)
            
            # Fallback на старую систему
            if strategy == "simple":
                # Простая задача - один эксперт
                expert_info = coordination_result.get("expert_info")
                if not expert_info:
                    logger.warning(f"⚠️ Нет информации об эксперте для простой задачи")
                    return None
                
                expert_name = expert_info.get("name")
                # Латинское имя (Veronica) → кириллица в БД
                try:
                    from app.expert_aliases import resolve_expert_name_for_db
                    expert_name = resolve_expert_name_for_db(expert_name) if expert_name else expert_name
                except ImportError:
                    expert_name = {"Veronica": "Вероника", "Victoria": "Виктория"}.get(expert_name, expert_name)
                system_prompt = expert_info.get("system_prompt", "")
                
                logger.info(f"👤 Выполняю задачу через эксперта '{expert_name}' из отдела '{department}'")
                
                # Выполняем через эксперта используя ReActAgent с system_prompt эксперта
                try:
                    from app.react_agent import ReActAgent
                    
                    # Создаем ReActAgent с system_prompt эксперта
                    base_prompt = system_prompt or f"Вы {expert_name}, эксперт отдела {department}. Выполняйте задачи профессионально и эффективно."
                    expert_system_prompt = f"""{base_prompt}

Для задач на создание кода, файлов или ботов: обязательно используй инструменты create_file или write_file. Завершай задачу (finish) только после выполнения инструментов и всегда передавай в finish параметр output с кратким описанием сделанного и путями к созданным файлам.

{PROMPT_RUSSIAN_ONLY}"""
                    expert_agent = ReActAgent(
                        agent_name=expert_name,
                        system_prompt=expert_system_prompt,
                        model_name=self.model_name
                    )
                    
                    # ReActAgent.run принимает goal и context
                    result_dict = await expert_agent.run(goal=goal, context=None)
                    # ReActAgent.run возвращает Dict с полями: agent, goal, status, iterations, steps, final_reflection
                    if isinstance(result_dict, dict):
                        # Пытаемся извлечь результат из final_reflection или последнего шага
                        result = (result_dict.get("final_reflection") or "").strip()
                        if not result and result_dict.get("steps"):
                            last_step = result_dict["steps"][-1] if result_dict["steps"] else None
                            if last_step and isinstance(last_step, dict):
                                result = (last_step.get("observation") or last_step.get("reflection") or "").strip()
                        # Агрегация из шагов create_file/write_file (план п.3)
                        steps = result_dict.get("steps") or []
                        file_step_parts = []
                        for step in steps:
                            if not isinstance(step, dict):
                                continue
                            if step.get("action") in ("create_file", "write_file"):
                                obs = (step.get("observation") or "").strip()
                                if obs:
                                    file_step_parts.append(obs)
                        if file_step_parts:
                            aggregated = "\n\n".join(file_step_parts)
                            if len(aggregated) > 12 * 1024:
                                aggregated = aggregated[: 12 * 1024] + "\n\n[... вывод обрезан ...]"
                            if not result or result.startswith("Задача выполнена экспертом"):
                                result = aggregated if not result else (result + "\n\n" + aggregated)
                                if result.startswith("Задача выполнена экспертом"):
                                    result = aggregated
                        # Если все еще пусто — подставная строка (план п.4: не отдавать как успех)
                        if not result:
                            result = f"Задача выполнена экспертом '{expert_name}' (статус: {result_dict.get('status', 'unknown')})"
                        # Пустой успех: модель вызвала finish без результата (план п.4)
                        _is_placeholder = "Задача выполнена экспертом" in (result or "") and "(статус: finish)" in (result or "")
                        is_empty_success = result_dict.get("status") == "finish" and _is_placeholder
                        if is_empty_success:
                            # Автоматический retry: агент сам разбивает на подзадачи и повторяет (не пользователь)
                            retry_system_prompt = f"""{base_prompt}

КРИТИЧЕСКИ ВАЖНО — ПОВТОРНАЯ ПОПЫТКА: Предыдущий запуск завершился без результата.
Ты ОБЯЗАН: 1) разбить задачу на конкретные подзадачи (шаги), 2) выполнить каждую через create_file или write_file, 3) в конце вызвать finish с параметром output — краткое описание сделанного и пути к созданным файлам. Не завершай задачу (finish) без использования инструментов и без параметра output.

{PROMPT_RUSSIAN_ONLY}"""
                            logger.info("🔄 [DEPARTMENT_TASK] Пустой успех — автоматический retry с разбивкой на подзадачи (выполняет эксперт)")
                            try:
                                retry_agent = ReActAgent(
                                    agent_name=expert_name,
                                    system_prompt=retry_system_prompt,
                                    model_name=self.model_name
                                )
                                result_dict = await retry_agent.run(goal=goal, context=None)
                                if isinstance(result_dict, dict):
                                    result = (result_dict.get("final_reflection") or "").strip()
                                    if not result and result_dict.get("steps"):
                                        last_step = result_dict["steps"][-1] if result_dict["steps"] else None
                                        if last_step and isinstance(last_step, dict):
                                            result = (last_step.get("observation") or last_step.get("reflection") or "").strip()
                                    # Агрегация из шагов create_file/write_file
                                    steps = result_dict.get("steps") or []
                                    file_step_parts = []
                                    for step in steps:
                                        if isinstance(step, dict) and step.get("action") in ("create_file", "write_file"):
                                            obs = (step.get("observation") or "").strip()
                                            if obs:
                                                file_step_parts.append(obs)
                                    if file_step_parts:
                                        aggregated = "\n\n".join(file_step_parts)
                                        if len(aggregated) > 12 * 1024:
                                            aggregated = aggregated[: 12 * 1024] + "\n\n[... вывод обрезан ...]"
                                        if not result or "Задача выполнена экспертом" in (result or ""):
                                            result = aggregated if not result else (result + "\n\n" + aggregated)
                                    if not result:
                                        result = f"Задача выполнена экспертом '{expert_name}' (статус: {result_dict.get('status', 'unknown')})"
                                    _is_placeholder_retry = "Задача выполнена экспертом" in (result or "") and "(статус: finish)" in (result or "")
                                    if _is_placeholder_retry:
                                        result = (
                                            "Система автоматически повторила попытку (эксперт получил инструкцию разбить задачу на подзадачи и выполнить через инструменты), "
                                            "но результат снова не получен. Рекомендуется уточнить задачу или запросить один конкретный шаг."
                                        )
                            except Exception as retry_e:
                                logger.warning(f"⚠️ Retry при пустом успехе не удался: {retry_e}")
                                result = (
                                    "Система автоматически повторила попытку (разбивку на подзадачи выполнял эксперт), но повтор не удался. "
                                    "Рекомендуется уточнить задачу или запросить один конкретный шаг."
                                )
                            if not result or ("Задача выполнена экспертом" in (result or "") and "(статус: finish)" in (result or "")):
                                result = (
                                    "Система автоматически повторила попытку (эксперт получил инструкцию разбить задачу на подзадачи), "
                                    "но результат снова пуст. Рекомендуется уточнить задачу или запросить один конкретный шаг."
                                )
                    else:
                        result = str(result_dict) if result_dict else ""
                    
                    if result:
                        logger.info(f"✅ Задача выполнена экспертом '{expert_name}': {result[:100]}...")
                        return {
                            "result": result,
                            "method": "department_heads",
                            "department": department,
                            "strategy": strategy,
                            "expert": expert_name,
                            "metadata": coordination_result
                        }
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка выполнения через ReActAgent: {e}, пробуем через ai_core")
                    
                    # Fallback: используем ai_core
                    try:
                        from app.ai_core import run_smart_agent_async
                        
                        prompt = f"""{system_prompt or f"Вы {expert_name}, эксперт отдела {department}."}

{PROMPT_RUSSIAN_ONLY}

ЗАДАЧА: {goal}

Выполните задачу профессионально и предоставьте результат на русском языке."""
                        
                        result = await run_smart_agent_async(
                            prompt,
                            expert_name=expert_name,
                            category="execution"
                        )
                        
                        if result:
                            logger.info(f"✅ Задача выполнена экспертом '{expert_name}' через ai_core")
                            return {
                                "result": result if isinstance(result, str) else str(result),
                                "method": "department_heads",
                                "department": department,
                                "strategy": strategy,
                                "expert": expert_name,
                                "metadata": coordination_result
                            }
                    except Exception as e2:
                        logger.error(f"❌ Ошибка выполнения через ai_core: {e2}")
                        return None
            
            elif strategy == "department_head":
                # Сложная задача - Department Head координирует
                head = coordination_result.get("head")
                experts = coordination_result.get("experts", [])
                
                if not head or not experts:
                    logger.warning(f"⚠️ Нет Head или экспертов для сложной задачи")
                    return None
                
                logger.info(f"👔 Сложная задача координируется через '{head.get('name')}' с {len(experts)} экспертами")
                
                # Для сложных задач используем Victoria Enhanced с контекстом отдела
                # Пока возвращаем информацию о координации
                return {
                    "result": f"Задача координируется через Department Head '{head.get('name')}' отдела '{department}' с участием {len(experts)} экспертов. Выполнение в процессе...",
                    "method": "department_heads",
                    "department": department,
                    "strategy": strategy,
                    "head": head.get("name"),
                    "experts_count": len(experts),
                    "metadata": coordination_result
                }
            
            elif strategy == "swarm":
                # Критическая задача - Swarm экспертов
                swarm_experts = coordination_result.get("swarm_experts", [])
                
                if not swarm_experts:
                    logger.warning(f"⚠️ Нет экспертов для Swarm")
                    return None
                
                logger.info(f"🐝 Критическая задача выполняется через Swarm из {len(swarm_experts)} экспертов")
                
                # Для критических задач используем Swarm Intelligence
                # Пока возвращаем информацию о координации
                return {
                    "result": f"Критическая задача выполняется через Swarm Intelligence отдела '{department}' с участием {len(swarm_experts)} экспертов: {', '.join([e.get('name', 'N/A') for e in swarm_experts[:3]])}...",
                    "method": "department_heads",
                    "department": department,
                    "strategy": strategy,
                    "swarm_size": len(swarm_experts),
                    "metadata": coordination_result
                }
            
            else:
                logger.warning(f"⚠️ Неизвестная стратегия: {strategy}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения задачи через Department Heads: {e}", exc_info=True)
            return None
    
    async def _execute_with_task_distribution(
        self,
        goal: str,
        task_plan: str,
        organizational_structure: Dict,
        department: str,
        task_plan_struct: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Выполнить задачу через систему распределения:
        План от Victoria (task_plan_struct — без повторного парсинга) → Task Distribution назначает →
        Сотрудники выполняют → Управляющий проверяет → Victoria синтезирует
        """
        logger.info(f"🔄 [TASK DISTRIBUTION] Начинаю выполнение (task_plan_struct={task_plan_struct is not None})...")
        
        try:
            from app.task_distribution_system import get_task_distribution_system
            # Единая локальная БД (в Docker задаётся DATABASE_URL через compose)
            db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
            task_dist = get_task_distribution_system(db_url)
            
            # Этап 1: Распределение — из структуры (оптимально) или из текста (fallback)
            logger.info("📋 [TASK DISTRIBUTION] Распределяю задачи по структуре организации...")
            if task_plan_struct:
                assignments = await task_dist.distribute_tasks_from_plan(
                    task_plan_struct,
                    organizational_structure
                )
            else:
                assignments = await task_dist.distribute_tasks_from_veronica_prompt(
                    task_plan or "",
                    organizational_structure
                )
            
            if not assignments:
                logger.warning("⚠️ Не удалось распределить задачи")
                return None
            
            logger.info(f"✅ Распределено {len(assignments)} задач")
            
            # Этап 2: Параллельное выполнение задач сотрудниками
            logger.info("👥 [EMPLOYEES] Сотрудники выполняют задачи параллельно...")
            execution_tasks = [
                task_dist.execute_task_assignment(assignment)
                for assignment in assignments
            ]
            completed_assignments = await asyncio.gather(*execution_tasks, return_exceptions=True)
            
            # Фильтруем ошибки
            valid_assignments = []
            for i, result in enumerate(completed_assignments):
                if isinstance(result, Exception):
                    logger.error(f"❌ Ошибка выполнения задачи {i}: {result}")
                else:
                    valid_assignments.append(result)
            
            logger.info(f"✅ Выполнено {len(valid_assignments)} задач из {len(assignments)}")
            
            # Этап 3: Управляющие проверяют задачи с улучшенной валидацией
            logger.info("👔 [MANAGERS] Управляющие проверяют выполненные задачи...")
            review_tasks = [
                task_dist.manager_review_task(assignment, goal)  # Передаем исходную задачу для валидации
                for assignment in valid_assignments
            ]
            reviewed_assignments = await asyncio.gather(*review_tasks, return_exceptions=True)
            
            # Фильтруем ошибки
            approved_assignments = [
                a for a in reviewed_assignments
                if not isinstance(a, Exception) and a.status.value == "reviewed"
            ]
            
            logger.info(f"✅ Проверено и утверждено {len(approved_assignments)} задач")
            
            # Этап 4: Department Head собирает задачи отдела (или fallback — собрать из всех выполненных)
            logger.info(f"👔 [DEPARTMENT HEAD] Собираю задачи отдела '{department}'...")
            dept_collection = await task_dist.department_head_collect_tasks(
                approved_assignments,
                department
            )
            if not dept_collection and valid_assignments:
                # Fallback: менеджер отклонил все или сбор вернул None — Victoria всё равно собирает из выполненных
                from app.task_distribution_system import TaskCollection
                agg = "\n\n".join([(a.result or "(пусто)") for a in valid_assignments if getattr(a, "result", None) is not None])
                if not agg.strip():
                    agg = "\n\n".join([f"Задача {getattr(a, 'task_id', i)}: результат пуст" for i, a in enumerate(valid_assignments, 1)])
                dept_collection = TaskCollection(
                    department=department,
                    aggregated_result=agg or "Результаты сотрудников не получены.",
                    assignments=valid_assignments,
                    quality_score=0.5
                )
                logger.info("🔄 [TASK DISTRIBUTION] Сбор из всех выполненных (approved пуст или сбор не удался)")
            if not dept_collection:
                logger.warning("⚠️ Не удалось собрать задачи отдела")
                return None
            
            # Этап 5: Veronica собирает результаты (если есть несколько отделов)
            # Пока у нас один отдел, пропускаем этот этап
            veronica_collection = dept_collection
            
            # Этап 6: Victoria синтезирует финальный ответ
            logger.info("🧠 [VICTORIA] Синтезирую финальный ответ...")
            final_result = await self._synthesize_collected_results(
                veronica_collection,
                goal
            )
            
            # Получаем метрики если доступны
            metrics_summary = None
            if hasattr(task_dist, 'metrics_collector') and task_dist.metrics_collector:
                metrics_summary = task_dist.metrics_collector.get_metrics_summary()
                logger.info(f"📊 Метрики выполнения: {metrics_summary}")
            
            # Пустой успех: не отдавать подставную строку (план п.4)
            _placeholder = "Задача выполнена экспертом" in (final_result or "") and "(статус: finish)" in (final_result or "")
            if final_result and _placeholder:
                logger.info("🔄 [TASK DISTRIBUTION] Заменяю пустой успех на честное сообщение")
                final_result = (
                    "Эксперт завершил задачу без вывода (модель вызвала finish без результата). "
                    "Система может повторить попытку с разбивкой на подзадачи (выполняет эксперт). Рекомендуется уточнить задачу."
                )
            return {
                "result": final_result,
                "method": "task_distribution",
                "department": department,
                "assignments_count": len(assignments),
                "completed_count": len(valid_assignments),
                "approved_count": len(approved_assignments),
                "metrics": metrics_summary,
                "metadata": {
                    "organizational_structure_used": True,
                    "task_distribution_used": True,
                    "parallel_execution": True,
                    "manager_review": True,
                    "department_head_collection": True,
                    "retry_enabled": hasattr(task_dist, 'retry_manager') and task_dist.retry_manager is not None,
                    "load_balancing_enabled": hasattr(task_dist, 'load_balancer') and task_dist.load_balancer is not None,
                    "validation_enabled": hasattr(task_dist, 'validator') and task_dist.validator is not None,
                    "escalation_enabled": hasattr(task_dist, 'escalator') and task_dist.escalator is not None
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения через Task Distribution: {e}", exc_info=True)
            return None
    
    async def _synthesize_collected_results(
        self,
        collection,
        original_goal: str
    ) -> str:
        """
        Victoria синтезирует финальный ответ из собранных результатов
        
        Args:
            collection: Собранная коллекция результатов
            original_goal: Исходная задача
            
        Returns:
            Синтезированный финальный ответ
        """
        logger.info(f"🔗 [VICTORIA SYNTHESIS] Синтезирую результаты от {len(collection.assignments)} сотрудников...")
        if not (collection.aggregated_result or "").strip():
            out = "Victoria собрала ответы сотрудников; результаты пусты или не получены. Рекомендуется уточнить задачу."
            logger.warning("⚠️ [VICTORIA SYNTHESIS] Нет агрегированного результата — возвращаю сообщение пользователю")
            return out
        
        synthesis_prompt = f"""Ты Victoria, главный оркестратор корпорации.

ИСХОДНАЯ ЗАДАЧА: {original_goal}

СОБРАННЫЕ РЕЗУЛЬТАТЫ ОТ СОТРУДНИКОВ:
{collection.aggregated_result}

ТВОЯ ЗАДАЧА:
Синтезируй все результаты в единый финальный ответ. 

КРИТИЧЕСКИ ВАЖНО:
1. Если сотрудники создали HTML код/файлы - ОБЪЕДИНИ их в единый готовый результат
2. НЕ создавай новый план - используй ГОТОВЫЕ результаты от сотрудников
3. Если это веб-сайт - объедини HTML от Frontend и SEO контент от Marketing в ОДИН готовый HTML файл
4. Результат должен быть ГОТОВ К ИСПОЛЬЗОВАНИЮ (полный HTML код, а не план)
5. Если результаты содержат код - верни ГОТОВЫЙ код, а не описание того, что нужно сделать
6. На русском языке

ФИНАЛЬНЫЙ ОТВЕТ (готовый код/HTML/файл):"""

        try:
            if EXTENDED_THINKING_AVAILABLE and self.extended_thinking:
                try:
                    # Пробуем с max_iterations
                    synthesis = await self.extended_thinking.think(
                        prompt=synthesis_prompt,
                        max_iterations=2
                    )
                except TypeError:
                    # Если не принимает max_iterations, вызываем без него
                    synthesis = await self.extended_thinking.think(
                        prompt=synthesis_prompt
                    )
            else:
                from app.ai_core import run_smart_agent_async
                synthesis = await run_smart_agent_async(
                    synthesis_prompt,
                    expert_name="Виктория",
                    category="synthesis"
                )
            
            # Извлекаем строку из ExtendedThinkingResult если нужно
            if hasattr(synthesis, 'final_answer'):
                synthesis_text = synthesis.final_answer
            elif isinstance(synthesis, str):
                synthesis_text = synthesis
            else:
                synthesis_text = str(synthesis)
            
            logger.info(f"✅ Результаты синтезированы ({len(synthesis_text)} символов)")
            if not (synthesis_text or "").strip():
                synthesis_text = collection.aggregated_result or "Victoria собрала ответы; результаты сотрудников пусты. Рекомендуется уточнить задачу."
            # Пустой успех из Task Distribution: не отдавать подставную строку (план п.4)
            if synthesis_text and "Задача выполнена экспертом" in synthesis_text and "(статус: finish)" in synthesis_text:
                synthesis_text = (
                    "Эксперт завершил задачу без вывода (модель вызвала finish без результата). "
                    "Система может повторить попытку с разбивкой на подзадачи (выполняет эксперт). Рекомендуется уточнить задачу."
                )
            return synthesis_text
            
        except Exception as e:
            logger.error(f"❌ Ошибка синтеза: {e}")
            # Fallback: всегда возвращаем ответ пользователю (собрали то, что есть)
            fallback = (collection.aggregated_result or "").strip() or "Victoria собрала ответы сотрудников; результаты пусты или синтез не удался. Рекомендуется уточнить задачу."
            if fallback and "Задача выполнена экспертом" in fallback and "(статус: finish)" in fallback:
                fallback = (
                    "Эксперт завершил задачу без вывода (модель вызвала finish без результата). "
                    "Система может повторить попытку с разбивкой на подзадачи (выполняет эксперт). Рекомендуется уточнить задачу."
                )
            return fallback
    
    def _is_simple_veronica_request(self, goal: str) -> bool:
        """
        Запрос — одношаговое действие (показать/вывести/прочитать).
        Только такие при PREFER_EXPERTS_FIRST идут в Veronica; остальные — Victoria/эксперты.
        Согласовано с task_detector.VERONICA_SIMPLE_KEYWORDS и docs/VERONICA_REAL_ROLE.md.
        """
        if not goal or len(goal.strip()) > 120:
            return False
        goal_lower = goal.lower().strip()
        simple = [
            "покажи файлы", "выведи список файлов", "список файлов", "покажи список",
            "прочитай файл", "покажи файл", "содержимое файла", "выведи содержимое",
        ]
        if any(kw in goal_lower for kw in simple):
            return True
        if len(goal_lower) <= 50 and ("покажи" in goal_lower or "выведи" in goal_lower or "список" in goal_lower):
            return True
        return False

    async def _should_delegate_task(self, goal: str, category: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Определить, нужно ли делегировать задачу другому агенту.
        При PREFER_EXPERTS_FIRST=true в Veronica идут только простые одношаговые запросы;
        «сделай», «напиши код», «создай API» остаются в Victoria/экспертах (docs/VERONICA_REAL_ROLE.md).
        
        Returns:
            (should_delegate, delegation_info)
        """
        if not self.task_delegator:
            logger.debug("🔍 TaskDelegator не доступен, делегирование невозможно")
            return False, {}
        
        try:
            prefer_experts_first = os.getenv("PREFER_EXPERTS_FIRST", "true").lower() in ("true", "1", "yes")
            if prefer_experts_first and not self._is_simple_veronica_request(goal):
                logger.debug("🔍 PREFER_EXPERTS_FIRST: задача не одношаговая → остаётся Victoria/эксперты")
                return False, {}

            # Анализируем задачу
            requirements = self.task_delegator.analyze_task(goal)
            logger.debug(f"🔍 Анализ задачи: requirements={requirements}")
            
            # Определяем, нужно ли делегировать
            # Victoria выполняет сама: planning, coordination, reasoning, code_analysis
            # Veronica — только простые одношаговые (уже отфильтровано выше при PREFER_EXPERTS_FIRST)
            
            required_capabilities = requirements.get("required_capabilities", [])
            logger.debug(f"🔍 Требуемые способности: {required_capabilities}")
            
            # Если задача требует execution, file_operations и т.д. (enum AgentCapability)
            from app.task_delegation import AgentCapability
            veronica_cap_set = {
                AgentCapability.EXECUTION,
                AgentCapability.FILE_OPERATIONS,
                AgentCapability.RESEARCH,
                AgentCapability.SYSTEM_ADMIN,
            }
            matching_caps = [c for c in required_capabilities if c in veronica_cap_set]
            if matching_caps:
                logger.info(f"📋 Найдены способности Вероники: {matching_caps}")
                return True, {
                    "agent": "Вероника",
                    "reason": "Требуются способности Вероники",
                    "capabilities": matching_caps
                }
            
            # Простые ключевые слова для Вероники (одно действие)
            goal_lower = goal.lower()
            veronica_keywords = [
                "создай файл", "create file", "прочитай файл", "read file",
                "выполни команду", "execute command", "запусти", "run",
                "найди", "find", "поиск", "search", "исследова", "research",
                "напишут", "напиши", "одностраничный сайт", "сайт по", "веб-сайт",
                "создай сайт", "создай страницу", "html страничку", "html страницу"
            ]
            found_keywords = [kw for kw in veronica_keywords if kw in goal_lower]
            if found_keywords:
                logger.info(f"📋 Найдены ключевые слова для Вероники: {found_keywords}")
                return True, {
                    "agent": "Вероника",
                    "reason": "Задача требует выполнения/файловых операций",
                    "keywords": found_keywords
                }
            
            # Victoria выполняет сама: planning, coordination, reasoning
            logger.debug("🔍 Задача остается для Victoria (planning/coordination/reasoning)")
            return False, {}
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки делегирования: {e}", exc_info=True)
            return False, {}
    
    def _select_optimal_method(self, category: str, goal: str) -> str:
        """Выбрать оптимальный метод. ReAct по умолчанию (доступ к файлам/инструментам), если доступен.
        Команда экспертов (много агентов) — только для complex (swarm/consensus); остальное — один исполнитель (модель или ReAct). См. docs/VICTORIA_TASK_CHAIN_FULL.md."""
        method_map = {
            "informational": "simple",  # «что умеешь», «кто ты» — без ReAct
            "status_query": "simple",   # статус/приоритеты — быстрый ответ, без долгих методов
            "fast": "react" if self.react_agent else "simple",
            "reasoning": "extended_thinking" if self.extended_thinking else "recap",
            "planning": "tree_of_thoughts" if self.tot else "hierarchical",
            "complex": "swarm" if self.swarm else "consensus",
            "execution": "react" if self.react_agent else "simple",
            "coding": "react" if self.react_agent else "simple",
            "general": "react" if self.react_agent else "simple",
        }
        default_method = "react" if self.react_agent else "simple"
        method = method_map.get(category, default_method)
        
        # Проверяем доступность метода
        if method == "extended_thinking" and not self.extended_thinking:
            method = "simple"
        elif method == "swarm" and not self.swarm:
            method = "consensus" if self.consensus else "simple"
        elif method == "react" and not self.react_agent:
            method = "simple"
        elif method == "tree_of_thoughts" and not self.tot:
            method = "hierarchical" if self.hierarchical_orch else "simple"
        elif method == "recap" and not self.recap:
            method = "extended_thinking" if self.extended_thinking else "simple"
        
        return method
    
    async def _execute_method(
        self,
        method: str,
        goal: str,
        category: str,
        context: Optional[Dict]
    ) -> Dict:
        """Выполнить задачу через выбранный метод"""
        start_time = datetime.now(timezone.utc)
        
        # Куратор + аудит 2026-02-08: единый источник configs.victoria_common.get_capabilities_text()
        if category == "informational":
            try:
                _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
                import sys
                if _root not in sys.path:
                    sys.path.insert(0, _root)
                from configs.victoria_common import get_capabilities_text
                capabilities = get_capabilities_text()
            except Exception:
                capabilities = (
                    "Я Виктория, Team Lead Atra Core. Умею:\n"
                    "• Отвечать на вопросы и вести чат (в т.ч. с экспертами и RAG по базе знаний)\n"
                    "• Составлять планы и выполнять задачи: код, файлы, команды в терминале\n"
                    "• Показывать список файлов, читать и анализировать проект\n"
                    "• Делегировать простые запросы в Veronica, сложные — оркестрировать с командой\n"
                    "Режимы: быстрый ответ на простые вопросы или полный цикл (ReAct) для сложных задач."
                )
            return {"result": capabilities, "method": "simple", "metadata": {"source": "curator_informational"}}
        
        try:
            if method == "react" and self.react_agent:
                # Выбираем оптимальную модель для coding задач
                coding_model = await self._get_model_for_category_async("coding")
                if coding_model and coding_model != self.react_agent.model_name:
                    self.react_agent.model_name = coding_model
                    logger.info(f"🎯 Используем модель {coding_model} для ReAct")
                
                try:
                    result = await self.react_agent.run(goal, context)
                    # Правильная обработка результата ReAct
                    if isinstance(result, dict):
                        result_text = result.get("final_reflection") or result.get("response", "")
                        if not result_text and result.get("steps"):
                            # При action=finish ответ в observation; иначе reflection/thought
                            last_step = result.get("steps", [])[-1] if result.get("steps") else None
                            if last_step:
                                result_text = (
                                    last_step.get("observation")
                                    or last_step.get("reflection")
                                    or last_step.get("thought", "")
                                )
                    else:
                        result_text = str(result)
                    
                    if result_text and result_text.strip():
                        if _is_gibberish_output(result_text):
                            logger.warning("⚠️ ReAct вернул похожий на мусор вывод, fallback на simple")
                            return await self._execute_method("simple", goal, category, context)
                        return {
                            "result": result_text.strip(),
                            "method": "react",
                            "steps": len(result.get("steps", [])) if isinstance(result, dict) else 0,
                            "metadata": {
                                **(result if isinstance(result, dict) else {}),
                                "model_used": coding_model or self.model_name,
                                "category": category
                            }
                        }
                    # ReAct вернул пустой результат — fallback на simple (мировая практика: не отдавать заглушку)
                    logger.warning("⚠️ ReAct вернул пустой результат, fallback на simple")
                    return await self._execute_method("simple", goal, category, context)
                except Exception as e:
                    logger.error(f"❌ Ошибка ReAct: {e}, используем simple метод")
                    return await self._execute_method("simple", goal, category, context)
            
            elif method == "extended_thinking" and self.extended_thinking:
                try:
                    # Выбираем оптимальную модель для reasoning задачи
                    reasoning_model = await self._get_model_for_category_async("reasoning")
                    if reasoning_model and reasoning_model != self.extended_thinking.model_name:
                        # Обновляем модель в Extended Thinking
                        self.extended_thinking.model_name = reasoning_model
                        logger.info(f"🎯 Используем модель {reasoning_model} для extended thinking")

                    # Подключаем контекст: best practices или база знаний для статуса/приоритетов
                    goal_lower = (goal or "").lower()
                    if any(kw in goal_lower for kw in ("мировые практики", "best practices", "world practices")):
                        goal = f"{WORLD_PRACTICES_CONTEXT}\n\nЗапрос: {goal}"
                        logger.info("🌍 Добавлен контекст мировых практик в extended thinking")

                    ctx_str = (context.get("kb_context") if isinstance(context, dict) and context else None) or (
                        context if isinstance(context, str) else None
                    )
                    result = await self.extended_thinking.think(goal, ctx_str, use_iterative=True, category=category)
                    # Проверяем что получили непустой ответ (final_answer может быть str или dict)
                    _fa = result.final_answer
                    _fa_str = (_fa if isinstance(_fa, str) else str(_fa)).strip() if _fa else ""
                    if _fa_str:
                        if _is_gibberish_output(_fa_str):
                            logger.warning("⚠️ Extended thinking вернул мусорный вывод, fallback на simple")
                            return await self._execute_method("simple", goal, category, context)
                        return {
                            "result": _fa_str,
                            "method": "extended_thinking",
                            "confidence": result.confidence,
                            "thinking_steps": len(result.thinking_steps),
                            "metadata": {
                                "total_tokens": result.total_tokens_used,
                                "thinking_time": result.thinking_time_seconds,
                                "model_used": reasoning_model or self.model_name
                            }
                        }
                    else:
                        # Пустой ответ от extended thinking, используем простой режим
                        logger.warning("Extended thinking вернул пустой ответ, используем простой режим")
                        method = "simple"
                except Exception as e:
                    logger.error(f"Ошибка extended thinking: {e}, используем простой режим")
                    method = "simple"
            
            elif method == "swarm" and self.swarm:
                # Выбираем модель для complex задач
                complex_model = await self._get_model_for_category_async("complex")
                if complex_model and hasattr(self.swarm, 'model_name'):
                    self.swarm.model_name = complex_model
                    logger.info(f"🎯 Используем модель {complex_model} для swarm")
                
                try:
                    # Агенты из БД — состав растёт динамически (max swarm_size)
                    from app.expert_services import get_all_expert_names
                    swarm_agents = get_all_expert_names(max_count=self.swarm.swarm_size if self.swarm else 16)
                    result = await self.swarm.solve(goal, agent_names=swarm_agents if swarm_agents else None)
                    # Правильная обработка SwarmResult
                    if hasattr(result, 'global_best'):
                        result_text = str(result.global_best)
                    elif isinstance(result, dict):
                        result_text = result.get('result', str(result))
                    else:
                        result_text = str(result)
                    
                    return {
                        "result": result_text,
                        "method": "swarm",
                        "global_best_score": getattr(result, 'global_best_score', None),
                        "iterations": getattr(result, 'iterations', None),
                        "convergence_rate": getattr(result, 'convergence_rate', None),
                        "metadata": {
                            "model_used": complex_model or self.model_name,
                            "category": category
                        }
                    }
                except Exception as e:
                    logger.error(f"❌ Ошибка swarm: {e}, используем simple метод")
                    method = "simple"  # Fallback на simple
            
            elif method == "consensus" and self.consensus:
                # Выбираем модель для complex задач
                complex_model = await self._get_model_for_category_async("complex")
                if complex_model and hasattr(self.consensus, 'model_name'):
                    self.consensus.model_name = complex_model
                    logger.info(f"🎯 Используем модель {complex_model} для consensus")
                
                # Агенты из БД — состав растёт динамически (до 10 для consensus)
                from app.expert_services import get_all_expert_names
                consensus_agents = get_all_expert_names(max_count=10)
                if not consensus_agents:
                    consensus_agents = ["Виктория", "Вероника", "Игорь", "Сергей", "Дмитрий"]
                result = await self.consensus.reach_consensus(consensus_agents, goal)
                return {
                    "result": result.final_answer,
                    "method": "consensus",
                    "consensus_score": result.consensus_score,
                    "model_used": complex_model or self.model_name,
                    "agreement_level": result.agreement_level,
                    "iterations": result.iterations,
                    "metadata": result
                }
            
            elif method == "tree_of_thoughts" and self.tot:
                result = await self.tot.solve(goal)
                return {
                    "result": result.final_answer,
                    "method": "tree_of_thoughts",
                    "confidence": result.confidence,
                    "total_thoughts": result.total_thoughts,
                    "exploration_depth": result.exploration_depth,
                    "metadata": result
                }
            
            elif method == "recap" and self.recap:
                result = await self.recap.solve(goal, context)
                return {
                    "result": result["final_result"],
                    "method": "recap",
                    "high_level_steps": len(result["plan"].high_level_steps),
                    "metadata": result
                }
            
            elif method == "hierarchical" and self.hierarchical_orch:
                # Нужны агенты для hierarchical
                agents = {
                    "Виктория": {"role": "team_lead"},
                    "Вероника": {"role": "developer"},
                    "Игорь": {"role": "backend"},
                    "Сергей": {"role": "devops"}
                }
                state = await self.hierarchical_orch.orchestrate(goal, agents)
                return {
                    "result": "Hierarchical orchestration completed",
                    "method": "hierarchical",
                    "goals_count": len(state.goals),
                    "dependencies": len(state.dependencies),
                    "metadata": state.visualization_data
                }
            
            elif method == "simple":
                # 🚀 БЫСТРЫЙ МЕТОД для простых задач - прямая генерация через быструю модель
                needs_db_query = False
                db_info = ""
                # Выбираем модель в зависимости от категории
                if category == "fast":
                    selected_model = await self._get_model_for_category_async("fast")
                elif category == "coding":
                    selected_model = await self._get_model_for_category_async("coding")
                else:
                    selected_model = await self._get_model_for_category_async("general")
                
                if not selected_model:
                    selected_model = self.model_name
                
                logger.info(f"⚡ Быстрый метод ({category}): используем модель {selected_model}")
                
                try:
                    import httpx
                    
                    # 🍎 ПРИОРИТЕТ 1: Попробовать MLX напрямую (без API Server)
                    try:
                        from mlx_router import get_mlx_router, is_mlx_available
                        if is_mlx_available():
                            mlx_router = get_mlx_router()
                            logger.info("🍎 [MLX] Пробуем использовать MLX напрямую для простых ответов")
                            try:
                                mlx_response = await mlx_router.generate_response(
                                    prompt=simple_prompt,
                                    max_tokens=max_tokens,
                                    temperature=temperature
                                )
                                if mlx_response and len(mlx_response) > 10:
                                    logger.info("✅ [MLX] Использован MLX напрямую")
                                    # Обрезка для простых задач
                                    if category == "fast" and len(mlx_response) > 200:
                                        sentences = mlx_response.split('.')
                                        if len(sentences) > 0:
                                            mlx_response = sentences[0] + '.' if not sentences[0].endswith('.') else sentences[0]
                                    
                                    return {
                                        "result": mlx_response[:200] if category == "fast" else mlx_response,
                                        "method": "simple",
                                        "metadata": {
                                            "model_used": selected_model,
                                            "source": "MLX (direct)",
                                            "fast_mode": (category == "fast"),
                                            "response_time": "optimized",
                                            "category": category
                                        }
                                    }
                            except Exception as mlx_error:
                                logger.debug(f"⚠️ [MLX] Ошибка MLX: {mlx_error}, пробуем MLX API Server")
                    except ImportError:
                        logger.debug("⚠️ MLX Router недоступен, пробуем MLX API Server")
                    except Exception as e:
                        logger.debug(f"⚠️ [MLX] Ошибка проверки MLX: {e}, пробуем MLX API Server")
                    
                    # MLX API Server (11435) и Ollama (11434) — сканируем доступные модели (кэш TTL)
                    is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
                    if is_docker:
                        mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
                        ollama_url = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_API_URL") or "http://host.docker.internal:11434"
                    else:
                        mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")
                        ollama_url = os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_API_URL") or "http://localhost:11434"
                    try:
                        from app.available_models_scanner import get_available_models, pick_ollama_model_for_category
                        mlx_models, ollama_models = await get_available_models(mlx_url, ollama_url)
                        # Повтор скана при пустом списке (из Docker первый запрос к host.docker.internal может не уложиться в таймаут)
                        if not ollama_models and not mlx_models:
                            mlx_models, ollama_models = await get_available_models(mlx_url, ollama_url, force_refresh=True)
                    except ImportError:
                        mlx_models, ollama_models = [], []
                    urls_to_try = []
                    if mlx_models:
                        urls_to_try.append(mlx_url)
                    if ollama_models:
                        urls_to_try.append(ollama_url)
                    if not urls_to_try:
                        urls_to_try = [ollama_url, mlx_url] if is_docker else [mlx_url, ollama_url]
                    # В Docker: Ollama первым — из контейнера MLX часто таймаут/вылет, Ollama стабильнее (host.docker.internal:11434)
                    if is_docker and ollama_url in urls_to_try and mlx_url in urls_to_try:
                        urls_to_try = [ollama_url, mlx_url]
                    logger.info(f"🔍 Доступно: MLX={len(mlx_models)}, Ollama={len(ollama_models)}. Пробуем: {urls_to_try}")
                    
                    # Персона: модель должна отвечать именно как Виктория, а не как безличный ассистент
                    role_instruction = "Отвечай от первого лица как Виктория (я, мы). Не как безличный справочник или энциклопедия — как Team Lead корпорации."
                    # Промпт зависит от категории
                    if category == "coding":
                        # Для задач с кодом - более детальный промпт; план §2: похожие успешные решения
                        similar_tasks_coding = await self._get_similar_tasks_context(goal, max_chars=400)
                        similar_block = f"\n{similar_tasks_coding}\n\n" if similar_tasks_coding else ""
                        simple_prompt = f"""Ты Виктория, Team Lead корпорации ATRA, эксперт по программированию. {role_instruction}

{PROMPT_RUSSIAN_ONLY}
{similar_block}Задача: {goal}

Создай рабочий код. Отвечай на русском языке, но код пиши правильно.
Если нужно создать файл, укажи полный путь и содержимое файла.

Ответ (на русском языке):"""
                    else:
                        # Простой промпт для быстрых ответов
                        # Для очень простых запросов типа "привет" - максимально короткий ответ
                        if len(goal.split()) <= 3 and any(word in goal.lower() for word in ["привет", "здравствуй", "hi", "hello"]):
                            simple_prompt = f"""Ты Виктория, Team Lead корпорации ATRA. {role_instruction}

{PROMPT_RUSSIAN_ONLY}

Пример правильного ответа на "привет":
"Привет! Я Виктория, Team Lead корпорации ATRA. Чем могу помочь?"

Запрос пользователя: {goal}

Твой ответ (только на русском, коротко, 1 предложение):"""
                        else:
                            # ========================================================
                            # УНИВЕРСАЛЬНЫЙ ИНСТРУМЕНТ: Text-to-SQL для любых вопросов
                            # Вместо жёсткой классификации — модель сама формирует SQL
                            # ========================================================
                            needs_db_query = False
                            db_info = ""
                            
                            try:
                                from app.corporation_data_tool import is_data_question, query_corporation_data, _extract_latest_user_message
                                # is_data_question(goal) — с историей: "сотрудник" может быть в предыдущих репликах
                                # goal_for_data — без истории: для Text-to-SQL только последний вопрос (не передаём 120 из истории)
                                goal_for_data = _extract_latest_user_message(goal)
                                if is_data_question(goal) or is_data_question(goal_for_data):
                                    logger.info(f"📊 [CORP DATA] Вопрос о данных: '{goal_for_data[:60]}...'")
                                    corp_result = await query_corporation_data(goal_for_data)
                                    if corp_result.get("success") and corp_result.get("answer"):
                                        logger.info(f"✅ [CORP DATA] Ответ через Text-to-SQL, SQL: {corp_result.get('sql', '')[:80]}...")
                                        # Возвращаем результат напрямую — не нужен LLM
                                        return {
                                            "result": corp_result["answer"],
                                            "method": "simple",
                                            "metadata": {
                                                "source": "corporation_data_tool",
                                                "sql": corp_result.get("sql"),
                                                "count": corp_result.get("count"),
                                                "fast_mode": True
                                            }
                                        }
                                    else:
                                        logger.debug(f"⚠️ [CORP DATA] Не удалось: {corp_result}")
                            except ImportError:
                                logger.debug("corporation_data_tool не импортирован")
                            except Exception as e:
                                logger.debug(f"corporation_data_tool ошибка: {e}")
                            
                            # Fallback: обычный промпт для LLM (не data-вопрос или Text-to-SQL не сработал)
                            # Подтягиваем эталон из RAG (curator_standards) для «статус проекта» / «что умеешь» — иначе 0/3 по эталону (Backend/QA)
                            kb_context = await self._get_curator_rag_context(goal)
                            
                            # Сингулярность 10.0: Подтягиваем знания AI Research (Anthropic, Google, OpenAI и др.)
                            ai_research_context = await self._get_ai_research_context(goal)
                            if ai_research_context:
                                logger.info("🧠 [AI RESEARCH] Добавлен контекст исследований гигантов")
                                if kb_context:
                                    kb_context += "\n" + ai_research_context
                                else:
                                    kb_context = ai_research_context

                            # [SEMANTIC HISTORY SEARCH] Поиск по смыслу в прошлых сессиях (Claude Opus 4.6 Pattern)
                            # Срабатывает на фразы: "помнишь", "как вчера", "обсуждали", "прошлый раз"
                            history_context = await self._get_semantic_history_context(goal, context.get("session_id") if context else None)
                            if history_context:
                                if kb_context:
                                    kb_context += "\n" + history_context
                                else:
                                    kb_context = history_context

                            # [SUMMARY READER] Если пользователь просит раскрыть логику ("как ты пришла к этому?")
                            goal_lower_for_rag = (goal or "").lower()
                            if any(kw in goal_lower_for_rag for kw in ["как ты пришла", "почему такое решение", "раскрой логику", "покажи мысли"]):
                                session_id = context.get("session_id") if context else None
                                if session_id:
                                    hidden_thoughts = VictoriaEnhanced.get_hidden_thoughts(session_id)
                                    if hidden_thoughts:
                                        thoughts_text = "\n".join([f"Шаг {t['step']}: {t['thought']}" for t in hidden_thoughts])
                                        kb_context = (kb_context or "") + f"\n\n### ТВОИ ПРЕДЫДУЩИЕ СКРЫТЫЕ МЫСЛИ (для ответа на вопрос о логике):\n{thoughts_text}"
                                        logger.info(f"🔓 [SUMMARY READER] Скрытые мысли подставлены в контекст для сессии {session_id}")

                            is_status_project_query = "статус" in goal_lower_for_rag and ("проект" in goal_lower_for_rag or "дашборд" in goal_lower_for_rag)
                            if not kb_context and is_status_project_query:
                                logger.warning(
                                    "RAG curator_standards пуст для запроса «статус проекта» — используем эталон из кода (проверьте узел status_project в БД)"
                                )
                                kb_context = (
                                    "Статус проекта смотрите в дашборде (Corporation Dashboard, порт 8501) и в списке задач Knowledge OS. "
                                    "Опираюсь на факты из MASTER_REFERENCE и задач, не придумываю сроки."
                                )
                            similar_tasks = await self._get_similar_tasks_context(goal)
                            kb_block = ""
                            if kb_context:
                                kb_block = f"""По базе знаний (эталон): используй ТОЛЬКО этот контекст для ответа. Не придумывай сроки и детали.
{kb_context}

"""
                            if similar_tasks:
                                kb_block += f"""{similar_tasks}

"""
                            if context and context.get("project_context"):
                                project_tasks = await self._get_project_tasks_context(context["project_context"])
                                if project_tasks:
                                    kb_block += f"""{project_tasks}

"""
                            try:
                                from configs.victoria_common import build_simple_prompt, WORLD_PRACTICES_LINE as _wp_common
                            except ImportError:
                                _wp_common = "Учитывай лучшие практики: один источник истины (документация), проверяемый результат, актуальная библия (MASTER_REFERENCE)."
                                def build_simple_prompt(role_instruction, kb_block, goal, *, world_practices_line=None):
                                    wp = world_practices_line or _wp_common
                                    return (
                                        f"Ты Виктория, Team Lead корпорации ATRA. {role_instruction}\n\nКРИТИЧЕСКИ ВАЖНО:\n{PROMPT_RUSSIAN_AND_BREVITY_LINES}\n"
                                        f"5. Если выше дан контекст из базы знаний — ответь ТОЛЬКО на его основе.\n6. {wp}\n\n{kb_block}Запрос: {goal}\n\nОтвет (кратко, 3-5 предложений, на русском):"
                                    )
                            # План «как я» п.4: для статус/что умеешь — краткий блок «в духе команды» (без вызова Swarm)
                            if category in ("status_query", "general"):
                                kb_block += """Ответ в духе команды: дашборд, MASTER_REFERENCE, эксперты Backend/QA/SRE/ML.

"""
                            if context and context.get("task_memory"):
                                task_mem = (context.get("task_memory") or "").strip()
                                if task_mem:
                                    kb_block += f"""Ранее по этой задаче (сессия):
{task_mem}

"""
                            if context and context.get("long_term_memory"):
                                long_term = (context.get("long_term_memory") or "").strip()
                                if long_term:
                                    kb_block += f"""Ранее по этому проекту/пользователю:
{long_term}

"""
                            simple_prompt = build_simple_prompt(role_instruction, kb_block, goal)
                    
                    # Вставляем историю чата в промпт как «ранее по задаче» (план «умнее, быстрее»: достаточно сказать)
                    if context and context.get("chat_history"):
                        _h = context.get("chat_history") or ""
                        history_text = (_h if isinstance(_h, str) else str(_h)).strip()
                        if history_text:
                            simple_prompt = f"""Ранее по задаче (контекст чата):
{history_text}

---
Текущий запрос (ответь с учётом контекста выше):

{simple_prompt}"""
                    
                    # Таймаут и параметры зависят от категории
                    # Для general, status_query и stats — больше времени (в Docker запрос к host.docker.internal может быть медленным)
                    if category in ("general", "status_query") or needs_db_query:
                        timeout = 60.0  # Больше времени для умных моделей и запросов из контейнера
                    elif category == "fast":
                        timeout = 15.0
                    else:
                        timeout = 30.0
                    # Для простых приветствий - короткие ответы, но с более мощной моделью
                    goal_lower = goal.lower().strip()
                    is_simple_greeting = (
                        len(goal.split()) <= 3 and 
                        any(word in goal_lower for word in ["привет", "здравствуй", "hi", "hello"])
                    )
                    is_what_can_you_do = any(
                        x in goal_lower for x in ["что умеешь", "что ты умеешь", "чем можешь помочь", "твои возможности", "кто ты"]
                    )
                    # Для general и stats запросов - больше токенов для более детальных ответов
                    if category == "general" or needs_db_query:
                        max_tokens = 500  # Больше токенов для умных моделей
                        temperature = 0.6  # Баланс между креативностью и точностью
                    elif category == "fast" and is_simple_greeting:
                        max_tokens = 100
                        temperature = 0.4
                    elif category == "fast":
                        max_tokens = 150
                        temperature = 0.5
                    else:
                        max_tokens = 2000
                        temperature = 0.7
                    
                    # Проверяем доступность интернета для внешних URL
                    from app.network_resilience import get_network_resilience, safe_http_request
                    network_resilience = get_network_resilience()
                    
                    # Для локальных URL (localhost, host.docker.internal) интернет не нужен
                    is_local_url = any(url.startswith(("http://localhost", "http://127.0.0.1", "http://host.docker.internal")) for url in urls_to_try)
                    
                    if not is_local_url:
                        await network_resilience.ensure_internet_check()
                        if not network_resilience.is_internet_available():
                            logger.warning("⚠️ Интернет недоступен, используем только локальные модели")
                            # Пропускаем внешние URL, используем только локальные
                            urls_to_try = [url for url in urls_to_try if url.startswith(("http://localhost", "http://127.0.0.1", "http://host.docker.internal"))]
                            if not urls_to_try:
                                logger.error("❌ Нет доступных локальных моделей, интернет недоступен")
                                return {
                                    "result": "Извините, интернет недоступен, а локальные модели не настроены. Проверьте подключение к интернету или настройте MLX API Server.",
                                    "method": "error",
                                    "metadata": {
                                        "error": "no_internet_no_local_models",
                                        "internet_available": False
                                    }
                                }
                    
                    # Проверяем доступность интернета для внешних URL
                    from app.network_resilience import get_network_resilience, safe_http_request
                    network_resilience = get_network_resilience()
                    
                    # Для локальных URL (localhost, host.docker.internal) интернет не нужен
                    is_local_url = any(url.startswith(("http://localhost", "http://127.0.0.1", "http://host.docker.internal")) for url in urls_to_try)
                    
                    if not is_local_url:
                        await network_resilience.ensure_internet_check()
                        if not network_resilience.is_internet_available():
                            logger.warning("⚠️ Интернет недоступен, используем только локальные модели")
                            # Пропускаем внешние URL, используем только локальные
                            urls_to_try = [url for url in urls_to_try if url.startswith(("http://localhost", "http://127.0.0.1", "http://host.docker.internal"))]
                            if not urls_to_try:
                                logger.error("❌ Нет доступных локальных моделей, интернет недоступен")
                                return {
                                    "result": "Извините, интернет недоступен, а локальные модели не настроены. Проверьте подключение к интернету или настройте MLX API Server.",
                                    "method": "error",
                                    "metadata": {
                                        "error": "no_internet_no_local_models",
                                        "internet_available": False
                                    }
                                }
                    
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        for llm_url in urls_to_try:
                            try:
                                # MLX API Server ожидает "category" (fast/coding/default); Ollama — "model" (имя модели Ollama)
                                is_mlx = "11435" in llm_url
                                if is_mlx:
                                    gen_payload = {
                                        "category": "default" if category == "general" else category,
                                        "prompt": simple_prompt,
                                        "stream": False,
                                        "max_tokens": max_tokens,
                                        "temperature": temperature,
                                    }
                                else:
                                    # Ollama: модель по категории из отсканированного списка (могут меняться)
                                    try:
                                        from app.available_models_scanner import pick_ollama_model_for_category
                                        ollama_model = pick_ollama_model_for_category(category, ollama_models)
                                    except ImportError:
                                        ollama_model = None
                                    if not ollama_model and ollama_models:
                                        ollama_model = ollama_models[0]
                                    if not ollama_model:
                                        ollama_model = "phi3.5:3.8b"
                                    gen_payload = {
                                        "model": ollama_model,
                                        "prompt": simple_prompt,
                                        "stream": False,
                                        "options": {
                                            "temperature": temperature,
                                            "num_predict": max_tokens,
                                            "top_p": 0.9,
                                            "stop": ["\n\n\n", "---", "###", "1. ", "2. ", "3. ", "Запрос:", "Ответ (кратко", "ОБЯЗАТЕЛЬНО на русском"]
                                        }
                                    }
                                timeout_sec = timeout.total_seconds() if hasattr(timeout, 'total_seconds') else float(timeout)
                                # В Docker запрос к host.docker.internal может идти дольше — даём запас (status_query до 120 с)
                                if is_docker:
                                    if category == "status_query":
                                        timeout_sec = max(timeout_sec, 120.0)
                                    elif timeout_sec < 90:
                                        timeout_sec = max(timeout_sec * 1.5, 90.0)
                                response = await safe_http_request(
                                    f"{llm_url}/api/generate",
                                    method="POST",
                                    timeout=timeout_sec,
                                    json=gen_payload
                                )
                                
                                if response is None:
                                    logger.warning(f"⚠️ Не удалось выполнить запрос к {llm_url}, пробуем следующий URL")
                                    continue
                                
                                # Проверяем статус ответа
                                if response.status_code != 200:
                                    logger.warning(f"⚠️ {llm_url} вернул статус {response.status_code}")
                                    continue
                                
                                # Используем response.json() вместо response.json() напрямую
                                result_data = response.json()
                                
                                # result_data уже получен выше через safe_http_request
                                _r = result_data.get('response', '') if result_data else ''
                                result_text = (_r if isinstance(_r, str) else str(_r)).strip() if _r else None
                                
                                if result_text:
                                    if result_text:
                                        # Немедленная очистка от паттернов промпта
                                        import re
                                        # Удаляем все вхождения паттернов промпта
                                        result_text = re.sub(r'Вопрос:.*?(?=\n|$)', '', result_text, flags=re.MULTILINE | re.DOTALL)
                                        result_text = re.sub(r'ДАННЫЕ ИЗ БАЗЫ.*?(?=\n|$)', '', result_text, flags=re.MULTILINE | re.DOTALL)
                                        result_text = re.sub(r'Запрос:.*?(?=\n|$)', '', result_text, flags=re.MULTILINE | re.DOTALL)
                                        result_text = re.sub(r'Ответ.*?:.*?(?=\n|$)', '', result_text, flags=re.MULTILINE | re.DOTALL)
                                        result_text = re.sub(r'Твой ответ.*?(?=\n|$)', '', result_text, flags=re.MULTILINE | re.DOTALL)
                                        
                                        source = "MLX API Server"
                                        logger.info(f"✅ Simple метод использует {source}: {llm_url}, модель: {selected_model}")
                                        
                                        # Агрессивная обрезка для простых задач
                                        if category == "fast":
                                            # Сначала удаляем все паттерны "Запрос:", "Ответ:", "ОБЯЗАТЕЛЬНО"
                                            import re
                                            result_text = re.sub(r'Запрос:.*?(?=\n|$)', '', result_text, flags=re.MULTILINE)
                                            result_text = re.sub(r'Ответ.*?:.*?(?=\n|$)', '', result_text, flags=re.MULTILINE)
                                            result_text = re.sub(r'ОБЯЗАТЕЛЬНО.*?(?=\n|$)', '', result_text, flags=re.MULTILINE)
                                            result_text = re.sub(r'ДАННЫЕ ИЗ БАЗЫ ДАННЫХ.*?(?=\n|$)', '', result_text, flags=re.MULTILINE)
                                            
                                            # Для простых задач - максимум 200 символов
                                            if len(result_text) > 200:
                                                # Берем первое предложение или первые 200 символов
                                                sentences = result_text.split('.')
                                                if len(sentences) > 0 and len(sentences[0]) < 200:
                                                    result_text = sentences[0] + '.' if not sentences[0].endswith('.') else sentences[0]
                                                else:
                                                    result_text = result_text[:200].rsplit('.', 1)[0] + '.' if '.' in result_text[:200] else result_text[:200]
                                            
                                            # Удаляем повторяющиеся паттерны, нумерованные списки и дубликаты
                                            import re
                                            # Сначала удаляем все паттерны промпта
                                            result_text = re.sub(r'Запрос:.*?(?=\n|$)', '', result_text, flags=re.MULTILINE | re.DOTALL)
                                            result_text = re.sub(r'Ответ.*?:.*?(?=\n|$)', '', result_text, flags=re.MULTILINE | re.DOTALL)
                                            result_text = re.sub(r'ОБЯЗАТЕЛЬНО.*?(?=\n|$)', '', result_text, flags=re.MULTILINE | re.DOTALL)
                                            result_text = re.sub(r'ДАННЫЕ ИЗ БАЗЫ.*?(?=\n|$)', '', result_text, flags=re.MULTILINE | re.DOTALL)
                                            
                                            lines = result_text.split('\n')
                                            seen = set()
                                            unique_lines = []
                                            for line in lines:
                                                line_stripped = line.strip()
                                                # Пропускаем пустые строки, нумерованные списки, длинные строки и повторяющиеся паттерны
                                                if (line_stripped and 
                                                    line_stripped not in seen and 
                                                    not (line_stripped[0].isdigit() and '. ' in line_stripped[:5]) and  # Не нумерованные списки
                                                    len(line_stripped) < 150 and
                                                    "Запрос:" not in line_stripped and
                                                    "Ответ" not in line_stripped and
                                                    "ОБЯЗАТЕЛЬНО" not in line_stripped and
                                                    "ДАННЫЕ ИЗ БАЗЫ" not in line_stripped):
                                                    seen.add(line_stripped)
                                                    unique_lines.append(line)
                                                if len(unique_lines) >= 2:  # Максимум 2 строки для простых задач
                                                    break
                                            
                                            result_text = '\n'.join(unique_lines[:2]).strip()
                                            
                                            # Финальная очистка - берем только первое предложение если есть проблемы
                                            if not result_text or len(result_text) > 150 or "Запрос:" in result_text or "Ответ" in result_text or "Вопрос:" in result_text or "ДАННЫЕ ИЗ БАЗЫ" in result_text:
                                                # Удаляем все строки с "Вопрос:", "ДАННЫЕ ИЗ БАЗЫ", "Запрос:", "Ответ"
                                                clean_lines = []
                                                for line in result_text.split('\n'):
                                                    if not any(word in line for word in ["Вопрос:", "ДАННЫЕ ИЗ БАЗЫ", "Запрос:", "Ответ", "ОБЯЗАТЕЛЬНО"]):
                                                        clean_lines.append(line)
                                                result_text = '\n'.join(clean_lines).strip()
                                                
                                                # Берем только первое предложение
                                                sentences = result_text.split('.')
                                                if len(sentences) > 0:
                                                    result_text = sentences[0] + '.' if not sentences[0].endswith('.') else sentences[0]
                                                    result_text = result_text[:150].strip()
                                            
                                            # Финальная проверка - если все еще есть проблемы, берем только цифры и краткий ответ
                                            if "Вопрос:" in result_text or "ДАННЫЕ ИЗ БАЗЫ" in result_text:
                                                # Извлекаем только числа и краткий ответ
                                                import re
                                                numbers = re.findall(r'\d+', result_text)
                                                if numbers and "не выполненных" in goal.lower():
                                                    result_text = f"В корпорации {numbers[2] if len(numbers) > 2 else numbers[0] if numbers else '0'} невыполненных задач."
                                                elif numbers and "выполненных" in goal.lower():
                                                    result_text = f"В корпорации {numbers[1] if len(numbers) > 1 else numbers[0] if numbers else '0'} выполненных задач."
                                                else:
                                                    # Берем только первое предложение без паттернов
                                                    sentences = result_text.split('.')
                                                    for sent in sentences:
                                                        if "Вопрос:" not in sent and "ДАННЫЕ" not in sent:
                                                            result_text = sent.strip()
                                                            break
                                        
                                        return {
                                            "result": result_text,
                                            "method": "simple",
                                            "metadata": {
                                                "model_used": selected_model,
                                                "source": source,
                                                "fast_mode": (category == "fast"),
                                                "response_time": "optimized",
                                                "category": category
                                            }
                                        }
                                elif response.status_code == 404:
                                    # Модель не найдена на этом URL, пробуем следующий
                                    logger.debug(f"Модель {selected_model} не найдена на {llm_url}, пробуем следующий URL...")
                                    continue
                            except Exception as e:
                                logger.debug(f"Ошибка при использовании {llm_url}: {e}, пробуем следующий URL...")
                                continue
                        
                        # Если все URL не сработали
                        logger.warning(f"⚠️ Не удалось использовать модель ни на одном URL (MLX 11435, Ollama 11434)")
                    
                    # Для «статус проекта» при недоступности LLM — эталонный ответ (дашборд, список задач), куратор 3/3 (CURATOR_MENTOR_CAUSES)
                    if category == "status_query" and is_status_project_query:
                        return {
                            "result": (
                                "Статус проекта смотрите в дашборде (Corporation Dashboard, порт 8501) и в списке задач (список задач Knowledge OS). "
                                "Опираюсь на факты из MASTER_REFERENCE и задач, не придумываю сроки."
                            ),
                            "method": "simple",
                            "metadata": {
                                "category": category,
                                "note": "status_project_fallback_no_llm"
                            }
                        }
                    # При недоступности LLM — эталонные ответы для приветствия и «что умеешь» (куратор, 3/3)
                    if category == "fast" and is_simple_greeting:
                        return {
                            "result": "Привет! Я Виктория, Team Lead корпорации ATRA. Чем могу помочь?",
                            "method": "simple",
                            "metadata": {"category": category, "note": "greeting_fallback_no_llm"}
                        }
                    if is_what_can_you_do:
                        try:
                            from configs.victoria_common import get_capabilities_text
                            what_result = get_capabilities_text().replace("\n", " ").strip()
                        except Exception:
                            what_result = (
                                "Я Виктория, Team Lead Atra Core. Умею: отвечать на вопросы и вести чат; "
                                "составлять планы и выполнять задачи; показывать список файлов; "
                                "делегировать в Veronica, сложные — оркестрировать с командой."
                            )
                        return {
                            "result": what_result,
                            "method": "simple",
                            "metadata": {"category": category, "note": "what_can_you_do_fallback_no_llm"}
                        }
                    
                    # Fallback: реальный ответ не получен — подсказка, что проверить
                    return {
                        "result": (
                            "Сейчас не могу подключиться к моделям (MLX API Server или Ollama). "
                            "Проверьте: MLX API Server на порту 11435, Ollama на 11434. "
                            "После запуска напишите снова — отвечу по существу."
                        ),
                        "method": "simple",
                        "metadata": {
                            "model_used": selected_model,
                            "category": category,
                            "note": "models_unavailable"
                        }
                    }
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка быстрого метода: {e}")
                    return {
                        "result": (
                            f"Ошибка при обращении к модели: {e}. "
                            "Проверьте MLX API Server (порт 11435) или Ollama (11434)."
                        ),
                        "method": "simple",
                        "error": str(e)
                    }
            
            else:
                # Fallback на простой метод
                return {
                    "result": f"Задача: {goal} (простой метод, enhancements недоступны)",
                    "method": "simple",
                    "note": "Enhanced methods not available"
                }
        
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения метода {method}: {e}")
            return {
                "result": f"Ошибка: {str(e)}",
                "method": method,
                "error": str(e)
            }
        finally:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"⏱️ Метод {method} выполнен за {elapsed:.2f}с")
    
    async def start(self):
        """
        Запустить Event-Driven Architecture и мониторинг (AutoGen pattern)
        
        При ENABLE_EVENT_MONITORING=false только помечает мониторинг как запущенный (экономия памяти).
        Иначе запускает: Event Bus, File Watcher, Service Monitor, Deadline Tracker, Skills Watcher.
        """
        if self.monitoring_started:
            logger.warning("⚠️ Мониторинг уже запущен")
            return
        
        _enable = (os.getenv("ENABLE_EVENT_MONITORING") or "").strip().lower() in ("true", "1", "yes")
        if not _enable:
            self.monitoring_started = True
            logger.info("✅ Victoria Enhanced готов (Event Bus/File Watcher отключены — ENABLE_EVENT_MONITORING=false)")
            return

        try:
            # Запускаем Event Bus
            if self.event_bus:
                await self.event_bus.start()
                logger.info("🚀 Event Bus запущен")
            
            # Загружаем skills
            if self.skill_loader:
                await self.skill_loader.load_all_skills()
                await self.skill_loader.start_watcher()
                if self.skill_loader.is_watching():
                    logger.info("🚀 Skills Watcher запущен")
                else:
                    logger.info("📦 Skills загружены (hot-reload недоступен без watchdog)")
            
            # Инициализируем и запускаем File Watcher
            try:
                from app.file_watcher import FileWatcher
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                self.file_watcher = FileWatcher(
                    watch_paths=[project_root],
                    file_extensions=[".py", ".md", ".json", ".yaml", ".yml"],
                    recursive=True
                )
                await self.file_watcher.start()
                logger.info("🚀 File Watcher запущен")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка запуска File Watcher: {e}")
            
            # Инициализируем и запускаем Service Monitor
            try:
                from app.service_monitor import ServiceMonitor
                self.service_monitor = ServiceMonitor(check_interval=30)
                await self.service_monitor.start()
                logger.info("🚀 Service Monitor запущен")
                
                # Опционально: запускаем MLX Server Supervisor если сервер не запущен
                # (только если MLX_PRELOAD_MODELS установлен, значит MLX используется)
                if os.getenv("MLX_PRELOAD_MODELS"):
                    try:
                        import httpx
                        async with httpx.AsyncClient(timeout=2.0) as client:
                            await client.get("http://localhost:11435/health")
                        logger.debug("✅ MLX API Server уже запущен")
                    except Exception:
                        # Сервер не запущен, запускаем Supervisor
                        try:
                            from app.mlx_server_supervisor import get_mlx_supervisor
                            supervisor = get_mlx_supervisor()
                            await supervisor.start()
                            logger.info("🚀 MLX Server Supervisor запущен (автоматический перезапуск)")
                        except Exception as e:
                            logger.debug(f"⚠️ MLX Server Supervisor недоступен: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка запуска Service Monitor: {e}")
            
            # Инициализируем и запускаем Deadline Tracker
            try:
                from app.deadline_tracker import DeadlineTracker
                self.deadline_tracker = DeadlineTracker(check_interval=300)
                await self.deadline_tracker.start()
                logger.info("🚀 Deadline Tracker запущен")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка запуска Deadline Tracker: {e}")
            
            # Подписываемся на события через Event Handlers
            if self.event_bus and self.event_handlers:
                from app.event_bus import EventType
                self.event_bus.subscribe(EventType.FILE_CREATED, self.event_handlers.handle_file_created)
                self.event_bus.subscribe(EventType.FILE_MODIFIED, self.event_handlers.handle_file_modified)
                self.event_bus.subscribe(EventType.SERVICE_DOWN, self.event_handlers.handle_service_down)
                self.event_bus.subscribe(EventType.DEADLINE_APPROACHING, self.event_handlers.handle_deadline_approaching)
                self.event_bus.subscribe(EventType.ERROR_DETECTED, self.event_handlers.handle_error_detected)
                self.event_bus.subscribe(EventType.SKILL_NEEDED, self.event_handlers.handle_skill_needed)
                
                # Подписываемся на события skills для Skill Discovery
                try:
                    from app.skill_discovery import SkillDiscovery
                    skill_discovery = SkillDiscovery(skill_registry=self.skill_registry)
                    self.event_bus.subscribe(EventType.SKILL_NEEDED, skill_discovery.handle_skill_needed_event)
                    logger.info("✅ Skill Discovery подключен к Event Bus")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось подключить Skill Discovery: {e}")
                
                logger.info("✅ Подписка на события выполнена")
            
            self.monitoring_started = True
            logger.info("✅ Все компоненты мониторинга запущены")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска мониторинга: {e}", exc_info=True)
    
    async def stop(self):
        """Остановить все компоненты мониторинга"""
        if not self.monitoring_started:
            return
        
        try:
            if self.file_watcher:
                await self.file_watcher.stop()
            if self.service_monitor:
                await self.service_monitor.stop()
            if self.deadline_tracker:
                await self.deadline_tracker.stop()
            if self.skill_loader:
                await self.skill_loader.stop_watcher()
            if self.event_bus:
                await self.event_bus.stop()
            
            self.monitoring_started = False
            logger.info("🛑 Все компоненты мониторинга остановлены")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки мониторинга: {e}")
    
    async def get_status(self) -> Dict:
        """Получить статус всех компонентов"""
        status = {
            "react_available": self.react_agent is not None,
            "extended_thinking_available": self.extended_thinking is not None,
            "swarm_available": self.swarm is not None,
            "consensus_available": self.consensus is not None,
            "collective_memory_available": self.collective_memory is not None,
            "hierarchical_available": self.hierarchical_orch is not None,
            "recap_available": self.recap is not None,
            "tot_available": self.tot is not None,
            "model": self.model_name
        }
        
        # Добавляем статус Event-Driven Architecture
        status.update({
            "event_bus_available": self.event_bus is not None,
            "skill_registry_available": self.skill_registry is not None,
            "skill_loader_available": self.skill_loader is not None,
            "event_handlers_available": self.event_handlers is not None,
            "file_watcher_available": self.file_watcher is not None,
            "service_monitor_available": self.service_monitor is not None,
            "deadline_tracker_available": self.deadline_tracker is not None,
            "monitoring_started": self.monitoring_started
        })
        
        # Статистика skills
        if self.skill_registry:
            status["skills_count"] = len(self.skill_registry.skills)
            status["skills_stats"] = self.skill_registry.get_stats()
        
        return status


async def main():
    """Тестирование Victoria Enhanced"""
    victoria = VictoriaEnhanced()
    
    # Проверяем статус
    status = await victoria.get_status()
    print("Статус компонентов:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Тестируем разные типы задач
    test_tasks = [
        ("Реши задачу: 2+2*2", "reasoning"),
        ("Спланируй оптимизацию базы данных", "planning"),
        ("Сложная задача требующая коллективного интеллекта", "complex"),
        ("Выполни анализ кода", "execution")
    ]
    
    print("\n🧪 Тестирование задач:")
    for goal, expected_category in test_tasks:
        print(f"\n📋 Задача: {goal}")
        result = await victoria.solve(goal)
        print(f"  Метод: {result.get('method')}")
        print(f"  Результат: {str(result.get('result', ''))[:200]}...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
