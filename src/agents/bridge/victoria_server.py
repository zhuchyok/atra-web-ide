"""
Victoria Agent — Team Lead ATRA. HTTP API для задач.
Отдельный сервер: контейнер victoria-agent запускает именно Викторию, а не Веронику.
"""

import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

# Загружаем .env при старте
load_dotenv()

# --- SINGULARITY 10.0: UNIFIED CHAT LOGIC ---
try:
    # Пытаемся импортировать из knowledge_os/app
    sys.path.insert(0, os.path.join(os.getcwd(), "knowledge_os/app"))
    from emotion_detector import EmotionDetector
    from expert_dna_manager import get_expert_dna_manager
    from query_orchestrator import QueryOrchestrator, QueryType
    from skill_mapper import get_skill_mapper

    EMOTION_DETECTOR_AVAILABLE = True
except ImportError:
    EmotionDetector = None
    QueryOrchestrator = None
    get_skill_mapper = None
    EMOTION_DETECTOR_AVAILABLE = False

# Простые сообщения для которых не нужен агент Victoria (быстрый путь через MLX/Ollama)
SIMPLE_PATTERNS = [
    "привет",
    "hello",
    "hi",
    "здравствуй",
    "добрый день",
    "добрый вечер",
    "как дела",
    "как ты",
    "что умеешь",
    "кто ты",
    "спасибо",
    "thanks",
    "пока",
    "bye",
    "ping",
    "pong",
]

# Паттерны для мгновенного ответа (Fast Track), игнорируя USE_VICTORIA_ENHANCED
FAST_TRACK_PATTERNS = [
    "привет",
    "hello",
    "hi",
    "здравствуй",
    "добрый день",
    "добрый вечер",
    "как дела",
    "как ты",
    "кто ты",
    "что ты умеешь",
    "спасибо",
    "thanks",
    "пока",
    "bye",
    "ping",
    "pong",
    "тест",
    "test",
]

# Паттерны для Victoria Agent (сложные задачи, корпорация, сервера, анализ данных)
VICTORIA_PATTERNS = [
    "файл на сервере",
    "ssh",
    "подключись",
    "запусти на",
    "выполни команду",
    "создай проект",
    "разверни",
    "deploy",
    "docker",
    "контейнер",
    "корпорац",
    "сервер",
    "статус",
    "проверь",
    "victoria",
    "виктория",
    "агент",
    "задач",
    "mac studio",
    "макстудио",
    "mlx",
    "rag",
    "знани",
    "база",
    # Анализ данных и программирование — всегда через ReAct агента
    ".parquet",
    ".csv",
    ".json",
    "duckdb",
    "pandas",
    "pyarrow",
    "/data/",
    "python",
    "код",
    "code",
    "анализ",
    "аномали",
    "стакан",
    "торгов",
    "маркет",
    "паттерн",
    "скрипт",
    "select ",
    "import ",
    "функци",
    "function",
    "класс",
    "class",
    "напиши код",
    "напиши скрипт",
    "выполни код",
    "объясни код",
    "создай скрипт",
]


def is_simple_message(content: str) -> bool:
    """Проверить, является ли сообщение простым (не требует агента)"""
    lower = content.lower().strip()

    # Если сообщение очень короткое (1-2 слова) и нет явных признаков сложности — это простое
    words = lower.split()
    if len(words) <= 2 and not any(p in lower for p in VICTORIA_PATTERNS):
        return True

    for pattern in VICTORIA_PATTERNS:
        if pattern in lower:
            return False

    if len(lower) < 100:  # Снизили порог с 200 до 100 для большей уверенности
        return True

    for pattern in SIMPLE_PATTERNS:
        if pattern in lower:
            return True
    return False


def is_fast_track_message(content: str) -> bool:
    """Проверить, нужно ли отвечать мгновенно (приветствия и т.д.)"""
    lower = content.lower().strip()
    # Если это одно слово из списка приветствий
    if lower in FAST_TRACK_PATTERNS:
        return True
    # Если сообщение начинается с приветствия и оно короткое
    for p in FAST_TRACK_PATTERNS:
        if lower.startswith(p) and len(lower) < 30:
            return True
    return False


def _select_model_for_chat(content: str, expert_name: Optional[str] = None) -> str:
    """Автоматический выбор модели на основе содержания сообщения и эксперта"""
    content_lower = content.lower()

    # [VIP ROUTE] Если в чате Иван (CEO) или запрос стратегический
    if any(
        word in content_lower
        for word in ["стратег", "корпорац", "совет", "директор", "иван", "ceo"]
    ):
        return "victoria-wisdom-v3.5"

    if any(
        word in content_lower
        for word in ["подумай", "логика", "планир", "reasoning", "анализ", "объясни", "почему"]
    ):
        return "victoria-wisdom-v3.5"

    if any(
        word in content_lower
        for word in [
            "код",
            "программир",
            "рефактор",
            "функци",
            "класс",
            "python",
            "javascript",
            "typescript",
            "алгоритм",
        ]
    ):
        return "victoria-wisdom-v3.5"

    if len(content) > 500:
        return "victoria-wisdom-v3.5"

    if len(content) < 200:
        return "tinyllama:1.1b-chat"  # Быстрая модель для коротких вопросов

    return "victoria-wisdom-v3.5"


# Загружаем .env при старте
load_dotenv()


def _refresh_knowledge_os_availability():
    global KNOWLEDGE_OS_AVAILABLE, asyncpg, USE_KNOWLEDGE_OS
    USE_KNOWLEDGE_OS = os.getenv("USE_KNOWLEDGE_OS", "true").lower() == "true"
    if USE_KNOWLEDGE_OS:
        try:
            import asyncpg

            KNOWLEDGE_OS_AVAILABLE = True
        except ImportError:
            logging.warning(
                "asyncpg не установлен, Knowledge OS недоступна. Установите: pip install asyncpg"
            )
            KNOWLEDGE_OS_AVAILABLE = False


_refresh_knowledge_os_availability()

