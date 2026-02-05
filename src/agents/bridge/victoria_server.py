"""
Victoria Agent — Team Lead ATRA. HTTP API для задач.
Отдельный сервер: контейнер victoria-agent запускает именно Викторию, а не Веронику.
"""
import logging
import os
import sys
import hashlib
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Any, List, Dict, Dict, List, Tuple
from contextlib import asynccontextmanager
import uvicorn
import httpx

# Хранилище фоновых задач (202 + polling): task_id -> { status, output, knowledge, error, created_at }
_run_task_store: Dict[str, Dict[str, Any]] = {}
_RUN_TASK_STORE_TTL = 3600  # секунд, потом удаляем

# Лимит шагов агента: сложные задачи (анализ, исправления) требуют больше итераций
DEFAULT_MAX_STEPS = int(os.getenv("VICTORIA_MAX_STEPS", "500"))

# Debug mode: VICTORIA_DEBUG=true enables verbose logging at all levels
VICTORIA_DEBUG = os.getenv("VICTORIA_DEBUG", "false").lower() in ("true", "1", "yes")

from src.agents.core.base_agent import AtraBaseAgent as BaseAgent
from src.agents.core.executor import OllamaExecutor, _ollama_base_url
from src.agents.tools.system_tools import SystemTools, WebTools
from src.agents.bridge.task_detector import detect_task_type, should_use_enhanced
from src.agents.bridge.enhanced_router import delegate_to_veronica
from src.agents.bridge.project_registry import get_projects_registry, get_main_project

# Интеграция с Knowledge OS (оркестратор, Виктория и сотрудники используют базу знаний)
# Выключить: USE_KNOWLEDGE_OS=false
USE_KNOWLEDGE_OS = os.getenv("USE_KNOWLEDGE_OS", "true").lower() == "true"
KNOWLEDGE_OS_AVAILABLE = False
asyncpg = None

# Canary: оркестрация V2 (A/B по проценту трафика)
ORCHESTRATION_V2_ENABLED = os.getenv("ORCHESTRATION_V2_ENABLED", "false").lower() in ("1", "true", "yes")
ORCHESTRATION_V2_PERCENTAGE = float(os.getenv("ORCHESTRATION_V2_PERCENTAGE", "10"))

if USE_KNOWLEDGE_OS:
    try:
        import asyncpg
        KNOWLEDGE_OS_AVAILABLE = True
    except ImportError:
        logging.warning("asyncpg не установлен, Knowledge OS недоступна. Установите: pip install asyncpg")
        KNOWLEDGE_OS_AVAILABLE = False

# Настройка логирования с поддержкой ELK
# VICTORIA_DEBUG=true enables DEBUG level logging for all components
_log_level = logging.DEBUG if VICTORIA_DEBUG else logging.INFO
logging.basicConfig(
    level=_log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if VICTORIA_DEBUG else '%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("victoria_bridge")
if VICTORIA_DEBUG:
    logger.setLevel(logging.DEBUG)
    logger.info("🐛 VICTORIA_DEBUG mode enabled - verbose logging active")

# Добавляем ELK handler если включен
if os.getenv("USE_ELK", "false").lower() in ("true", "1", "yes"):
    try:
        # Пытаемся найти elk_handler в knowledge_os/app
        elk_paths = [
            "/app/app",  # Путь в контейнере
            os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"),
            os.path.join(os.path.dirname(__file__), "../../knowledge_os/app"),
        ]
        elk_handler_imported = False
        for elk_path in elk_paths:
            if os.path.exists(os.path.join(elk_path, "elk_handler.py")):
                if elk_path not in sys.path:
                    sys.path.insert(0, elk_path)
                try:
                    from elk_handler import create_elk_handler
                    elk_url = os.getenv("ELASTICSEARCH_URL", "http://atra-elasticsearch:9200")
                    elk_handler = create_elk_handler(elasticsearch_url=elk_url, log_level=logging.INFO)
                    if elk_handler:
                        root_logger = logging.getLogger()
                        root_logger.addHandler(elk_handler)
                        logger.info("✅ ELK handler enabled for Victoria")
                        elk_handler_imported = True
                        break
                except Exception as e:
                    logger.warning(f"Failed to import ELK handler from {elk_path}: {e}")
        if not elk_handler_imported:
            logger.warning("ELK handler not found, continuing without ELK logging")
    except Exception as e:
        logger.warning(f"Failed to setup ELK handler: {e}")

# Глобальный экземпляр Victoria Enhanced (если включен)
victoria_enhanced_instance = None
victoria_enhanced_monitoring_started = False

# FastAPI lifespan events для запуска/остановки мониторинга
# Victoria = один сервис на 8010 с тремя уровнями: Agent (всегда), Enhanced, Initiative. Все три должны быть активны для полноценной работы.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan: запуск Victoria Enhanced + Initiative (все три уровня в одном процессе)."""
    global victoria_enhanced_instance, victoria_enhanced_monitoring_started

    def _env_bool(key: str, default: bool = False) -> bool:
        v = (os.getenv(key) or "").strip().strip('"\'')
        return v.lower() in ("true", "1", "yes")

    use_enhanced = _env_bool("USE_VICTORIA_ENHANCED", False)
    enable_monitoring = _env_bool("ENABLE_EVENT_MONITORING", True)  # по умолчанию true — Initiative должна быть запущена
    logger.info(f"Victoria lifespan: USE_VICTORIA_ENHANCED={use_enhanced}, ENABLE_EVENT_MONITORING={enable_monitoring}")
    if use_enhanced and enable_monitoring:
        try:
            import sys
            logger.info("Victoria Enhanced + Initiative: запуск мониторинга...")
            # Только /app/knowledge_os — иначе "from app.victoria_enhanced" не резолвится
            ko_paths = [
                "/app/knowledge_os",
                os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../knowledge_os")),
            ]
            for ko_root in ko_paths:
                if not os.path.exists(ko_root) and not ko_root.startswith("/app"):
                    continue
                if ko_root not in sys.path:
                    sys.path.insert(0, ko_root)
                try:
                    from app.victoria_enhanced import VictoriaEnhanced
                    logger.info("🚀 Инициализация Victoria Enhanced при старте сервера...")
                    victoria_enhanced_instance = VictoriaEnhanced()
                    await victoria_enhanced_instance.start()
                    victoria_enhanced_monitoring_started = True
                    logger.info("✅ Victoria Enhanced + Initiative мониторинг запущен при старте сервера")
                    break
                except ImportError as e:
                    logger.debug(f"Не удалось импортировать VictoriaEnhanced из {ko_root}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка запуска мониторинга при старте: {e}")
                    break
        except Exception as e:
            logger.warning(f"⚠️ Ошибка инициализации Victoria Enhanced при старте: {e}")
    
    # Предзагрузка команды экспертов из Knowledge OS (чтобы /status показывал experts_count)
    if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE:
        try:
            await agent._load_expert_team()
        except Exception as e:
            logger.warning("Предзагрузка экспертов при старте: %s", e)

    # Реестр проектов: загрузка из БД при старте (кэш для валидации project_context)
    try:
        await get_projects_registry()
        logger.info("Реестр проектов загружен при старте Victoria")
    except Exception as e:
        logger.warning("Загрузка реестра проектов при старте: %s", e)
    
    yield
    
    # Shutdown
    if victoria_enhanced_instance and victoria_enhanced_monitoring_started:
        try:
            await victoria_enhanced_instance.stop()
            logger.info("🛑 Victoria Enhanced мониторинг остановлен")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка остановки мониторинга: {e}")

app = FastAPI(title="Victoria ATRA Bridge API", lifespan=lifespan)


class VictoriaAgent(BaseAgent):
    """Виктория — Team Lead, использует оптимизированную конфигурацию моделей."""

    def __init__(self, name: str = "Виктория", model_name: str = None):
        logger.info("[VICTORIA_INIT] ========== VictoriaAgent initialization ==========")
        
        # Victoria выбирает модель из актуального списка Ollama+MLX (см. _ensure_best_available_models в run())
        # VICTORIA_MODEL задаёт явно; иначе при первом run() подставится лучшая доступная
        env_victoria_model = os.getenv("VICTORIA_MODEL", "")
        env_planner_model = os.getenv("VICTORIA_PLANNER_MODEL", "")
        
        logger.info("[VICTORIA_INIT] ENV VICTORIA_MODEL: '%s'", env_victoria_model)
        logger.info("[VICTORIA_INIT] ENV VICTORIA_PLANNER_MODEL: '%s'", env_planner_model)
        
        if model_name is None:
            model_name = env_victoria_model or "qwen2.5-coder:32b"  # fallback до первого сканирования
        
        logger.info("[VICTORIA_INIT] Initial model_name: %s", model_name)
        
        self._models_resolved = False  # при первом run() подставим лучшую из доступных
        
        super().__init__(name, model_name)
        base = _ollama_base_url()
        
        logger.info("[VICTORIA_INIT] Ollama base URL: %s", base)
        
        # Попытка использовать LocalAIRouter для поддержки MLX (если доступен)
        self.use_local_router = os.getenv("VICTORIA_USE_LOCAL_ROUTER", "true").lower() == "true"
        self.local_router = None
        
        logger.info("[VICTORIA_INIT] Use LocalAIRouter: %s", self.use_local_router)
        
        if self.use_local_router:
            try:
                # Пытаемся импортировать LocalAIRouter из knowledge_os
                import sys
                router_paths = [
                    "/app/app/local_router.py",
                    os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app/local_router.py"),
                    os.path.join(os.path.dirname(__file__), "../../knowledge_os/app/local_router.py"),
                ]
                for path in router_paths:
                    if os.path.exists(path):
                        if os.path.dirname(path) not in sys.path:
                            sys.path.insert(0, os.path.dirname(path))
                        try:
                            from local_router import LocalAIRouter
                            self.local_router = LocalAIRouter()
                            logger.info("[VICTORIA_INIT] ✅ LocalAIRouter (MLX support) загружен")
                            break
                        except ImportError as ie:
                            logger.debug(f"[VICTORIA_INIT] LocalAIRouter import failed from {path}: {ie}")
                            continue
            except Exception as e:
                logger.debug(f"[VICTORIA_INIT] LocalAIRouter недоступен: {e}, используем только Ollama")
        
        # По умолчанию planner = та же модель, что и executor: от понимания зависит всё, меньше галлюцинаций
        # VICTORIA_PLANNER_MODEL можно задать отдельно (например быстрая модель для планов)
        planner_model = env_planner_model or model_name
        self.planner = OllamaExecutor(model=planner_model, base_url=base)
        self.executor = OllamaExecutor(model=model_name, base_url=base)
        
        logger.info("[VICTORIA_INIT] ✅ Executors created:")
        logger.info("[VICTORIA_INIT]    Planner model: %s", self.planner.model)
        logger.info("[VICTORIA_INIT]    Executor model: %s", self.executor.model)
        logger.info("[VICTORIA_INIT]    Base URL: %s", base)
        logger.info("[VICTORIA_INIT] ========== Initialization complete ==========")
        self.add_tool("read_file", SystemTools.read_project_file)
        self.add_tool("run_terminal_cmd", SystemTools.run_local_command)
        self.add_tool("ssh_run", SystemTools.run_ssh_command)
        self.add_tool("list_directory", SystemTools.list_directory)
        self.add_tool("web_search", WebTools.web_search)
        
        # Интеграция с Knowledge OS (опционально)
        self.db_pool = None
        self.expert_team = {}
        self._expert_team_loaded = False
        self._last_expert_sync = None  # TTL для экспертов (5 мин)
        self._expert_cache_ttl_sec = int(os.getenv("VICTORIA_EXPERT_CACHE_TTL", "300"))
        self.use_cache = os.getenv("VICTORIA_USE_CACHE", "true").lower() == "true"
        self.task_cache = {}
        self.cache_ttl = timedelta(hours=24)
        
        if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE:
            # Инициализация будет выполнена асинхронно при первом использовании
            logger.info("✅ Knowledge OS интеграция включена (инициализация при первом использовании)")

    async def _get_db_pool(self):
        """Получить или создать pool соединений с Knowledge OS"""
        if not USE_KNOWLEDGE_OS or not KNOWLEDGE_OS_AVAILABLE:
            return None
        
        if self.db_pool is None:
            try:
                db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
                self.db_pool = await asyncpg.create_pool(
                    db_url,
                    min_size=1,
                    max_size=5
                )
                logger.info("✅ Knowledge OS Database pool создан")
            except Exception as e:
                logger.error(f"❌ Ошибка создания pool Knowledge OS: {e}")
                self.db_pool = None
        
        return self.db_pool
    
    async def _load_expert_team(self):
        """Загрузить команду экспертов из Knowledge OS. TTL кэша 5 мин (VICTORIA_EXPERT_CACHE_TTL)."""
        now = datetime.now(timezone.utc)
        if self._expert_team_loaded and self._last_expert_sync:
            if (now - self._last_expert_sync).total_seconds() < self._expert_cache_ttl_sec:
                return
            self._expert_team_loaded = False
        
        pool = await self._get_db_pool()
        if not pool:
            return
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, name, role, department, system_prompt
                    FROM experts
                    ORDER BY name
                """)
                self.expert_team = {row['name']: dict(row) for row in rows}
                self._expert_team_loaded = True
                self._last_expert_sync = datetime.now(timezone.utc)
                logger.info(f"✅ Загружено {len(self.expert_team)} экспертов из Knowledge OS")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки экспертов: {e}")
            self.expert_team = {}
    
    async def _get_embedding_for_rag(self, text: str) -> Optional[List[float]]:
        """Один эмбеддинг для RAG (Ollama nomic-embed-text). Таймаут короткий для скорости."""
        embed_url = os.getenv("OLLAMA_EMBED_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/api/embeddings")
        model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.post(
                    embed_url,
                    json={"model": model, "prompt": text[:8000]}
                )
                r.raise_for_status()
                return r.json().get("embedding")
        except Exception as e:
            logger.debug(f"Embedding для RAG недоступен: {e}")
            return None

    async def _get_knowledge_context(self, goal: str, limit: int = 5) -> str:
        """Релевантные знания из Knowledge OS: векторный поиск (RAG+) при наличии эмбеддингов, иначе ILIKE.
        Длина сниппета настраивается через RAG_SNIPPET_CHARS (по умолчанию 500).
        Для топ-1 по similarity передаётся полный контент до RAG_TOP1_FULL_MAX_CHARS (0 = отключено)."""
        pool = await self._get_db_pool()
        if not pool:
            return ""
        limit = min(int(os.getenv("RAG_CONTEXT_LIMIT", "5")), limit)
        threshold = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.6"))
        snippet_chars = int(os.getenv("RAG_SNIPPET_CHARS", "500"))
        top1_full_max = int(os.getenv("RAG_TOP1_FULL_MAX_CHARS", "2000"))

        def _format_content(row_content: str, index: int, is_vector: bool, similarity: float) -> str:
            raw = row_content or ""
            if not raw:
                return ""
            # Топ-1 по релевантности: полный контент до top1_full_max (мировая практика: один полный чанк улучшает ответ)
            if index == 0 and top1_full_max > 0 and is_vector and similarity >= threshold:
                use = raw[:top1_full_max]
                if len(raw) > top1_full_max:
                    use += "..."
                return use
            use = raw[:snippet_chars]
            if len(raw) > snippet_chars:
                use += "..."
            return use

        try:
            # RAG+: векторный поиск, если есть эмбеддинг
            embedding = await self._get_embedding_for_rag(goal)
            if embedding is not None:
                async with pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT content, metadata, (1 - (embedding <=> $1::vector)) AS similarity
                        FROM knowledge_nodes
                        WHERE embedding IS NOT NULL AND confidence_score >= 0.3
                        ORDER BY embedding <=> $1::vector
                        LIMIT $2
                    """, str(embedding), limit)
                    if rows:
                        context = "\n--- РЕЛЕВАНТНЫЕ ЗНАНИЯ ИЗ БАЗЫ (RAG) ---\n"
                        for i, row in enumerate(rows):
                            if row["similarity"] >= threshold:
                                content = _format_content(
                                    row["content"], i, is_vector=True, similarity=row["similarity"]
                                )
                                if content:
                                    context += f"- {content}\n"
                        if context.count("\n") > 1:
                            return context
            # Fallback: текстовый поиск (без similarity — все сниппеты)
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT content, confidence_score
                    FROM knowledge_nodes
                    WHERE confidence_score > 0.3
                    AND content ILIKE $1
                    ORDER BY confidence_score DESC NULLS LAST, created_at DESC
                    LIMIT $2
                """, f"%{goal[:50]}%", limit)
                if rows:
                    context = "\n--- РЕЛЕВАНТНЫЕ ЗНАНИЯ ИЗ БАЗЫ ---\n"
                    for i, row in enumerate(rows):
                        raw = row["content"] or ""
                        use = raw[:snippet_chars]
                        if len(raw) > snippet_chars:
                            use += "..."
                        if use:
                            context += f"- {use}\n"
                    return context
        except Exception as e:
            logger.warning(f"Ошибка поиска знаний: {e}")
        return ""
    
    def _categorize_task(self, goal: str) -> str:
        """Определить категорию задачи для выбора эксперта"""
        goal_lower = goal.lower()
        
        categories = {
            "backend": ["api", "сервер", "база данных", "postgresql", "sql", "docker", "fastapi"],
            "frontend": ["интерфейс", "ui", "ux", "веб", "браузер", "react", "vue", "frontend"],
            "ml": ["модель", "обучение", "нейросеть", "ml", "ai", "машинное обучение", "ollama"],
            "devops": ["развертывание", "deploy", "ci/cd", "мониторинг", "grafana", "prometheus", "docker"],
            "security": ["безопасность", "security", "уязвимость", "аудит"],
            "database": ["база данных", "миграция", "схема", "индекс", "postgresql", "sqlite"],
            "performance": ["производительность", "оптимизация", "скорость", "latency"],
        }
        
        for category, keywords in categories.items():
            if any(keyword in goal_lower for keyword in keywords):
                return category
        
        return "general"
    
    async def select_expert_for_task(self, goal: str, use_multiple: bool = False) -> Tuple[Optional[str], Optional[Dict], Optional[List[Tuple[str, Dict]]]]:
        """Автоматически выбрать лучшего эксперта(ов) для задачи с учетом специализации и загрузки
        
        Args:
            goal: Текст задачи
            use_multiple: Если True, возвращает несколько экспертов для сложных задач
        
        Returns:
            Tuple[primary_expert_name, primary_expert_data, additional_experts_list]
        """
        if not USE_KNOWLEDGE_OS or not KNOWLEDGE_OS_AVAILABLE:
            return None, None, None
        
        try:
            # Загрузить экспертов если еще не загружены
            if not self._expert_team_loaded:
                await self._load_expert_team()
            
            if not self.expert_team:
                return None, None, None
            
            # Определить категорию задачи
            category = self._categorize_task(goal)
            
            # Маппинг категорий на роли экспертов (расширенный)
            category_to_roles = {
                "backend": ["Backend Developer", "Full-stack Developer", "Principal Backend Architect"],
                "frontend": ["Frontend Developer", "UI/UX Designer", "Full-stack Developer"],
                "ml": ["ML Engineer", "Data Analyst", "Principal AI Systems Architect", "Principal Machine Learning Architect"],
                "devops": ["DevOps Engineer", "Security Engineer", "Performance Engineer", "Lead DevOps Architect"],
                "security": ["Security Engineer", "DevOps Engineer", "Code Reviewer"],
                "database": ["Database Engineer", "Backend Developer", "DevOps Engineer"],
                "performance": ["Performance Engineer", "Backend Developer", "DevOps Engineer"],
                "general": ["Team Lead", "Product Manager", "Technical Writer"]
            }
            
            target_roles = category_to_roles.get(category, ["Team Lead"])
            
            # Получить pool для запросов к БД
            pool = await self._get_db_pool()
            
            # Найти ВСЕХ экспертов с подходящими ролями
            candidates = []
            for expert_name, expert_data in self.expert_team.items():
                expert_role = expert_data.get('role', '')
                if expert_role in target_roles:
                    candidates.append((expert_name, expert_data))
            
            if not candidates:
                logger.warning(f"⚠️ Не найдено экспертов для категории {category}")
                return None, None, None
            
            # Оценить каждого кандидата и выбрать лучшего
            best_expert = None
            best_score = -1
            best_data = None
            
            for expert_name, expert_data in candidates:
                score = 0.0
                
                # 1. Базовый score по соответствию роли (приоритет основной роли)
                role_priority = target_roles.index(expert_data.get('role', '')) if expert_data.get('role', '') in target_roles else 999
                score += (10.0 - role_priority) * 2  # Основная роль = 20, дополнительные = меньше
                
                # 2. Релевантность специализации (department)
                department = expert_data.get('department', '').lower()
                goal_lower = goal.lower()
                if department and any(keyword in goal_lower for keyword in department.split()):
                    score += 5.0
                
                # 3. Опыт и загрузка (если есть доступ к БД)
                if pool:
                    try:
                        async with pool.acquire() as conn:
                            # Получить статистику эксперта из БД
                            expert_id = await conn.fetchval(
                                "SELECT id FROM experts WHERE name = $1",
                                expert_name
                            )
                            
                            if expert_id:
                                # Количество выполненных задач
                                completed_tasks = await conn.fetchval(
                                    """
                                    SELECT COUNT(*) 
                                    FROM tasks 
                                    WHERE assignee_expert_id = $1 
                                    AND status = 'completed'
                                    """,
                                    expert_id
                                ) or 0
                                
                                # Успешность (процент завершенных задач)
                                total_tasks = await conn.fetchval(
                                    """
                                    SELECT COUNT(*) 
                                    FROM tasks 
                                    WHERE assignee_expert_id = $1
                                    """,
                                    expert_id
                                ) or 1
                                
                                success_rate = (completed_tasks / total_tasks) if total_tasks > 0 else 0.5
                                
                                # Активные задачи (загрузка)
                                active_tasks = await conn.fetchval(
                                    """
                                    SELECT COUNT(*) 
                                    FROM tasks 
                                    WHERE assignee_expert_id = $1 
                                    AND status IN ('pending', 'in_progress')
                                    """,
                                    expert_id
                                ) or 0
                                
                                # Score на основе опыта и загрузки
                                score += completed_tasks * 0.5  # Опыт
                                score += success_rate * 10  # Успешность (0-10)
                                score -= active_tasks * 2  # Штраф за загрузку
                    except Exception as e:
                        logger.debug(f"Не удалось получить статистику для {expert_name}: {e}")
                
                # 4. Релевантность по metadata (если есть)
                metadata = expert_data.get('metadata', {})
                if isinstance(metadata, dict):
                    # Проверка специализации в metadata
                    if 'specialization' in metadata:
                        spec = str(metadata['specialization']).lower()
                        if any(keyword in goal_lower for keyword in spec.split(',')):
                            score += 3.0
                
                # Обновить лучшего кандидата
                if score > best_score:
                    best_score = score
                    best_expert = expert_name
                    best_data = expert_data
            
            if best_expert:
                logger.info(f"✅ Выбран лучший эксперт: {best_expert} ({best_data.get('role')}) для задачи: {goal[:50]} (score: {best_score:.1f})")
                logger.info(f"📊 Рассмотрено кандидатов: {len(candidates)} из {len(self.expert_team)} экспертов")
            
            # Дополнительные эксперты для сложных задач
            additional_experts = []
            if use_multiple and len(candidates) > 1:
                # Выбрать еще 1-2 экспертов (исключая уже выбранного)
                remaining = [(n, d) for n, d in candidates if n != best_expert]
                # Сортировать по score и взять лучших
                remaining_scores = []
                for name, data in remaining:
                    # Простая оценка для дополнительных
                    role_idx = target_roles.index(data.get('role', '')) if data.get('role', '') in target_roles else 999
                    score = (10.0 - role_idx) * 1
                    remaining_scores.append((score, name, data))
                
                remaining_scores.sort(reverse=True)
                for _, name, data in remaining_scores[:2]:  # Максимум 2 дополнительных
                    additional_experts.append((name, data))
                    logger.info(f"  + Дополнительный эксперт: {name} ({data.get('role')})")
            
            # Логируем статистику команды
            if self._expert_team_loaded:
                total_experts = len(self.expert_team)
                unique_roles = len(set(e.get('role', '') for e in self.expert_team.values()))
                logger.info(f"📊 Команда экспертов: {total_experts} экспертов, {unique_roles} уникальных ролей")
            
            additional_list = additional_experts if use_multiple and additional_experts else None
            return best_expert, best_data, additional_list
            
        except Exception as e:
            logger.error(f"❌ Ошибка выбора эксперта: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, None, None
    
    def _task_hash(self, goal: str) -> str:
        """Хеш задачи для кэширования"""
        normalized = " ".join(goal.lower().strip().split())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _get_cached_result(self, goal: str) -> Optional[str]:
        """Получить результат из кэша"""
        if not self.use_cache:
            return None
        
        task_hash = self._task_hash(goal)
        if task_hash in self.task_cache:
            cached_data = self.task_cache[task_hash]
            if datetime.now() - cached_data['timestamp'] < self.cache_ttl:
                logger.info(f"✅ Использован кэш для задачи: {goal[:50]}")
                return cached_data['result']
            else:
                del self.task_cache[task_hash]
        
        return None
    
    def _save_to_cache(self, goal: str, result: str):
        """Сохранить результат в кэш"""
        if not self.use_cache:
            return
        
        task_hash = self._task_hash(goal)
        if result and "ошибка" not in result.lower() and "error" not in result.lower():
            self.task_cache[task_hash] = {
                'result': result,
                'timestamp': datetime.now()
            }
            logger.debug(f"💾 Сохранено в кэш: {goal[:50]}")
    
    async def _learn_from_task(self, goal: str, result: str):
        """Обучение на основе выполненной задачи"""
        pool = await self._get_db_pool()
        if not pool:
            return
        
        try:
            async with pool.acquire() as conn:
                # Проверяем схему таблицы
                columns = await conn.fetch("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'knowledge_nodes'
                """)
                column_names = [row['column_name'] for row in columns]
                
                # Формируем запрос в зависимости от схемы
                if 'source' in column_names and 'metadata' in column_names:
                    # Полная схема с source и metadata
                    await conn.execute("""
                        INSERT INTO knowledge_nodes (content, domain_id, confidence_score, source, metadata)
                        VALUES ($1, (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1), 0.8, 'victoria_agent', $2::jsonb)
                        ON CONFLICT DO NOTHING
                    """, result[:500], json.dumps({
                        "task": goal[:200],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "expert": "Виктория"
                    }))
                elif 'metadata' in column_names:
                    # Схема без source, но с metadata
                    await conn.execute("""
                        INSERT INTO knowledge_nodes (content, domain_id, confidence_score, metadata)
                        VALUES ($1, (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1), 0.8, $2::jsonb)
                        ON CONFLICT DO NOTHING
                    """, result[:500], json.dumps({
                        "task": goal[:200],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "expert": "Виктория",
                        "source": "victoria_agent"
                    }))
                else:
                    # Минимальная схема
                    await conn.execute("""
                        INSERT INTO knowledge_nodes (content, domain_id, confidence_score)
                        VALUES ($1, (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1), 0.8)
                        ON CONFLICT DO NOTHING
                    """, result[:500])
                
                logger.debug(f"📚 Сохранено знание из задачи: {goal[:50]}")
        except Exception as e:
            logger.warning(f"Ошибка сохранения знания: {e}")

    async def orchestrate_task(self, goal: str) -> str:
        """Главный метод оркестрации: анализирует задачу, выбирает стратегию, координирует выполнение
        
        Args:
            goal: Текст задачи
            
        Returns:
            Финальный результат выполнения задачи
        """
        logger.info(f"🎯 Victoria оркестрирует задачу: {goal[:80]}")
        
        # 1. Анализ задачи (быстро, локально)
        complexity = self._assess_complexity(goal)
        category = self._categorize_task(goal)
        
        logger.info(f"📊 Анализ: сложность={complexity}, категория={category}")
        
        # 2. Выбор стратегии
        if complexity == "simple":
            # Простая задача → один эксперт или Veronica
            expert_name, expert_data, _ = await self.select_expert_for_task(goal, use_multiple=False)
            
            if expert_name:
                logger.info(f"✅ Простая задача → делегируем {expert_name}")
                # Для простых задач можно использовать Veronica или эксперта напрямую
                # Пока используем текущий механизм через run()
                result = await self.run(goal, max_steps=500)
                return result
            else:
                # Fallback: выполняем сами
                return await self.run(goal, max_steps=500)
        
        elif complexity == "complex":
            # Сложная задача → Swarm (3-5 экспертов параллельно)
            logger.info("🐝 Сложная задача → Swarm подход")
            primary_expert, primary_data, additional_experts = await self.select_expert_for_task(goal, use_multiple=True)
            
            if not primary_expert:
                # Fallback: выполняем сами
                return await self.run(goal, max_steps=500)
            
            # Собираем команду экспертов
            expert_team = [primary_expert]
            if additional_experts:
                expert_team.extend([name for name, _ in additional_experts[:2]])  # Максимум 3 эксперта
            
            logger.info(f"👥 Swarm команда: {expert_team}")
            
            # Параллельный сбор ответов (через ai_core)
            try:
                # Импортируем ai_core для параллельной обработки
                import sys
                import os
                ai_core_paths = [
                    "/app/app/ai_core.py",
                    "/app/knowledge_os/app/ai_core.py",
                    os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app/ai_core.py"),
                    os.path.join(os.path.dirname(__file__), "../../knowledge_os/app/ai_core.py"),
                ]
                
                ai_core_imported = False
                for path in ai_core_paths:
                    if os.path.exists(path):
                        if os.path.dirname(path) not in sys.path:
                            sys.path.insert(0, os.path.dirname(path))
                        try:
                            from ai_core import run_smart_agent_async
                            ai_core_imported = True
                            break
                        except ImportError:
                            continue
                
                if ai_core_imported:
                    # Услуги сотрудников: краткая справка для экспертов (кто ещё в корпорации)
                    expert_services_line = ""
                    try:
                        for _p in [os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"),
                                  os.path.join(os.path.dirname(__file__), "../../knowledge_os/app"), "/app/knowledge_os/app"]:
                            if os.path.isdir(_p) and _p not in sys.path:
                                sys.path.insert(0, _p)
                        from expert_services import get_expert_services_text
                        expert_services_line = "\n\nКоллеги корпорации (при необходимости согласуй с ними): " + get_expert_services_text(12) + "\n"
                    except ImportError:
                        expert_services_line = "\n"
                    # Параллельный сбор ответов
                    tasks = []
                    for expert_name in expert_team:
                        prompt = f"ВЫ - {expert_name}. Проанализируйте задачу и дайте экспертное заключение.{expert_services_line}\nЗАДАЧА:\n{goal}"
                        tasks.append(run_smart_agent_async(prompt, expert_name=expert_name, category="swarm_expert"))
                    
                    responses = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Фильтруем ошибки
                    valid_responses = []
                    for i, resp in enumerate(responses):
                        if isinstance(resp, Exception):
                            logger.warning(f"⚠️ Эксперт {expert_team[i]} вернул ошибку: {resp}")
                            continue
                        if isinstance(resp, tuple):
                            resp = resp[0] if resp[0] else (resp[1] if len(resp) > 1 else None)
                        if isinstance(resp, dict):
                            resp = resp.get('response', resp.get('text', str(resp)))
                        if resp and isinstance(resp, str) and len(resp.strip()) > 10:
                            valid_responses.append((expert_team[i], resp))
                    
                    if valid_responses:
                        # Услуги сотрудников: справка для Виктории при синтезе (из configs/experts/employees.json)
                        expert_services_line = ""
                        for _path in [
                            os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"),
                            os.path.join(os.path.dirname(__file__), "../../knowledge_os/app"),
                            "/app/knowledge_os/app",
                        ]:
                            if os.path.isdir(_path) and _path not in sys.path:
                                sys.path.insert(0, _path)
                        try:
                            from expert_services import get_expert_services_text
                            expert_services_line = "\n\nУслуги сотрудников корпорации (для справки при синтезе): " + get_expert_services_text(20)
                        except ImportError:
                            expert_services_line = "\n\n(Список экспертов: Павел — стратегия, Мария — риск, Максим — данные, Игорь — код, Виктория — координация.)"
                        # Синтез консенсуса через Victoria
                        synthesis_prompt = f"""ВЫ - ВИКТОРИЯ, TEAM LEAD КОРПОРАЦИИ ATRA.

ЗАДАЧА: {goal}
{expert_services_line}

МНЕНИЯ ЭКСПЕРТОВ:
"""
                        for expert_name, response in valid_responses:
                            synthesis_prompt += f"\n--- {expert_name} ---\n{response}\n"
                        
                        synthesis_prompt += "\n\nЗАДАЧА: Сформируйте финальное, идеальное решение на основе мнений экспертов. Учтите все точки зрения, устраните противоречия, создайте единое решение."
                        
                        final_result = await self.executor.ask(synthesis_prompt, history=[])
                        return final_result if isinstance(final_result, str) else str(final_result)
                    else:
                        logger.warning("⚠️ Нет валидных ответов от экспертов, выполняем сами")
                        return await self.run(goal, max_steps=500)
                else:
                    logger.warning("⚠️ ai_core недоступен, выполняем задачу сами")
                    return await self.run(goal, max_steps=500)
            except Exception as e:
                logger.error(f"❌ Ошибка в Swarm оркестрации: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Fallback: выполняем сами
                return await self.run(goal, max_steps=500)
        
        else:  # multi_department или unknown
            # Межотдельная задача → иерархия (пока упрощенная версия)
            logger.info("🏢 Межотдельная задача → иерархический подход")
            # Пока используем Swarm подход как fallback
            return await self.orchestrate_task(goal)  # Рекурсивно, но с use_multiple=True
        
    def _assess_complexity(self, goal: str) -> str:
        """Оценить сложность задачи
        
        Returns:
            "simple", "complex", или "multi_department"
        """
        goal_lower = goal.lower()
        
        # Ключевые слова для сложных задач
        complex_keywords = [
            "проанализируй", "оптимизируй", "разработай", "создай систему",
            "архитектура", "дизайн", "стратегия", "комплексное",
            "несколько", "множество", "интеграция", "миграция"
        ]
        
        # Ключевые слова для межотдельных задач
        multi_dept_keywords = [
            "backend и frontend", "ml и backend", "devops и security",
            "несколько отделов", "межотдельный", "комплексное решение"
        ]
        
        # Проверка межотдельных
        if any(keyword in goal_lower for keyword in multi_dept_keywords):
            return "multi_department"
        
        # Проверка сложных
        if any(keyword in goal_lower for keyword in complex_keywords):
            return "complex"
        
        # Простые задачи
        simple_keywords = ["скажи", "привет", "покажи", "выведи", "список"]
        if any(keyword in goal_lower for keyword in simple_keywords) and len(goal.split()) <= 10:
            return "simple"
        
        # По умолчанию - сложная (для безопасности)
        return "complex"
    
    async def understand_goal(self, raw_goal: str) -> dict:
        """
        Мировая практика: сначала понять и переформулировать запрос под модули.
        Один быстрый вызов LLM: что хочет пользователь (одно предложение), категория, первый шаг.
        """
        prompt = f"""Запрос пользователя: {raw_goal[:500]}

Задача: переформулировать в одно ясное предложение для исполнителя и указать категорию.
Доступные инструменты исполнителя: только finish, read_file, list_directory, run_terminal_cmd, ssh_run.
Ответь СТРОГО одним JSON (без текста до/после):
{{"restated": "одно предложение: что сделать", "category": "simple|investigate|multi_step", "first_step": "конкретный первый шаг, например: list_directory в frontend, или пустая строка"}}

Пример: "ошибки на странице X, найди и исправь" → {{"restated": "Проверить структуру frontend и найти причину 404 на странице X", "category": "investigate", "first_step": "list_directory в frontend"}}
JSON:"""
        try:
            out = await self.planner.ask(prompt, raw_response=True)
            if not out or not isinstance(out, str):
                return {"restated": raw_goal, "category": "multi_step", "first_step": ""}
            out = out.strip()
            start = out.find("{")
            end = out.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(out[start:end])
                _r = data.get("restated") or raw_goal
                restated = (_r if isinstance(_r, str) else str(_r)).strip()
                _c = data.get("category") or "multi_step"
                category = (_c if isinstance(_c, str) else str(_c)).strip().lower()
                if category not in ("simple", "investigate", "multi_step"):
                    category = "multi_step"
                _f = data.get("first_step") or ""
                first_step = (_f if isinstance(_f, str) else str(_f)).strip()
                return {"restated": restated, "category": category, "first_step": first_step[:200]}
        except Exception as e:
            logger.debug("understand_goal parse failed: %s", e)
        return {"restated": raw_goal, "category": "multi_step", "first_step": ""}
    
    async def plan(self, goal: str):
        if goal.lower() not in ["повтори", "еще раз", "давай заново"]:
            self.memory = []
            self.executed_commands_hash = []
        
        # Определить сложность задачи (для выбора нескольких экспертов)
        is_complex = any(keyword in goal.lower() for keyword in [
            "проанализируй", "оптимизируй", "разработай стратегию", "создай архитектуру",
            "комплексное", "полное решение", "несколько", "команда"
        ])
        
        # Параллельно: эксперт + контекст RAG (ракетная скорость)
        expert_name = None
        expert_data = None
        additional_experts = None
        knowledge_context = ""
        if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE:
            expert_fut = self.select_expert_for_task(goal, use_multiple=is_complex)
            context_fut = self._get_knowledge_context(goal)
            expert_result, knowledge_context = await asyncio.gather(expert_fut, context_fut)
            expert_name, expert_data, additional_experts = expert_result
            if knowledge_context is None:
                knowledge_context = ""
        
        # Формировать промпт с учетом эксперта(ов)
        if expert_name and expert_data:
            expert_info = f"\nЭКСПЕРТ ДЛЯ ЗАДАЧИ: {expert_name} ({expert_data.get('role', 'Expert')})"
            if expert_data.get('system_prompt'):
                expert_info += f"\nЗНАНИЯ ЭКСПЕРТА: {expert_data['system_prompt'][:300]}..."
            
            # Добавить информацию о дополнительных экспертах для сложных задач
            if additional_experts:
                expert_info += f"\n\nДОПОЛНИТЕЛЬНЫЕ ЭКСПЕРТЫ ДЛЯ КОНСУЛЬТАЦИИ:"
                for add_name, add_data in additional_experts:
                    expert_info += f"\n- {add_name} ({add_data.get('role', 'Expert')})"
        else:
            expert_info = ""
        
        plan_prompt = f"""ТЫ — ВИКТОРИЯ, TEAM LEAD КОРПОРАЦИИ ATRA.{expert_info}

{knowledge_context}

ЗАДАЧА: {goal}

КРИТИЧЕСКИ ВАЖНО:
- План должен быть МАКСИМАЛЬНО ПРОСТЫМ (1 шаг для простых задач)
- НЕ добавляй дополнительные требования (".txt", "за 24 часа", "база данных" и т.д.)
- НЕ придумывай сложные действия если задача простая
- Выполняй ТОЧНО то что просят, ничего лишнего

ПРАВИЛА:
- "скажи привет" → План: "Ответить приветствием"
- "покажи файлы" / "выведи список файлов" → План: "Выполнить ls -la"
- "прочитай файл X" → План: "Прочитать файл X"
- НЕ добавляй шаги с базой данных, SSH, поиском если их не просили!

ПРИМЕРЫ:
Q: "скажи привет" → План: "Ответить приветствием"
Q: "выведи список файлов" → План: "Выполнить ls -la"
Q: "покажи файлы в текущей директории" → План: "Выполнить ls -la"

ПЛАН (только 1-2 шага, максимально просто):"""
        return await self.planner.ask(plan_prompt, raw_response=True)

    async def _select_model_for_task(self, goal: str) -> str:
        """Выбрать оптимальную модель для задачи на основе категории"""
        try:
            # Определяем категорию задачи
            category = self._categorize_task(goal)
            goal_lower = goal.lower()
            
            # Маппинг категорий на модели из PLAN.md
            model_map = {
                "backend": ["qwen2.5-coder:32b", "phi3.5:3.8b", "qwen2.5:3b", "tinyllama:1.1b-chat"],
                "frontend": ["qwen2.5-coder:32b", "phi3.5:3.8b", "qwen2.5:3b", "tinyllama:1.1b-chat"],
                "ml": ["deepseek-r1-distill-llama:70b", "llama3.3:70b", "qwen2.5-coder:32b", "phi3.5:3.8b"],
                "devops": ["qwen2.5-coder:32b", "phi3.5:3.8b", "qwen2.5:3b"],
                "security": ["command-r-plus:104b", "llama3.3:70b", "deepseek-r1-distill-llama:70b"],
                "database": ["qwen2.5-coder:32b", "phi3.5:3.8b", "qwen2.5:3b"],
                "performance": ["qwen2.5-coder:32b", "phi3.5:3.8b"],
                "general": ["qwen2.5-coder:32b", "phi3.5:3.8b", "qwen2.5:3b", "tinyllama:1.1b-chat"]
            }
            
            # Определяем тип задачи для выбора модели
            if any(word in goal_lower for word in ["код", "программируй", "напиши код", "coding"]):
                priorities = model_map.get("backend", model_map["general"])
            elif any(word in goal_lower for word in ["реши", "рассчитай", "reasoning", "логика"]):
                priorities = ["deepseek-r1-distill-llama:70b", "llama3.3:70b", "qwen2.5-coder:32b", "phi3.5:3.8b"]
            elif any(word in goal_lower for word in ["сложн", "комплекс", "complex", "enterprise"]):
                priorities = ["command-r-plus:104b", "llama3.3:70b", "deepseek-r1-distill-llama:70b", "qwen2.5-coder:32b"]
            elif len(goal.split()) <= 5:  # Простые задачи — всё равно берём из general (меньше галлюцинаций)
                priorities = model_map.get("general", model_map["general"])
            else:
                priorities = model_map.get(category, model_map["general"])
            
            # Проверяем доступность моделей
            try:
                import sys
                selector_paths = [
                    "/app/app/model_selector.py",
                    os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app/model_selector.py"),
                    os.path.join(os.path.dirname(__file__), "../../knowledge_os/app/model_selector.py"),
                ]
                for path in selector_paths:
                    if os.path.exists(path):
                        if os.path.dirname(path) not in sys.path:
                            sys.path.insert(0, os.path.dirname(path))
                        try:
                            from app.model_selector import select_available_model
                            selected = await select_available_model(priorities, self.executor.base_url, category)
                            if selected:
                                logger.info(f"🎯 Выбрана модель для категории '{category}': {selected}")
                                return selected
                        except ImportError:
                            continue
            except Exception as e:
                logger.debug(f"Model selector недоступен: {e}")
            
            # Fallback: используем текущую модель
            return self.executor.model
        except Exception as e:
            logger.warning(f"⚠️ Ошибка выбора модели: {e}, используем {self.executor.model}")
            return self.executor.model
    
    async def step(self, prompt: str):
        context_memory = self.memory[-10:] if len(self.memory) > 10 else self.memory
        
        # Попытка использовать LocalAIRouter (MLX) если доступен
        if self.local_router:
            try:
                # Формируем system_prompt из executor; передаём модель — роутер попробует MLX и Ollama
                system_prompt = self.executor.system_prompt
                # category=None → LocalAIRouter сам определит из промпта (fast/general/reasoning/coding)
                # Это даёт автовыбор модели из MLX/Ollama в зависимости от сложности запроса
                result, routing_source = await self.local_router.run_local_llm(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    category=None,  # автоопределение как в ai_core и worker
                    model=getattr(self.executor, "model", None)
                )
                if result and routing_source:
                    logger.debug(f"✅ Victoria использовала {routing_source} через LocalAIRouter")
                    # Парсим ответ через executor для единообразия
                    parsed = self.executor._parse_response(result)
                    return parsed
            except Exception as e:
                logger.debug(f"⚠️ LocalAIRouter недоступен в step(): {e}, используем Ollama")
        
        # Fallback: используем стандартный OllamaExecutor
        return await self.executor.ask(prompt, history=context_memory)

    async def _ensure_best_available_models(self) -> None:
        """
        Один раз за сессию: сканируем Ollama и MLX РАЗДЕЛЬНО.
        
        ВАЖНО: 
        - Ollama и MLX модели НЕ смешиваются!
        - Executor/Planner ходят в Ollama API → выбираем только из Ollama
        - LocalAIRouter может использовать оба → для него MLX модели тоже важны
        """
        logger.info("[MODEL_SELECT] " + "=" * 60)
        logger.info("[MODEL_SELECT] СКАНИРОВАНИЕ МОДЕЛЕЙ (Ollama и MLX РАЗДЕЛЬНО)")
        logger.info("[MODEL_SELECT] " + "=" * 60)
        
        if getattr(self, "_models_resolved", True):
            logger.info("[MODEL_SELECT] Models already resolved. Current:")
            logger.info("[MODEL_SELECT]    Planner: %s", getattr(self.planner, 'model', 'unknown'))
            logger.info("[MODEL_SELECT]    Executor: %s", getattr(self.executor, 'model', 'unknown'))
            return
        
        try:
            # Определяем URLs
            is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
            if is_docker:
                mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
                ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
            else:
                mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")
                ollama_url = getattr(self.executor, "base_url", None) or _ollama_base_url()
            
            logger.info("[MODEL_SELECT] Ollama URL: %s", ollama_url)
            logger.info("[MODEL_SELECT] MLX URL: %s", mlx_url)
            
            # Добавляем путь к knowledge_os
            for path in ["/app/knowledge_os/app", os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"), os.path.join(os.path.dirname(__file__), "../../knowledge_os/app")]:
                if path and os.path.exists(path) and path not in sys.path:
                    sys.path.insert(0, path)
            
            try:
                from app.available_models_scanner import scan_and_select_models, pick_best_ollama  # type: ignore
            except ImportError:
                from available_models_scanner import scan_and_select_models, pick_best_ollama  # type: ignore
            
            # Сканируем модели РАЗДЕЛЬНО
            selection = await scan_and_select_models(mlx_url, ollama_url, force_refresh=True)
            
            # Сохраняем списки для других компонентов
            self._ollama_models = selection.ollama_models
            self._mlx_models = selection.mlx_models
            self._best_ollama = selection.ollama_best
            self._best_mlx = selection.mlx_best
            
            logger.info("[MODEL_SELECT] " + "-" * 60)
            logger.info("[MODEL_SELECT] 🔵 OLLAMA МОДЕЛИ (для executor/planner):")
            logger.info("[MODEL_SELECT]    Доступно: %d", len(selection.ollama_models))
            logger.info("[MODEL_SELECT]    Список: %s", selection.ollama_models)
            logger.info("[MODEL_SELECT]    Лучшая: %s", selection.ollama_best or "(нет)")
            logger.info("[MODEL_SELECT] " + "-" * 60)
            logger.info("[MODEL_SELECT] 🟢 MLX МОДЕЛИ (для LocalAIRouter):")
            logger.info("[MODEL_SELECT]    Доступно: %d", len(selection.mlx_models))
            logger.info("[MODEL_SELECT]    Список: %s", selection.mlx_models)
            logger.info("[MODEL_SELECT]    Лучшая: %s", selection.mlx_best or "(нет)")
            logger.info("[MODEL_SELECT] " + "-" * 60)
            
            # Выбор модели для executor/planner (ТОЛЬКО из Ollama!)
            env_model = os.getenv("VICTORIA_MODEL", "").strip()
            env_planner = os.getenv("VICTORIA_PLANNER_MODEL", "").strip()
            
            # Проверяем env модели в Ollama списке
            ollama_lower_to_exact = {m.strip().lower(): m.strip() for m in selection.ollama_models if m}
            
            # Executor model
            executor_model = None
            if env_model:
                if env_model.strip().lower() in ollama_lower_to_exact:
                    executor_model = ollama_lower_to_exact[env_model.strip().lower()]
                    logger.info("[MODEL_SELECT] ✅ VICTORIA_MODEL='%s' найдена в Ollama", executor_model)
                else:
                    logger.warning("[MODEL_SELECT] ⚠️ VICTORIA_MODEL='%s' НЕ НАЙДЕНА в Ollama!", env_model)
                    logger.warning("[MODEL_SELECT]    Доступные Ollama модели: %s", list(ollama_lower_to_exact.keys()))
            
            if not executor_model:
                # Предпочитаем qwen2.5-coder:32b для executor (качество) или glm-4.7-flash
                preferred_executor = ["qwen2.5-coder:32b", "glm-4.7-flash:q8_0", "phi3.5:3.8b"]
                for pref in preferred_executor:
                    if pref.lower() in ollama_lower_to_exact:
                        executor_model = ollama_lower_to_exact[pref.lower()]
                        break
                if not executor_model:
                    executor_model = selection.ollama_best
                logger.info("[MODEL_SELECT] Используем Ollama модель для executor: %s", executor_model)
            
            # Planner model - используем БЫСТРУЮ модель для плпланирования!
            # Это критично для отзывчивости Victoria
            planner_model = None
            if env_planner:
                if env_planner.strip().lower() in ollama_lower_to_exact:
                    planner_model = ollama_lower_to_exact[env_planner.strip().lower()]
                    logger.info("[MODEL_SELECT] ✅ VICTORIA_PLANNER_MODEL='%s' найдена в Ollama", planner_model)
                else:
                    logger.warning("[MODEL_SELECT] ⚠️ VICTORIA_PLANNER_MODEL='%s' НЕ НАЙДЕНА в Ollama!", env_planner)
            
            if not planner_model:
                # Предпочитаем БЫСТРУЮ модель для planner (отзывчивость важнее качества для планирования)
                preferred_planner = ["phi3.5:3.8b", "glm-4.7-flash:q8_0", "tinyllama:1.1b-chat"]
                for pref in preferred_planner:
                    if pref.lower() in ollama_lower_to_exact:
                        planner_model = ollama_lower_to_exact[pref.lower()]
                        logger.info("[MODEL_SELECT] Используем быструю модель для planner: %s", planner_model)
                        break
                if not planner_model:
                    planner_model = executor_model  # Fallback на executor
            
            # Применяем выбранные модели
            if executor_model:
                old_executor = getattr(self.executor, 'model', 'unknown')
                old_planner = getattr(self.planner, 'model', 'unknown')
                
                self.executor.model = executor_model
                self.planner.model = planner_model
                
                logger.info("[MODEL_SELECT] " + "=" * 60)
                logger.info("[MODEL_SELECT] ✅ МОДЕЛИ ВЫБРАНЫ:")
                logger.info("[MODEL_SELECT]    Executor: %s → %s", old_executor, executor_model)
                logger.info("[MODEL_SELECT]    Planner: %s → %s", old_planner, planner_model)
                logger.info("[MODEL_SELECT]    (Для LocalAIRouter доступна MLX: %s)", selection.mlx_best or "нет")
                logger.info("[MODEL_SELECT] " + "=" * 60)
            else:
                logger.error("[MODEL_SELECT] ❌ Нет доступных моделей в Ollama!")
                logger.info("[MODEL_SELECT] Проверьте: curl %s/api/tags", ollama_url)
            
            self._models_resolved = True
            
        except Exception as e:
            logger.error("[MODEL_SELECT] ❌ Ошибка при сканировании моделей: %s", e)
            import traceback
            logger.error(traceback.format_exc())
            self._models_resolved = True

    async def run(self, goal: str, max_steps: Optional[int] = None) -> str:
        logger.info("[AGENT_RUN] ========== VictoriaAgent.run() ==========")
        logger.info("[AGENT_RUN] Goal: %s", goal[:150] if goal else "(empty)")
        logger.info("[AGENT_RUN] Max steps: %s", max_steps or DEFAULT_MAX_STEPS)
        
        if max_steps is None:
            max_steps = DEFAULT_MAX_STEPS
        # Проверка кэша
        cached_result = self._get_cached_result(goal)
        if cached_result:
            logger.info("[AGENT_RUN] Cache hit! Returning cached result")
            return cached_result

        goal_lower = (goal or "").strip().lower()
        try:
            # Быстрый путь: простые приветствия — сразу ответ (полный цикл без зависания на LLM)
            if goal_lower in ("привет", "скажи привет", "здравствуй", "здравствуйте", "как дела", "что нового"):
                logger.info("[AGENT_RUN] Fast path: greeting detected, returning hardcoded response")
                return "Привет! Я Виктория, Team Lead корпорации ATRA. Чем могу помочь?"
            # Быстрый путь: покажи файлы — одна команда ls и ответ
            if "покажи файлы" in goal_lower or "выведи список файлов" in goal_lower or "список файлов" in goal_lower:
                logger.info("[AGENT_RUN] Fast path: file listing detected")
                tool = self.tools.get("run_terminal_cmd")
                if tool:
                    out = await tool(command="ls -la")
                    return (out if isinstance(out, str) else str(out)) or "Список файлов получен."
        except Exception as e:
            logger.warning("[AGENT_RUN] Fast path error: %s", e)
            # не поднимаем — идём в обычный цикл
        
        # Один раз: подставить лучшую доступную модель из Ollama+MLX (актуальный список)
        logger.info("[AGENT_RUN] Calling _ensure_best_available_models()...")
        await self._ensure_best_available_models()
        logger.info("[AGENT_RUN] After model selection: executor=%s, planner=%s", 
                   self.executor.model, self.planner.model)
        
        # Фаза 1: понять и переформулировать запрос под модули (мировая практика)
        logger.info("[AGENT_RUN] Phase 1: Understanding goal via planner...")
        understood = await self.understand_goal(goal)
        restated = understood.get("restated") or goal
        category = understood.get("category") or "multi_step"
        first_step_hint = (understood.get("first_step") or "").strip()
        
        logger.info("[AGENT_RUN] Understood: category=%s, restated=%s", category, restated[:100])
        
        if restated != goal:
            logger.info("[AGENT_RUN] 📝 Restated: %s → %s", goal[:60], restated[:60])
        
        # Выбираем оптимальную модель для задачи (по переформулированной цели)
        optimal_model = await self._select_model_for_task(restated)
        if optimal_model and optimal_model != self.executor.model:
            logger.info("[AGENT_RUN] 🎯 Model change: %s → %s", self.executor.model, optimal_model)
            self.executor.model = optimal_model
        
        # Простые/короткие или category=simple — без планировщика
        simple_tasks = ["скажи", "привет", "покажи файлы", "выведи список", "список файлов"]
        goal_lower = restated.lower()
        words = restated.split()
        is_short = len(words) <= 12
        is_simple_phrase = any(task in goal_lower for task in simple_tasks) and len(words) <= 10
        is_info_question = is_short and any(
            w in goal_lower for w in ["сколько", "какой", "какая", "когда", "статус", "задач", "в работе", "что сейчас"]
        )
        
        if is_simple_phrase or is_info_question or category == "simple":
            logger.info("[AGENT_RUN] Simple task path (no planner)")
            hint = f"\nПервый шаг (если нужен): {first_step_hint}." if first_step_hint else ""
            enhanced = f"ВЫПОЛНИ ЗАДАЧУ: {restated}{hint}\n\nВАЖНО: Ответь кратко. Только JSON: {{\"thought\": \"...\", \"tool\": \"finish\" или один инструмент, \"tool_input\": {{...}}}}."
        else:
            logger.info("[AGENT_RUN] Complex task path (with planner)")
            raw_plan = await self.plan(restated)
            _rp = (raw_plan if isinstance(raw_plan, str) else str(raw_plan) if raw_plan is not None else "") or ""
            _rp = _rp.strip()
            logger.info("[AGENT_RUN] Raw plan length: %d chars", len(_rp))
            if (
                len(_rp) > 600
                or "Дополнительная сложность" in _rp
                or "Ollama HTTP" in _rp
            ):
                raw_plan = f"Выполнить: {restated}"
                logger.info("[AGENT_RUN] Plan rejected (too long or garbage), using simple plan")
            else:
                raw_plan = _rp
            hint = f"\nПервый шаг (рекомендация): {first_step_hint}." if first_step_hint else ""
            enhanced = f"ТВОЙ ПЛАН:\n{raw_plan}\n\nПРИСТУПАЙ К ВЫПОЛНЕНИЮ: {restated}{hint}"
        
        logger.info("[AGENT_RUN] Enhanced prompt length: %d chars", len(enhanced))
        logger.info("[AGENT_RUN] Calling super().run() with model: %s", self.executor.model)
        
        result = await super().run(enhanced, max_steps)
        
        logger.info("[AGENT_RUN] super().run() returned, result length: %d chars", len(str(result)) if result else 0)
        logger.info("[AGENT_RUN] Result preview: %s...", str(result)[:200] if result else "(empty)")
        
        # Сохранить в кэш
        self._save_to_cache(goal, result)
        
        # Сохранить в Knowledge OS для обучения (если включено)
        if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE and result:
            await self._learn_from_task(goal, result)
        
        logger.info("[AGENT_RUN] ========== run() complete ==========")
        
        return result


agent = VictoriaAgent(name="Виктория")

agent.executor.system_prompt = """ТЫ — ВИКТОРИЯ, TEAM LEAD КОРПОРАЦИИ ATRA. ТЫ ИСПОЛЬЗУЕШЬ VICTORIA ENHANCED.

КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском языке! Все ответы должны быть на русском!

🌟 ТВОИ VICTORIA ENHANCED ВОЗМОЖНОСТИ:
- ReAct Framework: Reasoning + Acting для сложных задач
- Extended Thinking: Глубокое рассуждение
- Swarm Intelligence: Параллельная работа команды экспертов
- Consensus: Согласование мнений экспертов
- Collective Memory: Использование накопленных знаний
- Tree of Thoughts: Поиск оптимального решения
- Hierarchical Orchestration: Иерархическая координация
- ReCAP Framework: Reasoning, Context, Action, Planning

ТЫ АВТОМАТИЧЕСКИ ВЫБИРАЕШЬ ОПТИМАЛЬНЫЙ МЕТОД для каждой задачи.

Доступны ТОЛЬКО инструменты: read_file, list_directory, run_terminal_cmd, ssh_run, finish. НЕТ: web_search, web_edit, git_run, write_file, web_review. Пути — только реальные (., frontend, backend), НЕ /path/to/.

ПРАВИЛА:
- Не придумывай инструменты и пути. Один ответ — один JSON: {"thought": "...", "tool": "...", "tool_input": {...}}
- Перед завершением проверяй результат (ls, cat). Не выводи длинные планы — выполняй шаги и завершай finish.
"""


def _extract_last_answer_from_long(s: str) -> str:
    """Из длинного вывода извлечь последний осмысленный результат: answer или output."""
    import re
    last_m = None
    for pattern in (r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', r'"output"\s*:\s*"((?:[^"\\]|\\.)*)"'):
        for m in re.finditer(pattern, s):
            if last_m is None or m.start() > last_m.start():
                last_m = m
    if last_m:
        try:
            out = last_m.group(1).replace("\\n", "\n").replace('\\"', '"')
            if out and len(out) < 3000:
                return out
        except Exception:
            pass
    return ""