# Canary: оркестрация V2 (A/B по проценту трафика)
ORCHESTRATION_V2_ENABLED = os.getenv("ORCHESTRATION_V2_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)
ORCHESTRATION_V2_PERCENTAGE = float(os.getenv("ORCHESTRATION_V2_PERCENTAGE", "10"))


def _refresh_orchestration_v2_settings():
    global ORCHESTRATION_V2_ENABLED, ORCHESTRATION_V2_PERCENTAGE
    ORCHESTRATION_V2_ENABLED = os.getenv("ORCHESTRATION_V2_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    ORCHESTRATION_V2_PERCENTAGE = float(
        os.getenv("ORCHESTRATION_V2_PERCENTAGE", "100")
    )  # Принудительно 100 для монстра


_refresh_orchestration_v2_settings()

# --- SHARED STATE (REDIS) ---
try:
    from app.redis_manager import redis_manager
except ImportError:
    try:
        from redis_manager import redis_manager
    except ImportError:
        redis_manager = None

# Хранилище фоновых задач (202 + polling): task_id -> { status, output, knowledge, error, created_at }
_run_task_store: Dict[str, Dict[str, Any]] = {}
_RUN_TASK_STORE_TTL = 86400  # 24 часа для God Mode


async def _save_task_to_db(task_id: str, data: Dict[str, Any]):
    """Сохранить состояние задачи в БД для Task Persistence"""
    if not KNOWLEDGE_OS_AVAILABLE:
        return
    try:
        pool = await agent._get_db_pool()
        if not pool:
            return

        # [SINGULARITY 21.12] Получаем эмбеддинг для семантического поиска в будущем
        embedding = None
        goal_text = data.get("goal", "")
        if goal_text and len(goal_text) > 5:
            try:
                embedding = await agent._get_embedding_for_rag(goal_text)
            except Exception as ee:
                logger.debug(f"Embedding generation for task failed: {ee}")

        async with pool.acquire() as conn:
            if embedding:
                await conn.execute(
                    """
                    INSERT INTO tasks (id, goal, status, result, metadata, created_at, updated_at, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        result = EXCLUDED.result,
                        metadata = tasks.metadata || EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at,
                        embedding = EXCLUDED.embedding
                """,
                    task_id,
                    goal_text,
                    data.get("status"),
                    data.get("output"),
                    json.dumps(data.get("metadata", {})),
                    data.get("created_at", datetime.now(timezone.utc)),
                    datetime.now(timezone.utc),
                    str(embedding),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO tasks (id, goal, status, result, metadata, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        result = EXCLUDED.result,
                        metadata = tasks.metadata || EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at
                """,
                    task_id,
                    goal_text,
                    data.get("status"),
                    data.get("output"),
                    json.dumps(data.get("metadata", {})),
                    data.get("created_at", datetime.now(timezone.utc)),
                    datetime.now(timezone.utc),
                )
    except Exception as e:
        logger.debug(f"Task persistence save failed: {e}")


async def _cleanup_stale_tasks():
    """Фоновая задача: каждые 5 мин переводит processing-задачи старше 30 мин в failed."""
    STALE_THRESHOLD_SEC = 30 * 60  # 30 минут
    CHECK_INTERVAL_SEC = 5 * 60  # проверка каждые 5 мин
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL_SEC)
            now = datetime.now(timezone.utc)
            stale_ids = []
            for task_id, store in list(_run_task_store.items()):
                if store.get("status") != "processing":
                    continue
                updated_raw = store.get("updated_at") or store.get("created_at")
                if not updated_raw:
                    continue
                try:
                    if isinstance(updated_raw, str):
                        updated_at = datetime.fromisoformat(updated_raw)
                    else:
                        updated_at = updated_raw
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    age_sec = (now - updated_at).total_seconds()
                    if age_sec > STALE_THRESHOLD_SEC:
                        stale_ids.append(task_id)
                except Exception:
                    pass
            for task_id in stale_ids:
                _run_task_store[task_id]["status"] = "failed"
                _run_task_store[task_id]["error"] = (
                    f"Task timed out after {STALE_THRESHOLD_SEC // 60}m (auto-cleanup)"
                )
                try:
                    await redis_manager.update_task_status(
                        task_id, "failed", result=f"Timeout after {STALE_THRESHOLD_SEC // 60}m"
                    )
                except Exception:
                    pass
                logger.warning(
                    "[CLEANUP] Stale task %s → failed (was processing > %dm)",
                    task_id[:8],
                    STALE_THRESHOLD_SEC // 60,
                )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug("[CLEANUP] _cleanup_stale_tasks error: %s", e)


async def _load_tasks_from_db():
    """Загрузить незавершенные задачи из БД при старте"""
    if not KNOWLEDGE_OS_AVAILABLE:
        return
    try:
        pool = await agent._get_db_pool()
        if not pool:
            return
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, goal, status, result, metadata, created_at
                FROM tasks
                WHERE status IN ('pending', 'in_progress')
                AND updated_at > NOW() - INTERVAL '24 hours'
            """)
            for row in rows:
                _run_task_store[row["id"]] = {
                    "goal": row["goal"],
                    "status": row["status"],
                    "output": row["result"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                    "created_at": row["created_at"],
                }
                # Если задача была in_progress, пробуем её перезапустить в фоне
                if row["status"] == "in_progress":
                    asyncio.create_task(resume_task_execution(row["id"]))
            if rows:
                logger.info(f"♻️ Восстановлено {len(rows)} задач из БД")
    except Exception as e:
        logger.debug(f"Task persistence load failed: {e}")


async def resume_task_execution(task_id: str):
    """Перезапуск прерванной задачи"""
    task = _run_task_store.get(task_id)
    if not task or not isinstance(task, dict):
        return
    goal = task.get("goal") or "Unknown Goal"
    if not isinstance(goal, str):
        goal = str(goal) if goal is not None else "Unknown Goal"
    logger.info(f"🔄 Перезапуск задачи {task_id}: {goal[:50]}...")
    # Здесь логика вызова agent.run() с сохранением промежуточных результатов
    # Для простоты пока просто логируем, в будущем добавим полноценный resume


# Кэш контекста RAG по query_hash (RAG_PLUS_ROCKET_SPEED): key -> (context_str, expiry_ts)
# RAG_CACHE_BACKEND=memory|redis (по умолчанию memory). При redis — общий кэш между инстансами (NEXT_STEPS §2).
_rag_ctx_cache: Dict[str, Tuple[str, float]] = {}
_RAG_CTX_CACHE_MAX = 500
RAG_CACHE_BACKEND = (
    (os.getenv("RAG_CACHE_BACKEND", "redis") or "redis").strip().lower()
)  # По умолчанию теперь redis
_RAG_REDIS_AVAILABLE = True


async def _rag_cache_get(key: str) -> Optional[str]:
    """Получить контекст из кэша RAG (memory или Redis)."""
    if not key:
        return None
    if RAG_CACHE_BACKEND == "redis" and redis_manager:
        return await redis_manager.get_cache(f"rag_ctx:{key}")

    now = time.time()
    if key in _rag_ctx_cache and _rag_ctx_cache[key][1] > now:
        return _rag_ctx_cache[key][0]
    return None


async def _rag_cache_set(key: str, value: str, ttl_sec: int) -> None:
    """Записать контекст в кэш RAG (memory или Redis)."""
    if not key or ttl_sec <= 0:
        return
    if RAG_CACHE_BACKEND == "redis" and redis_manager:
        await redis_manager.set_cache(f"rag_ctx:{key}", value, ttl=ttl_sec)
        return

    _rag_ctx_cache[key] = (value, time.time() + ttl_sec)
    while len(_rag_ctx_cache) > _RAG_CTX_CACHE_MAX:
        k_old = min(_rag_ctx_cache.keys(), key=lambda k: _rag_ctx_cache[k][1])
        del _rag_ctx_cache[k_old]


# Метрики латентности RAG+ для отслеживания и проверки «тормозит ли» (GET /status, алерты по логам)
_rag_latency_last: Dict[str, float] = {"embed_ms": 0.0, "prepare_ms": 0.0, "llm_plan_ms": 0.0}
_rag_latency_slow_count: int = 0
_rag_latency_last_slow_at: Optional[str] = None

# Лимит шагов агента. Для чата/Telegram клиенты передают max_steps=50 (VICTORIA_MAX_STEPS_CHAT / VICTORIA_MAX_STEPS)
DEFAULT_MAX_STEPS = int(os.getenv("VICTORIA_MAX_STEPS", "500"))
# Длинный контекст (план «умнее быстрее»): лимиты истории и цели; 0 = без обрезки
VICTORIA_CHAT_HISTORY_MAX_MESSAGES = max(
    1, int(os.getenv("VICTORIA_CHAT_HISTORY_MAX_MESSAGES", "30"))
)
VICTORIA_HISTORY_MAX_CHARS = int(os.getenv("VICTORIA_HISTORY_MAX_CHARS", "0"))  # 0 = не обрезать
VICTORIA_GOAL_MAX_CHARS = int(os.getenv("VICTORIA_GOAL_MAX_CHARS", "0"))  # 0 = не обрезать

# Debug mode: VICTORIA_DEBUG=true enables verbose logging at all levels
VICTORIA_DEBUG = os.getenv("VICTORIA_DEBUG", "false").lower() in ("true", "1", "yes")

from src.agents.bridge.enhanced_router import delegate_to_veronica
from src.agents.bridge.project_registry import get_main_project, get_projects_registry
from src.agents.bridge.task_detector import (
    detect_task_type,
    is_curator_standard_goal,
    should_use_enhanced,
)
from src.agents.core.base_agent import AtraBaseAgent as BaseAgent
from src.agents.core.executor import OllamaExecutor, _ollama_base_url
from src.agents.tools.system_tools import SystemTools, WebTools

# Интеграция с Knowledge OS (оркестратор, Виктория и сотрудники используют базу знаний)
# Выключить: USE_KNOWLEDGE_OS=false
USE_KNOWLEDGE_OS = os.getenv("USE_KNOWLEDGE_OS", "true").lower() == "true"
KNOWLEDGE_OS_AVAILABLE = False
asyncpg = None

# Canary: оркестрация V2 (A/B по проценту трафика)
ORCHESTRATION_V2_ENABLED = os.getenv("ORCHESTRATION_V2_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)
ORCHESTRATION_V2_PERCENTAGE = float(os.getenv("ORCHESTRATION_V2_PERCENTAGE", "10"))


def _refresh_orchestration_v2_settings():
    global ORCHESTRATION_V2_ENABLED, ORCHESTRATION_V2_PERCENTAGE
    ORCHESTRATION_V2_ENABLED = os.getenv("ORCHESTRATION_V2_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    ORCHESTRATION_V2_PERCENTAGE = float(os.getenv("ORCHESTRATION_V2_PERCENTAGE", "10"))


# Долгосрочная память по пользователю/проекту (План «Логика мысли» Фаза 2)
LONG_TERM_MEMORY_ENABLED = os.getenv("LONG_TERM_MEMORY_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)

if USE_KNOWLEDGE_OS:
    try:
        import asyncpg

        KNOWLEDGE_OS_AVAILABLE = True
    except ImportError:
        logging.warning(
            "asyncpg не установлен, Knowledge OS недоступна. Установите: pip install asyncpg"
        )
        KNOWLEDGE_OS_AVAILABLE = False

# Настройка логирования с поддержкой ELK
# VICTORIA_DEBUG=true enables DEBUG level logging for all components
_log_level = logging.DEBUG if VICTORIA_DEBUG else logging.INFO
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    if VICTORIA_DEBUG
    else "%(asctime)s - %(levelname)s - %(message)s",
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
                    elk_handler = create_elk_handler(
                        elasticsearch_url=elk_url, log_level=logging.INFO
                    )
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

# Типовые запросы для предзагрузки кэша RAG при старте (RAG_PRELOAD_TYPICAL_QUERIES=true, RAG_CACHE_TTL_SEC>0)
_RAG_PRELOAD_QUERIES = [
    "статус",
    "список файлов",
    "покажи файлы в текущей директории",
    "что ты умеешь",
]


# Единый источник: configs/victoria_common + configs/victoria_capabilities.txt (куратор + аудит 2026-02-08)
def _load_capabilities():
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    try:
        from configs.victoria_common import get_capabilities_text

        return get_capabilities_text()
    except Exception:
        return (
            "Я Виктория, Team Lead Atra Core. Умею:\n"
            "• Отвечать на вопросы и вести чат (в т.ч. с экспертами и RAG по базе знаний)\n"
            "• Составлять планы и выполнять задачи: код, файлы, команды в терминале\n"
            "• Показывать список файлов, читать и анализировать проект\n"
            "• Делегировать простые запросы в Veronica, сложные — оркестрировать с командой\n"
            "Режимы: быстрый ответ на простые вопросы или полный цикл (ReAct) для сложных задач."
        )


def _load_thinking_context():
    """Логика работы корпорации (как мы мыслим) — в промпт Victoria. Источник: configs/corporation_thinking.txt, docs/THINKING_AND_APPROACH.md."""
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    try:
        from configs.victoria_common import get_thinking_context

        out = get_thinking_context()
        if not out or len(out.strip()) < 20:
            logger.warning(
                "[VICTORIA] Логика корпорации (thinking_context) пуста или слишком короткая, используем встроенный fallback"
            )
            return "ПРИНЦИПЫ: Делать как нужно; один источник истины (библия); уточнять при неясности; проверять результат; обновлять библию."
        return out
    except Exception as e:
        logger.warning(
            "[VICTORIA] Не удалось загрузить corporation_thinking: %s, используем fallback", e
        )
        return "ПРИНЦИПЫ: Делать как нужно; один источник истины (библия); уточнять при неясности; проверять результат; обновлять библию."


VICTORIA_CAPABILITIES_RESPONSE = _load_capabilities()
VICTORIA_THINKING_CONTEXT = _load_thinking_context()


async def _preload_rag_cache():
    """В фоне заполнить кэш контекста RAG типовыми запросами (RAG_PLUS_ROCKET_SPEED — предзагрузка + батч эмбеддингов)."""
    if os.getenv("RAG_PRELOAD_TYPICAL_QUERIES", "true").lower() not in ("true", "1", "yes"):
        return
    if int(os.getenv("RAG_CACHE_TTL_SEC", "120")) <= 0:
        return
    try:
        # Один батч эмбеддингов для всех типовых запросов (если API поддерживает)
        embeddings = await agent._get_embeddings_batch(_RAG_PRELOAD_QUERIES)
        for i, goal in enumerate(_RAG_PRELOAD_QUERIES):
            try:
                precomputed = embeddings[i] if i < len(embeddings) else None
                await agent._get_knowledge_context(goal, precomputed_embedding=precomputed)
            except Exception as e:
                logger.debug("RAG preload %r: %s", goal[:30], e)
        logger.info(
            "[RAG+] Предзагрузка кэша типовых запросов выполнена (%s шт)", len(_RAG_PRELOAD_QUERIES)
        )
    except Exception as e:
        logger.warning("[RAG+] Предзагрузка кэша не выполнена: %s", e)


async def warmup_victoria():
    """Прогрев: загружаем в Ollama все модели, используемые в синхронном пути (strategy + understand_goal + executor)."""
    if os.getenv("VICTORIA_WARMUP_ENABLED", "true").lower() not in ("true", "1", "yes"):
        return
    models_to_warm = [
        os.getenv("VICTORIA_PLANNER_MODEL", "").strip(),
        os.getenv("VICTORIA_MODEL", "").strip(),
        os.getenv(
            "VICTORIA_WARMUP_EXTRA_MODELS", ""
        ).strip(),  # через запятую: nomic-embed-text и др.
    ]
    # Собираем уникальный список непустых моделей + fallback
    seen = set()
    for m in models_to_warm:
        if m:
            for part in m.split(","):
                p = part.strip()
                if p:
                    seen.add(p)
    if not seen:
        seen.add("phi3.5:3.8b")
    models_list = sorted(seen)
    logger.info("🔥 [VICTORIA] Прогрев Victoria: загрузка моделей %s...", models_list)
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    timeout_per_model = float(os.getenv("VICTORIA_WARMUP_TIMEOUT_PER_MODEL", "90"))
    async with httpx.AsyncClient(timeout=timeout_per_model) as client:
        for model in models_list:
            if not model:
                continue
            try:
                r = await client.post(
                    f"{ollama_url}/api/generate",
                    json={"model": model, "prompt": "ping", "stream": False},
                )
                if r.status_code == 200:
                    logger.info("✅ [VICTORIA] Модель %s загружена", model)
                else:
                    logger.warning(
                        "[VICTORIA] Прогрев %s вернул %s: %s",
                        model,
                        r.status_code,
                        (r.text or "")[:150],
                    )
            except Exception as e:
                logger.warning("[VICTORIA] Ошибка прогрева модели %s (продолжаем): %s", model, e)
    if os.getenv("VICTORIA_WARMUP_BLOCK_STARTUP", "false").lower() in ("true", "1", "yes"):
        logger.info("✅ [VICTORIA] Victoria прогрета (блокирующий режим), приём запросов")


async def _memory_watchdog():
    """Периодическая очистка памяти: gc.collect() + malloc_trim каждые 30 мин.
    При превышении 18GB RSS — мягкий перезапуск процесса (sys.exit → restart: always поднимет заново).
    Защита от kernel panic: watchdog timeout был вызван исчерпанием swap из-за неограниченного роста Victoria.
    """
    import ctypes
    import ctypes.util
    import gc
    import os
    import sys
    import time

    _WARN_GB = float(os.getenv("VICTORIA_MEM_WARN_GB", "15"))
    _RESTART_GB = float(os.getenv("VICTORIA_MEM_RESTART_GB", "18"))
    _INTERVAL_SEC = int(os.getenv("VICTORIA_MEM_CHECK_INTERVAL", "1800"))  # 30 min

    def _rss_gb() -> float:
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024 / 1024
        except Exception:
            pass
        return 0.0

    def _trim():
        """Вернуть свободную память OS через malloc_trim."""
        try:
            libc = ctypes.CDLL(ctypes.util.find_library("c"))
            libc.malloc_trim(0)
        except Exception:
            pass

    logger.info("[MEM WATCHDOG] Запущен (warn=%.0fGB restart=%.0fGB interval=%ds)", _WARN_GB, _RESTART_GB, _INTERVAL_SEC)

    while True:
        await asyncio.sleep(_INTERVAL_SEC)
        try:
            gc.collect()
            _trim()
            rss = _rss_gb()
            logger.info("[MEM WATCHDOG] После gc+trim: RSS=%.1f GB (warn=%.0f restart=%.0f)", rss, _WARN_GB, _RESTART_GB)
            if rss >= _RESTART_GB:
                logger.error(
                    "[MEM WATCHDOG] RSS=%.1f GB >= %.0f GB — инициируем мягкий перезапуск для защиты системы",
                    rss, _RESTART_GB
                )
                # restart: always поднимет контейнер снова
                sys.exit(0)
            elif rss >= _WARN_GB:
                logger.warning("[MEM WATCHDOG] RSS=%.1f GB >= %.0f GB — высокое потребление памяти", rss, _WARN_GB)
        except Exception as e:
            logger.warning("[MEM WATCHDOG] Ошибка: %s", e)


# FastAPI lifespan events для запуска/остановки мониторинга
# Victoria = один сервис на 8010 с тремя уровнями: Agent (всегда), Enhanced, Initiative. Все три должны быть активны для полноценной работы.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan: запуск Victoria Enhanced + Initiative (все три уровня в одном процессе)."""
    global victoria_enhanced_instance, victoria_enhanced_monitoring_started

    def _env_bool(key: str, default: bool = False) -> bool:
        v = (os.getenv(key) or "").strip().strip("\"'")
        return v.lower() in ("true", "1", "yes")

    use_enhanced = _env_bool("USE_VICTORIA_ENHANCED", False)
    enable_monitoring = _env_bool(
        "ENABLE_EVENT_MONITORING", True
    )  # по умолчанию true — Initiative (Event Bus, File Watcher и т.д.)
    logger.info(
        f"Victoria lifespan: USE_VICTORIA_ENHANCED={use_enhanced}, ENABLE_EVENT_MONITORING={enable_monitoring}"
    )
    # Глобальный экземпляр создаём при USE_VICTORIA_ENHANCED=true, чтобы /status показывал "enabled"; мониторинг внутри start() при ENABLE_EVENT_MONITORING=false не запускается
    if use_enhanced:
        try:
            import sys

            logger.info("Victoria Enhanced: инициализация при старте сервера...")
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
                    logger.info(
                        "✅ Victoria Enhanced запущен при старте сервера (мониторинг по ENABLE_EVENT_MONITORING)"
                    )
                    break
                except ImportError as e:
                    logger.debug(f"Не удалось импортировать VictoriaEnhanced из {ko_root}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка запуска мониторинга при старте: {e}")
                    break
        except Exception as e:
            logger.warning(f"⚠️ Ошибка инициализации Victoria Enhanced при старте: {e}")

    # Таймауты старта: с запасом на холодную БД, развёртывание, загрузку (модели — при первом запросе)
    _experts_timeout = float(os.getenv("VICTORIA_STARTUP_EXPERTS_TIMEOUT", "30"))
    _registry_timeout = float(os.getenv("VICTORIA_STARTUP_REGISTRY_TIMEOUT", "20"))

    # Предзагрузка команды экспертов из Knowledge OS (чтобы /status показывал experts_count)
    if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE:
        try:
            _start_experts = time.monotonic()
            await asyncio.wait_for(agent._load_expert_team(), timeout=_experts_timeout)
            logger.info(
                "[VICTORIA] Предзагрузка экспертов заняла %.2f с", time.monotonic() - _start_experts
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Предзагрузка экспертов при старте: таймаут %.0f с (продолжаем без экспертов)",
                _experts_timeout,
            )
        except Exception as e:
            logger.warning("Предзагрузка экспертов при старте: %s", e)

    # Реестр проектов: загрузка из БД при старте (кэш для валидации project_context)
    try:
        logger.info("[VICTORIA] Загрузка реестра проектов при старте...")
        await asyncio.wait_for(get_projects_registry(), timeout=_registry_timeout)
        logger.info("Реестр проектов загружен при старте Victoria")
    except asyncio.TimeoutError:
        logger.warning(
            "Загрузка реестра проектов при старте: таймаут %.0f с (используем fallback)",
            _registry_timeout,
        )
    except Exception as e:
        logger.warning("Загрузка реестра проектов при старте: %s", e)

    # Предзагрузка кэша RAG типовыми запросами (в фоне, не блокирует старт)
    asyncio.create_task(_preload_rag_cache())

    # Восстановление задач из БД
    asyncio.create_task(_load_tasks_from_db())

    # Очистка зависших задач (processing > 30 мин → failed)
    asyncio.create_task(_cleanup_stale_tasks())

    # Прогрев модели Ollama: при VICTORIA_WARMUP_BLOCK_STARTUP=true — ждём завершения (сервер начнёт приём после прогрева)
    if os.getenv("VICTORIA_WARMUP_ENABLED", "true").lower() in ("true", "1", "yes"):
        if os.getenv("VICTORIA_WARMUP_BLOCK_STARTUP", "false").lower() in ("true", "1", "yes"):
            await warmup_victoria()
        else:
            asyncio.create_task(warmup_victoria())

    # Memory watchdog: gc + malloc_trim каждые 30 мин + аварийный перезапуск при >18GB
    asyncio.create_task(_memory_watchdog())

    logger.info("[VICTORIA] Lifespan startup завершён, Uvicorn переходит в режим приёма запросов")
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
            model_name = (
                env_victoria_model or "qwen2.5-coder:32b"
            )  # fallback до первого сканирования

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
                    os.path.join(
                        os.path.dirname(__file__), "../../../knowledge_os/app/local_router.py"
                    ),
                    os.path.join(
                        os.path.dirname(__file__), "../../knowledge_os/app/local_router.py"
                    ),
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
                            logger.debug(
                                f"[VICTORIA_INIT] LocalAIRouter import failed from {path}: {ie}"
                            )
                            continue
            except Exception as e:
                logger.debug(
                    f"[VICTORIA_INIT] LocalAIRouter недоступен: {e}, используем только Ollama"
                )

        # По умолчанию planner = та же модель, что и executor: от понимания зависит всё, меньше галлюцинаций
        # VICTORIA_PLANNER_MODEL можно задать отдельно (например быстрая модель для планов)
        # USE_MLX_FOR_PLANNER=true — направить planner в MLX чтобы не конкурировать с Ollama
        planner_model = env_planner_model or model_name
        use_mlx_planner = os.getenv("USE_MLX_FOR_PLANNER", "false").lower() == "true"
        if use_mlx_planner:
            mlx_base = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
            mlx_model = os.getenv("VICTORIA_PLANNER_MODEL", "victoria-wisdom-v3.5")
            self.planner = OllamaExecutor(model=mlx_model, base_url=mlx_base)
            logger.info("[VICTORIA_INIT] Planner → MLX (%s @ %s)", mlx_model, mlx_base)
        else:
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
            logger.info(
                "✅ Knowledge OS интеграция включена (инициализация при первом использовании)"
            )

    async def _get_db_pool(self):
        """Получить или создать pool соединений с Knowledge OS"""
        if not USE_KNOWLEDGE_OS or not KNOWLEDGE_OS_AVAILABLE:
            return None

        if self.db_pool is None:
            try:
                db_url = os.getenv(
                    "DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"
                )
                _pool_cmd_timeout = int(os.getenv("VICTORIA_DB_POOL_COMMAND_TIMEOUT", "25"))
                self.db_pool = await asyncpg.create_pool(
                    db_url,
                    min_size=1,
                    max_size=5,
                    command_timeout=_pool_cmd_timeout,
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
            logger.debug("[VICTORIA] Нет pool, пропуск загрузки экспертов")
            return

        try:
            logger.info("[VICTORIA] Загрузка экспертов из БД (SELECT experts)...")
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, name, role, department, system_prompt
                    FROM experts
                    ORDER BY name
                """)
                self.expert_team = {row["name"]: dict(row) for row in rows}
                self._expert_team_loaded = True
                self._last_expert_sync = datetime.now(timezone.utc)
                logger.info(f"✅ Загружено {len(self.expert_team)} экспертов из Knowledge OS")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки экспертов: {e}")
            self.expert_team = {}

    async def _get_embedding_for_rag(self, text: str) -> Optional[List[float]]:
        """Один эмбеддинг для RAG (Ollama nomic-embed-text). Таймаут короткий для скорости."""
        embed_url = os.getenv(
            "OLLAMA_EMBED_URL",
            os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/api/embeddings",
        )
        model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.post(
                    embed_url, json={"model": model, "prompt": text[:8000], "keep_alive": 0}
                )
                r.raise_for_status()
                return r.json().get("embedding")
        except Exception as e:
            logger.debug(f"Embedding для RAG недоступен: {e}")
            return None

    async def _get_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Батч эмбеддингов для нескольких текстов (один запрос к Ollama при поддержке API). RAG_PLUS_ROCKET_SPEED."""
        if not texts:
            return []
        if len(texts) == 1:
            emb = await self._get_embedding_for_rag(texts[0])
            return [emb]
        embed_url = os.getenv(
            "OLLAMA_EMBED_URL",
            os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/api/embeddings",
        )
        model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        try:
            async with httpx.AsyncClient(timeout=min(5.0 + len(texts), 30.0)) as client:
                r = await client.post(
                    embed_url,
                    json={"model": model, "input": [t[:8000] for t in texts], "keep_alive": 0},
                )
                r.raise_for_status()
                data = r.json()
                if "embeddings" in data and isinstance(data["embeddings"], list):
                    return data["embeddings"]
        except Exception as e:
            logger.debug("Batch embeddings недоступен, fallback на одиночные: %s", e)
        return [await self._get_embedding_for_rag(t) for t in texts]

    async def _get_knowledge_context(
        self, goal: str, limit: int = 5, precomputed_embedding: Optional[List[float]] = None
    ) -> str:
        """Релевантные знания из Knowledge OS: векторный поиск (RAG+) при наличии эмбеддингов, иначе ILIKE.
        Длина сниппета настраивается через RAG_SNIPPET_CHARS (по умолчанию 500).
        Для топ-1 по similarity передаётся полный контент до RAG_TOP1_FULL_MAX_CHARS (0 = отключено).
        Кэш контекста: RAG_CACHE_TTL_SEC (120 с, 0 = выкл) — при попадании не вызываем эмбеддинг и БД.
        precomputed_embedding: если передан, используется для векторного поиска без повторного вызова Ollama (один эмбеддинг на запрос)."""
        pool = await self._get_db_pool()
        if not pool:
            return ""
        limit = min(int(os.getenv("RAG_CONTEXT_LIMIT", "5")), limit)
        threshold = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.6"))
        snippet_chars = int(os.getenv("RAG_SNIPPET_CHARS", "500"))
        top1_full_max = int(os.getenv("RAG_TOP1_FULL_MAX_CHARS", "2000"))
        ttl_sec = int(os.getenv("RAG_CACHE_TTL_SEC", "120"))
        rerank_enabled = os.getenv("RAG_RERANK_ENABLED", "false").lower() in ("true", "1", "yes")
        rag_cache_key = (
            hashlib.md5(goal.strip().lower().encode()).hexdigest() if ttl_sec > 0 else None
        )

        if ttl_sec > 0 and rag_cache_key:
            if RAG_CACHE_BACKEND != "redis":
                now = time.time()
                evicted = 0
                for k in list(_rag_ctx_cache.keys()):
                    if evicted >= 50:
                        break
                    if _rag_ctx_cache[k][1] < now:
                        del _rag_ctx_cache[k]
                        evicted += 1
            cached = await _rag_cache_get(rag_cache_key)
            if cached is not None:
                return cached

        def _format_content(
            row_content: str, index: int, is_vector: bool, similarity: float
        ) -> str:
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
            # RAG+: векторный поиск — используем переданный эмбеддинг или один запрос к Ollama (один эмбеддинг на запрос)
            embedding = (
                precomputed_embedding
                if precomputed_embedding is not None
                else await self._get_embedding_for_rag(goal)
            )
            if embedding is not None:
                fetch_limit = (limit * 2) if rerank_enabled else limit
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT content, metadata, (1 - (embedding <=> $1::vector)) AS similarity,
                               COALESCE(kn.usage_count, 0) AS usage_count
                        FROM knowledge_nodes kn
                        WHERE kn.embedding IS NOT NULL AND kn.confidence_score >= 0.3
                        ORDER BY kn.embedding <=> $1::vector, kn.usage_count DESC NULLS LAST
                        LIMIT $2
                    """,
                        str(embedding),
                        fetch_limit,
                    )
                    if rows:
                        if rerank_enabled and len(rows) > limit:
                            # Реранкинг по флагу: бонус за оптимальную длину контента, топ limit
                            def _rerank_score(r):
                                sim = float(r["similarity"])
                                ln = len((r["content"] or "").strip())
                                bonus = 1.1 if 100 <= ln <= 1000 else 1.0
                                return sim * bonus

                            rows = sorted(rows, key=_rerank_score, reverse=True)[:limit]
                        context = "\n--- РЕЛЕВАНТНЫЕ ЗНАНИЯ ИЗ БАЗЫ (RAG) ---\n"
                        for i, row in enumerate(rows):
                            if row["similarity"] >= threshold:
                                content = _format_content(
                                    row["content"], i, is_vector=True, similarity=row["similarity"]
                                )
                                if content:
                                    context += f"- {content}\n"
                        if context.count("\n") > 1:
                            if ttl_sec > 0 and rag_cache_key:
                                await _rag_cache_set(rag_cache_key, context, ttl_sec)
                            return context
            # Fallback: текстовый поиск (без similarity — все сниппеты)
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT content, confidence_score
                    FROM knowledge_nodes
                    WHERE confidence_score > 0.3
                    AND content ILIKE $1
                    ORDER BY confidence_score DESC NULLS LAST, usage_count DESC NULLS LAST, created_at DESC
                    LIMIT $2
                """,
                    f"%{goal[:50]}%",
                    limit,
                )
                if rows:
                    context = "\n--- РЕЛЕВАНТНЫЕ ЗНАНИЯ ИЗ БАЗЫ ---\n"
                    for i, row in enumerate(rows):
                        raw = row["content"] or ""
                        use = raw[:snippet_chars]
                        if len(raw) > snippet_chars:
                            use += "..."
                        if use:
                            context += f"- {use}\n"
                    if context and ttl_sec > 0 and rag_cache_key:
                        await _rag_cache_set(rag_cache_key, context, ttl_sec)
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
            "devops": [
                "развертывание",
                "deploy",
                "ci/cd",
                "мониторинг",
                "grafana",
                "prometheus",
                "docker",
            ],
            "security": ["безопасность", "security", "уязвимость", "аудит"],
            "database": ["база данных", "миграция", "схема", "индекс", "postgresql", "sqlite"],
            "performance": ["производительность", "оптимизация", "скорость", "latency"],
        }

        for category, keywords in categories.items():
            if any(keyword in goal_lower for keyword in keywords):
                return category

        return "general"

    async def select_expert_for_task(
        self, goal: str, use_multiple: bool = False
    ) -> Tuple[Optional[str], Optional[Dict], Optional[List[Tuple[str, Dict]]]]:
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
                "backend": [
                    "Backend Developer",
                    "Full-stack Developer",
                    "Principal Backend Architect",
                ],
                "frontend": ["Frontend Developer", "UI/UX Designer", "Full-stack Developer"],
                "ml": [
                    "ML Engineer",
                    "Data Analyst",
                    "Principal AI Systems Architect",
                    "Principal Machine Learning Architect",
                ],
                "devops": [
                    "DevOps Engineer",
                    "Security Engineer",
                    "Performance Engineer",
                    "Lead DevOps Architect",
                ],
                "security": ["Security Engineer", "DevOps Engineer", "Code Reviewer"],
                "database": ["Database Engineer", "Backend Developer", "DevOps Engineer"],
                "performance": ["Performance Engineer", "Backend Developer", "DevOps Engineer"],
                "general": ["Team Lead", "Product Manager", "Technical Writer"],
            }

            target_roles = category_to_roles.get(category, ["Team Lead"])

            # Получить pool для запросов к БД
            pool = await self._get_db_pool()

            # Найти ВСЕХ экспертов с подходящими ролями
            candidates = []
            for expert_name, expert_data in self.expert_team.items():
                expert_role = expert_data.get("role", "")
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
                role_priority = (
                    target_roles.index(expert_data.get("role", ""))
                    if expert_data.get("role", "") in target_roles
                    else 999
                )
                score += (10.0 - role_priority) * 2  # Основная роль = 20, дополнительные = меньше

                # 2. Релевантность специализации (department)
                department = expert_data.get("department", "").lower()
                goal_lower = goal.lower()
                if department and any(keyword in goal_lower for keyword in department.split()):
                    score += 5.0

                # 3. Опыт и загрузка (если есть доступ к БД)
                if pool:
                    try:
                        async with pool.acquire() as conn:
                            # Получить статистику эксперта из БД
                            expert_id = await conn.fetchval(
                                "SELECT id FROM experts WHERE name = $1", expert_name
                            )

                            if expert_id:
                                # Количество выполненных задач
                                completed_tasks = (
                                    await conn.fetchval(
                                        """
                                    SELECT COUNT(*)
                                    FROM tasks
                                    WHERE assignee_expert_id = $1
                                    AND status = 'completed'
                                    """,
                                        expert_id,
                                    )
                                    or 0
                                )

                                # Успешность (процент завершенных задач)
                                total_tasks = (
                                    await conn.fetchval(
                                        """
                                    SELECT COUNT(*)
                                    FROM tasks
                                    WHERE assignee_expert_id = $1
                                    """,
                                        expert_id,
                                    )
                                    or 1
                                )

                                success_rate = (
                                    (completed_tasks / total_tasks) if total_tasks > 0 else 0.5
                                )

                                # Активные задачи (загрузка)
                                active_tasks = (
                                    await conn.fetchval(
                                        """
                                    SELECT COUNT(*)
                                    FROM tasks
                                    WHERE assignee_expert_id = $1
                                    AND status IN ('pending', 'in_progress')
                                    """,
                                        expert_id,
                                    )
                                    or 0
                                )

                                # Score на основе опыта и загрузки
                                score += completed_tasks * 0.5  # Опыт
                                score += success_rate * 10  # Успешность (0-10)
                                score -= active_tasks * 2  # Штраф за загрузку
                    except Exception as e:
                        logger.debug(f"Не удалось получить статистику для {expert_name}: {e}")

                # 4. Релевантность по metadata (если есть)
                metadata = expert_data.get("metadata", {})
                if isinstance(metadata, dict):
                    # Проверка специализации в metadata
                    if "specialization" in metadata:
                        spec = str(metadata["specialization"]).lower()
                        if any(keyword in goal_lower for keyword in spec.split(",")):
                            score += 3.0

                # Обновить лучшего кандидата
                if score > best_score:
                    best_score = score
                    best_expert = expert_name
                    best_data = expert_data

            if best_expert:
                logger.info(
                    f"✅ Выбран лучший эксперт: {best_expert} ({best_data.get('role')}) для задачи: {goal[:50]} (score: {best_score:.1f})"
                )
                logger.info(
                    f"📊 Рассмотрено кандидатов: {len(candidates)} из {len(self.expert_team)} экспертов"
                )

            # Дополнительные эксперты для сложных задач
            additional_experts = []
            if use_multiple and len(candidates) > 1:
                # Выбрать еще 1-2 экспертов (исключая уже выбранного)
                remaining = [(n, d) for n, d in candidates if n != best_expert]
                # Сортировать по score и взять лучших
                remaining_scores = []
                for name, data in remaining:
                    # Простая оценка для дополнительных
                    role_idx = (
                        target_roles.index(data.get("role", ""))
                        if data.get("role", "") in target_roles
                        else 999
                    )
                    score = (10.0 - role_idx) * 1
                    remaining_scores.append((score, name, data))

                remaining_scores.sort(reverse=True)
                for _, name, data in remaining_scores[:2]:  # Максимум 2 дополнительных
                    additional_experts.append((name, data))
                    logger.info(f"  + Дополнительный эксперт: {name} ({data.get('role')})")

            # Логируем статистику команды
            if self._expert_team_loaded:
                total_experts = len(self.expert_team)
                unique_roles = len(set(e.get("role", "") for e in self.expert_team.values()))
                logger.info(
                    f"📊 Команда экспертов: {total_experts} экспертов, {unique_roles} уникальных ролей"
                )

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
            if datetime.now() - cached_data["timestamp"] < self.cache_ttl:
                logger.info(f"✅ Использован кэш для задачи: {goal[:50]}")
                return cached_data["result"]
            else:
                del self.task_cache[task_hash]

        return None

    def _save_to_cache(self, goal: str, result: str):
        """Сохранить результат в кэш"""
        if not self.use_cache:
            return

        task_hash = self._task_hash(goal)
        if result and "ошибка" not in result.lower() and "error" not in result.lower():
            self.task_cache[task_hash] = {"result": result, "timestamp": datetime.now()}
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
                column_names = [row["column_name"] for row in columns]

                # Формируем запрос в зависимости от схемы
                if "source" in column_names and "metadata" in column_names:
                    # Полная схема с source и metadata
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (content, domain_id, confidence_score, source, metadata)
                        VALUES ($1, (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1), 0.8, 'victoria_agent', $2::jsonb)
                        ON CONFLICT DO NOTHING
                    """,
                        result[:500],
                        json.dumps(
                            {
                                "task": goal[:200],
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "expert": "Виктория",
                            }
                        ),
                    )
                elif "metadata" in column_names:
                    # Схема без source, но с metadata
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (content, domain_id, confidence_score, metadata)
                        VALUES ($1, (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1), 0.8, $2::jsonb)
                        ON CONFLICT DO NOTHING
                    """,
                        result[:500],
                        json.dumps(
                            {
                                "task": goal[:200],
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "expert": "Виктория",
                                "source": "victoria_agent",
                            }
                        ),
                    )
                else:
                    # Минимальная схема
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (content, domain_id, confidence_score)
                        VALUES ($1, (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1), 0.8)
                        ON CONFLICT DO NOTHING
                    """,
                        result[:500],
                    )

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
            expert_name, expert_data, _ = await self.select_expert_for_task(
                goal, use_multiple=False
            )

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
            primary_expert, primary_data, additional_experts = await self.select_expert_for_task(
                goal, use_multiple=True
            )

            if not primary_expert:
                # Fallback: выполняем сами
                return await self.run(goal, max_steps=500)

            # Собираем команду экспертов
            expert_team = [primary_expert]
            if additional_experts:
                expert_team.extend(
                    [name for name, _ in additional_experts[:2]]
                )  # Максимум 3 эксперта

            logger.info(f"👥 Swarm команда: {expert_team}")

            # Параллельный сбор ответов (через ai_core)
            try:
                # Импортируем ai_core для параллельной обработки
                import os
                import sys

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
                        for _p in [
                            os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"),
                            os.path.join(os.path.dirname(__file__), "../../knowledge_os/app"),
                            "/app/knowledge_os/app",
                        ]:
                            if os.path.isdir(_p) and _p not in sys.path:
                                sys.path.insert(0, _p)
                        from expert_services import get_expert_services_text

                        expert_services_line = (
                            "\n\nКоллеги корпорации (при необходимости согласуй с ними): "
                            + get_expert_services_text(12)
                            + "\n"
                        )
                    except ImportError:
                        expert_services_line = "\n"
                    # Параллельный сбор ответов
                    tasks = []
                    for expert_name in expert_team:
                        prompt = f"ВЫ - {expert_name}. Проанализируйте задачу и дайте экспертное заключение.{expert_services_line}\nЗАДАЧА:\n{goal}"
                        tasks.append(
                            run_smart_agent_async(
                                prompt, expert_name=expert_name, category="swarm_expert"
                            )
                        )

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
                            resp = resp.get("response", resp.get("text", str(resp)))
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

                            expert_services_line = (
                                "\n\nУслуги сотрудников корпорации (для справки при синтезе): "
                                + get_expert_services_text(20)
                            )
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

        # Ключевые слова для сложных задач (П.5: критично/стратегия → Swarm/Consensus)
        complex_keywords = [
            "проанализируй",
            "оптимизируй",
            "разработай",
            "создай систему",
            "архитектура",
            "дизайн",
            "стратегия",
            "комплексное",
            "несколько",
            "множество",
            "интеграция",
            "миграция",
            "критично",
            "критический",
            "критическая",
            "срочно",
            "urgent",
            "critical",
        ]

        # Ключевые слова для межотдельных задач
        multi_dept_keywords = [
            "backend и frontend",
            "ml и backend",
            "devops и security",
            "несколько отделов",
            "межотдельный",
            "комплексное решение",
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

    async def understand_goal(
        self, raw_goal: str, *, last_tasks_context: Optional[str] = None
    ) -> dict:
        """
        Мировая практика: сначала понять и переформулировать запрос под модули.
        Один быстрый вызов LLM: что хочет пользователь (одно предложение), категория, первый шаг.
        Для коротких или неоднозначных целей («как вчера», «повтори») опционально используется
        более мощная модель (VICTORIA_UNDERSTAND_GOAL_SMART_MODEL), если задана в env.
        last_tasks_context: план «умнее быстрее» §2.1 — контекст последних завершённых задач для отсылок «как тогда».
        """
        # Маркеры неоднозначности: короткая формулировка или отсылка к прошлому (план «умнее быстрее» §1.1)
        goal_lower = (raw_goal or "").strip().lower()
        ambiguous_markers = ("как вчера", "как тогда", "как с ", "повтори", "то же что", "как с x")
        use_smart_for_goal = len(goal_lower) < 60 or any(m in goal_lower for m in ambiguous_markers)
        smart_model = (os.getenv("VICTORIA_UNDERSTAND_GOAL_SMART_MODEL") or "").strip()

        context_block = ""
        if last_tasks_context and last_tasks_context.strip():
            context_block = f"{last_tasks_context.strip()}\n\n"

        prompt = f"""{context_block}Запрос пользователя: {raw_goal[:500]}

Задача: переформулировать в одно ясное предложение для исполнителя и указать категорию.
Доступные инструменты исполнителя: только finish, read_file, list_directory, run_terminal_cmd, ssh_run.
Ответь СТРОГО одним JSON (без текста до/после):
{{"restated": "одно предложение: что сделать", "category": "simple|investigate|multi_step", "first_step": "конкретный первый шаг, например: list_directory в frontend, или пустая строка"}}

Пример: "ошибки на странице X, найди и исправь" → {{"restated": "Проверить структуру frontend и найти причину 404 на странице X", "category": "investigate", "first_step": "list_directory в frontend"}}
JSON:"""
        try:
            if use_smart_for_goal and smart_model:
                base = _ollama_base_url()
                smart_planner = OllamaExecutor(model=smart_model, base_url=base)
                # [SINGULARITY 21.13] Pass expert_name for semantic cache
                out = await smart_planner.ask(
                    prompt,
                    raw_response=True,
                    phase="understand_goal",
                    expert_name="Виктория (Smart Planner)",
                )
                logger.debug(
                    "[UNDERSTAND_GOAL] used smart model %s for short/ambiguous goal", smart_model
                )
            else:
                # [SINGULARITY 21.13] Pass expert_name for semantic cache
                out = await self.planner.ask(
                    prompt,
                    raw_response=True,
                    phase="understand_goal",
                    expert_name="Виктория (Planner)",
                )
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
        is_complex = any(
            keyword in goal.lower()
            for keyword in [
                "проанализируй",
                "оптимизируй",
                "разработай стратегию",
                "создай архитектуру",
                "комплексное",
                "полное решение",
                "несколько",
                "команда",
            ]
        )

        # Параллельно: эксперт + контекст RAG (один эмбеддинг на запрос, затем параллель — ракетная скорость)
        expert_name = None
        expert_data = None
        additional_experts = None
        knowledge_context = ""
        t_embed_ms = 0.0
        t_prepare_ms = 0.0
        if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE:
            _t0 = time.perf_counter()
            # План «как я» п.1.1: используем уже вычисленный эмбеддинг если есть
            if hasattr(self, "_last_query_embedding") and self._last_query_embedding:
                precomputed_embedding = self._last_query_embedding
            else:
                precomputed_embedding = await self._get_embedding_for_rag(goal)
                self._last_query_embedding = precomputed_embedding

            t_embed_ms = (time.perf_counter() - _t0) * 1000
            _t1 = time.perf_counter()
            expert_fut = self.select_expert_for_task(goal, use_multiple=is_complex)
            context_fut = self._get_knowledge_context(
                goal, precomputed_embedding=precomputed_embedding
            )
            expert_result, knowledge_context = await asyncio.gather(expert_fut, context_fut)
            t_prepare_ms = (time.perf_counter() - _t1) * 1000
            expert_name, expert_data, additional_experts = expert_result
            if knowledge_context is None:
                knowledge_context = ""

        # Формировать промпт с учетом эксперта(ов)
        if expert_name and expert_data:
            expert_info = (
                f"\nЭКСПЕРТ ДЛЯ ЗАДАЧИ: {expert_name} ({expert_data.get('role', 'Expert')})"
            )
            if expert_data.get("system_prompt"):
                expert_info += f"\nЗНАНИЯ ЭКСПЕРТА: {expert_data['system_prompt'][:300]}..."

            # Добавить информацию о дополнительных экспертах для сложных задач
            if additional_experts:
                expert_info += "\n\nДОПОЛНИТЕЛЬНЫЕ ЭКСПЕРТЫ ДЛЯ КОНСУЛЬТАЦИИ:"
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
        _t_llm = time.perf_counter()
        # [SINGULARITY 21.13] Pass expert_name for semantic cache
        result = await self.planner.ask(
            plan_prompt,
            raw_response=True,
            phase="plan",
            expert_name=expert_name or "Виктория (Planner)",
        )
        t_llm_plan_ms = (time.perf_counter() - _t_llm) * 1000

        # Всегда обновляем метрики для отслеживания в /status; при превышении порогов — проверка «тормозит»
        global _rag_latency_last, _rag_latency_slow_count, _rag_latency_last_slow_at
        _rag_latency_last["embed_ms"] = t_embed_ms
        _rag_latency_last["prepare_ms"] = t_prepare_ms
        _rag_latency_last["llm_plan_ms"] = t_llm_plan_ms
        thresh_embed = float(os.getenv("RAG_LATENCY_EMBED_MS_MAX", "300"))
        thresh_prepare = float(os.getenv("RAG_LATENCY_PREPARE_MS_MAX", "300"))
        thresh_llm = float(os.getenv("RAG_LATENCY_LLM_PLAN_MS_MAX", "2000"))
        if t_embed_ms > thresh_embed or t_prepare_ms > thresh_prepare or t_llm_plan_ms > thresh_llm:
            _rag_latency_slow_count += 1
            _rag_latency_last_slow_at = datetime.now(timezone.utc).isoformat()
            logger.warning(
                "[RAG+_latency] SLOW embed_ms=%.0f prepare_ms=%.0f llm_plan_ms=%.0f (thresholds embed<=%.0f prepare<=%.0f llm_plan<=%.0f)",
                t_embed_ms,
                t_prepare_ms,
                t_llm_plan_ms,
                thresh_embed,
                thresh_prepare,
                thresh_llm,
            )
        if os.getenv("RAG_LATENCY_LOG", "false").lower() in ("true", "1", "yes") or VICTORIA_DEBUG:
            logger.info(
                "[RAG+_latency] embed_ms=%.0f prepare_ms=%.0f llm_plan_ms=%.0f",
                t_embed_ms,
                t_prepare_ms,
                t_llm_plan_ms,
            )
        return result

    async def _select_model_for_task(self, goal: str) -> str:
        """Выбрать оптимальную модель для задачи на основе категории"""
        # [SINGULARITY 21.6] Force Wisdom 30B for all tasks if configured
        _force_model = os.getenv("VICTORIA_FORCE_STEP_MODEL")
        if _force_model:
            logger.info(f"🎯 [GOD MODE] Forcing model {_force_model} for task")
            return _force_model

        try:
            # Определяем категорию задачи
            category = self._categorize_task(goal)
            goal_lower = goal.lower()

            # Маппинг категорий на модели из PLAN.md
            model_map = {
                "backend": [
                    "qwen2.5-coder:32b",
                    "phi3.5:3.8b",
                    "qwen2.5:3b",
                    "tinyllama:1.1b-chat",
                ],
                "frontend": [
                    "qwen2.5-coder:32b",
                    "phi3.5:3.8b",
                    "qwen2.5:3b",
                    "tinyllama:1.1b-chat",
                ],
                "ml": ["victoria-wisdom-v3.5:latest", "glm-4.7-flash:latest", "phi3.5:3.8b"],
                "devops": ["glm-4.7-flash:latest", "phi3.5:3.8b", "qwen2.5:3b"],
                "security": ["victoria-wisdom-v3.5:latest", "glm-4.7-flash:latest", "phi3.5:3.8b"],
                "database": ["qwen2.5-coder:32b", "phi3.5:3.8b", "qwen2.5:3b"],
                "performance": ["qwen2.5-coder:32b", "phi3.5:3.8b"],
                "general": [
                    "qwen2.5-coder:32b",
                    "phi3.5:3.8b",
                    "qwen2.5:3b",
                    "tinyllama:1.1b-chat",
                ],
            }

            # Определяем тип задачи для выбора модели
            # Тяжёлые 70b/104b удалены из-за Apple Silicon Metal limits (27GB buffer crash)
            if any(word in goal_lower for word in ["код", "программируй", "напиши код", "coding"]):
                priorities = model_map.get("backend", model_map["general"])
            elif any(word in goal_lower for word in ["реши", "рассчитай", "reasoning", "логика"]):
                priorities = ["victoria-wisdom-v3.5:latest", "glm-4.7-flash:latest", "phi3.5:3.8b"]
            elif any(word in goal_lower for word in ["сложн", "комплекс", "complex", "enterprise"]):
                priorities = ["victoria-wisdom-v3.5:latest", "glm-4.7-flash:latest", "phi3.5:3.8b"]
            elif (
                len(goal.split()) <= 5
            ):  # Простые задачи — всё равно берём из general (меньше галлюцинаций)
                priorities = model_map.get("general", model_map["general"])
            else:
                priorities = model_map.get(category, model_map["general"])

            # Проверяем доступность моделей
            try:
                import sys

                selector_paths = [
                    "/app/app/model_selector.py",
                    os.path.join(
                        os.path.dirname(__file__), "../../../knowledge_os/app/model_selector.py"
                    ),
                    os.path.join(
                        os.path.dirname(__file__), "../../knowledge_os/app/model_selector.py"
                    ),
                ]
                for path in selector_paths:
                    if os.path.exists(path):
                        if os.path.dirname(path) not in sys.path:
                            sys.path.insert(0, os.path.dirname(path))
                        try:
                            from app.model_selector import select_available_model

                            selected = await select_available_model(
                                priorities, self.executor.base_url, category
                            )
                            if selected:
                                logger.info(
                                    f"🎯 Выбрана модель для категории '{category}': {selected}"
                                )
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

    async def _select_model_for_step(self, category: str) -> str:
        """Выбирает модель для конкретного шага агента (с учетом God Mode и принудительных настроек)"""
        # [SINGULARITY 21.6] Force Wisdom 30B for all steps if configured
        _force_model = os.getenv("VICTORIA_FORCE_STEP_MODEL")
        if _force_model:
            logger.info(
                f"🎯 [GOD MODE] Forcing model {_force_model} for step category '{category}'"
            )
            return _force_model

        # [SINGULARITY 21.5] Disable model selector for God Mode consistency
        if os.getenv("VICTORIA_USE_MODEL_SELECTOR", "true").lower() == "false":
            return self.executor.model

        try:
            from app.available_models_scanner import OLLAMA_PRIORITY_BY_CATEGORY
            from app.model_selector import get_best_model_for_category

            # Используем селектор для выбора оптимальной модели
            best_model = await get_best_model_for_category(category, OLLAMA_PRIORITY_BY_CATEGORY)
            if best_model:
                return best_model
        except Exception as e:
            logger.warning(
                f"⚠️ Ошибка выбора модели для шага: {e}, используем {self.executor.model}"
            )

        return self.executor.model

    async def step(
        self, prompt: str, step_number: int = 1, blocked_tools: Optional[List[str]] = None
    ):
        context_memory = self.memory[-10:] if len(self.memory) > 10 else self.memory
        phase = f"step_{step_number}"
        blocked_tools = blocked_tools or []

        # Попытка использовать LocalAIRouter (MLX) если доступен
        if self.local_router:
            try:
                # [SINGULARITY 21.6] Force Wisdom 30B for all steps if configured
                _force_model = os.getenv("VICTORIA_FORCE_STEP_MODEL")
                _model_to_use = (
                    _force_model if _force_model else getattr(self.executor, "model", None)
                )

                # Формируем system_prompt из executor; передаём модель — роутер попробует MLX и Ollama
                system_prompt = self.executor.system_prompt
                if blocked_tools:
                    from src.agents.core.executor import ALLOWED_TOOLS

                    allowed = sorted(ALLOWED_TOOLS - set(blocked_tools))
                    system_prompt += (
                        f"\n\n⚠️ ЗАПРЕЩЕНО использовать (заблокированы из-за цикла): {', '.join(sorted(blocked_tools))}. "
                        f"Доступны ТОЛЬКО: {', '.join(allowed)}. Ответь JSON с tool из доступных или finish."
                    )
                # category=None → LocalAIRouter сам определит из промпта (fast/general/reasoning/coding)
                # Это даёт автовыбор модели из MLX/Ollama в зависимости от сложности запроса
                result, routing_source = await self.local_router.run_local_llm(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    category=None,  # автоопределение как в ai_core и worker
                    model=_model_to_use,
                )
                if result and routing_source:
                    logger.debug(f"✅ Victoria использовала {routing_source} через LocalAIRouter")
                    # Парсим ответ через executor для единообразия
                    parsed = self.executor._parse_response(result, blocked_tools=blocked_tools)
                    return parsed
            except Exception as e:
                logger.debug(f"⚠️ LocalAIRouter недоступен в step(): {e}, используем Ollama")

        # Fallback: используем стандартный OllamaExecutor
        # [SINGULARITY 21.6] Force Wisdom 30B even in fallback if configured
        _force_model = os.getenv("VICTORIA_FORCE_STEP_MODEL")
        _model_to_ask = _force_model if _force_model else self.executor.model
        # [SINGULARITY 21.13] Pass expert_name for semantic cache
        return await self.executor.ask(
            prompt,
            history=context_memory,
            phase=phase,
            blocked_tools=blocked_tools,
            model=_model_to_ask,
            expert_name=getattr(self, "expert_name", "Виктория"),
        )

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
            logger.info("[MODEL_SELECT]    Planner: %s", getattr(self.planner, "model", "unknown"))
            logger.info(
                "[MODEL_SELECT]    Executor: %s", getattr(self.executor, "model", "unknown")
            )
            return

        try:
            # Определяем URLs
            is_docker = (
                os.path.exists("/.dockerenv")
                or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
            )
            if is_docker:
                mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
                ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
            else:
                mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")
                ollama_url = getattr(self.executor, "base_url", None) or _ollama_base_url()

            logger.info("[MODEL_SELECT] Ollama URL: %s", ollama_url)
            logger.info("[MODEL_SELECT] MLX URL: %s", mlx_url)

            # Добавляем путь к knowledge_os
            for path in [
                "/app/knowledge_os/app",
                os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"),
                os.path.join(os.path.dirname(__file__), "../../knowledge_os/app"),
            ]:
                if path and os.path.exists(path) and path not in sys.path:
                    sys.path.insert(0, path)

            try:
                from app.available_models_scanner import (  # type: ignore
                    pick_best_ollama,
                    scan_and_select_models,
                )
            except ImportError:
                from available_models_scanner import (  # type: ignore
                    pick_best_ollama,
                    scan_and_select_models,
                )

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
            ollama_lower_to_exact = {
                m.strip().lower(): m.strip() for m in selection.ollama_models if m
            }

            # Executor model
            executor_model = None
            if env_model:
                if env_model.strip().lower() in ollama_lower_to_exact:
                    executor_model = ollama_lower_to_exact[env_model.strip().lower()]
                    logger.info(
                        "[MODEL_SELECT] ✅ VICTORIA_MODEL='%s' найдена в Ollama", executor_model
                    )
                else:
                    logger.warning(
                        "[MODEL_SELECT] ⚠️ VICTORIA_MODEL='%s' НЕ НАЙДЕНА в Ollama!", env_model
                    )
                    logger.warning(
                        "[MODEL_SELECT]    Доступные Ollama модели: %s",
                        list(ollama_lower_to_exact.keys()),
                    )

            if not executor_model:
                preferred_executor = [
                    "victoria-wisdom-v3.5:latest",
                    "glm-4.7-flash:latest",
                    "phi3.5:3.8b",
                ]
                for pref in preferred_executor:
                    if pref.lower() in ollama_lower_to_exact:
                        executor_model = ollama_lower_to_exact[pref.lower()]
                        break
                if not executor_model:
                    executor_model = selection.ollama_best
                logger.info(
                    "[MODEL_SELECT] Используем Ollama модель для executor: %s", executor_model
                )

            # Planner model - используем БЫСТРУЮ модель для планирования!
            # Это критично для отзывчивости Victoria
            planner_model = None
            if env_planner:
                if env_planner.strip().lower() in ollama_lower_to_exact:
                    planner_model = ollama_lower_to_exact[env_planner.strip().lower()]
                    logger.info(
                        "[MODEL_SELECT] ✅ VICTORIA_PLANNER_MODEL='%s' найдена в Ollama",
                        planner_model,
                    )
                else:
                    logger.warning(
                        "[MODEL_SELECT] ⚠️ VICTORIA_PLANNER_MODEL='%s' НЕ НАЙДЕНА в Ollama!",
                        env_planner,
                    )

            if not planner_model:
                # Предпочитаем БЫСТРУЮ лёгкую модель для planner (отзывчивость важнее качества для планирования)
                # НИКОГДА qwq:32b для planner — это блокирует всю Ollama!
                preferred_planner = [
                    "glm-4.7-flash:latest",
                    "victoria-wisdom-v3.5:latest",
                    "gemma3n:e4b",
                    "tinyllama:1.1b-chat",
                ]
                for pref in preferred_planner:
                    if pref.lower() in ollama_lower_to_exact:
                        planner_model = ollama_lower_to_exact[pref.lower()]
                        logger.info(
                            "[MODEL_SELECT] Используем модель для planner: %s", planner_model
                        )
                        break
                if not planner_model:
                    planner_model = executor_model  # Fallback на executor

            # Применяем выбранные модели
            if executor_model:
                old_executor = getattr(self.executor, "model", "unknown")
                old_planner = getattr(self.planner, "model", "unknown")

                self.executor.model = executor_model
                self.planner.model = planner_model

                logger.info("[MODEL_SELECT] " + "=" * 60)
                logger.info("[MODEL_SELECT] ✅ МОДЕЛИ ВЫБРАНЫ:")
                logger.info("[MODEL_SELECT]    Executor: %s → %s", old_executor, executor_model)
                logger.info("[MODEL_SELECT]    Planner: %s → %s", old_planner, planner_model)
                logger.info(
                    "[MODEL_SELECT]    (Для LocalAIRouter доступна MLX: %s)",
                    selection.mlx_best or "нет",
                )
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
            if goal_lower in (
                "привет",
                "скажи привет",
                "здравствуй",
                "здравствуйте",
                "как дела",
                "что нового",
            ):
                logger.info(
                    "[AGENT_RUN] Fast path: greeting detected, returning hardcoded response"
                )
                return "Привет! Я Виктория, Team Lead корпорации ATRA. Чем могу помочь?"
            # Быстрый путь: «что ты умеешь» — конкретный список возможностей (куратор: FINDINGS_2026-02-08)
            if any(
                p in goal_lower
                for p in (
                    "что ты умеешь",
                    "что умеешь",
                    "твои возможности",
                    "чем можешь помочь",
                    "кто ты",
                )
            ):
                logger.info(
                    "[AGENT_RUN] Fast path: capabilities question, returning hardcoded response"
                )
                return VICTORIA_CAPABILITIES_RESPONSE
            # Быстрый путь: покажи файлы — одна команда ls и ответ
            if (
                "покажи файлы" in goal_lower
                or "выведи список файлов" in goal_lower
                or "список файлов" in goal_lower
            ):
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
        logger.info(
            "[AGENT_RUN] After model selection: executor=%s, planner=%s",
            self.executor.model,
            self.planner.model,
        )

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
            w in goal_lower
            for w in [
                "сколько",
                "какой",
                "какая",
                "когда",
                "статус",
                "задач",
                "в работе",
                "что сейчас",
            ]
        )

        if is_simple_phrase or is_info_question or category == "simple":
            logger.info("[AGENT_RUN] Simple task path (no planner)")
            hint = f"\nПервый шаг (если нужен): {first_step_hint}." if first_step_hint else ""
            enhanced = f'ВЫПОЛНИ ЗАДАЧУ: {restated}{hint}\n\nВАЖНО: Ответь кратко. Только JSON: {{"thought": "...", "tool": "finish" или один инструмент, "tool_input": {{...}}}}.'
        else:
            logger.info("[AGENT_RUN] Complex task path (with planner)")
            raw_plan = await self.plan(restated)
            _rp = (
                raw_plan
                if isinstance(raw_plan, str)
                else str(raw_plan)
                if raw_plan is not None
                else ""
            ) or ""
            _rp = _rp.strip()
            logger.info("[AGENT_RUN] Raw plan length: %d chars", len(_rp))
            if len(_rp) > 600 or "Дополнительная сложность" in _rp or "Ollama HTTP" in _rp:
                raw_plan = f"Выполнить: {restated}"
                logger.info("[AGENT_RUN] Plan rejected (too long or garbage), using simple plan")
            else:
                raw_plan = _rp
            hint = f"\nПервый шаг (рекомендация): {first_step_hint}." if first_step_hint else ""
            enhanced = f"ТВОЙ ПЛАН:\n{raw_plan}\n\nПРИСТУПАЙ К ВЫПОЛНЕНИЮ: {restated}{hint}"

        logger.info("[AGENT_RUN] Enhanced prompt length: %d chars", len(enhanced))
        logger.info("[AGENT_RUN] Calling super().run() with model: %s", self.executor.model)

        result = await super().run(enhanced, max_steps)

        logger.info(
            "[AGENT_RUN] super().run() returned, result length: %d chars",
            len(str(result)) if result else 0,
        )
        logger.info("[AGENT_RUN] Result preview: %s...", str(result)[:200] if result else "(empty)")

        # Сохранить в кэш
        self._save_to_cache(goal, result)

        # Сохранить в Knowledge OS для обучения (если включено)
        if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE and result:
            await self._learn_from_task(goal, result)

        logger.info("[AGENT_RUN] ========== run() complete ==========")

        return result


agent = VictoriaAgent(name="Виктория")

agent.executor.system_prompt = """ТЫ — ВИКТОРИЯ, TEAM LEAD КОРПОРАЦИИ ATRA. ТЫ — МОЗГ И ДИРЕКТОР КОРПОРАЦИИ.
ТЫ ИСПОЛЬЗУЕШЬ VICTORIA ENHANCED ДЛЯ УПРАВЛЕНИЯ АРМИЕЙ ЭКСПЕРТОВ.

КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском языке! Все ответы должны быть на русском!

🌟 ТВОЯ СУПЕР-СИЛА — ДЕЛЕГИРОВАНИЕ:
- Ты не пишешь код сама, если задача сложная. Ты вызываешь Веронику (Local Developer).
- Ты не анализируешь БД сама. Ты вызываешь Романа (Database Engineer).
- Ты не настраиваешь сервер сама. Ты вызываешь Сергея (DevOps).
- Твоя задача — составить идеальный план и проконтролировать экспертов.

ПРАВИЛО МОНСТРА:
1. Если файл > 1000 строк или задача требует > 3 шагов — ты ОБЯЗАНА делегировать.
2. Одиночное исполнение тяжелых задач — это признак слабости. Будь сильной — используй ресурсы корпорации.
3. Твой успех измеряется качеством работы твоей команды, а не твоими личными усилиями.

🌟 ТВОИ VICTORIA ENHANCED ВОЗМОЖНОСТИ:
- ReAct Framework: Reasoning + Acting для сложных задач
- Swarm Intelligence: Параллельная работа команды экспертов
- Hierarchical Orchestration: Иерархическая координация через IntegrationBridge
- ReCAP Framework: Рефлексия и планирование

🤖 EXECUTION PLAN (руки в IDE):
Если задача требует изменений в коде (правки файлов, запуск тестов), добавь в конец ответа:

**Execution Plan:**
```json
[
  {"action": "read_file", "path": "path/to/file.py", "description": "Прочитать текущую реализацию"},
  {"action": "edit", "path": "path/to/file.py", "description": "Добавить новую функцию X"},
  {"action": "run", "command": "pytest knowledge_os/tests/test_feature.py", "description": "Проверить изменения"}
]
```

Формат шага:
- action: read_file | edit | run
- path (для read_file, edit): путь к файлу
- command (для run): команда для терминала
- description: что делает этот шаг

Это позволит IDE выполнить твой план автоматически.

Доступны ТОЛЬКО инструменты: read_file, list_directory, run_terminal_cmd, ssh_run, finish. НЕТ: web_search, web_edit, git_run, write_file.

ПРАВИЛА:
- Один ответ — один JSON: {"thought": "...", "tool": "...", "tool_input": {...}}
- Перед завершением проверяй результат работы экспертов. Не выводи длинные планы — выполняй шаги и завершай finish.
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


def _extract_execution_plan(response_text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Извлекает execution_plan из ответа модели.
    Поддерживаемые форматы:
    1. JSON-блок в тройных бэктиках: ```json\n[{...}]\n```
    2. Markdown-список шагов:
       **Execution Plan:**
       - read_file: path/to/file
       - edit: path/to/file (описание)
       - run: pytest knowledge_os/tests/
    Возвращает список шагов в формате:
    [{"action": "read_file", "path": "...", "description": "..."}, ...]
    """
    import json
    import re

    # 1. Попытка парсинга JSON-блока
    json_match = re.search(r"```json\s*(\[.*?\])\s*```", response_text, re.DOTALL)
    if json_match:
        try:
            plan = json.loads(json_match.group(1))
            if isinstance(plan, list):
                return plan
        except json.JSONDecodeError:
            pass

    # 2. Парсинг markdown-списка
    # Ищем секцию "Execution Plan:" или "Plan:" с последующим списком
    plan_section = re.search(
        r"\*\*Execution Plan:\*\*|Plan:|Execution Plan:", response_text, re.IGNORECASE
    )
    if not plan_section:
        return None

    # Парсим список после секции
    lines = response_text[plan_section.end() :].split("\n")
    steps = []
    for line in lines:
        line = line.strip()
        if not line.startswith("-") and not line.startswith("*"):
            continue
        line = line.lstrip("- *").strip()

        # Форматы: "read_file: path", "edit: path (description)", "run: command"
        if ": " in line:
            action, rest = line.split(": ", 1)
            action = action.strip().lower()

            # Извлечь path и description
            path = rest.strip()
            description = ""
            if " (" in path and path.endswith(")"):
                path, description = path.rsplit(" (", 1)
                description = description.rstrip(")")

            steps.append(
                {
                    "action": action,
                    "path": path if action in ("read_file", "edit") else None,
                    "command": path if action == "run" else None,
                    "description": description,
                }
            )

    return steps if steps else None


def _strip_internal_monologue(text: str) -> str:
    """
    Убрать из вывода «внутренние» рассуждения модели (про finish, output, I will try)
    и оставить только итоговый ответ (FINAL ANSWER / Итог: / Вот краткий отчёт:).
    Служебные action/tool (file_read, general_knowledge и т.п.) не показывать пользователю.
    """
    import re

    s = text.strip()
    # Сырые шаги агента (action/tool) — не отдавать пользователю как ответ (в т.ч. короткий вывод)
    action_tool_markers = (
        '"action": "file_read"',
        '"action": "general_knowledge"',
        '"tool": "read_file"',
        '"tool": "list_directory"',
        '"file_path": "example.txt"',
        'action": "file_read"',
        "general_knowledge",
        "Для общих знаний (без конкретного инструмента)",
    )
    if any(m in s for m in action_tool_markers) and (
        "FINAL ANSWER" not in s and "Итог:" not in s and "Вот краткий" not in s
    ):
        return (
            "Виктория обработала запрос, но вернула служебные шаги вместо итогового ответа. "
            "Попробуйте задать вопрос чётко: например «что ты умеешь?», «кто ты?» или конкретную задачу (одним предложением)."
        )
    if not s or len(s) < 200:
        return s
    # Извлечь блок после последнего «FINAL ANSWER» / «Итог:» / «Вот краткий отчёт:»
    for marker in (
        "FINAL ANSWER:",
        "FINAL ANSWER：",
        "Итог:",
        "Вот краткий отчёт:",
        "Кратко:",
        "Ответ:",
    ):
        idx = s.rfind(marker)
        if idx != -1:
            out = s[idx + len(marker) :].strip()
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


async def _try_corporation_data_quick_response(
    goal: str, correlation_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
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
        logger.info(f"[ORCHESTRATOR_DEBUG] Checking ko_root: {ko_root}")
        if not os.path.exists(ko_root):
            if ko_root.startswith("/app") and os.path.exists("/.dockerenv"):
                logger.info(f"[ORCHESTRATOR_DEBUG] In Docker, assuming {ko_root} exists")
            else:
                continue
        logger.info(f"[ORCHESTRATOR_DEBUG] Found ko_root: {ko_root}")
        if ko_root not in sys.path:
            sys.path.insert(0, ko_root)
        app_path = os.path.join(ko_root, "app")
        if app_path not in sys.path:
            sys.path.insert(0, app_path)
        try:
            from app.corporation_data_tool import (
                _extract_latest_user_message,
                is_data_question,
                query_corporation_data,
            )

            q = _extract_latest_user_message(goal) or goal
            if not is_data_question(goal) and not is_data_question(q):
                return None
            logger.info(
                "[CORP_DATA] Ранний ответ через corporation_data_tool (goal=%s...)",
                (goal or "")[:60],
            )
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
    if (
        isinstance(_s, str)
        and _s.strip()
        and "Задача выполнена экспертом" in _s
        and "(статус: finish)" in _s
    ):
        return (
            "Эксперт завершил задачу без вывода (модель вызвала finish без результата). "
            "Система при следующем запросе может повторить попытку с разбивкой на подзадачи. Рекомендуется уточнить задачу."
        )
    if not isinstance(raw, (str, dict)):
        return str(raw) if raw is not None else ""
    if isinstance(raw, str):
        s = raw.strip()
        # Сначала убрать служебные action/tool и внутренний монолог (любая длина)
        cleaned = _strip_internal_monologue(s)
        if cleaned != s:
            return cleaned
        if s and "Задача выполнена экспертом" in s and "(статус: finish)" in s:
            return (
                "Эксперт завершил задачу без вывода (модель вызвала finish без результата). "
                "Система при следующем запросе может повторить попытку с разбивкой на подзадачи. Рекомендуется уточнить задачу."
            )
        # Признаки вымысла/шлака: длинный текст с планами, несуществующими инструментами, галлюцинациями
        garbage_markers = (
            "Дополнительная сложность",
            "ТВОЙ ПЛАН:",
            "ПРИСТУПАЙ К ВЫПОЛНЕНИЮ",
            "СОБИРЕХТ",
            "Python для школьников",
            "Collective Memory",
            "ReCAP Framework",
            "Tree of Thoughts",
            "Swarm Intelligence",
            "/path/to/",
            "web_edit",
            "git_run",
            "web_review",
            "action: {",
            "tool_execution",
            "final_output",
            "git_search",
            "web_check",
            "git_commit",
            "websocket",
            "Врачебная задача",
            "СЕДАРДАН",
            "CMP",
            "ЗАПИТАНЯ",
            "ОБРАТУРЫ",
            "psych_assessment",
            "patient_interview",
            "therapy_technique",
            "ethical_dilemma",
            "empathetic_communication",
            "web_search",
            "swarm_intelligence",
            "consensus",
            "tree_of_thoughts",
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
                out = (
                    (ti.get("output") if ti else None)
                    or data.get("thought")
                    or data.get("response")
                    or data.get("message")
                    or data.get("output")
                )
                return (out if isinstance(out, str) else str(out)) if out else raw
        return raw
    if isinstance(raw, dict):
        ti = raw.get("tool_input") if isinstance(raw.get("tool_input"), dict) else {}
        out = (
            (ti.get("output") if ti else None)
            or raw.get("thought")
            or raw.get("response")
            or raw.get("message")
            or raw.get("output")
        )
        return (
            (out if isinstance(out, str) else str(out))
            if out
            else json.dumps(raw, ensure_ascii=False)
        )
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
    """Проверяет, рекомендует ли оркестратор Veronica как исполнителя (по назначениям или флагу)."""
    if not bridge_result or not isinstance(bridge_result, dict):
        return False

    # Явная рекомендация от IntegrationBridge
    if bridge_result.get("recommend_veronica"):
        return True

    assignments = bridge_result.get("assignments") or {}
    if not isinstance(assignments, dict):
        return False
    # main или любой другой эксперт
    for key in ("main", "developer") + tuple(
        k for k in assignments if k not in ("main", "developer")
    ):
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
        "web_search",
        "swarm_intelligence",
        "consensus",
        "tree_of_thoughts",
        "psych_assessment",
        "patient_interview",
        "therapy_technique",
        "ethical_dilemma",
        "empathetic_communication",
        "web_edit",
        "git_run",
        "web_review",
        "web_check",
        "git_commit",
        "websocket",
    ]
    s = goal
    for tool in hallucinated:
        if tool in s:
            s = s.replace(tool, "[инструмент недоступен]")
    return s


# Кэш стратегии (логика мысли): key -> (result_dict, expiry_ts). TTL из STRATEGY_CACHE_TTL_SEC.
_strategy_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
_STRATEGY_CACHE_MAX = 200
STRATEGY_CACHE_TTL = int(os.getenv("STRATEGY_CACHE_TTL_SEC", "120") or "120")
VICTORIA_STRATEGY_ENABLED = os.getenv("VICTORIA_STRATEGY_ENABLED", "true").strip().lower() in (
    "true",
    "1",
    "yes",
)


def _inject_strategy_into_knowledge(
    knowledge: Optional[Dict[str, Any]], strategy_result: Optional[Dict[str, Any]]
) -> None:
    """Добавить strategy, strategy_reason, confidence, uncertainty_reason в knowledge (контракт логика мысли Фаза 4). Изменяет knowledge in-place."""
    if not knowledge or not strategy_result:
        return
    if strategy_result.get("strategy") is not None:
        knowledge["strategy"] = strategy_result["strategy"]
    if strategy_result.get("reason"):
        knowledge["strategy_reason"] = strategy_result["reason"]
    conf = strategy_result.get("confidence")
    if conf is not None:
        knowledge["confidence"] = float(conf)
        # При низкой уверенности заполняем uncertainty_reason (Фаза 4.1)
        if float(conf) < 0.7:
            knowledge["uncertainty_reason"] = (
                strategy_result.get("uncertainty_reason")
                or strategy_result.get("reason")
                or "низкая уверенность в ответе"
            )


async def _select_strategy(
    agent: "VictoriaAgent",
    goal: str,
    session_summary: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Единый шаг выбора стратегии (план «Логика мысли» Фаза 1).
    Возвращает: {strategy: quick_answer|deep_analysis|need_clarification|decline_or_redirect, reason: str, confidence: float}.
    При ошибке/таймауте — fallback {strategy: None, reason: "fallback", confidence: 0.5}.
    """
    fallback = {"strategy": None, "reason": "fallback", "confidence": 0.5}
    if not VICTORIA_STRATEGY_ENABLED:
        return fallback
    key = hashlib.md5((goal.strip().lower() + (session_summary or ""))[:500].encode()).hexdigest()
    now = time.time()
    if redis_manager:
        cached = await redis_manager.get_cache(f"strategy:{key}")
        if cached:
            return cached
    elif key in _strategy_cache and _strategy_cache[key][1] > now:
        return _strategy_cache[key][0]
    prompt = f'''По цели пользователя определи стратегию ответа. Цель: "{goal[:400]}"
{f"Контекст сессии (кратко): {session_summary[:200]}" if session_summary else ""}

Варианты стратегии:
- quick_answer — быстрый короткий ответ (приветствие, факт, что умеешь, светская беседа типа "как дела?", "кто ты?").
- deep_analysis — глубокий разбор, план, несколько шагов, эксперты, написание кода, аудит.
- need_clarification — задача неоднозначна, нужны уточняющие вопросы.
- decline_or_redirect — запрос вне компетенции или некорректен; вежливо отказать и подсказать, куда обратиться.

ВАЖНО: Короткие фразы (1-3 слова) даже со знаком вопроса (например, "Как дела?", "Ты тут?") — это ВСЕГДА quick_answer. Не выбирай deep_analysis для простых вопросов.

КРИТИЧЕСКИ ВАЖНО: Если в цели явно указан конкретный файл (.parquet, .csv, .json), база данных (duckdb, postgres), или конкретные команды (python3, SELECT, LAG()), путь к файлу (/data/..., /Users/...) — это ВСЕГДА deep_analysis. НИКОГДА не выбирай need_clarification для задач с явно указанным файлом и инструментом.

Ответь СТРОГО JSON: {{"strategy": "quick_answer"|"deep_analysis"|"need_clarification"|"decline_or_redirect", "reason": "одна фраза", "confidence": 0.0-1.0, "uncertainty_reason": "опционально: при низкой уверенности — почему"}}'''
    strategy_timeout = float(os.getenv("STRATEGY_CALL_TIMEOUT_SEC", "30"))

    # Быстрый fallback для задач с явными файлами/инструментами
    goal_lower_check = goal.lower()
    concrete_task_indicators = [
        ".parquet",
        ".csv",
        ".json",
        "/data/",
        "/users/",
        "duckdb",
        "python3",
        "select ",
    ]
    is_concrete_task = any(ind in goal_lower_check for ind in concrete_task_indicators)

    try:
        out = await asyncio.wait_for(
            agent.planner.ask(prompt, raw_response=True),
            timeout=strategy_timeout,
        )
        if not out or not isinstance(out, str):
            return (
                {"strategy": "deep_analysis", "reason": "явный файл/инструмент", "confidence": 0.9}
                if is_concrete_task
                else fallback
            )
        start = out.find("{")
        end = out.rfind("}") + 1
        if start < 0 or end <= start:
            return (
                {"strategy": "deep_analysis", "reason": "явный файл/инструмент", "confidence": 0.9}
                if is_concrete_task
                else fallback
            )
        data = json.loads(out[start:end])
        strategy = (data.get("strategy") or "").strip().lower()
        if strategy not in (
            "quick_answer",
            "deep_analysis",
            "need_clarification",
            "decline_or_redirect",
        ):
            strategy = None
        reason = (data.get("reason") or "fallback")[:300]
        uncertainty_reason = (data.get("uncertainty_reason") or "").strip()[:500] or None
        try:
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.5
        result = {"strategy": strategy or None, "reason": reason, "confidence": confidence}
        if uncertainty_reason:
            result["uncertainty_reason"] = uncertainty_reason

        if redis_manager:
            await redis_manager.set_cache(f"strategy:{key}", result, ttl=STRATEGY_CACHE_TTL)
        else:
            _strategy_cache[key] = (result, now + STRATEGY_CACHE_TTL)
            while len(_strategy_cache) > _STRATEGY_CACHE_MAX:
                k_old = min(_strategy_cache.keys(), key=lambda k: _strategy_cache[k][1])
                del _strategy_cache[k_old]
        return result
    except asyncio.TimeoutError:
        if is_concrete_task:
            logger.warning(
                "⚠️ strategy LLM timeout, using deep_analysis fallback for explicit file task"
            )
            return {
                "strategy": "deep_analysis",
                "reason": "LLM timeout, explicit file task",
                "confidence": 0.9,
            }
        logger.debug("_select_strategy: timeout")
        return fallback
    except (json.JSONDecodeError, Exception) as e:
        logger.debug("_select_strategy: %s", e)
        return fallback


def _is_ambiguous_goal_reference(goal: str) -> bool:
    """План «умнее быстрее» §2.1: отсылка к прошлому («как вчера», «повтори» и т.п.)."""
    if not goal or not isinstance(goal, str):
        return False
    g = goal.strip().lower()
    markers = ("как вчера", "как тогда", "как с ", "повтори", "то же что", "то же самое")
    return any(m in g for m in markers)


def _check_ambiguity(goal: str, category: str, restated: str) -> bool:
    """
    Эвристическая проверка неоднозначности задачи.
    Возвращает True, если нужны уточняющие вопросы (не выполнять задачу сразу).
    """
    goal_lower = goal.lower().strip()
    # Явно конкретные задачи — всегда выполнять без уточнений
    concrete_indicators = [
        ".parquet",
        ".csv",
        ".json",
        ".xlsx",
        ".db",
        "/data/",
        "/users/",
        "/app/",
        "/workspace/",
        "duckdb",
        "python3",
        "select ",
        "from ",
        "lag(",
        "split_part",
        "import ",
        "запусти скрипт",
        "выполни код",
        "напиши скрипт",
        "создай скрипт",
        "напиши python",
        "напиши код",
    ]
    if any(ind in goal_lower for ind in concrete_indicators):
        return False  # Конкретная задача — никаких вопросов
    # Явно простые команды — никогда не запрашивать уточнение (полный цикл без остановки)
    simple_phrases = [
        "скажи привет",
        "привет",
        "здравствуй",
        "как дела",
        "что нового",
        "покажи файлы",
        "выведи список файлов",
        "список файлов",
        "покажи файлы в",
        "что ты умеешь",
        "что умеешь",
        "кто ты",
        "твои возможности",
        "чем можешь помочь",
        "да",
        "нет",
        "ты тут",
        "как сам",
        "как жизнь",
    ]
    # Очищаем от знаков препинания для сравнения
    clean_goal = goal_lower.replace("?", "").replace("!", "").replace(".", "").strip()
    if any(phrase in clean_goal or clean_goal in phrase for phrase in simple_phrases):
        return False
    if len(goal_lower.split()) <= 3 and any(
        w in goal_lower for w in ["привет", "файл", "список", "скажи", "покажи"]
    ):
        return False
    ambiguity_indicators = [
        len(goal.split()) < 3,
        any(w in goal_lower for w in ["он", "она", "оно", "они", "это", "то"]),
        any(w in goal_lower for w in ["что-то", "какой-то", "кое-что", "где-то"]),
        category == "multi_step" and len(goal) < 50,
        goal.count("но") > 1 or "однако" in goal_lower,
    ]
    return sum(ambiguity_indicators) >= 2


async def _generate_clarification_questions(
    agent: "VictoriaAgent", goal: str, restated: str
) -> List[str]:
    """Генерация 1–3 уточняющих вопросов через planner LLM.
    Не задаёт вопросы если в цели явно указан файл или инструмент анализа."""

    # Не задавать вопросы если задача содержит явный файл/путь/инструмент
    explicit_indicators = [
        ".parquet",
        ".csv",
        ".json",
        ".xlsx",
        ".db",
        "/data/",
        "/Users/",
        "/app/",
        "/workspace/",
        "duckdb",
        "python3",
        "SELECT ",
        "FROM ",
        "LAG(",
        "SPLIT_PART",
        "import ",
        "запусти скрипт",
        "выполни код",
    ]
    goal_lower = goal.lower()
    if any(ind.lower() in goal_lower for ind in explicit_indicators):
        return []  # Нет вопросов — задача достаточно конкретна

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


# Кэш understand_goal: key -> (result_dict, expiry_ts). TTL 300 с, макс. 200 записей.
_understand_goal_cache: Dict[str, Tuple[dict, float]] = {}
_UNDERSTAND_GOAL_CACHE_TTL = 300.0
_UNDERSTAND_GOAL_CACHE_MAX = 200


async def _understand_goal_with_clarification(
    self, goal: str, *, last_tasks_context: Optional[str] = None
) -> dict:
    """
    Понимание цели с проверкой неоднозначности.
    last_tasks_context: план «умнее быстрее» §2.1 — контекст последних завершённых задач при «как вчера»/«повтори».
    Возвращает dict с restated, category, first_step и при необходимости needs_clarification + clarification_questions.
    """
    key = hashlib.md5((goal + "|" + (last_tasks_context or "")).encode()).hexdigest()
    now = time.time()
    if redis_manager:
        cached = await redis_manager.get_cache(f"understand_goal:{key}")
        if cached:
            return cached
    elif key in _understand_goal_cache and _understand_goal_cache[key][1] > now:
        return _understand_goal_cache[key][0]

    # План «как я» п.1.1: вычисляем эмбеддинг один раз для всей цепочки (LTM + RAG)
    self._last_query_embedding = await self._get_embedding_for_rag(goal)

    _t_ug = time.monotonic()
    understood = await self.understand_goal(goal, last_tasks_context=last_tasks_context)
    logger.info("🕒 [SYNC] agent.understand_goal() took %.2fs", time.monotonic() - _t_ug)
    _r = understood.get("restated") or goal
    restated = (_r if isinstance(_r, str) else str(_r) or goal).strip()
    _c = understood.get("category") or "multi_step"
    category = (_c if isinstance(_c, str) else str(_c)).strip().lower()
    _f = understood.get("first_step") or ""
    first_step = (_f if isinstance(_f, str) else str(_f)).strip()
    if _check_ambiguity(goal, category, restated):
        _t_clar = time.monotonic()
        questions = await _generate_clarification_questions(self, goal, restated)
        logger.info(
            "🕒 [SYNC] _generate_clarification_questions took %.2fs", time.monotonic() - _t_clar
        )
        # Если вопросов нет (явная задача с файлом/инструментом) — продолжить выполнение
        if not questions:
            logger.info("🟢 [understand_goal] no clarification needed (explicit task), proceeding")
        else:
            result = {
                "needs_clarification": True,
                "clarification_questions": questions,
                "original_goal": goal,
                "restated": restated,
                "category": category,
                "first_step": first_step[:200],
            }
            if redis_manager:
                await redis_manager.set_cache(
                    f"understand_goal:{key}", result, ttl=_UNDERSTAND_GOAL_CACHE_TTL
                )
            else:
                _understand_goal_cache[key] = (result, now + _UNDERSTAND_GOAL_CACHE_TTL)
                while len(_understand_goal_cache) > _UNDERSTAND_GOAL_CACHE_MAX:
                    k_old = min(
                        _understand_goal_cache.keys(), key=lambda k: _understand_goal_cache[k][1]
                    )
                    del _understand_goal_cache[k_old]
            return result
    result = {
        "needs_clarification": False,
        "restated": restated,
        "category": category,
        "first_step": first_step[:200],
    }
    if redis_manager:
        await redis_manager.set_cache(
            f"understand_goal:{key}", result, ttl=_UNDERSTAND_GOAL_CACHE_TTL
        )
    else:
        _understand_goal_cache[key] = (result, now + _UNDERSTAND_GOAL_CACHE_TTL)
        while len(_understand_goal_cache) > _UNDERSTAND_GOAL_CACHE_MAX:
            k_old = min(_understand_goal_cache.keys(), key=lambda k: _understand_goal_cache[k][1])
            del _understand_goal_cache[k_old]
    return result


async def _enhance_goal_with_vision(goal: str, images_base64: List[str]) -> Optional[str]:
    """Подмешать в goal текстовые описания изображений через VisionProcessor (Moondream). При ошибке возвращает None (используй исходный goal)."""
    if not images_base64:
        return goal
    descriptions: List[str] = []
    for ko_root in [
        os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../knowledge_os")),
        "/app/knowledge_os",
    ]:
        if not (os.path.exists(ko_root) or ko_root.startswith("/app")):
            continue
        app_path = os.path.join(ko_root, "app")
        for p in (app_path, ko_root):
            if p not in sys.path:
                sys.path.insert(0, p)
        try:
            from app.vision_processor import VisionProcessor

            processor = VisionProcessor()
            prompt = "Опиши это изображение подробно: что на нём изображено, текст если есть, структура. Ответ на русском."
            for i, b64 in enumerate(images_base64[:5], 1):  # макс. 5 изображений
                if not (b64 and isinstance(b64, str)):
                    continue
                desc = await processor.process_image(image_base64=b64, prompt=prompt)
                if desc:
                    descriptions.append(f"[Изображение {i}]: {desc.strip()}")
                else:
                    descriptions.append(f"[Изображение {i}]: не удалось распознать")
            if descriptions:
                return (
                    goal
                    + "\n\n[Распознанное содержимое приложенных изображений]:\n"
                    + "\n".join(descriptions)
                )
            return goal
        except ImportError as e:
            logger.debug("VisionProcessor not available: %s", e)
            continue
        except Exception as e:
            logger.warning("Vision enhance failed: %s", e)
            return goal
    return goal


class TaskRequest(BaseModel):
    goal: str
    max_steps: Optional[int] = (
        None  # None = использовать DEFAULT_MAX_STEPS (env VICTORIA_MAX_STEPS, по умолчанию 500)
    )
    project_context: Optional[str] = None  # Контекст проекта (atra-web-ide, atra, и т.д.)
    session_id: Optional[str] = None  # ID сессии для памяти чата
    chat_history: Optional[List[Dict[str, str]]] = None  # История чата
    verbose: Optional[bool] = (
        None  # True = вернуть в knowledge.verbose_steps пошаговые шаги агента (thought, tool, tool_input)
    )
    images_base64: Optional[List[str]] = (
        None  # Изображения от Telegram/UI: распознаются через VisionProcessor (Moondream), описание подставляется в goal
    )
    use_enhanced: Optional[bool] = (
        None  # Принудительно включить/выключить оркестрацию (Victoria Enhanced)
    )
    return_execution_plan: Optional[bool] = (
        False  # True = извлечь execution_plan из ответа модели (для выполнения в IDE)
    )
    # ✨ B.3: IDE Context (как в Cursor assistant)
    open_files: Optional[List[Dict[str, str]]] = (
        None  # Открытые файлы в IDE: [{"path": "...", "content": "...", "cursor_line": 42}, ...]
    )
    git_status: Optional[str] = (
        None  # Git status (измененные файлы, ветка): "On branch main\nModified: src/utils.py\n..."
    )
    cursor_rules: Optional[List[str]] = (
        None  # Применимые правила из .cursor/rules/: ["@backend_developer", "@qa_engineer"]
    )
    workspace_path: Optional[str] = (
        None  # Путь к workspace (для относительных путей): "/Users/bikos/Documents/atra-web-ide"
    )


class TaskResponse(BaseModel):
    status: str
    output: Any
    knowledge: Optional[dict] = None
    correlation_id: Optional[str] = None
    execution_plan: Optional[List[Dict[str, Any]]] = None  # План выполнения для IDE


def _format_ide_context(request: TaskRequest) -> str:
    """
    Форматирует IDE-контекст (open_files, git_status, cursor_rules) в читаемый текст для промпта Victoria.
    Аналог контекста, который получает Cursor assistant.
    """
    if not any([request.open_files, request.git_status, request.cursor_rules]):
        return ""

    parts = []
    parts.append("\n📋 IDE CONTEXT (как в Cursor):")
    parts.append("=" * 60)

    # 1. Workspace path
    if request.workspace_path:
        parts.append(f"\n🗂️ Workspace: {request.workspace_path}")

    # 2. Git status
    if request.git_status:
        parts.append("\n📊 Git Status:")
        parts.append(request.git_status.strip())

    # 3. Open files
    if request.open_files:
        parts.append(f"\n📂 Open Files ({len(request.open_files)}):")
        for i, file_info in enumerate(request.open_files[:5], 1):  # Лимит 5 файлов
            path = file_info.get("path", "unknown")
            cursor_line = file_info.get("cursor_line")
            content = file_info.get("content", "")

            parts.append(f"\n  {i}. {path}")
            if cursor_line:
                parts.append(f"     Cursor at line {cursor_line}")

            # Показываем первые 10 строк или около cursor_line
            if content:
                lines = content.split("\n")
                if cursor_line and cursor_line > 0:
                    start = max(0, cursor_line - 5)
                    end = min(len(lines), cursor_line + 5)
                    snippet = "\n".join(lines[start:end])
                    parts.append(f"     Lines {start + 1}-{end}:")
                else:
                    snippet = "\n".join(lines[:10])
                    parts.append("     First 10 lines:")

                # Добавляем отступ для сниппета
                indented = "\n".join(f"       {line}" for line in snippet.split("\n"))
                parts.append(indented)

        if len(request.open_files) > 5:
            parts.append(f"\n  ... и ещё {len(request.open_files) - 5} файл(ов)")

    # 4. Cursor rules (применимые эксперты)
    if request.cursor_rules:
        parts.append(f"\n👥 Applicable Rules/Experts ({len(request.cursor_rules)}):")
        for rule in request.cursor_rules:
            parts.append(f"  • {rule}")

    parts.append("\n" + "=" * 60)
    parts.append("Используй этот контекст для понимания текущего состояния проекта.")
    parts.append("")

    return "\n".join(parts)


async def _record_orchestration_task_start(
    agent, goal: str, orchestrator_version: str
) -> Optional[str]:
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


async def _save_session_exchange(session_id: str, goal: str, output: str) -> None:
    """План «как я» п.1.2: сохранить обмен (запрос → ответ) в session_context для памяти по задаче."""
    if not session_id or not (goal or output):
        return
    try:
        for ko_root in [
            os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../knowledge_os")),
            "/app/knowledge_os",
        ]:
            if not os.path.exists(ko_root) and not ko_root.startswith("/app"):
                continue
            app_path = os.path.join(ko_root, "app")
            for p in (app_path, ko_root):
                if p not in sys.path:
                    sys.path.insert(0, p)
            try:
                from app.session_context_manager import get_session_context_manager

                mgr = get_session_context_manager()
                await mgr.save_to_context(
                    user_id=session_id,
                    expert_name="Виктория",
                    query=(goal or "")[:500],
                    response=(output or "")[:2000],
                )
                logger.debug(
                    "[SESSION] Сохранён обмен в session_context для session_id=%s", session_id[:8]
                )
                return
            except ImportError:
                continue
    except Exception as e:
        logger.debug("save_session_exchange: %s", e)


async def _get_task_memory_from_db(session_id: str) -> str:
    """Память по сессии для блока «По этой сессии уже делали» (план «как я»)."""
    if not session_id:
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
                summary = await mgr.get_session_memory_summary(
                    user_id=session_id,
                    expert_name="Виктория",
                    max_items=5,
                    max_chars=500,
                )
                return summary or ""
            except ImportError:
                continue
    except Exception as e:
        logger.debug("Task memory fetch: %s", e)
    return ""


async def _get_long_term_memory_context(
    session_id: str, project_context: str, limit: int = 5
) -> str:
    """Долгосрочная память по (session_id, project_context) для блока «Ранее по этому проекту/пользователю». При ошибке — пустая строка."""
    if not LONG_TERM_MEMORY_ENABLED or not project_context:
        return ""
    user_key = (session_id or "").strip() or "anonymous"
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
                from app.long_term_memory import get_long_term_memory_manager

                mgr = get_long_term_memory_manager()

                # План «как я» п.1.1: семантический поиск по LTM при наличии эмбеддинга
                embedding = None
                if hasattr(self, "_last_query_embedding") and self._last_query_embedding:
                    embedding = self._last_query_embedding

                if embedding:
                    ctx = await mgr.get_relevant_threads(
                        embedding, project_context, user_key=user_key, limit=limit, max_chars=600
                    )
                else:
                    ctx = await mgr.get_recent_threads(
                        user_key, project_context, limit=limit, max_chars=600
                    )

                return (ctx or "").strip()
            except ImportError:
                continue
    except Exception as e:
        logger.debug("Long-term memory fetch: %s", e)
    return ""


async def _save_long_term_memory(
    agent: "VictoriaAgent", session_id: str, project_context: str, goal: str, output: str
) -> None:
    """Сохранить краткое резюме обмена в долгосрочную память (Фаза 2). При ошибке — тихо пропуск."""
    if not LONG_TERM_MEMORY_ENABLED or not project_context:
        return
    user_key = (session_id or "").strip() or "anonymous"
    goal_summary = (goal or "")[:500].strip()
    outcome_summary = (output or "")[:500].strip()
    if not goal_summary and not outcome_summary:
        return
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
                from app.long_term_memory import get_long_term_memory_manager

                mgr = get_long_term_memory_manager()

                # План «как я» п.1.2: сохранение с эмбеддингом для семантического поиска в будущем
                embedding = None
                if hasattr(agent, "_last_query_embedding") and agent._last_query_embedding:
                    embedding = agent._last_query_embedding

                await mgr.save_thread(
                    user_key, project_context, goal_summary, outcome_summary, embedding=embedding
                )
                return
            except ImportError:
                continue
    except Exception as e:
        logger.debug("save_long_term_memory: %s", e)


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
                    logger.debug(
                        "📝 [SESSION_CONTEXT] Добавлен контекст сессии из БД (%d символов)",
                        len(ctx),
                    )
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


def _get_verbose_steps(agent) -> List[Dict[str, Any]]:
    """Из memory агента извлечь пошаговые шаги (thought, tool, tool_input) для verbose-ответа."""
    steps = []
    for m in getattr(agent, "memory", []):
        if m.get("role") != "assistant":
            continue
        c = m.get("content") or ""
        if not (c.strip().startswith("{") and "tool" in c):
            continue
        try:
            steps.append(json.loads(c))
        except (json.JSONDecodeError, TypeError):
            pass
    return steps


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
    verbose: bool = False,
    restated_goal: Optional[str] = None,
    strategy_result: Optional[Dict[str, Any]] = None,
) -> None:
    """Фоновое выполнение задачи (202 + polling). Результат пишется в _run_task_store[task_id]. restated_goal/strategy_result передаются из run_task (логика мысли)."""
    global sys  # Fix UnboundLocalError при обращении к sys.path в блоке orchestration
    if task_id not in _run_task_store:
        logger.error("❌ [STATUS] Task %s not found in store, skip background", task_id[:8])
        return
    store = _run_task_store[task_id]
    if correlation_id:
        store["correlation_id"] = correlation_id
    # Сразу переводим в processing, иначе клиент при polling видит только queued до завершения
    if redis_manager:
        await redis_manager.update_task_status(
            task_id, "processing", metadata={"stage": "strategy"}
        )
    else:
        store["status"] = "processing"
        store["stage"] = "strategy"
        store["updated_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("✅ [STATUS] Task %s → processing (stage=strategy)", task_id[:8])

    if max_steps is None:
        max_steps = DEFAULT_MAX_STEPS
    if task_type is None:
        task_type = detect_task_type(goal, project_context)

    # 202 до стратегии: выполняем стратегию и understand_goal в фоне, затем продолжаем или завершаем с clarify/decline
    if restated_goal is None and strategy_result is None:
        # === FAST TRACK (SINGULARITY 10.0) ===
        if is_fast_track_message(goal):
            ideal_model = _select_model_for_chat(goal)

            # [SINGULARITY 21.11] Session Context for Background Fast Path
            session_ctx = ""
            if session_id:
                session_ctx = await _get_session_context_from_db(session_id, goal)

            prompt_for_gen = goal
            if session_ctx:
                prompt_for_gen = f"{session_ctx}\n\nТЕКУЩИЙ ЗАПРОС: {prompt_for_gen}"

            content, source = await _generate_via_mlx_or_ollama(prompt_for_gen, ideal_model)
            if content:
                knowledge = {
                    "strategy": "quick_answer",
                    "confidence": 1.0,
                    "fast_path": True,
                    "source": source,
                }
                if redis_manager:
                    await redis_manager.update_task_status(
                        task_id,
                        "completed",
                        result=content,
                        metadata={"knowledge": knowledge, "stage": "completed"},
                    )
                else:
                    store["status"] = "completed"
                    store["output"] = content
                    store["knowledge"] = knowledge
                    store["updated_at"] = datetime.now(timezone.utc).isoformat()
                logger.info(
                    "[VICTORIA_CYCLE] background completed task_id=%s route=absolute_fast_track",
                    task_id[:8],
                )
                return

        # Ранний выход для приветствий и «что умеешь» — без вызова LLM (как в agent.run fast path). Интеграционные тесты и UI не зависают.
        goal_lower = (goal or "").strip().lower()
        if goal_lower in (
            "привет",
            "скажи привет",
            "здравствуй",
            "здравствуйте",
            "как дела",
            "что нового",
            "как дела?",
            "как у тебя дела?",
        ):
            output = "Привет! Я Виктория, Team Lead корпорации ATRA. Чем могу помочь?"
            knowledge = {"strategy": "quick_answer", "confidence": 1.0}
            if redis_manager:
                await redis_manager.update_task_status(
                    task_id,
                    "completed",
                    result=output,
                    metadata={"knowledge": knowledge, "stage": "completed"},
                )
            else:
                store["status"] = "completed"
                store["output"] = output
                store["knowledge"] = knowledge
                store["updated_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(
                "[VICTORIA_CYCLE] background completed task_id=%s route=quick_answer_greeting",
                task_id[:8],
            )
            return
        if any(
            p in goal_lower
            for p in (
                "что ты умеешь",
                "что умеешь",
                "твои возможности",
                "чем можешь помочь",
                "кто ты",
            )
        ):
            output = VICTORIA_CAPABILITIES_RESPONSE
            knowledge = {"strategy": "quick_answer", "confidence": 1.0}
            if redis_manager:
                await redis_manager.update_task_status(
                    task_id,
                    "completed",
                    result=output,
                    metadata={"knowledge": knowledge, "stage": "completed"},
                )
            else:
                store["status"] = "completed"
                store["output"] = output
                store["knowledge"] = knowledge
                store["updated_at"] = datetime.now(timezone.utc).isoformat()
            logger.info(
                "[VICTORIA_CYCLE] background completed task_id=%s route=quick_answer_capabilities",
                task_id[:8],
            )
            return

        session_summary = ""
        if session_id:
            session_summary = await _get_task_memory_from_db(session_id) or ""
        strategy_result = await _select_strategy(agent, goal, session_summary or None)
        if strategy_result.get("strategy") == "need_clarification":
            questions = await _generate_clarification_questions(agent, goal, goal)
            clarification_text = "Victoria уточняет: " + (
                "; ".join(questions) if questions else "Нужно уточнение."
            )
            knowledge = {
                "needs_clarification": True,
                "clarification_questions": questions,
                "strategy": "need_clarification",
            }
            _inject_strategy_into_knowledge(knowledge, strategy_result)
            if redis_manager:
                await redis_manager.update_task_status(
                    task_id,
                    "completed",
                    result=clarification_text,
                    metadata={"knowledge": knowledge, "stage": "clarification"},
                )
            else:
                store["status"] = "completed"
                store["output"] = clarification_text
                store["knowledge"] = knowledge
                store["updated_at"] = datetime.now(timezone.utc).isoformat()
            return
        if strategy_result.get("strategy") == "decline_or_redirect":
            reason = (
                strategy_result.get("reason")
                or "Запрос вне моей компетенции. Уточните задачу или обратитесь к документации."
            )
            output = f"Виктория: {reason}"
            knowledge = {
                "strategy": "decline_or_redirect",
                "strategy_reason": reason,
                "confidence": strategy_result.get("confidence", 0.5),
            }
            if redis_manager:
                await redis_manager.update_task_status(
                    task_id,
                    "completed",
                    result=output,
                    metadata={"knowledge": knowledge, "stage": "decline"},
                )
            else:
                store["status"] = "completed"
                store["output"] = output
                store["knowledge"] = knowledge
                store["updated_at"] = datetime.now(timezone.utc).isoformat()
            return
        last_tasks_context = ""
        if _is_ambiguous_goal_reference(goal):
            for _path in [
                "/app/knowledge_os",
                os.path.join(os.path.dirname(__file__), "../../knowledge_os"),
                os.path.join(os.path.dirname(__file__), "../../../knowledge_os"),
            ]:
                if (_path not in sys.path) and (os.path.exists(_path) or _path.startswith("/app")):
                    sys.path.insert(0, _path)
                _app = (
                    os.path.join(_path, "app")
                    if os.path.exists(_path) or _path.startswith("/app")
                    else None
                )
                if _app and _app not in sys.path:
                    sys.path.insert(0, _app)
                try:
                    from app.recent_tasks_context import (
                        get_recent_completed_tasks_context as _get_recent,
                    )

                    last_tasks_context = await _get_recent(project_context, limit=5) or ""
                    if last_tasks_context:
                        logger.info(
                            "[UNDERSTAND_GOAL] Контекст последних задач подставлен для «как тогда» (фон)"
                        )
                    break
                except ImportError:
                    continue
                except Exception as _e:
                    logger.debug("get_recent_completed_tasks_context: %s", _e)
                    break
            understanding = await _understand_goal_with_clarification(
                agent, goal, last_tasks_context=last_tasks_context or None
            )
            if understanding.get("needs_clarification"):
                questions = understanding.get("clarification_questions") or []
                clarification_text = "Victoria уточняет: " + (
                    "; ".join(questions) if questions else "Нужно уточнение."
                )
                store["status"] = "completed"
                store["output"] = clarification_text
                store["knowledge"] = {
                    "needs_clarification": True,
                    "clarification_questions": questions,
                }
                store["updated_at"] = datetime.now(timezone.utc).isoformat()
                return
            restated_goal = understanding.get("restated") or goal

    # Ранний ответ для вопросов о данных (метрики Mac Studio, корпорация) — без лимита 500 шагов
    quick_data = await _try_corporation_data_quick_response(goal, correlation_id)
    if quick_data:
        store["status"] = "completed"
        store["output"] = quick_data["output"]
        store["knowledge"] = quick_data.get("knowledge") or {}
        if not isinstance(store["knowledge"], dict):
            store["knowledge"] = {}
        _inject_strategy_into_knowledge(store["knowledge"], strategy_result)
        store["updated_at"] = datetime.now(timezone.utc).isoformat()
        if session_id:
            await _save_session_exchange(session_id, goal, quick_data.get("output") or "")
        logger.info(
            "[VICTORIA_CYCLE] background completed task_id=%s route=corporation_data_tool", task_id
        )
        return
    goal_for_exec = (restated_goal or goal).strip() or goal
    knowledge_os_task_id = None
    orchestration_plan_bg = None
    logger.info(
        f"[ORCHESTRATOR_DEBUG] V2_ENABLED={ORCHESTRATION_V2_ENABLED}, KO_AVAILABLE={KNOWLEDGE_OS_AVAILABLE}"
    )
    if ORCHESTRATION_V2_ENABLED and KNOWLEDGE_OS_AVAILABLE:
        logger.info("[ORCHESTRATOR_DEBUG] Entering orchestration block")
        try:
            ko_paths = [
                os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../knowledge_os")),
                os.path.normpath(os.path.join(os.getcwd(), "knowledge_os")),
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
                    logger.info(
                        f"[ORCHESTRATOR_DEBUG] PRE-IMPORT from {ko_root}, sys.path={sys.path}"
                    )
                    from app.task_orchestration.integration_bridge import IntegrationBridge

                    logger.info(f"[ORCHESTRATOR_DEBUG] POST-IMPORT from {ko_root}")
                    bridge = IntegrationBridge()
                    logger.info(
                        f"[ORCHESTRATOR] Calling bridge.process_task for goal: {goal_for_exec[:50]}..."
                    )
                    bridge_result = await bridge.process_task(
                        goal_for_exec, project_context=project_context
                    )
                    logger.info(f"[ORCHESTRATOR] Bridge result: {bridge_result}")
                    orchestration_plan_bg = bridge_result
                    version = bridge_result.get("orchestrator", "existing")
                    try:
                        knowledge_os_task_id = await _record_orchestration_task_start(
                            agent, goal_for_exec, version
                        )
                        if knowledge_os_task_id:
                            store["knowledge_os_task_id"] = knowledge_os_task_id
                    except Exception as db_e:
                        logger.warning("Orchestration V2 DB record failed (non-critical): %s", db_e)

                    # План «как я» п.12.2 п.1: при EXECUTE_ASSIGNMENTS_IN_RUN=true — выполнить назначения и подставить результаты в контекст (фон)
                    _exec_env = os.getenv("EXECUTE_ASSIGNMENTS_IN_RUN", "").strip().lower()
                    logger.info(f"[ORCHESTRATOR_DEBUG] EXECUTE_ASSIGNMENTS_IN_RUN={_exec_env}")
                    if _exec_env in ("true", "1", "yes"):
                        _assignments = (
                            (orchestration_plan_bg or {}).get("assignments")
                            if isinstance(orchestration_plan_bg, dict)
                            else {}
                        )
                        logger.info(
                            f"[ORCHESTRATOR_DEBUG] Found {len(_assignments) if _assignments else 0} assignments"
                        )
                        # МОНСТР-ЛОГИКА: всегда выполняем assignments, если их больше 1, даже если там есть Вероника
                        force_execute = len(_assignments) > 1 if _assignments else False
                        recommends_veronica = _orchestrator_recommends_veronica(
                            orchestration_plan_bg
                        )
                        logger.info(
                            f"[ORCHESTRATOR_DEBUG] force_execute={force_execute}, recommends_veronica={recommends_veronica}"
                        )
                        if (
                            _assignments
                            and isinstance(_assignments, dict)
                            and (force_execute or not recommends_veronica)
                        ):
                            try:
                                logger.info(
                                    "[ORCHESTRATOR_DEBUG] Calling execute_assignments_async (фон)"
                                )
                                try:
                                    from app.execute_assignments import execute_assignments_async
                                except ImportError:
                                    logger.warning(
                                        "[ORCHESTRATOR_DEBUG] app.execute_assignments not found, trying execute_assignments"
                                    )
                                    from execute_assignments import execute_assignments_async

                                _exec_results = await execute_assignments_async(
                                    _assignments,
                                    goal_for_exec,
                                    strategy=(orchestration_plan_bg or {}).get("strategy"),
                                    project_context=project_context,
                                )
                                if _exec_results:
                                    orchestration_context_bg = _exec_results
                                    logger.info(
                                        "[ORCHESTRATOR] Исполнение по assignments выполнено (фон), контекст подставлен"
                                    )
                            except Exception as _e:
                                logger.warning(
                                    "[ORCHESTRATOR] execute_assignments_async failed (фон): %s", _e
                                )
                    break
                except Exception as inner_e:
                    logger.error(
                        f"[ORCHESTRATOR_DEBUG] Inner exception in ko_root loop: {inner_e}",
                        exc_info=True,
                    )
                    continue
        except Exception as e:
            logger.error(
                f"[ORCHESTRATOR_DEBUG] Outer exception in orchestration block: {e}", exc_info=True
            )
    orchestration_context_bg = _build_orchestration_context(orchestration_plan_bg)
    try:
        store["status"] = "running"
        store["stage"] = "running"
        store["updated_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(
            "[VICTORIA_CYCLE] background start task_id=%s goal_preview=%s",
            task_id,
            (goal or "")[:60],
        )
        logger.info(
            "[TRACE] _run_task_background: start task_id=%s goal_preview=%s",
            task_id,
            (goal or "")[:60],
        )
        use_enhanced_actual = should_use_enhanced(goal, project_context, use_enhanced)
        veronica_tried_and_failed = False
        # Кураторские эталоны (статус проекта, что умеешь, дашборд) — только Enhanced + RAG, не Veronica
        prefer_veronica_bg = (
            task_type == "veronica" or _orchestrator_recommends_veronica(orchestration_plan_bg)
        ) and not is_curator_standard_goal(goal or "")
        if prefer_veronica_bg and use_enhanced_actual:
            store["stage"] = "delegate_veronica"
            veronica_result = await delegate_to_veronica(
                _sanitize_goal_for_prompt(goal_for_exec),
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
                    "goal_preview": (goal_for_exec or "")[:120],
                }
                _inject_strategy_into_knowledge(knowledge, strategy_result)
                store["status"] = "completed"
                store["output"] = _normalize_output_for_user(veronica_result.get("output") or "")
                if not isinstance(store["output"], str):
                    store["output"] = str(store["output"]) if store["output"] is not None else ""
                store["knowledge"] = knowledge
                if session_id:
                    await _save_session_exchange(
                        session_id, goal_for_exec, veronica_result.get("output") or ""
                    )
                    if LONG_TERM_MEMORY_ENABLED:
                        await _save_long_term_memory(
                            agent,
                            session_id,
                            project_context,
                            goal_for_exec,
                            veronica_result.get("output") or "",
                        )
                store["updated_at"] = datetime.now(timezone.utc).isoformat()
                logger.info(
                    "[VICTORIA_CYCLE] background completed task_id=%s route=veronica", task_id
                )
                logger.info(
                    "[TRACE] _run_task_background: completed via Veronica task_id=%s", task_id
                )
                return
            veronica_tried_and_failed = True
            logger.info(
                "[%s] Veronica недоступна или ошибка (фон) — выполняю через Enhanced/Victoria",
                (correlation_id or "")[:8],
            )
        enhanced = victoria_enhanced_instance
        if use_enhanced_actual and not veronica_tried_and_failed and enhanced is None:
            try:
                import sys

                for path in [
                    "/app/knowledge_os/app",
                    os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"),
                    os.path.join(os.path.dirname(__file__), "../../knowledge_os/app"),
                ]:
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
                max_msgs = min(len(chat_history), VICTORIA_CHAT_HISTORY_MAX_MESSAGES)
                history_text = "\n".join(
                    [
                        f"Пользователь: {msg.get('user', '')}\nVictoria: {msg.get('assistant', '')}"
                        for msg in chat_history[-max_msgs:]
                    ]
                )
                if (
                    VICTORIA_HISTORY_MAX_CHARS > 0
                    and len(history_text) > VICTORIA_HISTORY_MAX_CHARS
                ):
                    history_text = (
                        history_text[-VICTORIA_HISTORY_MAX_CHARS:]
                        + "\n[... обрезано по лимиту контекста ...]"
                    )
                context_with_history["chat_history"] = history_text
            elif session_id:
                session_ctx = await _get_session_context_from_db(session_id, goal_for_exec)
                if session_ctx:
                    context_with_history["chat_history"] = session_ctx
                task_mem = await _get_task_memory_from_db(session_id)
                if task_mem:
                    context_with_history["task_memory"] = task_mem
                if LONG_TERM_MEMORY_ENABLED:
                    long_term = await _get_long_term_memory_context(
                        session_id, project_context, limit=5
                    )
                    if long_term:
                        context_with_history["long_term_memory"] = long_term
            if orchestration_context_bg:
                context_with_history["orchestrator_plan"] = orchestration_context_bg
            context_with_history["project_context"] = project_context
            goal_for_enhanced_bg = _sanitize_goal_for_prompt(goal_for_exec)
            if VICTORIA_GOAL_MAX_CHARS > 0 and len(goal_for_enhanced_bg) > VICTORIA_GOAL_MAX_CHARS:
                goal_for_enhanced_bg = goal_for_enhanced_bg[:VICTORIA_GOAL_MAX_CHARS] + " [...]"
            if orchestration_context_bg:
                goal_for_enhanced_bg = (
                    orchestration_context_bg + "\n\nЗАДАЧА: " + goal_for_enhanced_bg
                )
            enhanced_result = await enhanced.solve(
                goal_for_enhanced_bg,
                use_enhancements=True,
                context=context_with_history if context_with_history else None,
            )
            if enhanced_result is None or not isinstance(enhanced_result, dict):
                store["status"] = "completed"
                store["output"] = (
                    "Victoria Enhanced не вернула результат (solve вернул None или не dict)."
                )
                store["knowledge"] = {
                    "method": "unknown",
                    "metadata": {"model_used": "Victoria Enhanced", "source": "local"},
                    "project_context": project_context,
                }
                _inject_strategy_into_knowledge(store["knowledge"], strategy_result)
            else:
                knowledge = {
                    "method": enhanced_result.get("method"),
                    "metadata": dict(enhanced_result.get("metadata") or {}),
                    "project_context": project_context,
                    "delegated_to": enhanced_result.get("delegated_to"),
                    "task_id": enhanced_result.get("task_id"),
                }
                knowledge["metadata"].setdefault("model_used", "Victoria Enhanced")
                knowledge["metadata"].setdefault("source", "local")
                knowledge["execution_trace"] = {
                    "task_type": task_type,
                    "use_enhanced": True,
                    "routed_to": "enhanced",
                    "delegated_to": enhanced_result.get("delegated_to"),
                    "method": enhanced_result.get("method") or "Victoria Enhanced",
                    "correlation_id": correlation_id,
                    "goal_preview": (goal_for_exec or "")[:120],
                }
                _inject_strategy_into_knowledge(knowledge, strategy_result)
                store["status"] = "completed"
                # Несколько ключей на случай разных путей Enhanced (CHANGES §56.1)
                raw_result = enhanced_result.get("result") or enhanced_result.get("output") or ""
                try:
                    store["output"] = _normalize_output_for_user(raw_result)
                    if not isinstance(store["output"], str):
                        store["output"] = (
                            str(store["output"]) if store["output"] is not None else ""
                        )
                except Exception as norm_e:
                    logger.warning("Нормализация вывода Enhanced: %s", norm_e)
                    store["output"] = (
                        str(raw_result)
                        if raw_result is not None
                        else "Результат не удалось нормализовать."
                    )
                # Пустой output при route=enhanced — баг CHANGES §56.1: fallback чтобы пользователь видел сообщение
                if not (store["output"] or "").strip():
                    method_name = enhanced_result.get("method") or "Victoria Enhanced"
                    store["output"] = (
                        f"Задача выполнена (маршрут: {method_name}), но текст ответа не был сохранён в цепочке. "
                        "Рекомендуется уточнить задачу или повторить запрос."
                    )
                    logger.warning(
                        "[VICTORIA_CYCLE] Пустой output от Enhanced — подставлен fallback (task_id=%s)",
                        task_id[:8],
                    )
                store["knowledge"] = knowledge
                if session_id:
                    await _save_session_exchange(session_id, goal_for_exec, raw_result)
                    if LONG_TERM_MEMORY_ENABLED:
                        await _save_long_term_memory(
                            agent, session_id, project_context, goal_for_exec, raw_result
                        )
            store["updated_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("[VICTORIA_CYCLE] background completed task_id=%s route=enhanced", task_id)
            logger.info("[TRACE] _run_task_background: after enhanced.solve task_id=%s", task_id)
        else:
            store["stage"] = "agent_run"
            logger.info("[TRACE] _run_task_background: before agent.run task_id=%s", task_id)
            original_prompt = agent.executor.system_prompt
            agent.executor.system_prompt = original_prompt + "\n" + project_prompt
            agent.memory = []
            try:
                goal_sanitized = _sanitize_goal_for_prompt(goal_for_exec)
                if orchestration_context_bg:
                    goal_sanitized = orchestration_context_bg + "\n\nЗАДАЧА: " + goal_sanitized
                result = await agent.run(goal_sanitized, max_steps=max_steps)
                store["status"] = "completed"
                try:
                    store["output"] = _normalize_output_for_user(result)
                    if not isinstance(store["output"], str):
                        store["output"] = (
                            str(store["output"]) if store["output"] is not None else ""
                        )
                except Exception as norm_e:
                    logger.warning("Нормализация вывода agent.run: %s", norm_e)
                    store["output"] = (
                        str(result) if result is not None else "Результат не удалось нормализовать."
                    )
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
                    "goal_preview": (goal_for_exec or "")[:120],
                }
                if verbose:
                    knowledge["verbose_steps"] = _get_verbose_steps(agent)
                _inject_strategy_into_knowledge(knowledge, strategy_result)
                store["knowledge"] = knowledge
                if session_id:
                    await _save_session_exchange(session_id, goal_for_exec, str(result) or "")
                    if LONG_TERM_MEMORY_ENABLED:
                        await _save_long_term_memory(
                            agent, session_id, project_context, goal_for_exec, str(result) or ""
                        )
            finally:
                agent.executor.system_prompt = original_prompt
            store["updated_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("[VICTORIA_CYCLE] background completed task_id=%s route=agent_run", task_id)
            logger.info("[TRACE] _run_task_background: after agent.run task_id=%s", task_id)
    except asyncio.CancelledError:
        logger.warning("[VICTORIA_CYCLE] background cancelled task_id=%s", task_id)
        if redis_manager:
            await redis_manager.update_task_status(task_id, "failed", result="Задача отменена")
        else:
            store["status"] = "failed"
            store["error"] = "Задача отменена"
        raise
    except Exception as e:
        logger.info("[VICTORIA_CYCLE] background failed task_id=%s error=%s", task_id, str(e)[:200])
        logger.exception("Фоновая задача %s завершилась с ошибкой", task_id)
        if redis_manager:
            await redis_manager.update_task_status(task_id, "failed", result=str(e))
        else:
            store["status"] = "failed"
            store["error"] = str(e)
    except BaseException as e:
        logger.exception("[VICTORIA_CYCLE] background BaseException task_id=%s: %s", task_id, e)
        if redis_manager:
            await redis_manager.update_task_status(task_id, "failed", result=str(e)[:2000])
        else:
            store["status"] = "failed"
            store["error"] = str(e)[:2000]
        raise
    finally:
        status_final = store.get("status") or "unknown"
        if redis_manager:
            # Синхронизируем финальное состояние
            await redis_manager.update_task_status(
                task_id,
                status_final,
                result=store.get("output") or store.get("error"),
                metadata={"knowledge": store.get("knowledge"), "stage": status_final},
            )
        else:
            store["stage"] = status_final
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
    """Статус фоновой задачи. status: queued|processing|completed|failed."""
    rec = None
    if redis_manager:
        rec = await redis_manager.get_task_status(task_id)

    if rec is None:
        if task_id not in _run_task_store:
            raise HTTPException(status_code=404, detail="task_id not found")
        rec = _run_task_store[task_id]

    # Разворачиваем метаданные из Redis если нужно
    if "metadata" in rec and isinstance(rec["metadata"], dict):
        # Объединяем корневые поля со вложенными метаданными
        meta = rec.pop("metadata")
        for k, v in meta.items():
            if k not in rec or rec[k] is None:
                rec[k] = v

    knowledge = rec.get("knowledge") or {}
    # Всегда указываем модель (мировая практика: прозрачность)
    meta = knowledge.get("metadata") or {}
    if not meta.get("model_used"):
        meta = dict(meta)
        meta["model_used"] = "local"
        meta.setdefault("source", "local")
        knowledge = dict(knowledge)
        knowledge["metadata"] = meta
    # Redis хранит текст в "result", in-memory store — в "output" (CHANGES §73)
    out = _normalize_output_for_user(rec.get("output") or rec.get("result"))
    if not isinstance(out, str):
        out = str(out) if out is not None else ""
    # Лимит 8000 для Telegram/длинных ответов (раньше 2000 — обрезало сложные ответы)
    if len(out) > 8000:
        out = out[:8000].rstrip() + "\n\n[... ответ обрезан ...]"
    status_val = rec.get("status", "queued")
    logger.info(
        "[VICTORIA_CYCLE] GET /run/status/%s status=%s output_len=%s", task_id, status_val, len(out)
    )
    resp = {
        "task_id": task_id,
        "status": status_val,
        "stage": rec.get("stage"),
        "output": out,
        "knowledge": knowledge,
        "error": rec.get("error"),
        "correlation_id": rec.get("correlation_id"),
        "updated_at": rec.get("updated_at"),
    }
    # При clarify в фоне — дублируем clarification_questions в корень для совместимости с парсингом 200 needs_clarification
    if status_val == "completed" and knowledge.get("clarification_questions") is not None:
        resp["clarification_questions"] = knowledge["clarification_questions"]
    return resp


async def _generate_via_mlx_or_ollama(
    full_prompt: str,
    ideal_model: str,
    system: str = "Ты - полезный ИИ-ассистент корпорации ATRA. Отвечай кратко на русском.",
) -> tuple:
    """Цепочка выбора: MLX → Ollama. Возвращает (content, source) или (None, None)."""
    # 1) MLX
    try:
        if hasattr(agent.executor, "mlx_url") and agent.executor.mlx_url:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{agent.executor.mlx_url}/api/chat",
                    json={
                        "model": ideal_model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": full_prompt},
                        ],
                        "stream": False,
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    return (data.get("message", {}).get("content", "").strip(), "mlx")
    except Exception as e:
        logger.debug(f"MLX generate failed: {e}")

    # 2) Ollama
    try:
        res = await agent.executor.ask(full_prompt, system=system, model=ideal_model)
        if res:
            return (res.strip(), "ollama")
    except Exception as e:
        logger.debug(f"Ollama generate failed: {e}")

    return (None, None)


@app.post("/stream")
async def run_task_stream(body: TaskRequest, request: Request):
    """
    SSE стриминг ответа (Singularity 14.0 Unified).
    Цепочка выбора: Fast Path (MLX/Ollama) → Expert Path (Victoria Enhanced).
    """
    correlation_id = (request.headers.get("X-Correlation-ID") or "").strip() or str(uuid.uuid4())
    logger.info(
        "[STREAM] correlation_id=%s goal_preview=%s", correlation_id[:8], (body.goal or "")[:50]
    )

    # ✅ SKILL DISCIPLINE: автоопределение и вызов скилла перед выполнением
    skill_context = None
    if get_skill_mapper:
        try:
            mapper = get_skill_mapper()
            skill_info = mapper.classify_task(body.goal)
            if skill_info:
                logger.info(
                    f"[SKILL_DISCIPLINE] Обнаружен скилл '{skill_info['skill']}': {skill_info['description']}"
                )
                # Добавляем инструкции скилла в начало goal
                instructions = mapper.get_skill_instructions(skill_info["skill"])
                if instructions:
                    skill_context = f"""
🎯 ПРИМЕНЯЕТСЯ СКИЛЛ: {skill_info["skill"].upper()}

{instructions}

ВАЖНО: Следуй чеклисту скилла СТРОГО. Это не рекомендация — это обязательный workflow.

---
ЗАДАЧА:
"""
                    logger.debug("[SKILL_DISCIPLINE] Добавлен контекст скилла в goal")
        except Exception as e:
            logger.warning(f"[SKILL_DISCIPLINE] Ошибка при определении скилла: {e}")

    async def sse_generator():
        # Обогащаем goal контекстом скилла (если применим)
        enriched_goal = body.goal
        if skill_context:
            enriched_goal = skill_context + body.goal
            yield f"data: {json.dumps({'type': 'step', 'stepType': 'thought', 'title': 'Применяется скилл', 'content': skill_info['description']})}\n\n"

        # ✅ B.3: IDE Context (как в Cursor)
        ide_context = _format_ide_context(body)
        if ide_context:
            enriched_goal = ide_context + "\n" + enriched_goal
            context_summary = f"Workspace: {body.workspace_path or 'unknown'}"
            if body.open_files:
                context_summary += f" | {len(body.open_files)} open file(s)"
            if body.git_status:
                context_summary += " | Git status included"
            yield f"data: {json.dumps({'type': 'step', 'stepType': 'thought', 'title': 'IDE Context', 'content': context_summary})}\n\n"

        emotion_data = {"emotion": "calm", "confidence": 1.0}
        if EMOTION_DETECTOR_AVAILABLE and EmotionDetector:
            try:
                detector = EmotionDetector()
                res = detector.detect_emotion(body.goal)
                emotion_data = {
                    "emotion": res.detected_emotion,
                    "confidence": round(res.confidence, 2),
                }
            except Exception as e:
                logger.debug("Emotion detection failed: %s", e)

        yield f"data: {json.dumps({'type': 'start', 'expert': 'Виктория', 'emotion': emotion_data})}\n\n"

        use_enhanced = body.use_enhanced
        if use_enhanced is None:
            use_enhanced = os.getenv("USE_VICTORIA_ENHANCED", "false").lower() == "true"

        is_simple = is_simple_message(body.goal)
        is_fast_track = is_fast_track_message(body.goal)

        # [VIP ROUTE] Проверка на VIP-запрос (Иван/Совет)
        is_vip = any(
            word in (body.goal or "").lower() for word in ["иван", "ceo", "стратег", "совет"]
        )

        # [FAST TRACK] Проверка на вопросы об обучении и способностях
        is_info_query = any(
            word in (body.goal or "").lower()
            for word in ["обучен", "умеешь", "навык", "способн", "help", "помощь"]
        )

        # Fast Track: Приветствия и прочее — всегда быстро, даже если Enhanced включен
        if is_fast_track or (is_simple and not use_enhanced) or is_vip or is_info_query:
            if is_vip:
                yield f"data: {json.dumps({'type': 'step', 'stepType': 'thought', 'title': 'VIP-коридор', 'content': 'Обнаружен VIP-запрос. Использую лучшие модели DeepSeek-R1.'})}\n\n"
            elif is_info_query:
                yield f"data: {json.dumps({'type': 'step', 'stepType': 'thought', 'title': 'Инфо-запрос', 'content': 'Отвечаю на вопрос о системе...'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'step', 'stepType': 'thought', 'title': 'Быстрый ответ', 'content': 'Простой запрос, отвечаю через локальную модель.'})}\n\n"

            ideal_model = _select_model_for_chat(body.goal)

            # [SINGULARITY 21.11] Session Context for Fast Path
            session_ctx = ""
            if body.session_id:
                session_ctx = await _get_session_context_from_db(body.session_id, body.goal)

            # Сингулярность 10.0: Подтягиваем знания AI Research даже для простых запросов
            ai_research_context = ""
            try:
                from app.victoria_enhanced import VictoriaEnhanced

                temp_enhanced = VictoriaEnhanced()
                ai_research_context = await temp_enhanced._get_ai_research_context(body.goal)
            except Exception as e:
                logger.debug("AI Research context fetch failed for stream: %s", e)

            prompt_for_gen = body.goal
            if session_ctx:
                prompt_for_gen = f"{session_ctx}\n\nТЕКУЩИЙ ЗАПРОС: {prompt_for_gen}"
            if ai_research_context:
                prompt_for_gen = f"{ai_research_context}\n\n{prompt_for_gen}"

            # [SINGULARITY 21.17] Expert DNA for Fast Path
            try:
                dna_mgr = get_expert_dna_manager()
                expert_dna = await dna_mgr.get_expert_dna("Виктория")
                if expert_dna:
                    prompt_for_gen = f"{expert_dna}\n\n{prompt_for_gen}"
            except Exception as de:
                logger.debug("Expert DNA fetch failed for stream: %s", de)

            content, source = await _generate_via_mlx_or_ollama(prompt_for_gen, ideal_model)
            if content:
                words = content.split()
                for i in range(0, len(words), 5):
                    chunk = " ".join(words[i : i + 5]) + " "
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                    await asyncio.sleep(0.05)
                yield f"data: {json.dumps({'type': 'end'})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'progress', 'step': 1, 'total': 3, 'status': 'analysis'})}\n\n"
            yield f"data: {json.dumps({'type': 'step', 'stepType': 'thought', 'title': 'Анализ задачи', 'content': 'Запускаю экспертную цепочку Victoria Enhanced...', 'correlation_id': correlation_id})}\n\n"

            try:
                result = await run_task(body, request, async_mode=False)
                if isinstance(result, TaskResponse):
                    content = result.output
                    if content:
                        words = content.split()
                        for i in range(0, len(words), 5):
                            chunk = " ".join(words[i : i + 5]) + " "
                            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                            await asyncio.sleep(0.02)
                elif isinstance(result, JSONResponse):
                    data = json.loads(result.body)
                    yield f"data: {json.dumps({'type': 'error', 'content': data.get('message', 'Ошибка')})}\n\n"
            except Exception as e:
                logger.error("Stream expert path error: %s", e, exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

            yield f"data: {json.dumps({'type': 'end'})}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.post("/run", response_model=TaskResponse)
async def run_task(
    body: TaskRequest,
    request: Request,
    async_mode: bool = Query(
        False, description="True = 202, задача в фоне, результат через GET /run/status/{task_id}"
    ),
):
    """
    Выполнить задачу через Victoria.
    async_mode=true: возвращает 202 + task_id, задача выполняется в фоне; результат — через GET /run/status/{task_id}.
    Заголовок X-Correlation-ID опционален; при отсутствии генерируется UUID для трассировки.
    """
    correlation_id = (request.headers.get("X-Correlation-ID") or "").strip() or str(uuid.uuid4())

    # === REQUEST FLOW TRACING ===
    logger.info(
        "[VICTORIA_CYCLE] accept POST /run correlation_id=%s goal_preview=%s async_mode=%s",
        correlation_id,
        (body.goal or "")[:80],
        async_mode,
    )
    logger.info("[REQUEST] ========== POST /run ==========")
    logger.info("[REQUEST] Correlation ID: %s", correlation_id)
    logger.info("[REQUEST] Goal: %s", body.goal[:200] if body.goal else "(empty)")
    logger.info("[REQUEST] Async mode: %s", async_mode)
    logger.info("[REQUEST] Project context: %s", body.project_context)
    logger.info("[REQUEST] Max steps: %s", body.max_steps)
    logger.info("[REQUEST] Current executor model: %s", getattr(agent.executor, "model", "unknown"))
    logger.info("[REQUEST] Current planner model: %s", getattr(agent.planner, "model", "unknown"))

    goal = body.goal or ""
    if body.images_base64:
        goal = await _enhance_goal_with_vision(goal, body.images_base64) or goal
        logger.info("[REQUEST] Goal enhanced with %d image(s) via vision", len(body.images_base64))

    # [SINGULARITY 21.8] Уточнение «библия проекта» — чтобы модель не путала с религиозной Библией
    if "библи" in (goal or "").lower():
        goal = (
            "Пояснение: «библия» здесь — документация проекта (MASTER_REFERENCE, .cursorrules), не религиозный текст.\n\n"
            + goal
        )
        logger.info("[REQUEST] Goal prefixed with project-bible clarification")

    # [AUTONOMOUS] Анализ логов и проактивные предложения
    if "статус" in (goal or "").lower() or "ошибк" in (goal or "").lower():
        try:
            from app.event_bus import EventType, get_event_bus

            bus = get_event_bus()
            recent_errors = bus.get_event_history(event_type=EventType.ERROR_DETECTED, limit=3)
            if recent_errors:
                error_context = "\n".join(
                    [f"- {e.payload.get('error_info', {}).get('message')}" for e in recent_errors]
                )
                goal = (
                    f"ВНИМАНИЕ: В системе зафиксированы недавние ошибки:\n{error_context}\n\nУчитывай это при ответе.\n\n"
                    + goal
                )
                logger.info("[AUTONOMOUS] Добавлен контекст недавних ошибок в запрос")
        except Exception:
            pass

    # [AUTONOMOUS] Мониторинг Mac Studio (нагрузка, температура, модели)
    if any(
        word in (goal or "").lower()
        for word in ["mac studio", "железо", "нагрузка", "температур", "ресурс"]
    ):
        try:
            from app.mac_studio_monitor import get_mac_studio_monitor

            monitor = get_mac_studio_monitor()
            mac_stats = await monitor.get_full_stats()
            if mac_stats:
                stats_context = f"""
🖥️ СТАТУС MAC STUDIO (Real-time):
- CPU: {mac_stats["hardware"]["cpu"]["percent"]}%
- RAM: {mac_stats["hardware"]["ram"]["used_gb"]}GB / {mac_stats["hardware"]["ram"]["total_gb"]}GB ({mac_stats["hardware"]["ram"]["percent"]}%)
- Thermal Level: {mac_stats["hardware"]["temperature"].get("thermal_level", "N/A")}
- Loaded Models (Ollama): {len(mac_stats["models"]["ollama"])}
- Loaded Models (MLX): {len(mac_stats["models"]["mlx"])}

Учитывай эти данные при ответе на вопросы о производительности и ресурсах.
"""
                goal = stats_context + "\n" + goal
                logger.info("[AUTONOMOUS] Добавлен контекст метрик Mac Studio в запрос")
        except Exception as e:
            logger.debug(f"Mac Studio monitor error: {e}")

    # Определяем контекст проекта (реестр из БД с fallback на env/hardcoded)
    main_project = get_main_project()
    project_context = body.project_context or main_project
    allowed_list, project_configs = await get_projects_registry()
    if project_context not in allowed_list:
        logger.warning(
            f"⚠️ Invalid project_context: {project_context}, using default: {main_project}"
        )
        project_context = main_project
    # RAG и ai_core.run_smart_agent_async используют project_context (аргумент или MAIN_PROJECT)
    _prev_main = os.environ.get("MAIN_PROJECT")
    os.environ["MAIN_PROJECT"] = project_context
    project_config = project_configs.get(
        project_context,
        project_configs.get(
            main_project,
            {"name": main_project, "description": "", "workspace": f"/workspace/{main_project}"},
        ),
    )
    main_config = project_configs.get(main_project, project_config)

    # Обновляем системный промпт с безопасным контекстом проекта
    project_prompt = f"""
🏢 КОНТЕКСТ ПРОЕКТА: {project_config["name"]}
🏢 ОСНОВНОЙ ПРОЕКТ КОРПОРАЦИИ: {main_config["name"]}

ВАЖНО:
- Ты работаешь в контексте проекта: {project_config["name"]}
- Основной проект корпорации: {main_config["name"]}
- Все файлы, команды и операции должны быть в контексте проекта {project_config["name"]}
- При работе с файлами используй пути относительно корня проекта
"""

    # [SINGULARITY 21.11] Session Context Injection: подмешивание истории диалога прямо в системный промпт
    if body.session_id:
        session_ctx = await _get_session_context_from_db(body.session_id, goal)
        if session_ctx:
            project_prompt += f"\n📝 КОНТЕКСТ ТЕКУЩЕЙ СЕССИИ (прошлые сообщения):\n{session_ctx}\n"
            logger.info(
                f"📝 [SESSION_INJECTION] Внедрен контекст сессии ({len(session_ctx)} симв.)"
            )

    project_prompt += f"""
🧠 БАЗА ЗНАНИЙ (ВСЕГДА ДОСТУПНА ДЛЯ ВСЕХ ПРОЕКТОВ):
- ✅ 58+ экспертов Knowledge OS - доступны для ВСЕХ проектов (та же БД, те же эксперты)
- ✅ Глобальные знания (global_knowledge.md) - доступны для ВСЕХ проектов
- ✅ Knowledge OS Database - доступна для ВСЕХ проектов (одна и та же БД)
- ✅ Все твои знания и экспертиза - доступны для ВСЕХ проектов
- ✅ Проект-специфичные знания - дополнительно к глобальным (не вместо них!)

⚠️ ВАЖНО: ТЫ НЕ СТАНОВИШЬСЯ ГЛУПЕЕ при работе с другими проектами!
Все твои знания, эксперты и база данных доступны ВСЕГДА, независимо от проекта.

🧠 КАК МЫ МЫСЛИМ (логика корпорации — следуй ей):
{VICTORIA_THINKING_CONTEXT}
"""
    if VICTORIA_DEBUG:
        logger.debug(
            "[VICTORIA] project_prompt length=%s, thinking_context length=%s",
            len(project_prompt),
            len(VICTORIA_THINKING_CONTEXT),
        )

    use_enhanced = body.use_enhanced
    if use_enhanced is None:
        use_enhanced = os.getenv("USE_VICTORIA_ENHANCED", "false").lower() == "true"

    logger.info("[REQUEST] USE_VICTORIA_ENHANCED: %s", use_enhanced)

    # === FAST PATH ДЛЯ ПРИВЕТСТВИЙ И ПРОСТЫХ ФРАЗ (SINGULARITY 10.0 UNIFIED) ===
    is_simple = is_simple_message(goal)
    is_fast_track = is_fast_track_message(goal)
    is_vip = any(word in goal.lower() for word in ["иван", "ceo", "стратег", "совет"])

    if is_fast_track or (is_simple and not use_enhanced) or is_vip:
        logger.info(
            "[VICTORIA_CYCLE] sync 200 correlation_id=%s route=unified_fast_path fast_track=%s vip=%s",
            correlation_id[:8],
            is_fast_track,
            is_vip,
        )

        ideal_model = _select_model_for_chat(goal)
        content, source = await _generate_via_mlx_or_ollama(goal, ideal_model)

        # Fallback для приветствий, если LLM зависла
        if not content and is_fast_track:
            goal_lower = goal.lower().strip()
            if any(p in goal_lower for p in ["привет", "здравствуй", "hello", "hi"]):
                content = "Привет! Я Виктория, Team Lead корпорации ATRA. Чем могу помочь?"
                source = "static_fallback"
            elif "что ты умеешь" in goal_lower:
                content = "Я — Виктория, Team Lead корпорации ATRA. Я умею управлять агентами, работать с файлами на серверах, анализировать код, отвечать на вопросы по базе знаний корпорации и мониторить состояние Mac Studio. Чем могу быть полезна?"
                source = "static_fallback"

        if content:
            # [SINGULARITY 21.17] Expert DNA for Fast Path
            try:
                dna_mgr = get_expert_dna_manager()
                expert_dna = await dna_mgr.get_expert_dna("Виктория")
                if expert_dna:
                    goal = f"{expert_dna}\n\n{goal}"
            except Exception as de:
                logger.debug("Expert DNA fetch failed for fast path: %s", de)

            # Для Fast Track ВСЕГДА возвращаем 200, даже если async_mode=true
            # Это убирает сообщение "Задача принята" в Telegram
            return TaskResponse(
                status="success",
                output=content,
                knowledge={
                    "strategy": "quick_answer",
                    "confidence": 1.0,
                    "fast_path": True,
                    "source": source,
                },
                correlation_id=correlation_id,
            )
    # ===========================================================================

    # Ранний ответ для вопросов о данных (метрики Mac Studio, корпорация) — без лимита 500 шагов
    quick_data = await _try_corporation_data_quick_response(goal, correlation_id)

    # Асинхронный режим (202 до стратегии): сразу 202, стратегия и understand_goal — в фоне
    if async_mode:
        task_id = str(uuid.uuid4())
        _task_type_async = detect_task_type(goal, body.project_context or project_context)

        task_data = {
            "status": "queued",
            "stage": "queued",
            "output": None,
            "knowledge": None,
            "error": None,
            "correlation_id": correlation_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }

        if redis_manager:
            await redis_manager.update_task_status(task_id, "queued", metadata=task_data)

        # Всегда сохраняем в локальный store для фонового процесса _run_task_background
        _run_task_store[task_id] = task_data
        _max_steps = body.max_steps if body.max_steps is not None else DEFAULT_MAX_STEPS
        task_coro = _run_task_background(
            task_id=task_id,
            goal=goal,
            project_context=project_context,
            project_prompt=project_prompt,
            chat_history=body.chat_history,
            use_enhanced=use_enhanced,
            correlation_id=correlation_id,
            task_type=_task_type_async,
            max_steps=_max_steps,
            session_id=body.session_id,
            verbose=bool(body.verbose),
            restated_goal=None,
            strategy_result=None,
        )

        def _done_callback(fut: asyncio.Future):
            try:
                exc = fut.exception()
                if exc is not None:
                    logger.exception(
                        "[VICTORIA_CYCLE] Фоновая задача %s завершилась с необработанным исключением: %s",
                        task_id,
                        exc,
                    )
                    store = _run_task_store.get(task_id)
                    if store is not None:
                        store["status"] = "failed"
                        store["error"] = str(exc)[:2000]
                        store["stage"] = "failed"
                        store["updated_at"] = datetime.now(timezone.utc).isoformat()
            except Exception as cb_e:
                logger.warning(
                    "[VICTORIA_CYCLE] Ошибка в done_callback для задачи %s: %s", task_id, cb_e
                )

        asyncio.create_task(task_coro).add_done_callback(_done_callback)
        logger.info(
            "[VICTORIA_CYCLE] async 202 task_id=%s status_url=/run/status/%s", task_id, task_id
        )
        return JSONResponse(
            status_code=202,
            content={
                "task_id": task_id,
                "correlation_id": correlation_id,
                "status_url": f"/run/status/{task_id}",
                "message": "Задача принята, выполняется в фоне. Опрашивайте status_url до status=completed.",
            },
        )

    # Синхронный путь: логика мысли — выбор стратегии и understand_goal (замеры для диагностики таймаутов)
    _t_sync_0 = time.monotonic()
    session_summary = ""
    if body.session_id:
        session_summary = await _get_task_memory_from_db(body.session_id) or ""
    strategy_result = await _select_strategy(agent, goal, session_summary or None)
    logger.info("🕒 [SYNC] _select_strategy took %.2fs", time.monotonic() - _t_sync_0)
    if strategy_result.get("strategy") == "need_clarification":
        questions = await _generate_clarification_questions(agent, goal, goal)
        content = {
            "status": "needs_clarification",
            "correlation_id": correlation_id,
            "clarification_questions": questions,
            "original_goal": goal,
            "suggested_restatement": goal,
            "knowledge": {},
        }
        _inject_strategy_into_knowledge(content["knowledge"], strategy_result)
        return JSONResponse(status_code=200, content=content)
    if strategy_result.get("strategy") == "decline_or_redirect":
        reason = (
            strategy_result.get("reason")
            or "Запрос вне моей компетенции. Уточните задачу или обратитесь к документации."
        )
        knowledge_decline = {
            "strategy": "decline_or_redirect",
            "strategy_reason": reason,
            "confidence": strategy_result.get("confidence", 0.5),
        }
        return TaskResponse(
            status="success",
            output=f"Виктория: {reason}",
            knowledge=knowledge_decline,
            correlation_id=correlation_id,
        )

    # План «умнее быстрее» §2.1: при «как вчера»/«повтори» подставляем контекст последних завершённых задач перед understand_goal
    last_tasks_context = ""
    if _is_ambiguous_goal_reference(goal):
        for _path in [
            "/app/knowledge_os",
            os.path.join(os.path.dirname(__file__), "../../knowledge_os"),
            os.path.join(os.path.dirname(__file__), "../../../knowledge_os"),
        ]:
            if (_path not in sys.path) and (os.path.exists(_path) or _path.startswith("/app")):
                sys.path.insert(0, _path)
            _app = (
                os.path.join(_path, "app")
                if os.path.exists(_path) or _path.startswith("/app")
                else None
            )
            if _app and _app not in sys.path:
                sys.path.insert(0, _app)
            try:
                from app.recent_tasks_context import (
                    get_recent_completed_tasks_context as _get_recent,
                )

                last_tasks_context = await _get_recent(body.project_context, limit=5) or ""
                if last_tasks_context:
                    logger.info(
                        "[UNDERSTAND_GOAL] Контекст последних задач подставлен для «как тогда»"
                    )
                break
            except ImportError:
                continue
            except Exception as _e:
                logger.debug("get_recent_completed_tasks_context: %s", _e)
                break
    _t_understand_0 = time.monotonic()
    understand_timeout = float(os.getenv("UNDERSTAND_GOAL_TIMEOUT_SEC", "180"))
    try:
        understanding = await asyncio.wait_for(
            _understand_goal_with_clarification(
                agent, goal, last_tasks_context=last_tasks_context or None
            ),
            timeout=understand_timeout,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "🕒 [SYNC] _understand_goal_with_clarification timeout (%.0fs), используем goal как restated",
            understand_timeout,
        )
        understanding = {
            "needs_clarification": False,
            "restated": goal,
            "category": "multi_step",
            "first_step": "",
        }
    logger.info(
        "🕒 [SYNC] _understand_goal_with_clarification took %.2fs",
        time.monotonic() - _t_understand_0,
    )
    logger.info("🕒 [SYNC] strategy + understand_goal total %.2fs", time.monotonic() - _t_sync_0)
    if understanding.get("needs_clarification"):
        return JSONResponse(
            status_code=200,
            content={
                "status": "needs_clarification",
                "correlation_id": correlation_id,
                "clarification_questions": understanding["clarification_questions"],
                "original_goal": understanding["original_goal"],
                "suggested_restatement": understanding.get("restated", goal),
            },
        )
    restated_goal = understanding.get("restated") or goal

    knowledge_os_task_id = None
    orchestration_plan = None  # План и назначения от оркестратора — Victoria использует при выполнении (мировая практика)
    orch_ctx = {"status": "failed", "result": ""}
    if ORCHESTRATION_V2_ENABLED and KNOWLEDGE_OS_AVAILABLE:
        try:
            ko_paths = [
                os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../knowledge_os")),
                os.path.normpath(os.path.join(os.getcwd(), "knowledge_os")),
                "/app/knowledge_os",
            ]
            for ko_root in ko_paths:
                app_path = (
                    os.path.join(ko_root, "app")
                    if os.path.exists(ko_root) or ko_root.startswith("/app")
                    else None
                )
                if not app_path and not ko_root.startswith("/app"):
                    continue
                if ko_root not in sys.path:
                    sys.path.insert(0, ko_root)
                if app_path and app_path not in sys.path:
                    sys.path.insert(0, app_path)
                try:
                    import sys as _sys

                    logger.info(
                        f"[ORCHESTRATOR_DEBUG] PRE-IMPORT from {ko_root}, sys.path={_sys.path}"
                    )
                    from app.task_orchestration.integration_bridge import IntegrationBridge

                    logger.info(f"[ORCHESTRATOR_DEBUG] POST-IMPORT from {ko_root}")
                    bridge = IntegrationBridge()
                    logger.info(
                        f"[ORCHESTRATOR] Calling bridge.process_task (sync path) for goal: {restated_goal[:50]}..."
                    )
                    bridge_result = await bridge.process_task(
                        restated_goal, project_context=project_context
                    )
                    logger.info(f"[ORCHESTRATOR] Bridge result (sync path): {bridge_result}")
                    orchestration_plan = bridge_result  # Сохраняем план и назначения для использования при выполнении (контекст в промпт; исполнение — Victoria Enhanced/Veronica/agent_run, см. docs/VICTORIA_TASK_CHAIN_FULL.md)
                    version = bridge_result.get("orchestrator", "existing")
                    try:
                        knowledge_os_task_id = await _record_orchestration_task_start(
                            agent, restated_goal, version
                        )
                    except Exception as db_e:
                        logger.warning("[ORCHESTRATOR] DB record failed (non-critical): %s", db_e)
                    if bridge_result.get("assignments") or bridge_result.get("strategy"):
                        logger.info(
                            "[ORCHESTRATOR] План и назначения получены, передаём Victoria для выполнения"
                        )
                    break
                except ImportError as imp_e:
                    logger.warning(f"[ORCHESTRATOR] ImportError in bridge (sync path): {imp_e}")
                    continue
        except Exception as e:
            logger.debug("Orchestration V2 A/B record start: %s", e)
    orchestration_context_str = _build_orchestration_context(orchestration_plan)
    # План «как я» п.12.2 п.1: при EXECUTE_ASSIGNMENTS_IN_RUN=true — выполнить назначения и подставить результаты в контекст
    if os.getenv("EXECUTE_ASSIGNMENTS_IN_RUN", "").strip().lower() in ("true", "1", "yes"):
        _assignments = (
            (orchestration_plan or {}).get("assignments")
            if isinstance(orchestration_plan, dict)
            else {}
        )
        if (
            _assignments
            and isinstance(_assignments, dict)
            and not _orchestrator_recommends_veronica(orchestration_plan)
        ):
            try:
                for _path in [
                    "/app/knowledge_os",
                    os.path.join(os.path.dirname(__file__), "../../knowledge_os"),
                    os.path.join(os.path.dirname(__file__), "../../../knowledge_os"),
                ]:
                    if _path not in sys.path and (
                        os.path.exists(_path) or _path.startswith("/app")
                    ):
                        sys.path.insert(0, _path)
                try:
                    from app.execute_assignments import execute_assignments_async
                except ImportError:
                    from execute_assignments import execute_assignments_async

                _exec_results = await execute_assignments_async(
                    _assignments,
                    restated_goal or "",
                    strategy=(orchestration_plan or {}).get("strategy")
                    if isinstance(orchestration_plan, dict)
                    else None,
                    project_context=project_context,
                )
                if _exec_results:
                    orchestration_context_str = _exec_results
                    logger.info(
                        "[ORCHESTRATOR] Исполнение по assignments выполнено, контекст подставлен"
                    )
            except Exception as _e:
                logger.warning("[ORCHESTRATOR] execute_assignments_async failed: %s", _e)
    # Маршрутизация: простой чат (привет и т.п.) — без Enhanced для скорости. Логика мысли: стратегия перебивает.
    use_enhanced_for_request = should_use_enhanced(
        restated_goal, body.project_context, use_enhanced
    )
    if strategy_result.get("strategy") == "quick_answer":
        use_enhanced_for_request = False
    elif strategy_result.get("strategy") == "deep_analysis":
        use_enhanced_for_request = True
    task_type = detect_task_type(restated_goal, body.project_context or "")
    logger.info(
        "Запрос [%s] тип: %s, use_enhanced: %s",
        correlation_id[:8],
        task_type,
        use_enhanced_for_request,
    )

    try:
        # Маршрутизация: Veronica если task_type=veronica ИЛИ оркестратор рекомендует Veronica (мировая практика)
        # Кураторские эталоны (статус проекта, что умеешь, дашборд) — только Enhanced + RAG, не Veronica
        veronica_tried_and_failed = False
        prefer_veronica = (
            task_type == "veronica" or _orchestrator_recommends_veronica(orchestration_plan)
        ) and not is_curator_standard_goal(restated_goal or "")
        if prefer_veronica and use_enhanced_for_request:
            logger.info(
                "[TRACE] run_task: before delegate_to_veronica correlation_id=%s",
                correlation_id[:8],
            )
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
                logger.info(
                    "[VICTORIA_CYCLE] sync 200 correlation_id=%s route=veronica output_len=%s",
                    correlation_id[:8],
                    out_len,
                )
                if body.session_id:
                    await _save_session_exchange(
                        body.session_id, restated_goal or goal, veronica_result.get("output") or ""
                    )
                    if LONG_TERM_MEMORY_ENABLED:
                        await _save_long_term_memory(
                            agent,
                            body.session_id,
                            project_context,
                            restated_goal or goal,
                            veronica_result.get("output") or "",
                        )
                _inject_strategy_into_knowledge(knowledge, strategy_result)
                return TaskResponse(
                    status="success",
                    output=_normalize_output_for_user(veronica_result.get("output") or ""),
                    knowledge=knowledge,
                    correlation_id=correlation_id,
                )
            veronica_tried_and_failed = True
            logger.info(
                "[%s] Veronica недоступна или ошибка — выполняю задачу через Victoria (инструменты)",
                correlation_id[:8],
            )
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
                            max_msgs = min(
                                len(body.chat_history), VICTORIA_CHAT_HISTORY_MAX_MESSAGES
                            )
                            history_text = "\n".join(
                                [
                                    f"Пользователь: {msg.get('user', '')}\nVictoria: {msg.get('assistant', '')}"
                                    for msg in body.chat_history[-max_msgs:]
                                ]
                            )
                            if (
                                VICTORIA_HISTORY_MAX_CHARS > 0
                                and len(history_text) > VICTORIA_HISTORY_MAX_CHARS
                            ):
                                history_text = (
                                    history_text[-VICTORIA_HISTORY_MAX_CHARS:]
                                    + "\n[... обрезано по лимиту контекста ...]"
                                )
                            context_with_history["chat_history"] = history_text
                            logger.debug(
                                f"📝 Передана история чата ({len(body.chat_history)} сообщений)"
                            )
                        elif body.session_id:
                            # Подмешивание session_context при session_id без chat_history (Telegram, скрипты)
                            session_ctx = await _get_session_context_from_db(
                                body.session_id, restated_goal
                            )
                            if session_ctx:
                                context_with_history["chat_history"] = session_ctx
                            task_mem = await _get_task_memory_from_db(body.session_id)
                            if task_mem:
                                context_with_history["task_memory"] = task_mem
                            if LONG_TERM_MEMORY_ENABLED:
                                long_term = await _get_long_term_memory_context(
                                    body.session_id or "", project_context, limit=5
                                )
                                if long_term:
                                    context_with_history["long_term_memory"] = long_term
                        if (
                            LONG_TERM_MEMORY_ENABLED
                            and project_context
                            and "long_term_memory" not in context_with_history
                        ):
                            long_term = await _get_long_term_memory_context(
                                body.session_id or "", project_context, limit=5
                            )
                            if long_term:
                                context_with_history["long_term_memory"] = long_term
                        if orchestration_context_str:
                            context_with_history["orchestrator_plan"] = orchestration_context_str
                        context_with_history["project_context"] = project_context

                        # Передаем контекст проекта, историю и план оркестратора в Enhanced (мировая практика: оркестратор распределил — Victoria выполняет по плану)
                        goal_for_enhanced = _sanitize_goal_for_prompt(restated_goal)
                        if (
                            VICTORIA_GOAL_MAX_CHARS > 0
                            and len(goal_for_enhanced) > VICTORIA_GOAL_MAX_CHARS
                        ):
                            goal_for_enhanced = (
                                goal_for_enhanced[:VICTORIA_GOAL_MAX_CHARS] + " [...]"
                            )
                        if orchestration_context_str:
                            goal_for_enhanced = (
                                orchestration_context_str + "\n\nЗАДАЧА: " + goal_for_enhanced
                            )
                        logger.info(
                            "[TRACE] run_task: before enhanced.solve correlation_id=%s",
                            correlation_id[:8],
                        )
                        enhanced_result = await enhanced.solve(
                            goal_for_enhanced,
                            use_enhancements=True,
                            context=context_with_history if context_with_history else None,
                        )
                        logger.info(
                            f"✅ Enhanced метод: {enhanced_result.get('method')} [проект: {project_context}]"
                        )
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
                        logger.info(
                            "[VICTORIA_CYCLE] sync 200 correlation_id=%s route=enhanced output_len=%s",
                            correlation_id[:8],
                            out_len,
                        )
                        if body.session_id:
                            await _save_session_exchange(
                                body.session_id,
                                restated_goal or goal,
                                enhanced_result.get("result") or "",
                            )
                            if LONG_TERM_MEMORY_ENABLED:
                                await _save_long_term_memory(
                                    agent,
                                    body.session_id,
                                    project_context,
                                    restated_goal or goal,
                                    enhanced_result.get("result") or "",
                                )
                        _inject_strategy_into_knowledge(knowledge, strategy_result)
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
            logger.warning(
                f"⚠️ Ошибка использования VictoriaEnhanced, fallback на стандартный режим: {e}"
            )

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
        logger.info(
            "[EXECUTE] Executor model BEFORE run: %s", getattr(agent.executor, "model", "unknown")
        )
        logger.info(
            "[EXECUTE] Planner model BEFORE run: %s", getattr(agent.planner, "model", "unknown")
        )
        logger.info(
            "[EXECUTE] Max steps: %s",
            body.max_steps if body.max_steps is not None else DEFAULT_MAX_STEPS,
        )

        # Временно обновляем системный промпт с контекстом проекта
        original_prompt = agent.executor.system_prompt
        agent.executor.system_prompt = original_prompt + "\n" + project_prompt
        agent.memory = []

        import time as _time

        _exec_start = _time.time()

        result = await agent.run(
            goal_for_run,
            max_steps=body.max_steps if body.max_steps is not None else DEFAULT_MAX_STEPS,
        )

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
        if body.verbose:
            knowledge["verbose_steps"] = _get_verbose_steps(agent)
        orch_ctx["status"] = "completed"
        orch_ctx["result"] = (str(result) or "")[:5000]
        logger.info(
            "[VICTORIA_CYCLE] sync 200 correlation_id=%s route=agent_run output_len=%s",
            correlation_id[:8],
            len(str(result) or ""),
        )
        if body.session_id:
            await _save_session_exchange(body.session_id, restated_goal or goal, str(result) or "")
            if LONG_TERM_MEMORY_ENABLED:
                await _save_long_term_memory(
                    agent,
                    body.session_id,
                    project_context,
                    restated_goal or goal,
                    str(result) or "",
                )
        _inject_strategy_into_knowledge(knowledge, strategy_result)
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
            await _record_orchestration_task_complete(
                agent, knowledge_os_task_id, orch_ctx["status"], orch_ctx["result"]
            )


@app.post("/orchestrate", response_model=TaskResponse)
async def orchestrate_task(request: TaskRequest):
    """Новый endpoint для оркестрации через Victoria"""
    try:
        logger.info("🎯 Получена задача для оркестрации: %s", request.goal[:80])
        agent.memory = []
        result = await agent.orchestrate_task(request.goal)

        # Извлечение execution_plan, если запрошено
        execution_plan = None
        if request.return_execution_plan:
            result_text = result if isinstance(result, str) else str(result)
            execution_plan = _extract_execution_plan(result_text)
            if execution_plan:
                logger.info("✅ Извлечён execution_plan (%d шагов)", len(execution_plan))
            else:
                logger.debug("⚠️ execution_plan не найден в ответе модели")

        return TaskResponse(
            status="success",
            output=result,
            knowledge=agent.project_knowledge,
            execution_plan=execution_plan,
        )
    except Exception as e:
        logger.exception("Ошибка оркестрации задачи")
        raise HTTPException(status_code=500, detail=str(e)) from e


class BatchReadRequest(BaseModel):
    """Запрос параллельного чтения файлов."""

    file_paths: List[str]  # Список путей к файлам
    workspace_path: Optional[str] = "/Users/bikos/Documents/atra-web-ide"
    max_concurrent: Optional[int] = 10
    max_file_size_mb: Optional[int] = 1


class BatchGrepRequest(BaseModel):
    """Запрос параллельного поиска в файлах."""

    pattern: str  # Регулярное выражение
    file_paths: List[str]
    workspace_path: Optional[str] = "/Users/bikos/Documents/atra-web-ide"
    case_sensitive: Optional[bool] = False
    max_concurrent: Optional[int] = 10


@app.post("/batch_read")
async def batch_read_endpoint(request: BatchReadRequest):
    """
    Параллельное чтение множества файлов (быстрое сканирование проекта).
    Используется для задач типа \"найди все файлы с X\" или \"покажи содержимое этих 20 файлов\".
    """
    try:
        # Импортируем batch_read функцию
        sys.path.insert(0, os.path.join(os.getcwd(), "knowledge_os/app"))
        from batch_read import batch_read_files

        results = await batch_read_files(
            file_paths=request.file_paths,
            workspace_path=request.workspace_path,
            max_concurrent=request.max_concurrent,
            max_file_size_mb=request.max_file_size_mb,
        )

        success_count = sum(1 for r in results if r["status"] == "success")

        return {
            "status": "success",
            "results": results,
            "summary": {
                "total": len(results),
                "success": success_count,
                "errors": len(results) - success_count,
            },
        }
    except Exception as e:
        logger.exception("Ошибка batch_read")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/batch_grep")
async def batch_grep_endpoint(request: BatchGrepRequest):
    """
    Параллельный поиск паттерна в множестве файлов (аналог grep).
    Используется для задач типа \"найди все упоминания функции X в проекте\".
    """
    try:
        sys.path.insert(0, os.path.join(os.getcwd(), "knowledge_os/app"))
        from batch_read import batch_grep_files

        results = await batch_grep_files(
            pattern=request.pattern,
            file_paths=request.file_paths,
            workspace_path=request.workspace_path,
            case_sensitive=request.case_sensitive,
            max_concurrent=request.max_concurrent,
        )

        total_matches = sum(r["match_count"] for r in results)
        files_with_matches = sum(1 for r in results if r["match_count"] > 0)

        return {
            "status": "success",
            "results": results,
            "summary": {
                "total_files": len(results),
                "files_with_matches": files_with_matches,
                "total_matches": total_matches,
            },
        }
    except Exception as e:
        logger.exception("Ошибка batch_grep")
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
            text = text[len(wrap) :].strip()
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


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, req: Request):
    """OpenAI-совместимый эндпоинт для Open WebUI, Chatbox и др. (поддерживает стриминг)"""
    correlation_id = str(uuid.uuid4())
    logger.info(
        f"🔗 [OPENAI-API] Request received. Model: {request.model}, Stream: {request.stream}"
    )

    # Извлекаем последнее сообщение пользователя как цель (goal)
    user_messages = [m for m in request.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user messages found")

    goal = user_messages[-1].content

    # Формируем историю чата для Виктории
    chat_history = []
    for m in request.messages[:-1]:
        if m.role == "user":
            chat_history.append({"user": m.content, "assistant": ""})
        elif m.role == "assistant":
            if chat_history and not chat_history[-1]["assistant"]:
                chat_history[-1]["assistant"] = m.content
            else:
                chat_history.append({"user": "", "assistant": m.content})

    # Создаем объект запроса, совместимый с нашим run_task
    task_req = TaskRequest(
        goal=goal,
        project_context=os.getenv("MAIN_PROJECT", "atra-web-ide"),
        session_id=f"openai-{correlation_id[:8]}",
        chat_history=chat_history,
        async_mode=False,  # Open WebUI ожидает синхронный ответ или стрим
        use_enhanced=True,  # Всегда используем Enhanced для OpenAI API (Open WebUI)
    )

    # [SINGULARITY 15.0] Интеграция LongTermMemory
    memory_context = ""
    try:
        from knowledge_os.app.long_term_memory import get_long_term_memory_manager

        ltm = get_long_term_memory_manager()
        # Ищем последние 5 обменов для этого пользователя/проекта
        memory_context = await ltm.get_recent_threads(
            user_key=f"openai-{correlation_id[:8]}",
            project_context=task_req.project_context,
            limit=5,
        )
        if memory_context:
            logger.info(f"🧠 [OPENAI-API] LongTermMemory found: {len(memory_context)} chars")
            # Подмешиваем память в goal, чтобы Victoria её увидела
            goal = f"РАНЕЕ ОБСУЖДАЛОСЬ:\n{memory_context}\n\nТЕКУЩИЙ ЗАПРОС: {goal}"
            task_req.goal = goal
    except Exception as e:
        logger.error(f"❌ [OPENAI-API] Memory error: {e}")

    # [SINGULARITY 16.0] Omni-RAG Integration for Open WebUI
    # Подтягиваем релевантные знания через Hybrid Search v2 перед отправкой в Victoria
    try:
        from app.enhanced_search import SearchMode, enhanced_search_knowledge

        logger.info("🔍 [OPENAI-API] Omni-RAG: Searching knowledge for goal...")
        rag_res = await enhanced_search_knowledge(query=goal, mode=SearchMode.HYBRID, limit=3)
        if rag_res and rag_res.get("results"):
            knowledge_text = rag_res.get("result_text", "")
            if knowledge_text:
                logger.info(
                    f"📚 [OPENAI-API] Omni-RAG: Found {len(rag_res['results'])} relevant nodes"
                )
                # Внедряем знания в начало запроса
                task_req.goal = f"КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ (Omni-RAG):\n{knowledge_text}\n\nЗАПРОС ПОЛЬЗОВАТЕЛЯ: {task_req.goal}"
    except Exception as e:
        logger.warning(f"⚠️ [OPENAI-API] Omni-RAG search failed: {e}")

    # [SINGULARITY 16.1] Omni-RAG: Telegram Notification Hook
    # Если запрос пришел от Telegram (по session_id или метаданным), можно добавить логику уведомлений
    if task_req.session_id.startswith("tg-"):
        logger.info(f"📱 [OMNI-RAG] Telegram request detected: {task_req.session_id}")

    # --- РЕАЛИЗАЦИЯ СТРИМИНГА (OPENAI COMPATIBLE) ---
    if request.stream:

        async def openai_stream_generator():
            full_response_content = ""
            try:
                # 1. Сначала шлем пустой чанк для инициализации роли
                initial_chunk = {
                    "id": f"chatcmpl-{correlation_id}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": request.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": ""},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(initial_chunk)}\n\n"
                await asyncio.sleep(0.01)

                # 2. Выполняем задачу в фоне; каждые 15с шлём keep-alive (Singularity 15.0 — против TransferEncodingError)
                run_task_coro = run_task(task_req, req, async_mode=False)
                task = asyncio.create_task(run_task_coro)
                heartbeat_sec = int(os.getenv("VICTORIA_STREAM_HEARTBEAT_SEC", "15"))
                while not task.done():
                    done, _ = await asyncio.wait([task], timeout=heartbeat_sec)
                    if not done:
                        hb_chunk = {
                            "id": f"chatcmpl-{correlation_id}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": request.model,
                            "choices": [
                                {"index": 0, "delta": {"content": ""}, "finish_reason": None}
                            ],
                        }
                        yield f"data: {json.dumps(hb_chunk)}\n\n"
                try:
                    result = task.result()
                except Exception as run_err:
                    logger.exception("[OPENAI-STREAM] run_task failed: %s", run_err)
                    result = None
                    full_response_content = f"[Ошибка Victoria]: {str(run_err)}"

                # Извлекаем контент
                if result is None:
                    pass  # full_response_content уже задан выше
                elif isinstance(result, JSONResponse):
                    body_data = json.loads(result.body.decode())
                    if "clarification_questions" in body_data:
                        questions = body_data["clarification_questions"]
                        full_response_content = "🤔 Мне нужно уточнить несколько деталей, чтобы выполнить задачу максимально точно:\n\n"
                        for i, q in enumerate(questions, 1):
                            full_response_content += f"{i}. {q}\n"
                    else:
                        full_response_content = body_data.get("output", str(body_data))
                elif isinstance(result, TaskResponse):
                    full_response_content = result.output if result.output is not None else ""
                elif hasattr(result, "output"):
                    full_response_content = result.output if result.output is not None else ""
                else:
                    full_response_content = str(result) if result is not None else ""

                # 3. Стримим контент частями
                if full_response_content:
                    # Разбиваем на мелкие части для плавности
                    chunk_size = 20
                    for i in range(0, len(full_response_content), chunk_size):
                        part = full_response_content[i : i + chunk_size]
                        chunk = {
                            "id": f"chatcmpl-{correlation_id}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": request.model,
                            "choices": [
                                {"index": 0, "delta": {"content": part}, "finish_reason": None}
                            ],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
                        await asyncio.sleep(0.01)

                # 4. Финальный чанк по протоколу OpenAI
                final_chunk = {
                    "id": f"chatcmpl-{correlation_id}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": request.model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"

                # Сохраняем в память (фоном)
                try:
                    from knowledge_os.app.long_term_memory import get_long_term_memory_manager

                    ltm = get_long_term_memory_manager()
                    await ltm.save_thread(
                        user_key=f"openai-{correlation_id[:8]}",
                        project_context=task_req.project_context,
                        goal_summary=user_messages[-1].content[:200],
                        outcome_summary=(full_response_content or "")[:200],
                    )
                except:
                    pass

            except Exception as e:
                logger.error(f"❌ [OPENAI-STREAM] Error: {e}")
                error_msg = f"\n[Ошибка стриминга]: {str(e)}"
                err_chunk = {
                    "id": f"chatcmpl-{correlation_id}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": request.model,
                    "choices": [
                        {"index": 0, "delta": {"content": error_msg}, "finish_reason": "stop"}
                    ],
                }
                yield f"data: {json.dumps(err_chunk)}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            openai_stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Transfer-Encoding": "chunked",
                "X-Accel-Buffering": "no",
            },
        )

    # --- ОБЫЧНЫЙ СИНХРОННЫЙ ОТВЕТ ---
    try:
        # Вызываем нашу основную логику (принудительно async_mode=False)
        result = await run_task(task_req, req, async_mode=False)

        # Если вернулся JSONResponse (например, 202), извлекаем реальный результат
        if isinstance(result, JSONResponse):
            body_data = json.loads(result.body.decode())
            if "clarification_questions" in body_data:
                questions = body_data["clarification_questions"]
                output_text = "🤔 Мне нужно уточнить несколько деталей:\n\n"
                for i, q in enumerate(questions, 1):
                    output_text += f"{i}. {q}\n"
            else:
                output_text = body_data.get("output", body_data.get("message", str(body_data)))
        elif isinstance(result, TaskResponse):
            output_text = result.output
        elif hasattr(result, "output"):
            output_text = result.output
        else:
            output_text = str(result)

        # [SINGULARITY 15.0] Сохранение в LongTermMemory после успешного ответа
        try:
            from knowledge_os.app.long_term_memory import get_long_term_memory_manager

            ltm = get_long_term_memory_manager()
            # Сохраняем краткую версию (первые 200 символов)
            await ltm.save_thread(
                user_key=f"openai-{correlation_id[:8]}",
                project_context=task_req.project_context,
                goal_summary=user_messages[-1].content[:200],
                outcome_summary=output_text[:200],
            )
        except Exception as e:
            logger.debug(f"Memory save failed: {e}")

        # Формируем ответ в формате OpenAI
        response_data = {
            "id": f"chatcmpl-{correlation_id}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": output_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        return JSONResponse(content=response_data)
    except Exception as e:
        logger.error(f"❌ [OPENAI-API] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    """Список моделей для OpenAI-совместимых клиентов."""
    return {
        "object": "list",
        "data": [
            {"id": "Victoria", "object": "model", "created": int(time.time()), "owned_by": "atra"},
            {
                "id": "Victoria-Enhanced",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "atra",
            },
        ],
    }


@app.get("/status")
async def get_status():
    # При первом запросе к /status подгрузить экспертов, если ещё не загружены (БД могла быть недоступна при старте)
    if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE and not agent._expert_team_loaded:
        try:
            await agent._load_expert_team()
        except Exception:
            pass
    # Получить статистику экспертов из БД
    experts_stats = {"total": len(agent.expert_team), "unique_roles": 0, "departments": 0}
    if agent._expert_team_loaded and agent.expert_team:
        unique_roles = set(e.get("role", "") for e in agent.expert_team.values() if e.get("role"))
        unique_departments = set(
            e.get("department", "") for e in agent.expert_team.values() if e.get("department")
        )
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
        "cache_size": len(agent.task_cache),
        "rag_latency": {
            "last": dict(_rag_latency_last),
            "slow_count": _rag_latency_slow_count,
            "last_slow_at": _rag_latency_last_slow_at,
            "thresholds_ms": {
                "embed": float(os.getenv("RAG_LATENCY_EMBED_MS_MAX", "300")),
                "prepare": float(os.getenv("RAG_LATENCY_PREPARE_MS_MAX", "300")),
                "llm_plan": float(os.getenv("RAG_LATENCY_LLM_PLAN_MS_MAX", "2000")),
            },
        },
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
                "service_monitor_available": enhanced_status.get(
                    "service_monitor_available", False
                ),
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
    mlx_url = os.getenv(
        "MLX_API_URL",
        "http://host.docker.internal:11435" if is_docker else "http://localhost:11435",
    )
    ollama_url = os.getenv(
        "OLLAMA_BASE_URL",
        "http://host.docker.internal:11434" if is_docker else "http://localhost:11434",
    )
    try:
        for path in [
            "/app/knowledge_os/app",
            os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"),
        ]:
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


@app.get("/metrics")
async def metrics():
    """Prometheus-совместимые метрики RAG+ латентности (для Grafana / алертов)."""
    # Формат Prometheus exposition: gauge — последние значения (секунды), counter — число «тормозов»
    embed_s = _rag_latency_last.get("embed_ms", 0) / 1000.0
    prepare_s = _rag_latency_last.get("prepare_ms", 0) / 1000.0
    llm_plan_s = _rag_latency_last.get("llm_plan_ms", 0) / 1000.0
    body = (
        "# HELP victoria_rag_embed_seconds Last RAG embed time (seconds)\n"
        "# TYPE victoria_rag_embed_seconds gauge\n"
        f"victoria_rag_embed_seconds {embed_s:.6f}\n"
        "# HELP victoria_rag_prepare_seconds Last RAG prepare (expert+context) time (seconds)\n"
        "# TYPE victoria_rag_prepare_seconds gauge\n"
        f"victoria_rag_prepare_seconds {prepare_s:.6f}\n"
        "# HELP victoria_rag_llm_plan_seconds Last LLM plan call time (seconds)\n"
        "# TYPE victoria_rag_llm_plan_seconds gauge\n"
        f"victoria_rag_llm_plan_seconds {llm_plan_s:.6f}\n"
        "# HELP victoria_rag_slow_requests_total Number of RAG+ requests that exceeded latency thresholds\n"
        "# TYPE victoria_rag_slow_requests_total counter\n"
        f"victoria_rag_slow_requests_total {_rag_latency_slow_count}\n"
    )
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8")


@app.get("/health")
async def health():
    return {"status": "ok", "agent": agent.name}


@app.get("/health/telegram")
async def telegram_health():
    """Health check для Telegram бота"""
    # Проверяем кэшированный статус в Victoria Server
    global _telegram_bot_last_report

    report = {"status": "error", "bot_process": "unknown", "pids": []}

    if _telegram_bot_last_report:
        report["last_report"] = _telegram_bot_last_report
        # Проверка свежести пульса (не более 60 сек)
        last_ts = _telegram_bot_last_report.get("last_heartbeat")
        if last_ts:
            try:
                from datetime import datetime, timezone

                last_dt = datetime.fromisoformat(last_ts)
                diff = (datetime.now(timezone.utc) - last_dt).total_seconds()
                report["heartbeat_age_seconds"] = diff
                if diff > 60:
                    report["status"] = "warning"
                    report["message"] = "Heartbeat is stale"
                    report["bot_process"] = "stale"
                else:
                    # Если есть свежий пульс, значит бот точно работает
                    report["status"] = "ok"
                    report["bot_process"] = "running"
            except Exception:
                pass

    return report


_telegram_bot_last_report = {}


@app.post("/api/telegram/register")
async def register_telegram(data: dict):
    global _telegram_bot_last_report
    _telegram_bot_last_report["registered_at"] = datetime.now(timezone.utc).isoformat()
    return {"status": "registered"}


@app.post("/api/telegram/heartbeat")
async def telegram_heartbeat(data: dict):
    global _telegram_bot_last_report

    # Сохраняем предыдущие значения для инкрементальных метрик
    prev_messages = _telegram_bot_last_report.get("processed_messages", 0)
    prev_errors = _telegram_bot_last_report.get("errors", 0)

    _telegram_bot_last_report.update(data)

    # Используем импортированный datetime
    from datetime import datetime, timezone

    _telegram_bot_last_report["server_received_at"] = datetime.now(timezone.utc).isoformat()

    # Обновляем Prometheus метрики
    try:
        # Пытаемся импортировать метрики (путь может отличаться в зависимости от запуска)
        try:
            from backend.app.metrics.prometheus_metrics import (
                TELEGRAM_BOT_ERRORS,
                TELEGRAM_BOT_HEARTBEAT_AGE,
                TELEGRAM_BOT_MESSAGES,
                TELEGRAM_BOT_STATUS,
            )
        except Exception:
            # Fallback для Docker/разных путей
            potential_path = os.path.join(os.path.dirname(__file__), "../../..")
            if potential_path not in sys.path:
                sys.path.append(potential_path)
            from backend.app.metrics.prometheus_metrics import (
                TELEGRAM_BOT_ERRORS,
                TELEGRAM_BOT_HEARTBEAT_AGE,
                TELEGRAM_BOT_MESSAGES,
                TELEGRAM_BOT_STATUS,
            )

        if "TELEGRAM_BOT_STATUS" in locals():
            TELEGRAM_BOT_STATUS.set(1 if data.get("status") == "running" else 0)

            new_messages = data.get("processed_messages", 0)
            if new_messages > prev_messages:
                TELEGRAM_BOT_MESSAGES.inc(new_messages - prev_messages)

            new_errors = data.get("errors", 0)
            if new_errors > prev_errors:
                TELEGRAM_BOT_ERRORS.inc(new_errors - prev_errors)

            # Возраст пульса обновляется в /metrics или здесь
            last_ts = data.get("last_heartbeat")
            if last_ts:
                last_dt = datetime.fromisoformat(last_ts)
                diff = (datetime.now(timezone.utc) - last_dt).total_seconds()
                TELEGRAM_BOT_HEARTBEAT_AGE.set(diff)

    except Exception as e:
        logger.debug(f"Metrics update failed: {e}")

    return {"status": "ok"}


@app.get("/api/hidden-thoughts/{session_id}")
async def get_hidden_thoughts(session_id: str):
    """Получить скрытые рассуждения для сессии (Summary Reader)"""
    try:
        # Пытаемся импортировать VictoriaEnhanced и вызвать статический метод
        for path in [
            "/app/knowledge_os/app",
            os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"),
        ]:
            if path and os.path.exists(path) and path not in sys.path:
                sys.path.insert(0, path)
        if "/app/knowledge_os" not in sys.path:
            sys.path.insert(0, "/app/knowledge_os")

        from app.victoria_enhanced import VictoriaEnhanced

        thoughts = VictoriaEnhanced.get_hidden_thoughts(session_id)

        if thoughts:
            return {"status": "success", "session_id": session_id, "thoughts": thoughts}
        else:
            return {"status": "not_found", "message": "No hidden thoughts found for this session"}
    except Exception as e:
        logger.error(f"Error in get_hidden_thoughts: {e}")
        return {"status": "error", "message": str(e)}


class OmniSearchRequest(BaseModel):
    query: str
    domain: Optional[str] = None
    limit: Optional[int] = 3


@app.post("/api/omni-rag/search")
async def omni_rag_search(request: OmniSearchRequest):
    """
    Унифицированный поиск Omni-RAG для внешних систем (Telegram, Open WebUI и др.)
    Использует Hybrid Search v2 + Cross-Encoder Re-ranking.
    """
    try:
        from app.enhanced_search import SearchMode, enhanced_search_knowledge

        logger.info(f"🔍 [OMNI-RAG] Search request: {request.query} (domain: {request.domain})")

        results = await enhanced_search_knowledge(
            query=request.query, domain=request.domain, mode=SearchMode.HYBRID, limit=request.limit
        )
        return results
    except Exception as e:
        logger.error(f"❌ [OMNI-RAG] Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(
        os.getenv("VICTORIA_PORT", "8010")
    )  # 8010 — как в Docker (host), 8000 — внутри контейнера
    workers = int(
        os.getenv("UVICORN_WORKERS", "1")
    )  # 1 = один event loop; при workers>1 нужен общий store для /run/status
    timeout_keep_alive = int(
        os.getenv("UVICORN_TIMEOUT_KEEP_ALIVE", "600")
    )  # долгие sync-запросы (стратегия + LLM)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        workers=workers,
        timeout_keep_alive=timeout_keep_alive,
    )