def _strip_internal_monologue(text: str) -> str:
    """
    Убрать из вывода «внутренние» рассуждения модели (про finish, output, I will try)
    и оставить только итоговый ответ (FINAL ANSWER / Итог: / Вот краткий отчёт:).
    """
    import re
    s = text.strip()
    if not s or len(s) < 200:
        return s
    # Извлечь блок после последнего «FINAL ANSWER» / «Итог:» / «Вот краткий отчёт:»
    for marker in ("FINAL ANSWER:", "FINAL ANSWER：", "Итог:", "Вот краткий отчёт:", "Кратко:", "Ответ:"):
        idx = s.rfind(marker)
        if idx != -1:
            out = s[idx + len(marker):].strip()
            # Убрать повторяющиеся абзацы (одинаковые строки подряд)
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            seen = set()
            unique = []
            for ln in lines:
                if ln not in seen and len(ln) > 10:
                    seen.add(ln)
                    unique.append(ln)
            if unique:
                result = "\n\n".join(unique[:5])  # не более 5 абзацев
                if len(result) <= 1500:
                    return result
                return result[:1500].rstrip() + "\n\n[...]"
    # Признаки внутреннего монолога (рассуждения про finish/output)
    monologue_markers = (
        "call finish without the output",
        "finish without the output parameter",
        "I need to provide the output parameter",
        "Now I will try to do everything correctly",
        "Окей, понял что нужно",
        "вызываю finish без параметра output",
        "не могу сделать из-за ошибок в использовании функции finish",
    )
    if any(m in s for m in monologue_markers) and len(s) > 400:
        # Вернуть короткое сообщение вместо сырого монолога
        return (
            "Виктория обработала запрос, но модель вернула служебные рассуждения вместо краткого ответа. "
            "Попробуйте переформулировать вопрос короче (например: «что ты умеешь?», «перечисли свои возможности»)."
        )
    return s


async def _try_corporation_data_quick_response(goal: str, correlation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Если goal — вопрос о данных (метрики Mac Studio, корпорация), сразу отвечаем через corporation_data_tool.
    Используется до выбора enhanced/agent, чтобы не упираться в лимит 500 шагов на старом агенте.
    """
    if not (goal or "").strip():
        return None
    ko_paths = [
        "/app/knowledge_os",
        os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../knowledge_os")),
    ]
    for ko_root in ko_paths:
        if not os.path.exists(ko_root) and not ko_root.startswith("/app"):
            continue
        if ko_root not in sys.path:
            sys.path.insert(0, ko_root)
        app_path = os.path.join(ko_root, "app")
        if app_path not in sys.path:
            sys.path.insert(0, app_path)
        try:
            from app.corporation_data_tool import is_data_question, query_corporation_data, _extract_latest_user_message
            q = _extract_latest_user_message(goal) or goal
            if not is_data_question(goal) and not is_data_question(q):
                return None
            logger.info("[CORP_DATA] Ранний ответ через corporation_data_tool (goal=%s...)", (goal or "")[:60])
            corp_result = await query_corporation_data(q)
            answer = corp_result.get("answer") or ""
            if not answer:
                return None
            knowledge = {
                "method": "simple",
                "metadata": {"source": "corporation_data_tool", "fast_mode": True},
                "correlation_id": correlation_id,
            }
            return {"output": answer, "knowledge": knowledge}
        except ImportError:
            continue
        except Exception as e:
            logger.warning("[CORP_DATA] corporation_data_tool: %s", e)
            return None
    return None


def _normalize_output_for_user(raw: Any) -> str:
    """Из сырого ответа агента (dict/str) извлечь текст для пользователя. Избегает вывода {'thought':..., 'tool':...}."""
    if raw is None:
        return ""
    # Пустой успех: не отдавать подставную строку (план п.4 — TASK_ARCHITECTURE_WHY_EMPTY_RESULT)
    _s = (raw.get("result") if isinstance(raw, dict) else raw) if raw else ""
    if isinstance(_s, str) and _s.strip() and "Задача выполнена экспертом" in _s and "(статус: finish)" in _s:
        return (
            "Эксперт завершил задачу без вывода (модель вызвала finish без результата). "
            "Система при следующем запросе может повторить попытку с разбивкой на подзадачи. Рекомендуется уточнить задачу."
        )
    if not isinstance(raw, (str, dict)):
        return str(raw) if raw is not None else ""
    if isinstance(raw, str):
        s = raw.strip()
        if s and "Задача выполнена экспертом" in s and "(статус: finish)" in s:
            return (
                "Эксперт завершил задачу без вывода (модель вызвала finish без результата). "
                "Система при следующем запросе может повторить попытку с разбивкой на подзадачи. Рекомендуется уточнить задачу."
            )
        # Признаки вымысла/шлака: длинный текст с планами, несуществующими инструментами, галлюцинациями
        garbage_markers = (
            "Дополнительная сложность", "ТВОЙ ПЛАН:", "ПРИСТУПАЙ К ВЫПОЛНЕНИЮ",
            "СОБИРЕХТ", "Python для школьников", "Collective Memory", "ReCAP Framework",
            "Tree of Thoughts", "Swarm Intelligence", "/path/to/", "web_edit", "git_run", "web_review", "action: {",
            "tool_execution", "final_output", "git_search", "web_check", "git_commit", "websocket",
            "Врачебная задача", "СЕДАРДАН", "CMP", "ЗАПИТАНЯ", "ОБРАТУРЫ",
            "psych_assessment", "patient_interview", "therapy_technique", "ethical_dilemma", "empathetic_communication",
            "web_search", "swarm_intelligence", "consensus", "tree_of_thoughts",
        )
        is_likely_garbage = len(s) > 800 and any(m in s for m in garbage_markers)
        if is_likely_garbage:
            last = _extract_last_answer_from_long(s)
            if last and len(last) < 2000 and not any(m in last for m in garbage_markers):
                return last
            # Показываем усечённый ответ вместо полного скрытия — пользователь видит часть результата/действий
            head = 700
            tail = 400
            footer = "\n\n💡 Если выше только план без действий — задайте один шаг: «покажи файлы в frontend» или «найди ошибки в frontend»."
            if len(s) <= head + tail:
                return s.strip() + footer
            return s[:head].rstrip() + "\n\n[...]\n\n" + s[-tail:].lstrip() + footer
        # Убрать внутренний монолог модели (рассуждения про finish/output) и оставить итоговый ответ
        if len(s) > 300:
            cleaned = _strip_internal_monologue(s)
            if cleaned != s:
                s = cleaned
                if len(s) > 1200:
                    return s[:1200].rstrip() + "\n\n[...]"
                return s
        # Жёсткий лимит длины
        if len(s) > 1200:
            return s[:1200].rstrip() + "\n\n[... ответ обрезан ...]"
        if s.startswith("{") and ("thought" in s or "tool" in s):
            try:
                data = json.loads(s) if s.startswith("{") else None
            except json.JSONDecodeError:
                try:
                    import ast
                    data = ast.literal_eval(s)
                except Exception:
                    return raw
            if isinstance(data, dict):
                ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
                out = (ti.get("output") if ti else None) or data.get("thought") or data.get("response") or data.get("message") or data.get("output")
                return (out if isinstance(out, str) else str(out)) if out else raw
        return raw
    if isinstance(raw, dict):
        ti = raw.get("tool_input") if isinstance(raw.get("tool_input"), dict) else {}
        out = (ti.get("output") if ti else None) or raw.get("thought") or raw.get("response") or raw.get("message") or raw.get("output")
        return (out if isinstance(out, str) else str(out)) if out else json.dumps(raw, ensure_ascii=False)
    return str(raw)


def _build_orchestration_context(bridge_result: Optional[Dict[str, Any]]) -> str:
    """
    Мировая практика: оркестратор распределяет и составляет план; Victoria использует его при выполнении.
    Строит текст плана/назначений из ответа оркестратора для передачи в контекст LLM.
    """
    if not bridge_result or not isinstance(bridge_result, dict):
        return ""
    parts = []
    strategy = bridge_result.get("strategy")
    if strategy:
        parts.append(f"Стратегия оркестратора: {strategy}")
    assignments = bridge_result.get("assignments") or {}
    if assignments:
        lines = []
        for k, v in assignments.items() if isinstance(assignments, dict) else []:
            if isinstance(v, dict):
                name = v.get("expert_name") or v.get("expert_id") or k
                models = v.get("assigned_models")
                line = f"  • {k}: {name}"
                if models:
                    line += f" (модели: {models})"
                lines.append(line)
            else:
                lines.append(f"  • {k}: {v}")
        if lines:
            parts.append("Назначения оркестратора:\n" + "\n".join(lines))
    execution_order = bridge_result.get("execution_order")
    if execution_order:
        parts.append(f"Порядок выполнения: {execution_order}")
    if not parts:
        return ""
    return "План от оркестратора (следуй ему):\n" + "\n".join(parts)


def _orchestrator_recommends_veronica(bridge_result: Optional[Dict[str, Any]]) -> bool:
    """Проверяет, рекомендует ли оркестратор Veronica как исполнителя (по назначениям)."""
    if not bridge_result or not isinstance(bridge_result, dict):
        return False
    assignments = bridge_result.get("assignments") or {}
    if not isinstance(assignments, dict):
        return False
    # main или первый подзадача
    for key in ("main",) + tuple(k for k in assignments if k != "main"):
        v = assignments.get(key)
        if isinstance(v, dict):
            name = (v.get("expert_name") or v.get("expert_id") or "").lower()
            if "veronica" in name or "вероника" in name:
                return True
    return False


def _sanitize_goal_for_prompt(goal: str) -> str:
    """
    Убирает из текста цели упоминания несуществующих инструментов,
    чтобы модель не подхватывала их в ответе. Используются только
    finish, read_file, list_directory, run_terminal_cmd, ssh_run.
    """
    if not goal or not isinstance(goal, str):
        return goal
    # Упоминания инструментов-галлюцинаций заменяем на нейтральное
    hallucinated = [
        "web_search", "swarm_intelligence", "consensus", "tree_of_thoughts",
        "psych_assessment", "patient_interview", "therapy_technique",
        "ethical_dilemma", "empathetic_communication", "web_edit", "git_run",
        "web_review", "web_check", "git_commit", "websocket",
    ]
    s = goal
    for tool in hallucinated:
        if tool in s:
            s = s.replace(tool, "[инструмент недоступен]")
    return s


def _check_ambiguity(goal: str, category: str, restated: str) -> bool:
    """
    Эвристическая проверка неоднозначности задачи.
    Возвращает True, если нужны уточняющие вопросы (не выполнять задачу сразу).
    """
    goal_lower = goal.lower().strip()
    # Явно простые команды — никогда не запрашивать уточнение (полный цикл без остановки)
    simple_phrases = [
        "скажи привет", "привет", "здравствуй", "как дела", "что нового",
        "покажи файлы", "выведи список файлов", "список файлов", "покажи файлы в",
        "да", "нет",
    ]
    if any(phrase in goal_lower or goal_lower in phrase for phrase in simple_phrases):
        return False
    if len(goal_lower.split()) <= 3 and any(w in goal_lower for w in ["привет", "файл", "список", "скажи", "покажи"]):
        return False
    ambiguity_indicators = [
        len(goal.split()) < 3,
        any(w in goal_lower for w in ["он", "она", "оно", "они", "это", "то"]),
        any(w in goal_lower for w in ["что-то", "какой-то", "кое-что", "где-то"]),
        category == "multi_step" and len(goal) < 50,
        goal.count("но") > 1 or "однако" in goal_lower,
    ]
    return sum(ambiguity_indicators) >= 2


async def _generate_clarification_questions(agent: "VictoriaAgent", goal: str, restated: str) -> List[str]:
    """Генерация 1–3 уточняющих вопросов через planner LLM."""
    prompt = f'''Пользователь просит: "{goal[:300]}"
Переформулировка системы: "{restated[:200]}"
Задача неоднозначна. Дай 2–3 кратких уточняющих вопроса (на русском).
Ответь СТРОГО JSON: {{"questions": ["Вопрос 1?", "Вопрос 2?"]}}'''
    try:
        out = await agent.planner.ask(prompt, raw_response=True)
        if not out or not isinstance(out, str):
            raise ValueError("empty response")
        start = out.find("{")
        end = out.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(out[start:end])
            questions = data.get("questions") or []
        else:
            questions = [q.strip() for q in out.split("\n") if q.strip().endswith("?")][:3]
        questions = [q[:200] for q in questions if isinstance(q, str) and 10 < len(q) <= 200][:3]
    except Exception:
        questions = []
    if not questions:
        questions = [
            "Можете уточнить, что именно нужно сделать?",
            "Какие требования к результату?",
            "Есть ли ограничения или условия?",
        ]
    return questions[:3]


async def _understand_goal_with_clarification(agent: "VictoriaAgent", goal: str) -> dict:
    """
    Понимание цели с проверкой неоднозначности.
    Возвращает dict с restated, category, first_step и при необходимости needs_clarification + clarification_questions.
    """
    understood = await agent.understand_goal(goal)
    _r = understood.get("restated") or goal
    restated = (_r if isinstance(_r, str) else str(_r) or goal).strip()
    _c = understood.get("category") or "multi_step"
    category = (_c if isinstance(_c, str) else str(_c)).strip().lower()
    _f = understood.get("first_step") or ""
    first_step = (_f if isinstance(_f, str) else str(_f)).strip()
    if _check_ambiguity(goal, category, restated):
        questions = await _generate_clarification_questions(agent, goal, restated)
        return {
            "needs_clarification": True,
            "clarification_questions": questions,
            "original_goal": goal,
            "restated": restated,
            "category": category,
            "first_step": first_step[:200],
        }
    return {
        "needs_clarification": False,
        "restated": restated,
        "category": category,
        "first_step": first_step[:200],
    }


class TaskRequest(BaseModel):
    goal: str
    max_steps: Optional[int] = None  # None = использовать DEFAULT_MAX_STEPS (env VICTORIA_MAX_STEPS, по умолчанию 500)
    project_context: Optional[str] = None  # Контекст проекта (atra-web-ide, atra, и т.д.)
    session_id: Optional[str] = None  # ID сессии для памяти чата
    chat_history: Optional[List[Dict[str, str]]] = None  # История чата


class TaskResponse(BaseModel):
    status: str
    output: Any
    knowledge: Optional[dict] = None
    correlation_id: Optional[str] = None


async def _record_orchestration_task_start(agent, goal: str, orchestrator_version: str) -> Optional[str]:
    """Записать старт задачи в knowledge_os.tasks для A/B метрик. Возвращает task_id (UUID) или None."""
    if not USE_KNOWLEDGE_OS or not KNOWLEDGE_OS_AVAILABLE:
        return None
    pool = await agent._get_db_pool()
    if not pool:
        return None
    title = (goal or "Task")[:255]
    description = (goal or "")[:10000]
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tasks (title, description, status, orchestrator_version)
                VALUES ($1, $2, 'in_progress', $3)
                RETURNING id
                """,
                title,
                description,
                orchestrator_version,
            )
            return str(row["id"]) if row else None
    except Exception as e:
        if "orchestrator_version" in str(e):
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "INSERT INTO tasks (title, description, status) VALUES ($1, $2, 'in_progress') RETURNING id",
                        title,
                        description,
                    )
                    return str(row["id"]) if row else None
            except Exception:
                pass
        logger.debug("_record_orchestration_task_start: %s", e)
        return None


async def _get_session_context_from_db(session_id: str, goal: str) -> str:
    """Подмешивание session_context при user_id/session_id (мировая практика: контекст диалога).
    session_context_manager берёт последние запросы из БД (knowledge_os.session_context).
    Возвращает пустую строку при недоступности или ошибке."""
    if not session_id or not goal:
        return ""
    try:
        ko_paths = [
            os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../knowledge_os")),
            "/app/knowledge_os",
        ]
        for ko_root in ko_paths:
            if not os.path.exists(ko_root) and not ko_root.startswith("/app"):
                continue
            app_path = os.path.join(ko_root, "app")
            for p in (app_path, ko_root):
                if p not in sys.path:
                    sys.path.insert(0, p)
            try:
                from app.session_context_manager import get_session_context_manager
                mgr = get_session_context_manager()
                ctx = await mgr.get_session_context(
                    user_id=session_id,  # session_id используется как user_id для lookup
                    expert_name="Виктория",
                    current_query=goal,
                )
                if ctx:
                    logger.debug("📝 [SESSION_CONTEXT] Добавлен контекст сессии из БД (%d символов)", len(ctx))
                return ctx or ""
            except ImportError:
                continue
    except Exception as e:
        logger.debug("Session context fetch: %s", e)
    return ""


async def _record_orchestration_task_complete(
    agent,
    knowledge_os_task_id: Optional[str],
    status: str,
    result_preview: str = "",
) -> None:
    """Обновить задачу в knowledge_os.tasks (completed_at, status, result)."""
    if not knowledge_os_task_id or not USE_KNOWLEDGE_OS or not KNOWLEDGE_OS_AVAILABLE:
        return
    pool = await agent._get_db_pool()
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE tasks SET status = $1, completed_at = CURRENT_TIMESTAMP, result = $2
                WHERE id = $3
                """,
                status if status in ("completed", "failed") else "completed",
                (result_preview or "")[:5000],
                uuid.UUID(knowledge_os_task_id),
            )
    except Exception as e:
        logger.debug("_record_orchestration_task_complete: %s", e)


async def _run_task_background(
    task_id: str,
    goal: str,
    project_context: str,
    project_prompt: str,
    chat_history: Optional[List[Dict[str, str]]],
    use_enhanced: bool,
    correlation_id: Optional[str] = None,
    task_type: Optional[str] = None,
    max_steps: Optional[int] = None,
    session_id: Optional[str] = None,
) -> None:
    """Фоновое выполнение задачи (202 + polling). Результат пишется в _run_task_store[task_id]."""
    if max_steps is None:
        max_steps = DEFAULT_MAX_STEPS
    if task_type is None:
        task_type = detect_task_type(goal, project_context)
    store = _run_task_store.get(task_id)
    if store and correlation_id:
        store["correlation_id"] = correlation_id
    if not store:
        return
    # Ранний ответ для вопросов о данных (метрики Mac Studio, корпорация) — без лимита 500 шагов
    quick_data = await _try_corporation_data_quick_response(goal, correlation_id)
    if quick_data:
        store["status"] = "completed"
        store["output"] = quick_data["output"]
        store["knowledge"] = quick_data.get("knowledge", {})
        store["updated_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("[VICTORIA_CYCLE] background completed task_id=%s route=corporation_data_tool", task_id)
        return
    knowledge_os_task_id = None
    orchestration_plan_bg = None
    if ORCHESTRATION_V2_ENABLED and KNOWLEDGE_OS_AVAILABLE:
        try:
            ko_paths = [
                os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../knowledge_os")),
                "/app/knowledge_os",
            ]
            for ko_root in ko_paths:
                if not os.path.exists(ko_root) and not ko_root.startswith("/app"):
                    continue
                app_path = os.path.join(ko_root, "app")
                if app_path not in sys.path:
                    sys.path.insert(0, app_path)
                if ko_root not in sys.path:
                    sys.path.insert(0, ko_root)
                try:
                    from app.task_orchestration.integration_bridge import IntegrationBridge
                    bridge = IntegrationBridge()
                    bridge_result = await bridge.process_task(goal, project_context=project_context)
                    version = bridge_result.get("orchestrator", "existing")
                    knowledge_os_task_id = await _record_orchestration_task_start(agent, goal, version)
                    if knowledge_os_task_id:
                        store["knowledge_os_task_id"] = knowledge_os_task_id
                    orchestration_plan_bg = bridge_result
                    break
                except ImportError:
                    continue
        except Exception as e:
            logger.debug("Orchestration V2 A/B record start: %s", e)
    orchestration_context_bg = _build_orchestration_context(orchestration_plan_bg)
    try:
        store["status"] = "running"
        store["stage"] = "running"
        store["updated_at"] = datetime.now(timezone.utc).isoformat()
        logger.info("[VICTORIA_CYCLE] background start task_id=%s goal_preview=%s", task_id, (goal or "")[:60])
        logger.info("[TRACE] _run_task_background: start task_id=%s goal_preview=%s", task_id, (goal or "")[:60])
        use_enhanced_actual = should_use_enhanced(goal, project_context, use_enhanced)
        veronica_tried_and_failed = False
        prefer_veronica_bg = task_type == "veronica" or _orchestrator_recommends_veronica(orchestration_plan_bg)
        if prefer_veronica_bg and use_enhanced_actual:
            store["stage"] = "delegate_veronica"
            veronica_result = await delegate_to_veronica(
                _sanitize_goal_for_prompt(goal),
                project_context,
                correlation_id,
                max_steps=max_steps,
            )
            if veronica_result and veronica_result.get("status") == "success":
                raw_knowledge = veronica_result.get("knowledge")
                knowledge = dict(raw_knowledge) if isinstance(raw_knowledge, dict) else {}
                meta = knowledge.get("metadata")
                if not isinstance(meta, dict):
                    meta = {}
                knowledge["metadata"] = meta
                meta["model_used"] = meta.get("model_used") or "Вероника"
                meta.setdefault("source", "local")
                knowledge["delegated_to"] = "Вероника"
                knowledge["execution_trace"] = {
                    "task_type": task_type,
                    "use_enhanced": use_enhanced_actual,
                    "routed_to": "veronica",
                    "delegated_to": "Вероника",
                    "method": meta.get("model_used") or "Вероника",
                    "correlation_id": correlation_id,
                    "goal_preview": (goal or "")[:120],
                }
                store["status"] = "completed"
                store["output"] = _normalize_output_for_user(veronica_result.get("output") or "")
                if not isinstance(store["output"], str):
                    store["output"] = str(store["output"]) if store["output"] is not None else ""
                store["knowledge"] = knowledge
                logger.info("[VICTORIA_CYCLE] background completed task_id=%s route=veronica", task_id)
                logger.info("[TRACE] _run_task_background: completed via Veronica task_id=%s", task_id)
                return
            veronica_tried_and_failed = True
            logger.info("[%s] Veronica недоступна или ошибка (фон) — выполняю через Enhanced/Victoria", (correlation_id or "")[:8])
        enhanced = victoria_enhanced_instance
        if use_enhanced_actual and not veronica_tried_and_failed and enhanced is None:
            try:
                import sys
                for path in ["/app/knowledge_os/app", os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"), os.path.join(os.path.dirname(__file__), "../../knowledge_os/app")]:
                    if (os.path.exists(path) or path.startswith("/app")) and path not in sys.path:
                        sys.path.insert(0, path)
                    if "/app/knowledge_os" not in sys.path:
                        sys.path.insert(0, "/app/knowledge_os")
                    try:
                        from app.victoria_enhanced import VictoriaEnhanced
                        enhanced = VictoriaEnhanced()
                        break
                    except ImportError:
                        continue
            except Exception as e:
                logger.warning("Фоновая задача: не удалось создать VictoriaEnhanced: %s", e)
        if use_enhanced_actual and not veronica_tried_and_failed and enhanced is not None:
            store["stage"] = "enhanced_solve"
            logger.info("[TRACE] _run_task_background: before enhanced.solve task_id=%s", task_id)
            context_with_history = {}
            if chat_history:
                history_text = "\n".join([
                    f"Пользователь: {msg.get('user', '')}\nVictoria: {msg.get('assistant', '')}"
                    for msg in chat_history[-30:]
                ])
                context_with_history["chat_history"] = history_text
            elif session_id:
                session_ctx = await _get_session_context_from_db(session_id, goal)
                if session_ctx:
                    context_with_history["chat_history"] = session_ctx
            if orchestration_context_bg:
                context_with_history["orchestrator_plan"] = orchestration_context_bg
            goal_for_enhanced_bg = _sanitize_goal_for_prompt(goal)
            if orchestration_context_bg:
                goal_for_enhanced_bg = orchestration_context_bg + "\n\nЗАДАЧА: " + goal_for_enhanced_bg
            enhanced_result = await enhanced.solve(
                goal_for_enhanced_bg,
                use_enhancements=True,
                context=context_with_history if context_with_history else None,
            )
            if enhanced_result is None or not isinstance(enhanced_result, dict):
                store["status"] = "completed"
                store["output"] = "Victoria Enhanced не вернула результат (solve вернул None или не dict)."
                store["knowledge"] = {
                    "method": "unknown",
                    "metadata": {"model_used": "Victoria Enhanced", "source": "local"},
                    "project_context": project_context,
                }
            else:
                knowledge = {
                    "method": enhanced_result.get("method"),
                    "metadata": dict(enhanced_result.get("metadata") or {}),
                    "project_context": project_context,
                    "delegated_to": enhanced_result.get("delegated_to"),
                    "task_id": enhanced_result.get("task_id"),
                }
                # Всегда указываем модель (важно для пользователя)
                knowledge["metadata"].setdefault("model_used", "Victoria Enhanced")
                knowledge["metadata"].setdefault("source", "local")
                knowledge["execution_trace"] = {
                    "task_type": task_type,
                    "use_enhanced": True,
                    "routed_to": "enhanced",
                    "delegated_to": enhanced_result.get("delegated_to"),
                    "method": enhanced_result.get("method") or "Victoria Enhanced",
                    "correlation_id": correlation_id,
                    "goal_preview": (goal or "")[:120],
                }
                store["status"] = "completed"
                raw_result = enhanced_result.get("result") or ""
                try:
                    store["output"] = _normalize_output_for_user(raw_result)
                    if not isinstance(store["output"], str):
                        store["output"] = str(store["output"]) if store["output"] is not None else ""
                except Exception as norm_e:
                    logger.warning("Нормализация вывода Enhanced: %s", norm_e)
                    store["output"] = str(raw_result) if raw_result is not None else "Результат не удалось нормализовать."
                store["knowledge"] = knowledge
            logger.info("[VICTORIA_CYCLE] background completed task_id=%s route=enhanced", task_id)
            logger.info("[TRACE] _run_task_background: after enhanced.solve task_id=%s", task_id)
        else:
            store["stage"] = "agent_run"
            logger.info("[TRACE] _run_task_background: before agent.run task_id=%s", task_id)
            original_prompt = agent.executor.system_prompt
            agent.executor.system_prompt = original_prompt + "\n" + project_prompt
            agent.memory = []
            try:
                goal_sanitized = _sanitize_goal_for_prompt(goal)
                if orchestration_context_bg:
                    goal_sanitized = orchestration_context_bg + "\n\nЗАДАЧА: " + goal_sanitized
                result = await agent.run(goal_sanitized, max_steps=max_steps)
                store["status"] = "completed"
                try:
                    store["output"] = _normalize_output_for_user(result)
                    if not isinstance(store["output"], str):
                        store["output"] = str(store["output"]) if store["output"] is not None else ""
                except Exception as norm_e:
                    logger.warning("Нормализация вывода agent.run: %s", norm_e)
                    store["output"] = str(result) if result is not None else "Результат не удалось нормализовать."
                knowledge = {**agent.project_knowledge, "project_context": project_context}
                model_used = getattr(agent.executor, "model", None) or "unknown"
                knowledge.setdefault("metadata", {})["model_used"] = model_used
                knowledge["metadata"].setdefault("source", "local")
                knowledge["execution_trace"] = {
                    "task_type": task_type,
                    "use_enhanced": use_enhanced_actual,
                    "routed_to": "agent_run",
                    "delegated_to": None,
                    "method": model_used,
                    "correlation_id": correlation_id,
                    "goal_preview": (goal or "")[:120],
                }
                store["knowledge"] = knowledge
            finally:
                agent.executor.system_prompt = original_prompt
            logger.info("[VICTORIA_CYCLE] background completed task_id=%s route=agent_run", task_id)
            logger.info("[TRACE] _run_task_background: after agent.run task_id=%s", task_id)
    except Exception as e:
        logger.info("[VICTORIA_CYCLE] background failed task_id=%s error=%s", task_id, str(e)[:200])
        logger.exception("Фоновая задача %s завершилась с ошибкой", task_id)
        store["status"] = "failed"
        store["error"] = str(e)
    finally:
        store["stage"] = store.get("status") or "unknown"
        store["updated_at"] = datetime.now(timezone.utc).isoformat()
        if store.get("knowledge_os_task_id"):
            await _record_orchestration_task_complete(
                agent,
                store["knowledge_os_task_id"],
                store.get("status", "failed"),
                (store.get("output") or store.get("error") or "")[:5000],
            )


@app.get("/run/status/{task_id}")
async def get_run_status(task_id: str):
    """Статус фоновой задачи. status: queued|running|completed|failed."""
    if task_id not in _run_task_store:
        raise HTTPException(status_code=404, detail="task_id not found")
    rec = _run_task_store[task_id]
    knowledge = rec.get("knowledge") or {}
    # Всегда указываем модель (мировая практика: прозрачность)
    meta = knowledge.get("metadata") or {}
    if not meta.get("model_used"):
        meta = dict(meta)
        meta["model_used"] = "local"
        meta.setdefault("source", "local")
        knowledge = dict(knowledge)
        knowledge["metadata"] = meta
    out = _normalize_output_for_user(rec.get("output"))
    if not isinstance(out, str):
        out = str(out) if out is not None else ""
    # Лимит 8000 для Telegram/длинных ответов (раньше 2000 — обрезало сложные ответы)
    if len(out) > 8000:
        out = out[:8000].rstrip() + "\n\n[... ответ обрезан ...]"
    status_val = rec.get("status", "queued")
    logger.info("[VICTORIA_CYCLE] GET /run/status/%s status=%s output_len=%s", task_id, status_val, len(out))
    return {
        "task_id": task_id,
        "status": status_val,
        "stage": rec.get("stage"),
        "output": out,
        "knowledge": knowledge,
        "error": rec.get("error"),
        "correlation_id": rec.get("correlation_id"),
        "updated_at": rec.get("updated_at"),
    }


@app.post("/run", response_model=TaskResponse)
async def run_task(
    body: TaskRequest,
    request: Request,
    async_mode: bool = Query(False, description="True = 202, задача в фоне, результат через GET /run/status/{task_id}"),
):
    """
    Выполнить задачу через Victoria.
    async_mode=true: возвращает 202 + task_id, задача выполняется в фоне; результат — через GET /run/status/{task_id}.
    Заголовок X-Correlation-ID опционален; при отсутствии генерируется UUID для трассировки.
    """
    correlation_id = (request.headers.get("X-Correlation-ID") or "").strip() or str(uuid.uuid4())
    
    # === REQUEST FLOW TRACING ===
    logger.info("[VICTORIA_CYCLE] accept POST /run correlation_id=%s goal_preview=%s async_mode=%s",
                correlation_id, (body.goal or "")[:80], async_mode)
    logger.info("[REQUEST] ========== POST /run ==========")
    logger.info("[REQUEST] Correlation ID: %s", correlation_id)
    logger.info("[REQUEST] Goal: %s", body.goal[:200] if body.goal else "(empty)")
    logger.info("[REQUEST] Async mode: %s", async_mode)
    logger.info("[REQUEST] Project context: %s", body.project_context)
    logger.info("[REQUEST] Max steps: %s", body.max_steps)
    logger.info("[REQUEST] Current executor model: %s", getattr(agent.executor, 'model', 'unknown'))
    logger.info("[REQUEST] Current planner model: %s", getattr(agent.planner, 'model', 'unknown'))
    
    # Определяем контекст проекта (реестр из БД с fallback на env/hardcoded)
    main_project = get_main_project()
    project_context = body.project_context or main_project
    allowed_list, project_configs = await get_projects_registry()
    if project_context not in allowed_list:
        logger.warning(f"⚠️ Invalid project_context: {project_context}, using default: {main_project}")
        project_context = main_project
    project_config = project_configs.get(project_context, project_configs.get(main_project, {"name": main_project, "description": "", "workspace": f"/workspace/{main_project}"}))
    main_config = project_configs.get(main_project, project_config)
    
    # Обновляем системный промпт с безопасным контекстом проекта
    project_prompt = f"""
🏢 КОНТЕКСТ ПРОЕКТА: {project_config['name']}
🏢 ОСНОВНОЙ ПРОЕКТ КОРПОРАЦИИ: {main_config['name']}

ВАЖНО:
- Ты работаешь в контексте проекта: {project_config['name']}
- Основной проект корпорации: {main_config['name']}
- Все файлы, команды и операции должны быть в контексте проекта {project_config['name']}
- При работе с файлами используй пути относительно корня проекта

🧠 БАЗА ЗНАНИЙ (ВСЕГДА ДОСТУПНА ДЛЯ ВСЕХ ПРОЕКТОВ):
- ✅ 58+ экспертов Knowledge OS - доступны для ВСЕХ проектов (та же БД, те же эксперты)
- ✅ Глобальные знания (global_knowledge.md) - доступны для ВСЕХ проектов
- ✅ Knowledge OS Database - доступна для ВСЕХ проектов (одна и та же БД)
- ✅ Все твои знания и экспертиза - доступны для ВСЕХ проектов
- ✅ Проект-специфичные знания - дополнительно к глобальным (не вместо них!)

⚠️ ВАЖНО: ТЫ НЕ СТАНОВИШЬСЯ ГЛУПЕЕ при работе с другими проектами!
Все твои знания, эксперты и база данных доступны ВСЕГДА, независимо от проекта.
"""
    
    use_enhanced = os.getenv("USE_VICTORIA_ENHANCED", "false").lower() == "true"
    
    logger.info("[REQUEST] USE_VICTORIA_ENHANCED: %s", use_enhanced)

    # Асинхронный режим (202): задача в фоне, результат — через GET /run/status/{task_id}
    if async_mode:
        task_id = str(uuid.uuid4())
        _task_type_for_async = detect_task_type(body.goal, body.project_context or project_context)
        
        logger.info("[REQUEST] Async mode enabled")
        logger.info("[REQUEST] Task ID: %s", task_id)
        logger.info("[REQUEST] Task type detected: %s", _task_type_for_async)
        
        _run_task_store[task_id] = {
            "status": "queued",
            "stage": "queued",
            "output": None,
            "knowledge": None,
            "error": None,
            "correlation_id": correlation_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        _max_steps = body.max_steps if body.max_steps is not None else DEFAULT_MAX_STEPS
        asyncio.create_task(_run_task_background(
            task_id=task_id,
            goal=body.goal,
            project_context=project_context,
            project_prompt=project_prompt,
            chat_history=body.chat_history,
            use_enhanced=use_enhanced,
            correlation_id=correlation_id,
            task_type=_task_type_for_async,
            max_steps=_max_steps,
            session_id=body.session_id,
        ))
        logger.info("[VICTORIA_CYCLE] async 202 task_id=%s status_url=/run/status/%s", task_id, task_id)
        return JSONResponse(
            status_code=202,
            content={
                "task_id": task_id,
                "correlation_id": correlation_id,
                "status_url": f"/run/status/{task_id}",
                "message": "Задача принята, выполняется в фоне. Опрашивайте status_url до status=completed.",
            },
        )
    
    # Ранний ответ для вопросов о данных (метрики Mac Studio, корпорация) — без лимита 500 шагов
    quick_data = await _try_corporation_data_quick_response(body.goal, correlation_id)
    if quick_data:
        logger.info("[VICTORIA_CYCLE] sync 200 correlation_id=%s route=corporation_data_tool", correlation_id[:8])
        return TaskResponse(
            status="success",
            output=quick_data["output"],
            knowledge=quick_data.get("knowledge"),
            correlation_id=correlation_id,
        )
    
    # Понимание цели и проверка неоднозначности (уточняющие вопросы)
    understanding = await _understand_goal_with_clarification(agent, body.goal)
    if understanding.get("needs_clarification"):
        return JSONResponse(
            status_code=200,
            content={
                "status": "needs_clarification",
                "correlation_id": correlation_id,
                "clarification_questions": understanding["clarification_questions"],
                "original_goal": understanding["original_goal"],
                "suggested_restatement": understanding.get("restated", body.goal),
            },
        )
    restated_goal = understanding.get("restated") or body.goal
    knowledge_os_task_id = None
    orchestration_plan = None  # План и назначения от оркестратора — Victoria использует при выполнении (мировая практика)
    orch_ctx = {"status": "failed", "result": ""}
    if ORCHESTRATION_V2_ENABLED and KNOWLEDGE_OS_AVAILABLE:
        try:
            ko_paths = [
                os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../knowledge_os")),
                "/app/knowledge_os",
            ]
            for ko_root in ko_paths:
                app_path = os.path.join(ko_root, "app") if os.path.exists(ko_root) or ko_root.startswith("/app") else None
                if not app_path and not ko_root.startswith("/app"):
                    continue
                if ko_root not in sys.path:
                    sys.path.insert(0, ko_root)
                if app_path and app_path not in sys.path:
                    sys.path.insert(0, app_path)
                try:
                    from app.task_orchestration.integration_bridge import IntegrationBridge
                    bridge = IntegrationBridge()
                    bridge_result = await bridge.process_task(restated_goal, project_context=project_context)
                    version = bridge_result.get("orchestrator", "existing")
                    knowledge_os_task_id = await _record_orchestration_task_start(agent, restated_goal, version)
                    orchestration_plan = bridge_result  # Сохраняем план и назначения для использования при выполнении
                    if bridge_result.get("assignments") or bridge_result.get("strategy"):
                        logger.info("[ORCHESTRATOR] План и назначения получены, передаём Victoria для выполнения")
                    break
                except ImportError:
                    continue
        except Exception as e:
            logger.debug("Orchestration V2 A/B record start: %s", e)
    orchestration_context_str = _build_orchestration_context(orchestration_plan)
    # Маршрутизация: простой чат (привет и т.п.) — без Enhanced для скорости
    use_enhanced_for_request = should_use_enhanced(restated_goal, body.project_context, use_enhanced)
    task_type = detect_task_type(restated_goal, body.project_context or "")
    logger.info(
        "Запрос [%s] тип: %s, use_enhanced: %s",
        correlation_id[:8],
        task_type,
        use_enhanced_for_request,
    )

    try:
        # Маршрутизация: Veronica если task_type=veronica ИЛИ оркестратор рекомендует Veronica (мировая практика)
        veronica_tried_and_failed = False
        prefer_veronica = task_type == "veronica" or _orchestrator_recommends_veronica(orchestration_plan)
        if prefer_veronica and use_enhanced_for_request:
            logger.info("[TRACE] run_task: before delegate_to_veronica correlation_id=%s", correlation_id[:8])
            veronica_result = await delegate_to_veronica(
                _sanitize_goal_for_prompt(restated_goal),
                body.project_context or project_context,
                correlation_id,
                max_steps=body.max_steps if body.max_steps is not None else DEFAULT_MAX_STEPS,
            )
            if veronica_result and veronica_result.get("status") == "success":
                raw_knowledge = veronica_result.get("knowledge")
                knowledge = dict(raw_knowledge) if isinstance(raw_knowledge, dict) else {}
                meta = knowledge.get("metadata")
                if not isinstance(meta, dict):
                    meta = {}
                knowledge["metadata"] = meta
                meta["model_used"] = meta.get("model_used") or "Вероника"
                meta.setdefault("source", "local")
                meta["correlation_id"] = correlation_id
                knowledge["delegated_to"] = "Вероника"
                knowledge["execution_trace"] = {
                    "task_type": task_type,
                    "use_enhanced": use_enhanced_for_request,
                    "routed_to": "veronica",
                    "delegated_to": "Вероника",
                    "method": knowledge.get("metadata", {}).get("model_used") or "Вероника",
                    "correlation_id": correlation_id,
                    "goal_preview": (restated_goal or "")[:120],
                }
                orch_ctx["status"] = "completed"
                orch_ctx["result"] = (veronica_result.get("output") or "")[:5000]
                out_len = len(veronica_result.get("output") or "")
                logger.info("[VICTORIA_CYCLE] sync 200 correlation_id=%s route=veronica output_len=%s", correlation_id[:8], out_len)
                return TaskResponse(
                    status="success",
                    output=_normalize_output_for_user(veronica_result.get("output") or ""),
                    knowledge=knowledge,
                    correlation_id=correlation_id,
                )
            veronica_tried_and_failed = True
            logger.info("[%s] Veronica недоступна или ошибка — выполняю задачу через Victoria (инструменты)", correlation_id[:8])
    except Exception as e:
        logger.warning("[run_task] Ошибка при делегировании Veronica, fallback на Victoria: %s", e)
        veronica_tried_and_failed = True

    # Enhanced только если не пытались veronica и не сработало (тогда идём в agent.run() — реальные действия)
    if use_enhanced_for_request and not veronica_tried_and_failed:
        # Используем Victoria Enhanced с новыми компонентами
        try:
            import sys
            enhanced_paths = [
                "/app/knowledge_os/app",  # Путь в Docker контейнере
                os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"),
                os.path.join(os.path.dirname(__file__), "../../knowledge_os/app"),
            ]
            for path in enhanced_paths:
                if os.path.exists(path) or path.startswith("/app"):
                    if path not in sys.path:
                        sys.path.insert(0, path)
                    try:
                        # Добавляем путь для импорта
                        if "/app/knowledge_os" not in sys.path:
                            sys.path.insert(0, "/app/knowledge_os")
                        # Используем глобальный экземпляр если он уже создан, иначе создаем новый
                        if victoria_enhanced_instance is not None:
                            enhanced = victoria_enhanced_instance
                            logger.debug("♻️ Используем существующий экземпляр Victoria Enhanced")
                        else:
                            from app.victoria_enhanced import VictoriaEnhanced
                            logger.info("🚀 Victoria Enhanced активирован!")
                            enhanced = VictoriaEnhanced()
                        
                        # Формируем контекст с историей чата
                        context_with_history = {}
                        if body.chat_history:
                            # Добавляем историю в контекст (последние 30 пар — вся сессия до закрытия чата)
                            history_text = "\n".join([
                                f"Пользователь: {msg.get('user', '')}\nVictoria: {msg.get('assistant', '')}"
                                for msg in body.chat_history[-30:]
                            ])
                            context_with_history["chat_history"] = history_text
                            logger.debug(f"📝 Передана история чата ({len(body.chat_history)} сообщений)")
                        elif body.session_id:
                            # Подмешивание session_context при session_id без chat_history (Telegram, скрипты)
                            session_ctx = await _get_session_context_from_db(body.session_id, restated_goal)
                            if session_ctx:
                                context_with_history["chat_history"] = session_ctx
                        if orchestration_context_str:
                            context_with_history["orchestrator_plan"] = orchestration_context_str
                        
                        # Передаем контекст проекта, историю и план оркестратора в Enhanced (мировая практика: оркестратор распределил — Victoria выполняет по плану)
                        goal_for_enhanced = _sanitize_goal_for_prompt(restated_goal)
                        if orchestration_context_str:
                            goal_for_enhanced = orchestration_context_str + "\n\nЗАДАЧА: " + goal_for_enhanced
                        logger.info("[TRACE] run_task: before enhanced.solve correlation_id=%s", correlation_id[:8])
                        enhanced_result = await enhanced.solve(
                            goal_for_enhanced,
                            use_enhancements=True,
                            context=context_with_history if context_with_history else None
                        )
                        logger.info(f"✅ Enhanced метод: {enhanced_result.get('method')} [проект: {project_context}]")
                        knowledge = {
                            "method": enhanced_result.get("method"),
                            "metadata": dict(enhanced_result.get("metadata") or {}),
                            "project_context": project_context,
                            "delegated_to": enhanced_result.get("delegated_to"),
                            "task_id": enhanced_result.get("task_id"),
                        }
                        # Всегда указываем модель (важно для пользователя)
                        knowledge["metadata"].setdefault("model_used", "Victoria Enhanced")
                        knowledge["metadata"].setdefault("source", "local")
                        knowledge["metadata"]["correlation_id"] = correlation_id
                        knowledge["execution_trace"] = {
                            "task_type": task_type,
                            "use_enhanced": True,
                            "routed_to": "enhanced",
                            "delegated_to": enhanced_result.get("delegated_to"),
                            "method": enhanced_result.get("method") or "Victoria Enhanced",
                            "correlation_id": correlation_id,
                            "goal_preview": (restated_goal or "")[:120],
                        }
                        orch_ctx["status"] = "completed"
                        orch_ctx["result"] = (enhanced_result.get("result") or "")[:5000]
                        out_len = len(enhanced_result.get("result") or "")
                        logger.info("[VICTORIA_CYCLE] sync 200 correlation_id=%s route=enhanced output_len=%s", correlation_id[:8], out_len)
                        return TaskResponse(
                            status="success",
                            output=_normalize_output_for_user(enhanced_result.get("result") or ""),
                            knowledge=knowledge,
                            correlation_id=correlation_id,
                        )
                    except ImportError as e:
                        logger.warning(f"⚠️ Не удалось импортировать VictoriaEnhanced: {e}")
                        break
        except Exception as e:
            logger.warning(f"⚠️ Ошибка использования VictoriaEnhanced, fallback на стандартный режим: {e}")
    
    # Стандартный режим: цель + план оркестратора (если есть), чтобы LLM следовал назначениям
    try:
        goal_for_run = _sanitize_goal_for_prompt(restated_goal)
        if orchestration_context_str:
            goal_for_run = orchestration_context_str + "\n\nЗАДАЧА: " + goal_for_run
            logger.info("[EXECUTE] Цель дополнена планом оркестратора")
        
        logger.info("[EXECUTE] ========== Standard mode execution ==========")
        logger.info("[EXECUTE] Correlation ID: %s", correlation_id[:8])
        logger.info("[EXECUTE] Goal (sanitized): %s", goal_for_run[:100])
        logger.info("[EXECUTE] Task type: %s", task_type)
        logger.info("[EXECUTE] Executor model BEFORE run: %s", getattr(agent.executor, 'model', 'unknown'))
        logger.info("[EXECUTE] Planner model BEFORE run: %s", getattr(agent.planner, 'model', 'unknown'))
        logger.info("[EXECUTE] Max steps: %s", body.max_steps if body.max_steps is not None else DEFAULT_MAX_STEPS)
        
        # Временно обновляем системный промпт с контекстом проекта
        original_prompt = agent.executor.system_prompt
        agent.executor.system_prompt = original_prompt + "\n" + project_prompt
        agent.memory = []
        
        import time as _time
        _exec_start = _time.time()
        
        result = await agent.run(goal_for_run, max_steps=body.max_steps if body.max_steps is not None else DEFAULT_MAX_STEPS)
        
        _exec_elapsed = _time.time() - _exec_start
        
        # Восстанавливаем оригинальный промпт
        agent.executor.system_prompt = original_prompt
        model_used = getattr(agent.executor, "model", None) or "unknown"
        
        logger.info("[EXECUTE] ========== Execution complete ==========")
        logger.info("[EXECUTE] Elapsed time: %.2f seconds", _exec_elapsed)
        logger.info("[EXECUTE] Model used: %s", model_used)
        logger.info("[EXECUTE] Result type: %s", type(result).__name__)
        logger.info("[EXECUTE] Result length: %d chars", len(str(result)) if result else 0)
        logger.info("[EXECUTE] Result preview: %s...", str(result)[:200] if result else "(empty)")
        
        knowledge = {**agent.project_knowledge, "project_context": project_context}
        knowledge.setdefault("metadata", {})["model_used"] = model_used
        knowledge["metadata"].setdefault("source", "local")
        knowledge["metadata"]["correlation_id"] = correlation_id
        knowledge["execution_trace"] = {
            "task_type": task_type,
            "use_enhanced": False,
            "routed_to": "agent_run",
            "delegated_to": None,
            "method": model_used,
            "veronica_tried_and_failed": veronica_tried_and_failed,
            "correlation_id": correlation_id,
            "goal_preview": (restated_goal or "")[:120],
            "execution_time_seconds": _exec_elapsed,
        }
        orch_ctx["status"] = "completed"
        orch_ctx["result"] = (str(result) or "")[:5000]
        logger.info("[VICTORIA_CYCLE] sync 200 correlation_id=%s route=agent_run output_len=%s", correlation_id[:8], len(str(result) or ""))
        return TaskResponse(
            status="success",
            output=_normalize_output_for_user(result),
            knowledge=knowledge,
            correlation_id=correlation_id,
        )
    except Exception as e:
        logger.exception("[EXECUTE] ❌ Ошибка выполнения задачи: %s", e)
        orch_ctx["status"] = "failed"
        orch_ctx["result"] = str(e)[:5000]
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        if knowledge_os_task_id:
            await _record_orchestration_task_complete(agent, knowledge_os_task_id, orch_ctx["status"], orch_ctx["result"])


@app.post("/orchestrate", response_model=TaskResponse)
async def orchestrate_task(request: TaskRequest):
    """Новый endpoint для оркестрации через Victoria"""
    try:
        logger.info("🎯 Получена задача для оркестрации: %s", request.goal[:80])
        agent.memory = []
        result = await agent.orchestrate_task(request.goal)
        return TaskResponse(status="success", output=result, knowledge=agent.project_knowledge)
    except Exception as e:
        logger.exception("Ошибка оркестрации задачи")
        raise HTTPException(status_code=500, detail=str(e)) from e


class PlanRequest(BaseModel):
    """Запрос только плана (без выполнения)."""
    goal: str


def _normalize_plan_display(raw: Any) -> str:
    """Преобразует сырой ответ planner (JSON или текст) в читаемый план для UI."""
    if not raw:
        return "План не сформирован."
    text = raw if isinstance(raw, str) else str(raw)
    text = text.strip()
    # Пробуем извлечь читаемый план из JSON (thought / tool_input.output)
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(text[start:end])
            parts = []
            if data.get("thought"):
                parts.append(data["thought"].strip())
            ti = data.get("tool_input")
            if isinstance(ti, dict) and ti.get("output"):
                parts.append(ti["output"].strip())
            if parts:
                return "\n\n".join(parts)
    except (json.JSONDecodeError, TypeError):
        pass
    # Убрать обёртки markdown/code
    for wrap in ("```json", "```", "```text"):
        if text.startswith(wrap):
            text = text[len(wrap):].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    return text or "План не сформирован."


@app.post("/plan")
async def plan_only(request: PlanRequest):
    """
    Только план выполнения (режим Plan как в Cursor).
    Один вызов LLM: план шагов без выполнения инструментов.
    """
    try:
        logger.info("[PLAN] Запрос плана: %s", request.goal[:80])
        plan_text = await agent.plan(request.goal)
        plan_display = _normalize_plan_display(plan_text)
        return {"plan": plan_display, "status": "success"}
    except Exception as e:
        logger.exception("Ошибка формирования плана")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/status")
async def get_status():
    # При первом запросе к /status подгрузить экспертов, если ещё не загружены (БД могла быть недоступна при старте)
    if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE and not agent._expert_team_loaded:
        try:
            await agent._load_expert_team()
        except Exception:
            pass
    # Получить статистику экспертов из БД
    experts_stats = {
        "total": len(agent.expert_team),
        "unique_roles": 0,
        "departments": 0
    }
    if agent._expert_team_loaded and agent.expert_team:
        unique_roles = set(e.get('role', '') for e in agent.expert_team.values() if e.get('role'))
        unique_departments = set(e.get('department', '') for e in agent.expert_team.values() if e.get('department'))
        experts_stats["unique_roles"] = len(unique_roles)
        experts_stats["departments"] = len(unique_departments)
    
    status = {
        "status": "online",
        "agent": agent.name,
        "knowledge_size": len(agent.project_knowledge),
        "knowledge_os_enabled": USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE,
        "experts_loaded": agent._expert_team_loaded,
        "experts_count": len(agent.expert_team),
        "experts_stats": experts_stats,
        "cache_enabled": agent.use_cache,
        "cache_size": len(agent.task_cache)
    }
    
    # Статус трёх уровней Victoria (один сервис 8010): Agent | Enhanced | Initiative
    status["victoria_levels"] = {
        "agent": True,  # базовый уровень всегда активен в этом процессе
        "enhanced": victoria_enhanced_instance is not None,
        "initiative": victoria_enhanced_monitoring_started,
    }
    if victoria_enhanced_instance:
        try:
            enhanced_status = await victoria_enhanced_instance.get_status()
            status["victoria_enhanced"] = {
                "enabled": True,
                "monitoring_started": enhanced_status.get("monitoring_started", False),
                "event_bus_available": enhanced_status.get("event_bus_available", False),
                "skill_registry_available": enhanced_status.get("skill_registry_available", False),
                "skills_count": enhanced_status.get("skills_count", 0),
                "file_watcher_available": enhanced_status.get("file_watcher_available", False),
                "service_monitor_available": enhanced_status.get("service_monitor_available", False)
            }
        except Exception as e:
            logger.debug(f"Ошибка получения статуса Enhanced: {e}")
            status["victoria_enhanced"] = {"enabled": True, "error": str(e)}
    else:
        status["victoria_enhanced"] = {"enabled": False}

    return status


@app.get("/api/available-models")
async def available_models():
    """Сканирует доступные модели в MLX и Ollama (прогрев кэша при запуске чата)."""
    import os
    is_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() == "true"
    mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435" if is_docker else "http://localhost:11435")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434" if is_docker else "http://localhost:11434")
    try:
        for path in ["/app/knowledge_os/app", os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app")]:
            if path and os.path.exists(path) and path not in sys.path:
                sys.path.insert(0, path)
        if "/app/knowledge_os" not in sys.path:
            sys.path.insert(0, "/app/knowledge_os")
        from app.available_models_scanner import get_available_models  # type: ignore
        mlx_list, ollama_list = await get_available_models(mlx_url, ollama_url)
        return {"mlx": mlx_list, "ollama": ollama_list}
    except Exception as e:
        logger.warning("available_models: %s", e)
        return {"mlx": [], "ollama": [], "error": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok", "agent": agent.name}


if __name__ == "__main__":
    port = int(os.getenv("VICTORIA_PORT", "8010"))  # 8010 — как в Docker (host), 8000 — внутри контейнера
    uvicorn.run(app, host="0.0.0.0", port=port)
