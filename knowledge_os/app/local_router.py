import asyncio
import hashlib
import json
import logging
import os
import random
import time
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import httpx

# ML Router Data Collector
try:
    from ml_router_data_collector import MLRouterDataCollector, get_collector
except ImportError:
    MLRouterDataCollector = None
    get_collector = None

# ML Router Model
try:
    from ml_router_model import MLRouterModel
except ImportError:
    MLRouterModel = None

# ML Router A/B Test
try:
    from ml_router_ab_test import get_ab_test
except ImportError:
    get_ab_test = None

# Load Balancer
try:
    from load_balancer import get_load_balancer
except ImportError:
    get_load_balancer = None

try:
    from prometheus_metrics import record_llm_request
except ImportError:
    try:
        # Fallback for knowledge_os structure
        import os
        import sys

        sys.path.append(os.path.join(os.path.dirname(__file__), "../../backend/app/metrics"))
        from prometheus_metrics import record_llm_request
    except ImportError:

        def record_llm_request(*args, **kwargs):
            pass


try:
    from prometheus_metrics import OLLAMA_BACKPRESSURE_SKIPS as _OLLAMA_BP_SKIPS
except ImportError:
    try:
        import os as _os
        import sys as _sys

        _sys.path.append(_os.path.join(_os.path.dirname(__file__), "../../backend/app/metrics"))
        from prometheus_metrics import OLLAMA_BACKPRESSURE_SKIPS as _OLLAMA_BP_SKIPS
    except ImportError:

        class _DummyCounter:
            def inc(self, *a, **kw):
                pass

        _OLLAMA_BP_SKIPS = _DummyCounter()


logger = logging.getLogger(__name__)

# Debug mode: VICTORIA_DEBUG=true enables verbose logging
VICTORIA_DEBUG = os.getenv("VICTORIA_DEBUG", "false").lower() in ("true", "1", "yes")
if VICTORIA_DEBUG:
    logger.setLevel(logging.DEBUG)
    logging.getLogger().setLevel(logging.DEBUG)

# Config - Mac Studio (локальная обработка). OLLAMA_BASE_URL используется Victoria/Veronica
_is_docker = (
    os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
)
_default_ollama = "http://host.docker.internal:11434" if _is_docker else "http://localhost:11434"


def _valid_http_url(url: str) -> bool:
    """True если url — валидный http(s) URL (не 'disabled' и не пустой)."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip().lower()
    return u.startswith("http://") or u.startswith("https://")


OLLAMA_API_URL = (
    os.getenv("OLLAMA_API_URL")
    or os.getenv("OLLAMA_BASE_URL")
    or os.getenv("SERVER_LLM_URL")
    or _default_ollama
)
_raw_mlx = (
    os.getenv("MLX_API_URL")
    or os.getenv("MAC_LLM_URL")
    or ("http://host.docker.internal:11435" if _is_docker else "http://localhost:11435")
)
MLX_API_URL = (
    _raw_mlx if _valid_http_url(_raw_mlx) else None
)  # MLX_API_URL=disabled → None, только Ollama


try:
    from app.circuit_breaker import CircuitBreakerOpenError, CircuitState, get_circuit_breaker
except ImportError:
    from circuit_breaker import CircuitBreakerOpenError, CircuitState, get_circuit_breaker

try:
    from app.context_mirror import ContextMirror
except ImportError:
    from context_mirror import ContextMirror

try:
    from app.mlx_monitor import get_mlx_monitor
except ImportError:
    from mlx_monitor import get_mlx_monitor

try:
    from app.mlx_recovery_state import is_mlx_recovery_event, should_run_unload_on_recovery
except ImportError:
    from mlx_recovery_state import is_mlx_recovery_event, should_run_unload_on_recovery

try:
    from app.ollama_keep_alive_policy import (
        MLX_RAM_RESERVE_GB,
        get_keep_alive,
        unload_ollama_fallback_models,
    )
except ImportError:
    from ollama_keep_alive_policy import (
        MLX_RAM_RESERVE_GB,
        get_keep_alive,
        unload_ollama_fallback_models,
    )

# [SINGULARITY 21.3] God Mode 128GB: Immortal models and zero-swap
IMMORTAL_MODELS = {"nomic-embed-text", "nomic-embed-text:latest", "moondream", "moondream:latest"}
# [SINGULARITY 21.4] Tool Guard: Only these models can execute tools
TOOL_CALL_ALLOWED_MODELS = [
    "victoria-wisdom-v3.5",
    "victoria-wisdom-v3.5:latest",
    "victoria-wisdom-v3.5",
    "victoria-wisdom-v3.5:latest",
    "qwen3.5:35b",
    "deepseek-r1:32b",
    "qwq:32b",
]


def can_delegate_tool(model_name: str, tool_name: str) -> bool:
    """Проверяет, может ли модель выполнять инструменты (God Mode Guard)"""
    if tool_name in ["run_terminal_cmd", "write_file", "execute_code", "ssh_run"]:
        return any(m in model_name.lower() for m in TOOL_CALL_ALLOWED_MODELS)
    return True


SWAP_THRESHOLD = float(os.getenv("SWAP_THRESHOLD", "0"))
RAM_RESERVE_GB = float(os.getenv("RAM_RESERVE_GB", "24"))

# Обратная совместимость (legacy)
MAC_LLM_URL = MLX_API_URL
SERVER_LLM_URL = OLLAMA_API_URL
USE_LOCAL_LLM = os.getenv("USE_LOCAL_LLM", "true").lower() == "true"
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

# Health check cache (120 seconds TTL - увеличен для снижения нагрузки на /api/tags)
_health_cache = {"nodes": [], "timestamp": 0}
_HEALTH_CACHE_TTL = 120  # 2 минуты вместо 30 секунд для снижения rate limiting

# ========== ДИНАМИЧЕСКОЕ ОБНАРУЖЕНИЕ МОДЕЛЕЙ ==========
# Модели сканируются с серверов каждые 2 минуты через available_models_scanner
# Это позволяет автоматически подхватывать новые модели и замечать удаленные

try:
    from available_models_scanner import (
        MLX_PRIORITY_BY_CATEGORY,
        OLLAMA_PRIORITY_BY_CATEGORY,
        get_available_models,
        pick_mlx_for_category,
        pick_ollama_for_category,
    )

    _HAS_MODEL_SCANNER = True
except ImportError:
    _HAS_MODEL_SCANNER = False
    logger.warning("⚠️ available_models_scanner не доступен, используем fallback")

# Кэш доступных моделей (обновляется динамически)
_cached_mlx_models: list = []
_cached_ollama_models: list = []
_models_cache_time: float = 0
_MODELS_CACHE_TTL = 120  # 2 минуты

# Мозг и руки — victoria-wisdom-v3.5.
OLLAMA_MODELS_FALLBACK = {
    "reasoning": os.getenv("MODEL_REASONING", "victoria-wisdom-v3.5:latest"),
    "coding": os.getenv("MODEL_CODER", "victoria-wisdom-v3.5:latest"),
    "chat": "victoria-wisdom-v3.5:latest",
    "fast": os.getenv("MODEL_FAST", "tinyllama:1.1b-chat"),
    "vision": os.getenv("MODEL_VISION", "minicpm-v:latest"),
    "vision_hd": "minicpm-v:latest",
    "vision_pdf": os.getenv("MODEL_VISION_PDF", "minicpm-v:latest"),
    "thinking": os.getenv("MODEL_THINKING", "lfm2.5-thinking:1.2b"),
    "default": "victoria-wisdom-v3.5:latest",
    "vip": "victoria-wisdom-v3.5:latest",
}

# MLX: только лёгкие — 70b/104b/32b удалены (Metal/память); не подставлять удалённые.
# [SINGULARITY 21.5] Victoria v3.5 Total Dominance: v3.5 is now the primary brain in MLX
MLX_MODELS_FALLBACK = {
    "reasoning": "victoria-wisdom-v3.5",
    "coding": "victoria-wisdom-v3.5",
    "chat": "victoria-wisdom-v3.5",
    "fast": "phi3.5:3.8b-stable",
    "default": "victoria-wisdom-v3.5",
}

# Для обратной совместимости
MLX_MODELS = MLX_MODELS_FALLBACK
OLLAMA_MODELS = OLLAMA_MODELS_FALLBACK

# Legacy MODEL_MAP для обратной совместимости
MODEL_MAP = {
    "coding": os.getenv("MODEL_CODING", OLLAMA_MODELS["coding"]),
    "reasoning": os.getenv("MODEL_REASONING", MLX_MODELS["reasoning"]),
    "fast": "tinyllama:1.1b-chat",
    "vision": OLLAMA_MODELS["vision"],
    "vision_pdf": OLLAMA_MODELS["vision_pdf"],
    "default": os.getenv("MODEL_DEFAULT", OLLAMA_MODELS["default"]),
}

# List of task categories that can be handled locally (L1)
LOCAL_TASK_CATEGORIES = [
    "code_audit",
    "log_analysis",
    "unit_test_generation",
    "text_summarization",
    "simple_query",
    "grammar_correction",
    "logic_check",
]


class LocalAIRouter:
    def __init__(self):
        self.use_local = USE_LOCAL_LLM
        is_docker = (
            os.path.exists("/.dockerenv")
            or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
        )
        # Используем URL из env (docker-compose). MLX_API_URL=disabled → только Ollama (не добавляем MLX node)
        ollama_url = OLLAMA_API_URL or (
            "http://host.docker.internal:11434" if is_docker else "http://localhost:11434"
        )
        if not _valid_http_url(ollama_url):
            ollama_url = (
                "http://host.docker.internal:11434" if is_docker else "http://localhost:11434"
            )
        mlx_url = MLX_API_URL or (
            "http://host.docker.internal:11435" if is_docker else "http://localhost:11435"
        )
        self.nodes = []
        if _valid_http_url(mlx_url):
            self.nodes.append(
                {
                    "name": "Mac Studio (MLX)",
                    "url": mlx_url,
                    "priority": 0,
                    "routing_key": "mlx_studio",
                }
            )
        self.nodes.append(
            {
                "name": "Mac Studio (Ollama)",
                "url": ollama_url,
                "priority": 1,
                "routing_key": "ollama_studio",
            }
        )
        self._active_node = None
        self._performance_cache = {}  # Cache for node performance metrics
        self._cache_ttl = 300  # 5 minutes

        # ML Model for intelligent routing
        self.ml_model = None
        self.ml_model_path = os.path.join(os.path.dirname(__file__), "ml_router_model.pkl")
        self._load_ml_model()

        # Model Memory Manager для оптимизации памяти (ленивая инициализация)
        self._memory_manager = None
        self._memory_manager_url = OLLAMA_API_URL
        self._tunnel_checked = False
        # Кэш ответов по (prompt, category, model) — ускорение повторяющихся запросов
        self._prompt_cache: Dict[str, Tuple[str, str]] = {}
        self._prompt_cache_meta: Dict[str, float] = {}
        self._prompt_cache_max = 500
        self._prompt_cache_ttl = 1800  # 30 мин
        self._prompt_cache_hits = 0
        self._prompt_cache_misses = 0

        # Context Mirror for failover
        self.context_mirror = ContextMirror()

        # [SINGULARITY 21.10] Per-node Circuit Breakers
        self._node_breakers = {}

        # [SINGULARITY 25.0] Context Compressor integration
        try:
            from context_compressor import ContextCompressor

            self.compressor = ContextCompressor()
        except ImportError:
            self.compressor = None

        for node in self.nodes:
            # Создаем уникальный CB для каждого URL
            node_url = node["url"]
            breaker_name = (
                f"node_{node_url.replace('://', '_').replace(':', '_').replace('.', '_')}"
            )
            self._node_breakers[node_url] = get_circuit_breaker(
                name=breaker_name,
                failure_threshold=10,  # [SINGULARITY 25.0] 10 failures → OPEN (tolerates burst post-recovery; was 5)
                recovery_timeout=60,  # [SINGULARITY 25.0] 60s probe cycle (was 120s — faster recovery)
            )
            logger.debug(f"🛡️ [CIRCUIT BREAKER] Initialized for {node_url} as {breaker_name}")

        # [SINGULARITY 25.0] Startup sanity-check: warn if Ollama semaphore and NUM_PARALLEL are out of sync.
        # Ольга (Performance Engineer): меняя OLLAMA_NUM_PARALLEL без OLLAMA_GLOBAL_MAX_SLOTS → рассинхронизация.
        _num_parallel = int(os.getenv("OLLAMA_NUM_PARALLEL", "2"))  # [FIX 2026-06-23] was 5
        _max_slots = int(os.getenv("OLLAMA_GLOBAL_MAX_SLOTS", "2"))  # [FIX 2026-06-23] was 3
        if _max_slots >= _num_parallel:
            logger.warning(
                "⚠️ [CONFIG SYNC] OLLAMA_GLOBAL_MAX_SLOTS=%d >= OLLAMA_NUM_PARALLEL=%d — "
                "semaphore provides no buffer! Set OLLAMA_GLOBAL_MAX_SLOTS to NUM_PARALLEL-1 or less.",
                _max_slots,
                _num_parallel,
            )
        elif _num_parallel - _max_slots > 2:
            logger.warning(
                "⚠️ [CONFIG SYNC] OLLAMA_GLOBAL_MAX_SLOTS=%d is %d below OLLAMA_NUM_PARALLEL=%d — "
                "large buffer may under-utilize Ollama capacity.",
                _max_slots,
                _num_parallel - _max_slots,
                _num_parallel,
            )
        else:
            logger.info(
                "✅ [CONFIG SYNC] Ollama semaphore: %d/%d slots (buffer=%d) — OK",
                _max_slots,
                _num_parallel,
                _num_parallel - _max_slots,
            )

    @property
    def memory_manager(self):
        """Доступ к memory_manager для обратной совместимости"""
        return self._memory_manager

    def _evict_prompt_cache_if_needed(self) -> None:
        """Удаляет старые записи кэша при переполнении (LRU по timestamp)."""
        if len(self._prompt_cache) < self._prompt_cache_max:
            return
        now = time.time()
        # Удаляем истёкшие
        expired = [
            k for k, ts in self._prompt_cache_meta.items() if (now - ts) >= self._prompt_cache_ttl
        ]
        for k in expired:
            self._prompt_cache.pop(k, None)
            self._prompt_cache_meta.pop(k, None)
        if len(self._prompt_cache) >= self._prompt_cache_max:
            # Удаляем самые старые по timestamp
            sorted_keys = sorted(
                self._prompt_cache_meta.keys(), key=lambda x: self._prompt_cache_meta[x]
            )
            for k in sorted_keys[: max(0, len(self._prompt_cache) - self._prompt_cache_max + 1)]:
                self._prompt_cache.pop(k, None)
                self._prompt_cache_meta.pop(k, None)

    _cached_ml_model = None  # класс-уровень: один экземпляр на процесс (переиспользование при множестве LocalAIRouter)
    _cached_ml_model_path = None

    def _load_ml_model(self):
        """Загружает ML-модель если доступна. Переиспользует кэш на уровне класса (один раз на процесс)."""
        if MLRouterModel and os.path.exists(self.ml_model_path):
            if (
                LocalAIRouter._cached_ml_model_path == self.ml_model_path
                and LocalAIRouter._cached_ml_model is not None
            ):
                self.ml_model = LocalAIRouter._cached_ml_model
                return
            try:
                self.ml_model = MLRouterModel()
                self.ml_model.load(self.ml_model_path)
                LocalAIRouter._cached_ml_model = self.ml_model
                LocalAIRouter._cached_ml_model_path = self.ml_model_path
                logger.info("✅ [ML ROUTER] ML model loaded successfully (cached for process)")
            except Exception as e:
                logger.warning(f"⚠️ [ML ROUTER] Failed to load ML model: {e}")
                self.ml_model = None
        else:
            logger.debug("ℹ️ [ML ROUTER] ML model not available, using heuristic routing")

    async def predict_optimal_route(self, prompt: str, category: Optional[str] = None) -> tuple:
        """
        Предсказывает оптимальный маршрут используя ML-модель.

        Args:
            prompt: Промпт пользователя
            category: Категория задачи

        Returns:
            (predicted_route, confidence) или (None, None) если модель недоступна
        """
        if self.ml_model is None:
            return None, None

        try:
            # Определяем тип задачи
            task_type = self._determine_task_type(prompt, category)

            # Получаем метрики узлов
            node_metrics = await self._get_node_performance_metrics()

            # Предсказываем маршрут
            predicted_route, confidence = self.ml_model.predict(
                task_type=task_type,
                prompt_length=len(prompt),
                category=category,
                node_metrics=node_metrics,
            )

            logger.info(
                f"🤖 [ML ROUTER] Predicted route: {predicted_route} (confidence: {confidence:.2f})"
            )
            return predicted_route, confidence
        except Exception as e:
            logger.warning(f"⚠️ [ML ROUTER] Prediction error: {e}")
            return None, None

    async def check_health(self, force_refresh: bool = False) -> List[Dict]:
        """Check which nodes are alive and return their latency. Uses caching."""
        global _health_cache
        current_time = time.time()

        # Return cached result if still valid
        if not force_refresh and (current_time - _health_cache["timestamp"]) < _HEALTH_CACHE_TTL:
            return _health_cache["nodes"]

        healthy_nodes = []
        async with httpx.AsyncClient() as client:
            for node in self.nodes:
                try:
                    start_time = time.time()
                    # Пробуем легкий /health endpoint сначала (быстрее, без rate limiting)
                    health_url = f"{node['url']}/health"
                    try:
                        response = await client.get(health_url, timeout=2.0)
                        if response.status_code == 200:
                            latency = time.time() - start_time
                            healthy_nodes.append({**node, "latency": latency, "status": "online"})
                            continue  # Успешно, переходим к следующему узлу
                    except Exception:
                        pass  # /health недоступен, пробуем /api/tags

                    # Fallback на /api/tags (если /health недоступен)
                    response = await client.get(f"{node['url']}/api/tags", timeout=2.0)
                    latency = time.time() - start_time
                    if response.status_code == 200:
                        healthy_nodes.append({**node, "latency": latency, "status": "online"})
                except Exception as e:
                    logger.warning(f"⚠️ Node {node['name']} is offline: {e}")

        # Не кэшируем пустой результат — следующая попытка сразу перепроверит
        if not healthy_nodes:
            logger.warning(
                "⚠️ [HEALTH] Нет здоровых узлов, не кэшируем (повторная проверка при следующем запросе)"
            )
            return []

        # Get performance metrics from cache for each node
        performance_metrics = await self._get_node_performance_metrics()

        # Enhance nodes with performance data
        for node in healthy_nodes:
            routing_key = node.get("routing_key", "")
            if routing_key in performance_metrics:
                node["performance_score"] = performance_metrics[routing_key].get(
                    "avg_performance", 0.8
                )
                node["success_rate"] = performance_metrics[routing_key].get("success_rate", 0.9)
            else:
                node["performance_score"] = 0.8  # Default
                node["success_rate"] = 0.9  # Default

        # Sort by: performance_score (higher is better), then priority, then latency
        sorted_nodes = sorted(
            healthy_nodes,
            key=lambda x: (-x.get("performance_score", 0.8), x["priority"], x["latency"]),
        )

        # [SINGULARITY 21.8] MLX Recovery Event: unload fallback models in Ollama
        if is_mlx_recovery_event(sorted_nodes) and should_run_unload_on_recovery():
            ollama_node = next(
                (n for n in sorted_nodes if "11434" in n["url"] or "ollama" in n["url"].lower()),
                None,
            )
            if ollama_node:
                asyncio.create_task(unload_ollama_fallback_models(ollama_node["url"]))

        # Update cache
        _health_cache = {"nodes": sorted_nodes, "timestamp": current_time}

        return sorted_nodes

    async def _get_node_performance_metrics(self) -> Dict:
        """Получение метрик производительности узлов из semantic_ai_cache"""
        try:
            # Check cache first
            current_time = time.time()
            if hasattr(self, "_performance_cache") and self._performance_cache:
                cache_time = self._performance_cache.get("timestamp", 0)
                if (current_time - cache_time) < self._cache_ttl:
                    return self._performance_cache.get("metrics", {})

            # Try to connect to DB
            try:
                conn = await asyncpg.connect(DB_URL, timeout=2)
            except (asyncpg.PostgresError, OSError, ValueError):
                return {}

            try:
                # Check if columns exist
                columns_exist = (
                    await conn.fetchval("""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name = 'semantic_ai_cache'
                    AND column_name IN ('routing_source', 'performance_score')
                """)
                    == 2
                )

                if not columns_exist:
                    await conn.close()
                    return {}

                # Get performance metrics for each routing source (last 24 hours)
                metrics = await conn.fetch("""
                    SELECT
                        routing_source,
                        AVG(performance_score) as avg_performance,
                        COUNT(*) as total_requests,
                        COUNT(*) FILTER (WHERE performance_score >= 0.7) as successful_requests
                    FROM semantic_ai_cache
                    WHERE routing_source IS NOT NULL
                    AND routing_source IN ('local_mac', 'local_server')
                    AND last_used_at > NOW() - INTERVAL '24 hours'
                    GROUP BY routing_source
                """)

                result = {}
                for row in metrics:
                    routing_key = row["routing_source"]
                    total = row["total_requests"] or 0
                    successful = row["successful_requests"] or 0
                    result[routing_key] = {
                        "avg_performance": float(row["avg_performance"] or 0.8),
                        "success_rate": (successful / total) if total > 0 else 0.9,
                        "total_requests": total,
                    }

                await conn.close()

                # Update cache
                self._performance_cache = {"metrics": result, "timestamp": current_time}

                return result
            except Exception as e:
                logger.warning(f"⚠️ Error getting performance metrics: {e}")
                await conn.close()
                return {}
        except Exception as e:
            logger.warning(f"⚠️ Error in _get_node_performance_metrics: {e}")
            return {}

    def _is_echo_response(self, result: str, prompt: str) -> bool:
        """Проверяет, не является ли ответ эхом промпта (модель/сервер вернула запрос как ответ).
        Условие ослаблено: короткий ответ (<200 символов) считаем эхо только при явном совпадении
        или если ответ почти полностью совпадает с началом промпта (≥80% длины ответа), чтобы
        не отбрасывать легитимные короткие ответы («Да», «Готово»).

        [SINGULARITY 21.1] Для длинных ответов (>500 символов) эхо-детектор отключен,
        так как вероятность случайного эха крайне мала, а риск ложного срабатывания в дебатах высок.
        """
        if not result or not prompt:
            return False
        r = result.strip()
        p = prompt.strip()

        # [SINGULARITY 21.1] Длинные ответы (>500 символов) не считаем эхом
        if len(r) > 500:
            return False

        if r == p:
            return True
        # Частичное эхо: только если ответ короткий И явно копирует промпт (промпт начинается с ответа
        # и ответ не слишком короткий для легитимного «Да»/«Ок» — минимум 50 символов для частичного эхо)
        if len(r) < 200:
            if p.startswith(r) and len(r) >= 50:
                return True
            if r.startswith(p) and len(p) >= 50:
                return True
        return False

    def _is_simple_task(self, prompt: str, category: Optional[str] = None) -> bool:
        """Определяет, является ли задача простой (можно использовать Ollama при перегрузке MLX)"""
        # Простые задачи:
        # - Короткие промпты (< 500 символов)
        # - Простые категории (fast, simple_query, text_summarization)
        # - Простой чат (без сложной логики)
        # - Не требует reasoning

        prompt_lower = prompt.lower()

        # Простые категории
        simple_categories = ["fast", "simple_query", "text_summarization", "grammar_correction"]
        if category in simple_categories:
            return True

        # Короткие промпты
        if len(prompt) < 500:
            return True

        # Простой чат (без сложных ключевых слов)
        complex_keywords = [
            "подумай",
            "логика",
            "архитектура",
            "стратегия",
            "анализ",
            "планирование",
        ]
        if not any(keyword in prompt_lower for keyword in complex_keywords):
            return True

        return False

    async def _refresh_available_models(self, force: bool = False) -> None:
        """Обновляет кэш доступных моделей с серверов (если истёк TTL или force=True)"""
        global _cached_mlx_models, _cached_ollama_models, _models_cache_time

        now = time.time()
        if not force and (now - _models_cache_time) < _MODELS_CACHE_TTL:
            return  # Кэш ещё актуален

        if _HAS_MODEL_SCANNER:
            try:
                mlx_url = MLX_API_URL or ""
                ollama_url = OLLAMA_API_URL or "http://localhost:11434"
                mlx_models, ollama_models = await get_available_models(
                    mlx_url, ollama_url, force_refresh=force
                )
                _cached_mlx_models = mlx_models
                _cached_ollama_models = ollama_models
                _models_cache_time = now
                logger.info(
                    f"🔄 [MODEL SCAN] Обновлены модели: MLX={len(mlx_models)}, Ollama={len(ollama_models)}"
                )
            except Exception as e:
                logger.warning(f"⚠️ Ошибка сканирования моделей: {e}, используем fallback")

    def _select_model(
        self,
        prompt: str,
        category: Optional[str] = None,
        use_ollama: bool = False,
        node_type: Optional[str] = None,
    ) -> str:
        """Select the best local model for the task.

        [THERMAL PROTECTION] Если Mac Studio перегрет, выбирает максимально легкие модели.
        """
        # Проверка термального состояния для выбора модели
        is_throttled = False
        try:
            from app.mac_studio_monitor import get_mac_studio_monitor

            monitor = get_mac_studio_monitor()
            if monitor.last_stats:
                thermal_level = (
                    monitor.last_stats.get("hardware", {})
                    .get("temperature", {})
                    .get("thermal_level", "0")
                )
                if int(thermal_level) >= 1:
                    is_throttled = True
                    logger.warning(
                        "🔥 [THERMAL PROTECTION] Mac Studio is hot! Switching to light models."
                    )
        except:
            pass

        prompt_lower = prompt.lower()

        # Определяем категорию из промпта если не задана явно
        effective_category = category
        if not effective_category:
            if "подумай" in prompt_lower or "логика" in prompt_lower or "планир" in prompt_lower:
                effective_category = "reasoning"
            elif "привет" in prompt_lower or "здравств" in prompt_lower:
                effective_category = "general"
            elif "код" in prompt_lower or "программируй" in prompt_lower:
                effective_category = "coding"
            elif "изображен" in prompt_lower or "картинк" in prompt_lower:
                effective_category = "vision"
            elif len(prompt) < 300:
                effective_category = "fast"
            else:
                effective_category = "default"

        # ========== ДИНАМИЧЕСКИЙ ВЫБОР МОДЕЛИ ==========
        # Используем scanner если доступен, иначе fallback

        if is_throttled:
            # При перегреве форсируем самые легкие модели
            if node_type == "mlx":
                return "phi3.5:3.8b-stable"
            else:
                return "tinyllama:1.1b-chat"

        if _HAS_MODEL_SCANNER and (_cached_mlx_models or _cached_ollama_models):
            # Динамический выбор из реально доступных моделей
            if node_type == "mlx" and _cached_mlx_models:
                model = pick_mlx_for_category(effective_category, _cached_mlx_models)
                if model:
                    logger.debug(f"🎯 [DYNAMIC] MLX: {model} для {effective_category}")
                    return model
            elif node_type == "ollama" and _cached_ollama_models:
                model = pick_ollama_for_category(effective_category, _cached_ollama_models)
                if model:
                    logger.debug(f"🎯 [DYNAMIC] Ollama: {model} для {effective_category}")
                    return model

        # ========== FALLBACK: Статический выбор ==========
        # Используется если scanner недоступен или модели не найдены

        if effective_category == "reasoning":
            if node_type == "mlx":
                return MLX_MODELS_FALLBACK["reasoning"]
            else:
                return OLLAMA_MODELS_FALLBACK["reasoning"]

        if effective_category == "general":
            if node_type == "mlx":
                return MLX_MODELS_FALLBACK["chat"]
            else:
                return OLLAMA_MODELS_FALLBACK["chat"]

        if effective_category == "coding":
            if node_type == "mlx":
                return MLX_MODELS_FALLBACK["coding"]
            else:
                return OLLAMA_MODELS_FALLBACK["coding"]

        if effective_category == "fast":
            if node_type == "mlx":
                return MLX_MODELS_FALLBACK["fast"]
            else:
                return OLLAMA_MODELS_FALLBACK["fast"]

        if effective_category == "vision":
            return OLLAMA_MODELS_FALLBACK["vision"]

        # По умолчанию
        if node_type == "mlx":
            return MLX_MODELS_FALLBACK["default"]
        else:
            return OLLAMA_MODELS_FALLBACK["default"]

    async def _is_mlx_overloaded(self) -> bool:
        """Проверяет, перегружен ли MLX API Server"""
        try:
            from app.mlx_request_queue import get_request_queue

            queue = get_request_queue()
            stats = queue.get_stats()

            # MLX перегружен если:
            # - Все слоты заняты (active_requests >= max_concurrent)
            # - Есть очередь (queue_size > 0)
            is_overloaded = (
                stats.get("active_requests", 0) >= stats.get("max_concurrent", 5)
                or stats.get("queue_size", 0) > 0
            )

            if is_overloaded:
                logger.debug(
                    f"⚠️ MLX перегружен: активных={stats.get('active_requests')}/"
                    f"{stats.get('max_concurrent')}, очередь={stats.get('queue_size')}"
                )

            return is_overloaded
        except Exception as e:
            logger.debug(f"⚠️ Не удалось проверить загрузку MLX: {e}")
            return False  # Если не можем проверить, считаем что не перегружен

    def should_use_local(
        self, prompt: str, category: Optional[str] = None, images: Optional[list] = None
    ) -> bool:
        """Determine if the task should be routed to local LLM. По умолчанию предпочитаем локальные модели (Ollama/MLX)."""
        if not self.use_local:
            logger.debug("[LOCAL ROUTER] should_use_local=False: USE_LOCAL_LLM отключен")
            return False

        # If images are provided, we MUST use local vision model (e.g., moondream)
        if images:
            return True

        # Если категория задана — предпочитаем локальные модели (оркестратор, воркер, кодинг и т.д.)
        if category in LOCAL_TASK_CATEGORIES or category in MODEL_MAP:
            return True
        if category in (
            "autonomous_worker",
            "orchestrator",
            "general",
            "research",
            "reasoning",
            "coding",
            "fast",
        ):
            return True

        # Heuristic based on prompt content
        prompt_lower = prompt.lower()
        if any(
            keyword in prompt_lower
            for keyword in [
                "анализ логов",
                "проверь код",
                "напиши тест",
                "суммаризируй",
                "исправь опечатку",
            ]
        ):
            return True

        # If the prompt is very large (context-heavy) and doesn't require high-level reasoning
        if (
            len(prompt) > 2000
            and "архитектура" not in prompt_lower
            and "стратегия" not in prompt_lower
        ):
            return True

        # По умолчанию для неизвестных категорий — всё равно пробуем локальные модели (приоритет корпорации)
        if category is not None:
            return True

        return False

    async def search_visual_context(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        [OMNI-RAG v3] Поиск по визуальным артефактам через victoria-visual-search.
        """
        visual_search_url = os.getenv("VISUAL_SEARCH_URL", "http://victoria-visual-search:8005")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{visual_search_url}/search", json={"queries": [query], "top_k": top_k}
                )
                if response.status_code == 200:
                    results = response.json().get("results", [])
                    logger.info(
                        f"🖼️ [VISUAL SEARCH] Found {len(results)} matches for: {query[:50]}..."
                    )
                    return results
        except Exception as e:
            logger.debug(f"Visual search failed: {e}")
        return []

    async def _get_system_resources(self) -> Dict[str, Any]:
        """[SINGULARITY 28.0] Get current system resources (RAM/VRAM)."""
        try:
            from resource_monitor import get_resource_monitor

            rm = get_resource_monitor()
            return await rm.get_system_resources()
        except Exception:
            return {}

    async def _get_ice_mode(self) -> bool:
        """[SINGULARITY 29.7] Check if system:ice_mode is active in Redis."""
        try:
            from app.redis_manager import redis_manager

            client = await redis_manager.get_client()
            # We use a simple key check. If it exists and is "true" or "1", ice_mode is active.
            val = await client.get("system:ice_mode")
            return str(val).lower() in ("true", "1", "yes")
        except Exception as e:
            logger.debug(f"Failed to check ice_mode: {e}")
            return False

    async def run_local_llm(
        self,
        prompt: str,
        system_prompt: str = "",
        category: Optional[str] = None,
        images: Optional[list] = None,
        max_retries: int = 2,
        model: Optional[str] = None,
        model_hint: Optional[str] = None,
        is_vip: bool = False,
        session_id: Optional[str] = None,
        expert_name: Optional[str] = None,
    ) -> Optional[tuple]:
        """
        Запускает локальную LLM модель.
        Приоритет: MLX API Server (HTTP) и Ollama — оба используются (балансировка).
        model: если задан — используем эту модель и перебираем узлы (MLX/Ollama) пока один не ответит.
        model_hint: подсказка для выбора модели (для совместимости с ансамблем).
        is_vip: если True, запрос идет через VIP-коридор (приоритет и лучшие модели).

        Returns:
            tuple: (response, routing_source)
        """
        # [OMNI-RAG v3] Автоматическое обогащение визуальным контекстом
        # [SINGULARITY 29.5] Skip visual enrichment for reasoning/discovery sub-tasks to prevent loops
        prompt_lower = prompt.lower()
        is_subtask = (
            category in ["reasoning", "discovery", "internal"] or "#internal" in prompt_lower
        )

        if not is_subtask and (
            "#multimodal" in prompt_lower
            or any(kw in prompt_lower for kw in ["скриншот", "интерфейс", "схема", "ui", "дизайн"])
        ):
            visual_results = await self.search_visual_context(prompt)
            if visual_results:
                visual_block = "\n\n🖼️ [VISUAL CONTEXT]:\n"
                for res in visual_results:
                    visual_block += f"- {res.get('file_path')}: {res.get('description', 'No description available')}\n"
                prompt += visual_block
                logger.info("🎨 [OMNI-RAG] Injected visual context into prompt")

        # VIP-коридор: форсируем категорию и приоритет
        if is_vip:
            category = "vip"
            logger.info("🌟 [VIP ROUTE] Запрос через VIP-коридор (Иван/Совет)")

        # Используем подсказку, если модель не задана явно
        if model is None and model_hint:
            model = model_hint

        # МОНСТР-ЛОГИКА: Поддержка форсированного локального роутинга
        if getattr(self, "force_local", False):
            logger.info("🚀 [MONSTER] Форсирован локальный роутинг для этого запроса.")
        logger.info("[ROUTER] ========== LocalAIRouter.run_local_llm() ==========")
        logger.info("[ROUTER] Input model: %s", model)
        logger.info("[ROUTER] Category: %s", category)
        logger.info("[ROUTER] Prompt length: %d chars", len(prompt))
        logger.info("[ROUTER] Prompt preview: %s...", prompt[:150])

        # [SINGULARITY 24.3] Persona Injection for Experts
        if expert_name and not system_prompt:
            system_prompt = f"ТЫ - {expert_name}. Действуй и отвечай в соответствии со своей ролью и характером."
            logger.info(f"🎭 [PERSONA] Injected persona for {expert_name}")

        # [SINGULARITY 30.1] Rate Limiter: LLM inference requires a token
        try:
            from app.services.blackboard_service import get_blackboard_service

            blackboard = get_blackboard_service()
            if not await blackboard.acquire_token(timeout=10.0):
                logger.warning("🛑 [LIMITER] LLM inference rejected (no tokens available)")
                return ("System is overloaded. Please try again later.", "limiter")
        except Exception as e:
            logger.debug(f"Rate limiter check failed: {e}")

        # 🔄 ДИНАМИЧЕСКОЕ ОБНОВЛЕНИЕ СПИСКА МОДЕЛЕЙ (если истёк TTL)
        # Это позволяет подхватывать новые модели и замечать удалённые
        await self._refresh_available_models()

        # ПРИОРИТЕТ: Использовать MLX API Server и Ollama через HTTP роутинг
        # MLX Router напрямую не используется в контейнере (требует модуль mlx)
        # Вместо этого используем MLX API Server через HTTP (уже настроен в nodes)
        """Call local LLM (Ollama style) with automatic failover, retry logic and node selection."""

        # Модель: параметр вызова, или _preferred_model от воркера (батчи по модели — меньше load/unload)
        initial_model = model or getattr(self, "_preferred_model", None)

        # [SINGULARITY 29.6] Dynamic Model Tiering: Downgrades model if RAM is low.
        # [SINGULARITY 29.7] Load-aware Tiering: Downgrades if system:ice_mode is active.
        # [SINGULARITY 28.1] Quality Guard: Only downgrade for dialogue/fast tasks.
        # For expert/heavy tasks, we wait for memory instead of sacrificing quality.
        try:
            # Check ice_mode first (system-wide pressure flag)
            ice_mode = await self._get_ice_mode()

            res = await self._get_system_resources()
            avail_gb = res.get("ram", {}).get("available_gb", 100)
            is_dialogue = category == "chat" or (
                isinstance(prompt, str) and "#chat" in prompt.lower()
            )
            is_rd = category == "r&d_optimization" or (
                isinstance(prompt, str) and "#rd" in prompt.lower()
            )

            # [SINGULARITY 29.7] Load-aware Downgrade
            if ice_mode:
                is_expert = category in ("reasoning", "coding", "research", "expert") or (
                    initial_model
                    and (
                        "70b" in initial_model.lower()
                        or "32b" in initial_model.lower()
                        or "35b" in initial_model.lower()
                    )
                )
                if is_expert:
                    target_model = (
                        "phi3.5:3.8b-stable"
                        if "mlx" in str(getattr(self, "_active_node", {}).get("url", ""))
                        else "tinyllama:1.1b-chat"
                    )
                    logger.warning(
                        f"❄️ [ICE MODE] System pressure detected! Downgrading expert request: {initial_model} -> {target_model}"
                    )
                    initial_model = target_model
                    model = initial_model

            # [SINGULARITY 29.6] Aggressive Memory Guard for R&D
            if is_rd and avail_gb < 12:
                logger.info(
                    f"🧠 [R&D MEMORY GUARD] RAM low ({avail_gb:.1f}GB). Performing aggressive model cleanup..."
                )
                if self._memory_manager:
                    await self._memory_manager.cleanup_unused_models()
                    # Force Ollama to unload all models to free up VRAM/RAM
                    try:
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            # Ollama /api/tags doesn't unload, but loading a non-existent model or
                            # sending a request with keep_alive=0 might help.
                            # Best way is to use the internal memory manager if it supports it.
                            pass
                    except:
                        pass
                    await asyncio.sleep(5)
                    res = await self._get_system_resources()
                    avail_gb = res.get("ram", {}).get("available_gb", 100)
                    logger.info(f"🛡️ [R&D MEMORY GUARD] RAM after cleanup: {avail_gb:.1f}GB")

            if avail_gb < 8:
                if is_dialogue:
                    # For chat, speed is priority, so we downgrade
                    if avail_gb < 4 and initial_model and "tinyllama" not in initial_model.lower():
                        logger.warning(
                            f"📉 [TIERING] RAM critical ({avail_gb:.1f}GB). Downgrading {initial_model} -> tinyllama:1.1b-chat (Chat Priority)"
                        )
                        initial_model = "tinyllama:1.1b-chat"
                        model = initial_model
                    elif (
                        avail_gb < 8
                        and initial_model
                        and ("35b" in initial_model.lower() or "32b" in initial_model.lower())
                    ):
                        logger.warning(
                            f"📉 [TIERING] RAM low ({avail_gb:.1f}GB). Downgrading {initial_model} -> phi3.5:3.8b-stable (Chat Priority)"
                        )
                        initial_model = "phi3.5:3.8b-stable"
                        model = initial_model
                else:
                    # For expert tasks, quality is priority. We wait for ModelMemoryManager to free up space.
                    logger.info(
                        f"⏳ [QUALITY GUARD] RAM low ({avail_gb:.1f}GB) for expert task. Waiting for memory instead of downgrading..."
                    )
                    if self._memory_manager:
                        await self._memory_manager.cleanup_unused_models()
                        # Give it a few seconds to settle
                        await asyncio.sleep(5)
                        # Re-check memory
                        res = await self._get_system_resources()
                        avail_gb = res.get("ram", {}).get("available_gb", 100)
                        logger.info(f"🛡️ [QUALITY GUARD] RAM after cleanup: {avail_gb:.1f}GB")
        except Exception as tier_err:
            logger.debug(f"Dynamic tiering failed: {tier_err}")

        if images and MODEL_MAP.get("vision"):
            model = MODEL_MAP["vision"]
            logger.info("[ROUTER] Using vision model: %s", model)
            initial_model = model  # Vision - принудительно

        # Кэш: только для коротких промптов без изображений
        prompt_cache_key = None
        if len(prompt) <= 1000 and not images:
            raw_key = f"{prompt}|{category or ''}|{model or ''}|{session_id or ''}"
            prompt_cache_key = hashlib.sha256(raw_key.encode()).hexdigest()[:32]
            now = time.time()
            if prompt_cache_key in self._prompt_cache:
                ts = self._prompt_cache_meta.get(prompt_cache_key, 0)
                if (now - ts) < self._prompt_cache_ttl:
                    self._prompt_cache_hits += 1
                    logger.debug("✅ [CACHE HIT] LocalAIRouter prompt cache")
                    return self._prompt_cache[prompt_cache_key]
            self._prompt_cache_misses += 1

        # Определяем тип задачи для сбора данных
        task_type = self._determine_task_type(prompt, category)

        # A/B Testing: определяем, использовать ли ML-роутинг
        use_ml_routing = False
        if get_ab_test and self.ml_model:
            ab_test = await get_ab_test(ml_ratio=0.5)  # 50% ML, 50% heuristic
            use_ml_routing = ab_test.should_use_ml()

        # ML Prediction: предсказываем оптимальный маршрут (если включен A/B тест)
        ml_predicted_route = None
        ml_confidence = None
        if use_ml_routing and self.ml_model:
            ml_predicted_route, ml_confidence = await self.predict_optimal_route(prompt, category)
            if ml_predicted_route and ml_confidence > 0.7:
                logger.info(
                    f"🤖 [ML ROUTER] Using ML prediction: {ml_predicted_route} (confidence: {ml_confidence:.2f})"
                )
        elif self.ml_model:
            logger.debug("📊 [HEURISTIC ROUTER] A/B test: using heuristic routing")

        # Ленивая инициализация memory_manager (только при использовании)
        if self._memory_manager is None and self._memory_manager_url:
            try:
                from model_memory_manager import get_memory_manager

                self._memory_manager = get_memory_manager(self._memory_manager_url)
                logger.debug("✅ ModelMemoryManager инициализирован (ленивая инициализация)")
            except Exception as e:
                logger.debug(f"⚠️ ModelMemoryManager недоступен: {e}")
                self._memory_manager = None

        # Проверка памяти перед выбором узла (для сервера)
        if self._memory_manager:
            available_mb = await self._memory_manager.get_available_memory_mb()
            if available_mb < 200:  # MIN_FREE_MEMORY_MB
                logger.warning(
                    f"⚠️ [MEMORY] Критическая нехватка памяти: {available_mb}MB, запускаем очистку..."
                )
                await self._memory_manager.emergency_memory_cleanup()

        # Discover healthy nodes (with caching)
        healthy_nodes = await self.check_health()
        if not healthy_nodes:
            logger.error("❌ No healthy local nodes found!")
            return ("No healthy local nodes found.", "error")

        # [SINGULARITY 30.6] Heavyweight Semaphore Logic
        is_heavy = model and any(x in model.lower() for x in ("70b", "32b", "35b", "qwq"))
        if is_heavy and self._memory_manager:
            try:
                from app.services.blackboard_service import get_blackboard_service

                blackboard = get_blackboard_service()

                logger.info(f"🐘 [HEAVY-MODEL] {model} is a heavyweight. Requesting global lock...")
                if not await blackboard.acquire_heavy_model_lock(model):
                    return (
                        "Heavyweight queue timeout. System is busy with another large model.",
                        "queue_timeout",
                    )

                # После захвата замка — проактивная выгрузка других моделей
                await self._memory_manager.predictive_unload("extreme")
            except Exception as e:
                logger.warning(f"⚠️ [HEAVY-LOCK] Error in semaphore logic: {e}")

        # УМНЫЙ ВЫБОР УЗЛА: система сама выбирает лучший источник на основе задачи
        # 1. Load Balancing: выбираем лучший узел на основе загрузки (приоритет)
        if get_load_balancer:
            load_balancer = get_load_balancer()
            best_node = load_balancer.select_best_node(healthy_nodes)
            if best_node and best_node != healthy_nodes[0]:
                # Перемещаем лучший узел в начало
                healthy_nodes.remove(best_node)
                healthy_nodes.insert(0, best_node)
                logger.info(
                    f"⚖️ [LOAD BALANCER] Выбран узел: {best_node['name']} на основе загрузки"
                )

        # 2. ML Prediction: если ML предсказал маршрут, учитываем его
        if ml_predicted_route and ml_predicted_route != "cloud":
            # Сортируем узлы, чтобы предсказанный был первым (но после load balancer)
            predicted_node = None
            other_nodes = []
            for node in healthy_nodes:
                if node.get("routing_key") == ml_predicted_route:
                    predicted_node = node
                else:
                    other_nodes.append(node)

            if predicted_node and predicted_node != healthy_nodes[0]:
                # Перемещаем предсказанный узел на второе место (после load balancer)
                healthy_nodes.remove(predicted_node)
                healthy_nodes.insert(1, predicted_node)
                logger.info(f"🤖 [ML ROUTER] Учитываем ML-предсказание: {predicted_node['name']}")

        # 3. Выбор на основе типа задачи (reasoning → MLX, fast → Ollama, и т.д.)
        # Это уже делается в _select_model на основе node_type

        # 4. БАЛАНСИРОВКА: Перемешиваем узлы для равномерного использования MLX и Ollama
        mlx_nodes = [n for n in healthy_nodes if "11435" in n["url"] or "mlx" in n["url"].lower()]
        ollama_nodes = [
            n for n in healthy_nodes if "11434" in n["url"] or "ollama" in n["url"].lower()
        ]
        other_nodes = [n for n in healthy_nodes if n not in mlx_nodes and n not in ollama_nodes]
        # Логируем раз в 5 мин, если MLX недоступен — чтобы было видно, что задачи идут только в Ollama
        if not mlx_nodes and ollama_nodes:
            _t = time.time()
            if (
                not hasattr(LocalAIRouter, "_last_no_mlx_log")
                or (_t - LocalAIRouter._last_no_mlx_log) > 300
            ):
                logger.warning(
                    "⚠️ [ROUTER] MLX API Server (порт 11435) недоступен — все задачи обрабатываются через Ollama. "
                    "Запуск: scripts/start_mlx_api_server.sh; проверка: curl -s http://localhost:11435/health"
                )
                LocalAIRouter._last_no_mlx_log = _t
        prefer_ollama_due_to_mlx_overload = False

        # 4.1 Если MLX перегружен (очередь/rate limit) — пробуем Ollama первым
        if mlx_nodes and ollama_nodes:
            try:
                if await self._is_mlx_overloaded():
                    prefer_ollama_due_to_mlx_overload = True
                    healthy_nodes = ollama_nodes + mlx_nodes + other_nodes
                    logger.info(
                        "🔄 [ROUTER] MLX перегружен — приоритет Ollama для этого запроса "
                        "(меньше 429, быстрее ответ)"
                    )
            except Exception as e:
                logger.debug(f"Проверка перегрузки MLX: {e}")

        # Если есть оба типа узлов и не поставили Ollama первым — чередуем их
        if mlx_nodes and ollama_nodes and not prefer_ollama_due_to_mlx_overload:
            balanced_nodes = []
            max_len = max(len(mlx_nodes), len(ollama_nodes))
            for i in range(max_len):
                if i < len(mlx_nodes):
                    balanced_nodes.append(mlx_nodes[i])
                if i < len(ollama_nodes):
                    balanced_nodes.append(ollama_nodes[i])
            # Добавляем остальные узлы в конец
            balanced_nodes.extend(other_nodes)
            # Обновляем порядок, но сохраняем первый узел от load balancer если он был выбран
            if healthy_nodes and balanced_nodes:
                first_node = healthy_nodes[0]
                if first_node in balanced_nodes:
                    balanced_nodes.remove(first_node)
                    balanced_nodes.insert(0, first_node)
                healthy_nodes = balanced_nodes
                logger.info(
                    f"⚖️ [BALANCED] Перемешаны узлы для равномерного использования MLX ({len(mlx_nodes)}) и Ollama ({len(ollama_nodes)})"
                )

        # Умный выбор узла на основе задачи и загрузки
        # Система сама выберет лучший источник (MLX или Ollama) на основе:
        # 1. Типа задачи (reasoning → мощная модель, fast → легкая)
        # 2. Загрузки узла (load balancing)
        # 3. Доступности модели
        # 4. Балансировки между MLX и Ollama

        # УЛУЧШЕНИЕ: Если есть предпочтительный источник (из worker'а), пробуем его первым
        preferred_source = getattr(self, "_preferred_source", None)

        # [SINGULARITY 21.3] God Mode: Victoria Brain → MLX, Victoria Hands → Ollama
        # victoria-wisdom-v3.5 (без тега)  = мозг  → MLX (планировщик, reasoning)
        # victoria-wisdom-v3.5:latest       = руки  → Ollama (executor, step execution)
        is_victoria = model and "victoria-wisdom-v3.5" in model.lower()
        # Руки — модель с явным тегом :latest → всегда Ollama
        is_victoria_hands = is_victoria and model and model.lower().endswith(":latest")
        # Мозг — без тега, или тег явно не :latest
        is_victoria_brain = is_victoria and not is_victoria_hands
        monitor = get_mlx_monitor()
        health_score = monitor.get_health_score()
        mlx_healthy = health_score >= 0.6 and bool(mlx_nodes)
        victoria_mlx_brain = os.environ.get("VICTORIA_MLX_BRAIN", "false").lower() == "true"

        # v135: wisdom MLX-primary (Google/SRE: right backend first). Opt-out via env.
        wisdom_mlx_primary = (
            os.environ.get("VICTORIA_WISDOM_MLX_PRIMARY", "true").lower() == "true"
            or victoria_mlx_brain
        )
        if is_victoria and wisdom_mlx_primary and mlx_healthy:
            preferred_source = "mlx"
            # MLX registry is untagged; strip :latest for brain/hands wisdom
            if model and model.lower().endswith(":latest"):
                model = model[: -len(":latest")]
            logger.info(
                "🧠 [WISDOM-MLX] victoria-wisdom → MLX primary (health=%.2f, model=%s)",
                health_score,
                model,
            )
        elif is_victoria_hands and ollama_nodes:
            # Legacy hands path when MLX-primary disabled or MLX unhealthy
            preferred_source = "ollama"
            logger.info("🤲 [HANDS] Victoria:latest → Ollama (executor path)")
        elif is_victoria_brain:
            if victoria_mlx_brain and mlx_healthy:
                preferred_source = "mlx"
                logger.info(
                    "🧠 [BRAIN] Victoria (no tag) → MLX (VICTORIA_MLX_BRAIN=true, health=%.2f)",
                    health_score,
                )
            elif mlx_healthy and not ollama_nodes:
                preferred_source = "mlx"
                logger.info("🧠 [BRAIN] Victoria → MLX (no Ollama available)")
            else:
                preferred_source = "ollama"
                logger.info(
                    "⚡ [BRAIN FALLBACK] Victoria → Ollama (MLX health=%.2f, Ollama available=%s)",
                    health_score,
                    bool(ollama_nodes),
                )

        # [SINGULARITY 21.5] Predictive Warmup for reasoning/complex tasks OR MLX overload OR Victoria
        should_warmup = category in ("reasoning", "complex") or health_score < 0.5 or is_victoria

        if should_warmup and ollama_nodes:
            ollama_model = self._select_model(prompt, category, node_type="ollama")
            # Получаем текущую историю для прогрева KV-Cache
            session_id = session_id or getattr(self, "_current_session_id", "default")
            current_history = []
            if session_id:
                current_history = await self.context_mirror.get_context(session_id) or []

            asyncio.create_task(
                self._trigger_predictive_warmup(
                    ollama_model, ollama_nodes[0]["url"], history=current_history
                )
            )

        if preferred_source:
            # Перемещаем предпочтительный узел в начало
            preferred_nodes = [
                n
                for n in healthy_nodes
                if (
                    preferred_source == "mlx" and ("11435" in n["url"] or "mlx" in n["url"].lower())
                )
                or (
                    preferred_source == "ollama"
                    and ("11434" in n["url"] or "ollama" in n["url"].lower())
                )
            ]
            if preferred_nodes:
                for node in preferred_nodes:
                    if node in healthy_nodes:
                        healthy_nodes.remove(node)
                        healthy_nodes.insert(0, node)
                logger.info(
                    f"🎯 [PREFERRED] Используем предпочтительный источник: {preferred_source}"
                )

        # [SINGULARITY 21.5] Context Mirroring: Save context before call
        session_id = session_id or getattr(self, "_current_session_id", None)
        if session_id:
            current_history = await self.context_mirror.get_context(session_id) or []
            # Add current prompt to history for mirroring
            current_history.append({"role": "user", "content": prompt})
            await self.context_mirror.save_context(session_id, current_history)

        # Try each node with retry logic
        start_time = time.time()
        for node in healthy_nodes:
            node_url_base = node["url"]

            # [SINGULARITY 21.10] Circuit Breaker Check
            # Мировая практика (Polly, Hystrix): при переходе OPEN→HALF_OPEN нужно
            # явно установить state=HALF_OPEN ДО probe-запроса, иначе _on_success()
            # не переводит CB в CLOSED (проверяет state == HALF_OPEN).
            # start_probe() защищает от thundering herd: только ОДИН probe одновременно.
            breaker = self._node_breakers.get(node_url_base)
            if breaker and breaker.state == CircuitState.OPEN:
                if not breaker._should_attempt_reset():
                    logger.warning(f"🚨 [CIRCUIT BREAKER] Node {node_url_base} is OPEN. Skipping.")
                    continue
                else:
                    if not breaker.start_probe():
                        # Другая корутина уже отправила probe — пропускаем
                        logger.debug(
                            "⏳ [CIRCUIT BREAKER] Node %s probe already in flight. Skipping.",
                            node_url_base,
                        )
                        continue
                    breaker.state = CircuitState.HALF_OPEN  # ← обязательно до probe
                    logger.info(
                        f"🔄 [CIRCUIT BREAKER] Node {node_url_base} OPEN→HALF_OPEN. Sending probe..."
                    )
                    # [FIX] Light-weight probe: use /api/tags instead of full LLM request.
                    # This avoids model-load timeout killing the probe.
                    try:
                        _health_ep = node_url_base.rstrip("/") + "/api/tags"
                        async with httpx.AsyncClient(timeout=5.0) as _hc:
                            _hr = await _hc.get(_health_ep)
                        if _hr.status_code == 200:
                            breaker._on_success()
                            logger.info(
                                "✅ [CIRCUIT BREAKER] Node %s health probe OK → CLOSED",
                                node_url_base,
                            )
                            # [SINGULARITY 25.0] Post-recovery jitter: stagger burst after probe succeeds.
                            # Without jitter all blocked coroutines rush Ollama simultaneously after CLOSED,
                            # causing 5+ simultaneous requests that re-fill the queue and reopen the CB.
                            _jitter = random.uniform(0.3, 2.0)
                            logger.info(
                                "[CIRCUIT BREAKER] ⏱️ Post-recovery jitter %.2fs for node %s",
                                _jitter,
                                node_url_base,
                            )
                            await asyncio.sleep(_jitter)
                            # Continue normally (CB is now CLOSED, request goes through after jitter)
                        else:
                            breaker._on_failure(f"HealthProbe HTTP {_hr.status_code}")
                            logger.warning(
                                "🔴 [CIRCUIT BREAKER] Node %s health probe failed (%d) → OPEN",
                                node_url_base,
                                _hr.status_code,
                            )
                            continue
                    except Exception as _probe_err:
                        breaker._on_failure(f"HealthProbe: {_probe_err}")
                        logger.warning(
                            "🔴 [CIRCUIT BREAKER] Node %s health probe error → OPEN: %s",
                            node_url_base,
                            _probe_err,
                        )
                        continue
            elif breaker and breaker.state == CircuitState.HALF_OPEN:
                # Уже в HALF_OPEN (установлено параллельной корутиной) — probe в процессе
                if breaker._probe_in_flight:
                    logger.debug(
                        "⏳ [CIRCUIT BREAKER] Node %s HALF_OPEN probe in flight. Skipping.",
                        node_url_base,
                    )
                    continue

            # Определяем, это Ollama или MLX API Server
            is_ollama = "11434" in node_url_base or "ollama" in node_url_base.lower()
            is_mlx = "11435" in node_url_base or "mlx" in node_url_base.lower()

            # [Prioritization] Worker с OLLAMA_REQUEST_PRIORITY=low уступает Ollama victoria-agent.
            # При перегрузке (очередь >= 80% от OLLAMA_MAX_QUEUE) пропускаем запрос → уходим на MLX.
            if is_ollama and os.getenv("OLLAMA_REQUEST_PRIORITY", "").lower() == "low":
                try:
                    ollama_max_queue = int(os.getenv("OLLAMA_MAX_QUEUE", "100"))
                    async with httpx.AsyncClient(timeout=3.0) as hc:
                        resp = await hc.get(f"{node_url_base}/api/ps")
                    if resp.status_code == 200:
                        ps_data = resp.json()
                        running = len(ps_data.get("models", []))
                        # Ollama не предоставляет длину очереди напрямую, но если нет свободных слотов — skip
                        ollama_num_parallel = int(os.getenv("OLLAMA_NUM_PARALLEL", "4"))
                        if running >= ollama_num_parallel:
                            logger.info(
                                "⏩ [LOW-PRIORITY] Ollama full (%d/%d running), skipping for low-prio worker.",
                                running,
                                ollama_num_parallel,
                            )
                            continue
                except Exception as _prio_err:
                    logger.debug("Ollama priority check failed: %s", _prio_err)

            # [SINGULARITY 21.10] MLX Admission Control: Protect brain from overload
            if is_mlx:
                try:
                    import psutil

                    ram = psutil.virtual_memory()
                    # Если свободного RAM меньше резерва MLX — блокируем запрос к MLX
                    reserve_bytes = MLX_RAM_RESERVE_GB * 1024**3
                    if ram.available < reserve_bytes:
                        logger.warning(
                            f"🧠 [ADMISSION CONTROL] MLX blocked to save brain! "
                            f"Available RAM {ram.available / 1024**3:.1f}GB < Reserve {MLX_RAM_RESERVE_GB}GB"
                        )
                        continue
                except Exception as e:
                    logger.debug(f"Admission control check failed: {e}")

            # [FALLBACK_MODE] If MLX failed and we are on Ollama, use mirrored context
            if is_ollama and any(
                "mlx" in n["url"] for n in healthy_nodes[: healthy_nodes.index(node)]
            ):
                logger.info("[FALLBACK_MODE] MLX failed, switching to Ollama with mirrored context")

            # ИНТЕЛЛЕКТУАЛЬНЫЙ ВЫБОР МОДЕЛИ на основе мировых практик
            # ВАЖНО: MLX и Ollama имеют РАЗНЫЕ модели! Выбираем для КАЖДОГО узла отдельно!
            node_type = "mlx" if is_mlx else "ollama" if is_ollama else "unknown"

            # 1. Модель от воркера (_preferred_model при батчах по модели) или параметр вызова
            current_model = None
            if initial_model:
                # Воркер задаёт модель по сканеру (source+model) — принимаем для подходящего типа узла
                if is_mlx or is_ollama:
                    current_model = initial_model
                else:
                    if initial_model in (list(MLX_MODELS.values()) + list(OLLAMA_MODELS.values())):
                        current_model = initial_model
                    else:
                        logger.debug(
                            f"⚠️ Модель {initial_model} не в fallback для {node_type}, выбираем автоматически"
                        )
                        current_model = None

            # 2. Если модель не задана или не совместима - выбираем для этого узла
            if not current_model:
                # [SINGULARITY 21.3] Memory Guard 2.1 (God Mode 128GB)
                if is_ollama:
                    try:
                        import psutil

                        ram = psutil.virtual_memory()
                        # [SINGULARITY 21.8] God Mode 128GB: учитываем резерв MLX (MLX_RAM_RESERVE_GB)
                        from app.ollama_keep_alive_policy import MLX_RAM_RESERVE_GB

                        effective_reserve = MLX_RAM_RESERVE_GB + RAM_RESERVE_GB

                        if ram.available < (effective_reserve * 1024**3):
                            logger.warning(
                                f"⚠️ [MEMORY GUARD] Low RAM ({ram.available / 1024**3:.1f}GB < {effective_reserve}GB reserve), cleaning up..."
                            )
                            async with httpx.AsyncClient(timeout=5.0) as unload_client:
                                # Выгружаем только если это не VIP и не Reasoning
                                if category not in ("reasoning", "vip") and not is_vip:
                                    # Выгружаем самую тяжелую не-бессмертную модель
                                    await unload_client.post(
                                        f"{node['url']}/api/generate",
                                        json={"model": "qwen3.5:35b", "keep_alive": 0},
                                    )
                                    await unload_client.post(
                                        f"{node['url']}/api/generate",
                                        json={"model": "deepseek-r1:32b", "keep_alive": 0},
                                    )
                    except Exception as mem_err:
                        logger.debug(f"Memory cleanup failed: {mem_err}")

                # ВАЖНО: Для REASONING задач ВСЕГДА используем _select_model()
                # Выбор модели по категории (scanner или fallback; MLX только лёгкие)
                if category == "reasoning":
                    current_model = self._select_model(prompt, category, node_type=node_type)
                    logger.info(
                        f"🎯 [REASONING] Узел: {node_type} | Модель: {current_model} (принудительный выбор для reasoning)"
                    )
                else:
                    # Используем простой выбор модели по приоритетам (быстрые модели первыми)
                    # Intelligent router отключён — он выбирает тяжёлые модели и перегружает систему
                    use_intelligent = os.getenv("USE_INTELLIGENT_ROUTER", "false").lower() in (
                        "true",
                        "1",
                        "yes",
                    )
                    if use_intelligent:
                        try:
                            from intelligent_model_router import get_intelligent_router

                            intelligent_router = get_intelligent_router()

                            available_models = []
                            if is_mlx:
                                available_models = list(MLX_MODELS.values())
                            elif is_ollama:
                                available_models = list(OLLAMA_MODELS.values())

                            if available_models:
                                optimize_mode = os.getenv("INTELLIGENT_ROUTER_OPTIMIZE", "speed")
                                (
                                    optimal_model,
                                    _task_cat,
                                    confidence,
                                ) = await intelligent_router.select_optimal_model(
                                    prompt=prompt,
                                    category=category or "",
                                    available_models=available_models,
                                    optimize_for=optimize_mode,
                                )

                                if optimal_model and confidence > 0.5:
                                    current_model = optimal_model
                                    logger.info(
                                        f"🧠 [INTELLIGENT ROUTER] Узел: {node_type} | Модель: {current_model} (confidence: {confidence:.2f})"
                                    )
                                else:
                                    current_model = self._select_model(
                                        prompt, category, node_type=node_type
                                    )
                            else:
                                current_model = self._select_model(
                                    prompt, category, node_type=node_type
                                )
                        except Exception as e:
                            logger.debug(f"Intelligent router failed: {e}, using fallback")
                            current_model = self._select_model(
                                prompt, category, node_type=node_type
                            )
                    else:
                        # Простой выбор по приоритетам (лёгкие модели первыми)
                        current_model = self._select_model(prompt, category, node_type=node_type)

            # Финальная модель для этого узла
            model = current_model
            logger.info(
                f"🎯 [SMART SELECTION] Узел: {node['name']} | Модель: {model} | Тип задачи: {category or 'auto'}"
            )

            # Используем /api/chat для Ollama (более современный endpoint)
            if is_ollama or is_mlx:
                node_url = f"{node['url']}/api/chat"
                logger.info(
                    f"🏠 [LOCAL ROUTE] Node: {node['name']} | Model: {model} | Endpoint: /api/chat"
                )

                messages = []
                # Use mirrored history if available
                if is_ollama and session_id:
                    mirrored_history = await self.context_mirror.get_context(session_id)
                    if mirrored_history:
                        # Create a copy to avoid modifying the original history
                        messages = list(mirrored_history)
                        # Check if last message is already the current prompt
                        if not messages or messages[-1].get("content") != prompt:
                            messages.append({"role": "user", "content": prompt})

                if not messages:
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})

                payload = {"model": model, "messages": messages, "stream": False}
                if self._should_disable_thinking(model):
                    payload["think"] = False
                # [SINGULARITY 24.8] Adaptive Context Window
                payload["options"] = self._get_adaptive_options(model)

                mlx_alive = any(
                    "mlx" in n["url"].lower() or "mlx" in n.get("routing_key", "").lower()
                    for n in healthy_nodes
                )
                payload["keep_alive"] = get_keep_alive(model, mlx_alive=mlx_alive)
            else:
                # Для других сервисов используем /api/generate
                node_url = f"{node['url']}/api/generate"
                logger.info(
                    f"🏠 [LOCAL ROUTE] Node: {node['name']} | Model: {model} | Endpoint: /api/generate"
                )

                # Use mirrored history if available for generate endpoint too
                full_prompt = ""
                if is_ollama and session_id:
                    mirrored_history = await self.context_mirror.get_context(session_id)
                    if mirrored_history:
                        for msg in mirrored_history:
                            role = "User" if msg.get("role") == "user" else "Assistant"
                            full_prompt += f"{role}: {msg.get('content')}\n"
                        if not mirrored_history or mirrored_history[-1].get("content") != prompt:
                            full_prompt += f"User: {prompt}\nAssistant:"
                        else:
                            full_prompt += "Assistant:"

                if not full_prompt:
                    full_prompt = f"{system_prompt}\n\nUser: {prompt}\nAssistant:"

                # [SINGULARITY 25.0] Adaptive Context Guard
                if self.compressor:
                    try:
                        from resource_monitor import get_resource_monitor

                        rm = get_resource_monitor()
                        sys_res = await rm.get_system_resources()
                        avail_gb = sys_res.get("ram", {}).get("available_gb", 100)

                        # Если RAM < 8GB или контекст слишком большой (грубая оценка по символам)
                        if avail_gb < 8 or len(full_prompt) > 40000:
                            logger.info(
                                f"✂️ [CONTEXT GUARD] RAM low ({avail_gb:.1f}GB) or prompt long ({len(full_prompt)}). Compressing..."
                            )
                            # Для отладки: принудительно сжимаем повторяющиеся строки
                            full_prompt = self.compressor.squeeze_prompt(full_prompt)
                            logger.info(
                                f"✅ [CONTEXT GUARD] Squeezed prompt to {len(full_prompt)} chars"
                            )
                    except Exception as cg_err:
                        logger.debug(f"Context guard failed: {cg_err}")

                payload = {"model": model, "prompt": full_prompt, "stream": False}
                if self._should_disable_thinking(model):
                    payload["think"] = False
                # [SINGULARITY 24.8] Adaptive Context Window
                payload["options"] = self._get_adaptive_options(model)

                mlx_alive = any(
                    "mlx" in n["url"].lower() or "mlx" in n.get("routing_key", "").lower()
                    for n in healthy_nodes
                )
                payload["keep_alive"] = get_keep_alive(model, mlx_alive=mlx_alive)
            if images:
                payload["images"] = images

            # 1165. Мониторинг ресурсов перед запросом (особенно для MLX)
            if is_mlx:
                # Circuit Breaker Check
                monitor = get_mlx_monitor()
                if not monitor.is_mlx_available():
                    logger.warning(
                        "🚨 [CIRCUIT BREAKER] MLX is temporarily disabled. Skipping node %s",
                        node["name"],
                    )
                    continue

                try:
                    from resource_monitor import get_resource_monitor

                    monitor = get_resource_monitor()
                    mlx_health = await monitor.get_mlx_health()

                    # Если MLX перегружен - пропускаем его
                    if monitor.should_throttle_mlx(mlx_health):
                        logger.warning(
                            f"⚠️ [RESOURCE] MLX перегружен: "
                            f"RAM={mlx_health.get('system', {}).get('ram', {}).get('used_percent', 0):.1f}%, "
                            f"CPU={mlx_health.get('system', {}).get('cpu', {}).get('percent', 0):.1f}%, "
                            f"Active={mlx_health.get('active_requests', 0)}/{mlx_health.get('max_concurrent', 5)}"
                        )
                        continue  # Пропускаем этот узел, пробуем следующий
                except Exception as e:
                    logger.debug(f"Resource monitoring failed: {e}")

            # Load Balancing: отмечаем начало запроса
            if get_load_balancer:
                load_balancer = get_load_balancer()
                load_balancer.start_request(node.get("routing_key", ""))

            # Retry logic with exponential backoff
            for attempt in range(max_retries + 1):
                try:
                    async with httpx.AsyncClient() as client:
                        request_start = time.time()
                        headers = {}
                        # VIP = только живой диалог с пользователем (is_vip=True).
                        # Воркеры с brain-задачами НЕ получают high — иначе они забивают VIP-очередь
                        # и запросы пользователя не получают приоритета.
                        if is_vip:
                            headers["X-Request-Priority"] = "high"
                            logger.info(
                                f"🌟 [VIP HEADER] User dialogue → high priority for {category or model}"
                            )
                        elif category == "reasoning":
                            headers["X-Request-Priority"] = "medium"
                            logger.info("⚙️ [WORKER HEADER] Worker reasoning task → medium priority")
                        else:
                            headers["X-Request-Priority"] = "normal"
                        # Таймаут по метрикам этой модели (load/processing с запасом); у каждой модели свои значения
                        _node_timeout = float(os.getenv("LOCAL_ROUTER_LLM_TIMEOUT", "300"))

                        # Увеличиваем таймаут для reasoning задач (Совет, стратегия)
                        if category == "reasoning":
                            _node_timeout = max(_node_timeout, 1800.0)
                            logger.info(f"🕒 [REASONING] Увеличен таймаут до {_node_timeout}с")

                        # МОНСТР-ЛОГИКА: Если форсирован локальный роутинг, увеличиваем таймаут до 10 минут
                        if getattr(self, "force_local", False):
                            _node_timeout = 1800.0
                            logger.info(
                                "🚀 [MONSTER] Увеличен таймаут HTTP до 1800с для форсированного локального роутинга."
                            )

                        try:
                            from app.model_performance_probe import (
                                get_timeout_estimate_from_metrics_dict,
                            )
                            from available_models_scanner import get_model_metrics

                            _source = (
                                "ollama" if node.get("routing_key") == "ollama_studio" else "mlx"
                            )
                            if model:
                                _m = get_model_metrics(model, _source)
                                if _m:
                                    _node_timeout = get_timeout_estimate_from_metrics_dict(
                                        max_tokens=2048, metrics_dict=_m
                                    )
                        except Exception:
                            pass

                        # [SINGULARITY 25.0] Global Ollama Backpressure Semaphore
                        # Acquire a global slot before any Ollama HTTP call to prevent
                        # concurrent overload across all containers → 503 → CB OPEN cycle.
                        # If Redis is unavailable, fail-open (allow request).
                        _ollama_slot_acquired = False
                        if is_ollama:
                            try:
                                from redis_manager import RedisManager as _RM

                                _slot_acquired = await _RM().acquire_ollama_slot()
                                if not _slot_acquired:
                                    logger.warning(
                                        "[ROUTER] ⏳ [BACKPRESSURE] Ollama global slots full, skipping node %s (no CB penalty)",
                                        node["name"],
                                    )
                                    try:
                                        _OLLAMA_BP_SKIPS.inc()
                                    except Exception:
                                        pass
                                    continue  # skip to MLX or next retry — NOT a CB failure
                                _ollama_slot_acquired = True
                            except Exception as _sem_err:
                                logger.debug(
                                    "[ROUTER] Ollama slot acquire error (%s), proceeding", _sem_err
                                )
                                _ollama_slot_acquired = True  # fail-open

                        # МОНСТР-ЛОГИКА: Если форсирован локальный роутинг или это REASONING/VIP, или используется тяжелая модель, используем стриминг для предотвращения ReadTimeout
                        is_heavy_model = any(
                            heavy in str(model).lower()
                            for heavy in [
                                "32b",
                                "30b",
                                "70b",
                                "104b",
                                "qwq",
                                "victoria-wisdom-v3.5",
                            ]
                        )
                        # [SINGULARITY 25.0] try/finally: release Ollama slot after HTTP call (streaming OR non-streaming)
                        try:
                            if (
                                getattr(self, "force_local", False)
                                or category in ("reasoning", "vip")
                                or is_heavy_model
                            ):
                                logger.info(
                                    f"🚀 [STREAMING] Использование стриминга для поддержания соединения (Heartbeat) [Model: {model}, Category: {category}]..."
                                )
                                full_response = []

                                # Включаем стриминг в полезной нагрузке
                                payload["stream"] = True
                                # Таймаут стриминга: read до 30 мин (первый токен у 35B+ может быть долгим), connect 60 с
                                _stream_timeout = float(
                                    os.getenv("LOCAL_ROUTER_STREAM_READ_TIMEOUT", "1800")
                                )
                                _stream_connect = float(
                                    os.getenv("LOCAL_ROUTER_STREAM_CONNECT_TIMEOUT", "60")
                                )

                                # [SINGULARITY 21.5] Predictive Warmup logic moved up
                                _streaming_error_text = (
                                    ""  # Will be set if streaming returns error status
                                )

                                async with client.stream(
                                    "POST",
                                    node_url,
                                    json=payload,
                                    headers=headers,
                                    timeout=httpx.Timeout(_stream_timeout, connect=_stream_connect),
                                ) as response:
                                    if response.status_code == 200:
                                        first_token_time = None
                                        token_times = []
                                        chunk_count = 0

                                        async for line in response.aiter_lines():
                                            if not line:
                                                continue
                                            try:
                                                chunk = json.loads(line)
                                                now = time.time()
                                                if first_token_time is None:
                                                    first_token_time = now
                                                else:
                                                    token_times.append(now)

                                                # Обработка разных форматов Ollama/MLX
                                                if "message" in chunk:
                                                    content = chunk["message"].get("content", "")
                                                elif "response" in chunk:
                                                    content = chunk.get("response", "")
                                                else:
                                                    content = ""

                                                if content:
                                                    full_response.append(content)
                                                    chunk_count += 1

                                                if chunk.get("done"):
                                                    break
                                            except (json.JSONDecodeError, KeyError, Exception):
                                                continue

                                        result = "".join(full_response)

                                        # Report metrics to MLXMonitor
                                        if is_mlx and first_token_time:
                                            ttft = first_token_time - request_start
                                            tbt = 0.0
                                            if len(token_times) > 1:
                                                # Calculate average TBT
                                                diffs = [
                                                    token_times[i] - token_times[i - 1]
                                                    for i in range(1, len(token_times))
                                                ]
                                                if not diffs:  # Only one token after first
                                                    diffs = [token_times[0] - first_token_time]
                                                tbt = sum(diffs) / len(diffs)

                                            total_duration = time.time() - request_start
                                            tps = (
                                                chunk_count / total_duration
                                                if total_duration > 0
                                                else 0
                                            )

                                            get_mlx_monitor().report_metrics(
                                                ttft=ttft, tbt=tbt, tps=tps
                                            )

                                        # Создаем фиктивный объект ответа для совместимости с кодом ниже
                                        class MockResponse:
                                            def __init__(self, text, status_code):
                                                self.text = text
                                                self.status_code = status_code

                                            def json(self):
                                                return {"message": {"content": self.text}}

                                        response = MockResponse(result, 200)
                                    else:
                                        # Если ошибка — считываем текст ошибки
                                        error_text = await response.aread()
                                        _streaming_error_text = (
                                            error_text.decode("utf-8", errors="replace")
                                            if error_text
                                            else ""
                                        )
                                        is_queue_full_503_stream = (
                                            is_ollama
                                            and response.status_code == 503
                                            and "maximum pending requests exceeded"
                                            in _streaming_error_text.lower()
                                        )
                                        if is_queue_full_503_stream:
                                            logger.warning(
                                                "Streaming backpressure from %s (%s): %s",
                                                node.get("name"),
                                                response.status_code,
                                                _streaming_error_text[:200],
                                            )
                                        else:
                                            logger.error(
                                                f"Streaming error: {response.status_code}: {_streaming_error_text[:200]}"
                                            )
                            else:
                                # [SINGULARITY 21.5] Predictive Warmup logic moved up

                                # Обычный запрос для легких задач
                                response = await client.post(
                                    node_url,
                                    json=payload,
                                    headers=headers,
                                    timeout=httpx.Timeout(_node_timeout, connect=30.0),
                                )
                        finally:
                            # Release global Ollama slot regardless of outcome (success or exception)
                            if _ollama_slot_acquired and is_ollama:
                                try:
                                    from redis_manager import RedisManager as _RM2

                                    await _RM2().release_ollama_slot()
                                    _ollama_slot_acquired = False
                                except Exception as _rel_err:
                                    logger.debug(
                                        "[ROUTER] Ollama slot release error (%s), ignoring",
                                        _rel_err,
                                    )
                        latency_ms = (time.time() - request_start) * 1000

                        # Load Balancing: обновляем метрики загрузки
                        if get_load_balancer:
                            load_balancer = get_load_balancer()
                            load_balancer.update_node_load(
                                node["name"],
                                node.get("routing_key", ""),
                                latency_ms / 1000.0,  # Конвертируем в секунды
                                success=(response.status_code == 200),
                            )
                            load_balancer.end_request(node.get("routing_key", ""))

                        logger.info(
                            "[ROUTER] HTTP response status: %d from %s",
                            response.status_code,
                            node["name"],
                        )

                        if response.status_code == 200:
                            if is_mlx:
                                get_mlx_monitor().record_success()

                            # [SINGULARITY 21.10] Record success for node breaker
                            if breaker:
                                breaker._on_success()
                            result_data = response.json()
                            # Обрабатываем разные форматы ответов
                            if "message" in result_data:
                                # Формат /api/chat
                                result = result_data["message"].get("content", "")
                                logger.info(
                                    "[ROUTER] Response format: /api/chat, content length: %d",
                                    len(result),
                                )
                            elif "response" in result_data:
                                # Формат /api/generate
                                result = result_data.get("response", "")
                                logger.info(
                                    "[ROUTER] Response format: /api/generate, content length: %d",
                                    len(result),
                                )
                            else:
                                result = str(result_data)
                                logger.info(
                                    "[ROUTER] Response format: unknown, raw data length: %d",
                                    len(result),
                                )

                            result = result if isinstance(result, str) else str(result)
                            logger.info(
                                "[ROUTER] Response preview: %s...",
                                result[:200] if result else "(empty)",
                            )

                            # Защита от эхо: если сервер/модель вернула промпт как ответ — не считаем успехом, пробуем следующий узел
                            if result and self._is_echo_response(result, prompt):
                                logger.warning(
                                    "[ROUTER] ⚠️ Эхо-ответ от %s (модель вернула промпт), пробуем следующий узел",
                                    node["name"],
                                )
                                continue

                            if result:
                                routing_source = node.get("routing_key", "ollama_studio")
                                performance_score = node.get("performance_score", 0.8)
                                logger.info(
                                    "[ROUTER] ✅ [SUCCESS] Node: %s, Model: %s, Latency: %.2fms, Performance: %.2f",
                                    node["name"],
                                    model,
                                    latency_ms,
                                    performance_score,
                                )

                                # Отмечаем использование модели для менеджера памяти
                                if (
                                    self._memory_manager
                                    and node.get("routing_key") == "local_server"
                                    and model
                                ):
                                    await self._memory_manager.mark_model_used(model)

                                # Сохраняем решение роутера для обучения ML
                                if get_collector:
                                    collector = await get_collector()
                                    await collector.collect_routing_decision(
                                        task_type=task_type,
                                        prompt_length=len(prompt),
                                        category=category,
                                        selected_route=routing_source,
                                        performance_score=performance_score,
                                        latency_ms=latency_ms,
                                        success=True,
                                        features={
                                            "model": model,
                                            "node_name": node["name"],
                                            "node_priority": node.get("priority", 0),
                                            "attempt": attempt + 1,
                                        },
                                    )

                                # Сохраняем информацию об использованной модели для отслеживания
                                # Это будет использовано в worker'е для записи производительности
                                if hasattr(self, "_current_task_id"):
                                    try:
                                        from model_performance_tracker import (
                                            get_performance_tracker,
                                        )

                                        tracker = get_performance_tracker()
                                        # Сохраняем в metadata задачи (будет использовано в worker'е)
                                        self._used_model = model
                                    except Exception:
                                        pass

                                # Сохраняем в кэш при успехе (короткий ответ)
                                if prompt_cache_key and len(result) < 5000:
                                    self._evict_prompt_cache_if_needed()
                                    self._prompt_cache[prompt_cache_key] = (
                                        str(result),
                                        str(routing_source),
                                    )
                                    self._prompt_cache_meta[prompt_cache_key] = time.time()
                                # Return (response, routing_source) tuple

                                # [SINGULARITY 21.2] Victoria Efficiency: Record tokens for local provider
                                try:
                                    in_tokens = len(prompt) // 4
                                    out_tokens = len(str(result)) // 4
                                    record_llm_request(
                                        provider="local",
                                        model=model or "unknown",
                                        input_tokens=in_tokens,
                                        output_tokens=out_tokens,
                                    )
                                except Exception as metrics_err:
                                    logger.debug(f"Failed to record local metrics: {metrics_err}")

                                # [SINGULARITY 30.6] Heavyweight Semaphore Release
                                if is_heavy:
                                    try:
                                        from app.services.blackboard_service import (
                                            get_blackboard_service,
                                        )

                                        blackboard = get_blackboard_service()
                                        await blackboard.release_heavy_model_lock(model)
                                    except Exception as e:
                                        logger.warning(f"⚠️ [HEAVY-LOCK] Error releasing lock: {e}")

                                return result, routing_source
                            else:
                                logger.warning(
                                    "[ROUTER] ⚠️ Node %s returned empty response for model %s. Retrying next node...",
                                    node["name"],
                                    model,
                                )
                                # [SINGULARITY 23.9] Force retry on empty response
                                if breaker:
                                    breaker._on_failure("EmptyResponse")
                                continue
                        else:
                            # [FIX] 503 from Ollama = "server busy" (not broken) → do NOT open CB
                            # 503 means the queue is full or model loading, NOT a real failure.
                            # Real failures are: 500, 502, 504, connection errors, timeouts.
                            is_queue_full_503 = response.status_code == 503 and is_ollama
                            if breaker and not is_queue_full_503:
                                breaker._on_failure(f"HTTP {response.status_code}")

                            # Log error response body for debugging
                            try:
                                error_text = response.text[:500]
                                if is_queue_full_503:
                                    logger.warning(
                                        "[ROUTER] ⏳ Node %s busy (queue full), skipping CB failure. Retrying...",
                                        node["name"],
                                    )
                                else:
                                    logger.error(
                                        "[ROUTER] ❌ Node %s returned HTTP %d: %s",
                                        node["name"],
                                        response.status_code,
                                        error_text,
                                    )
                            except Exception:
                                logger.error(
                                    "[ROUTER] ❌ Node %s returned HTTP %d",
                                    node["name"],
                                    response.status_code,
                                )
                except asyncio.TimeoutError:
                    if is_mlx:
                        get_mlx_monitor().record_failure()

                    # [SINGULARITY 21.10] Record failure for node breaker
                    if breaker:
                        breaker._on_failure("TimeoutError")
                    logger.warning(
                        "[ROUTER] ⏱️ Timeout: Node %s, Model %s (attempt %d/%d)",
                        node["name"],
                        model,
                        attempt + 1,
                        max_retries + 1,
                    )
                    if attempt < max_retries:
                        # [SINGULARITY 25.0] Jittered exponential backoff
                        import random

                        delay = (2**attempt) + random.uniform(0, 1)
                        await asyncio.sleep(delay)
                    continue
                except httpx.ConnectError as e:
                    if is_mlx:
                        get_mlx_monitor().record_failure()

                    # [SINGULARITY 21.10] Record failure for node breaker
                    if breaker:
                        breaker._on_failure(f"ConnectError: {e}")
                    logger.error("[ROUTER] ❌ Connection failed to %s: %s", node_url, e)
                    if attempt < max_retries:
                        # [SINGULARITY 25.0] Jittered exponential backoff
                        import random

                        delay = (2**attempt) + random.uniform(0, 1)
                        await asyncio.sleep(delay)
                    continue
                except Exception as e:
                    # [SINGULARITY 21.10] Record failure for node breaker
                    if breaker:
                        breaker._on_failure(f"{type(e).__name__}: {e}")

                    logger.error(
                        "[ROUTER] ❌ Exception calling Node %s: %s: %s",
                        node["name"],
                        type(e).__name__,
                        e,
                    )
                    if attempt < max_retries:
                        # [SINGULARITY 25.0] Jittered exponential backoff
                        import random

                        delay = (2**attempt) + random.uniform(0, 1)
                        await asyncio.sleep(delay)
                    continue

            # If we exhausted retries for this node, try next
            logger.warning(
                f"⚠️ Node {node['name']} failed after {max_retries + 1} attempts, trying next..."
            )

        # Все узлы не сработали - сохраняем неудачное решение
        total_latency = (time.time() - start_time) * 1000
        if get_collector:
            collector = await get_collector()
            await collector.collect_routing_decision(
                task_type=task_type,
                prompt_length=len(prompt),
                category=category,
                selected_route="cloud",  # Fallback в облако
                latency_ms=total_latency,
                success=False,
                features={"reason": "all_nodes_failed"},
            )

        return None, None

    async def run_local_llm_streaming(
        self,
        prompt: str,
        system_prompt: str = "",
        category: Optional[str] = None,
        images: Optional[list] = None,
        model: Optional[str] = None,
        is_vip: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Call local LLM with streaming support.
        Returns AsyncGenerator that yields response chunks.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            category: Task category
            images: List of images (for vision models)
            model: Specific model to use (if None, selected automatically)
            is_vip: If True, request goes through VIP corridor

        Yields:
            Response chunks as strings
        """
        # VIP-коридор: форсируем категорию
        if is_vip:
            category = "vip"
            logger.info("🌟 [VIP STREAM] Запрос через VIP-коридор")

        # Select model
        if model is None:
            model = self._select_model(prompt, category)
        if images and MODEL_MAP.get("vision"):
            model = MODEL_MAP["vision"]

        # Discover healthy nodes
        healthy_nodes = await self.check_health()
        if not healthy_nodes:
            logger.error("❌ [STREAMING] No healthy local nodes found!")
            return

        # Select best node
        # Для VIP/Reasoning задач в стриминге тоже предпочитаем MLX если он есть
        node = None
        if category == "reasoning" or is_vip:
            mlx_nodes = [
                n for n in healthy_nodes if "11435" in n["url"] or "mlx" in n["url"].lower()
            ]
            if mlx_nodes:
                # [SINGULARITY 21.10] MLX Admission Control for streaming
                try:
                    import psutil

                    ram = psutil.virtual_memory()
                    reserve_bytes = MLX_RAM_RESERVE_GB * 1024**3
                    if ram.available >= reserve_bytes:
                        node = mlx_nodes[0]
                        logger.info(f"🎯 [VIP STREAM] Выбран MLX узел: {node['name']}")
                    else:
                        logger.warning(
                            "🧠 [ADMISSION CONTROL] MLX skipped for streaming to save brain!"
                        )
                except:
                    pass

        if not node:
            # [SINGULARITY 21.10] Filter out OPEN nodes from streaming candidates
            available_nodes = []
            for n in healthy_nodes:
                breaker = self._node_breakers.get(n["url"])
                if breaker and breaker.state == CircuitState.OPEN:
                    if not breaker._should_attempt_reset():
                        continue
                available_nodes.append(n)

            if not available_nodes:
                logger.error("❌ [STREAMING] All nodes are OPEN or unavailable!")
                return

            node = available_nodes[0]

        node_url = f"{node['url']}/api/generate"
        logger.info(f"🌊 [STREAMING] Node: {node['name']} | Model: {model}")

        full_prompt = f"{system_prompt}\n\nUser: {prompt}\nAssistant:"
        payload = {"model": model, "prompt": full_prompt, "stream": True}
        if self._should_disable_thinking(model):
            payload["think"] = False
        # [SINGULARITY 24.8] Adaptive Context Window
        payload["options"] = self._get_adaptive_options(model)

        mlx_alive = any(
            "mlx" in n["url"].lower() or "mlx" in n.get("routing_key", "").lower()
            for n in healthy_nodes
        )
        payload["keep_alive"] = get_keep_alive(model, mlx_alive=mlx_alive)
        if images:
            payload["images"] = images

        # VIP Header — только живой диалог (is_vip=True), воркеры идут на medium
        headers = {}
        if is_vip:
            headers["X-Request-Priority"] = "high"
            logger.info(
                f"🌟 [VIP HEADER] User dialogue streaming → high priority for {category or model}"
            )
        elif category == "reasoning":
            headers["X-Request-Priority"] = "medium"

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST", node_url, json=payload, headers=headers
                ) as response:
                    if response.status_code != 200:
                        # [SINGULARITY 21.10] Record failure for node breaker
                        breaker = self._node_breakers.get(node["url"])
                        if breaker:
                            breaker._on_failure(f"HTTP {response.status_code}")

                        logger.error(f"❌ [STREAMING] Error: {response.status_code}")
                        return

                    # [SINGULARITY 21.10] Record success for node breaker
                    breaker = self._node_breakers.get(node["url"])
                    if breaker:
                        breaker._on_success()

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        try:
                            chunk_data = json.loads(line)
                            if "response" in chunk_data:
                                yield chunk_data["response"]
                            if chunk_data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            # [SINGULARITY 21.10] Record failure for node breaker
            breaker = self._node_breakers.get(node["url"])
            if breaker:
                breaker._on_failure(f"StreamException: {e}")

            logger.error(f"❌ [STREAMING] Error: {e}")
            return

    def _get_adaptive_options(self, model_name: str) -> Dict:
        """
        [SINGULARITY 24.9] Adaptive Context Window — NUM_PARALLEL-aware.

        КРИТИЧНО: OLLAMA_NUM_PARALLEL=6 → Ollama pre-allocates KV cache for ALL 6 slots per model.
        Формула: total_vram = num_parallel × kv_cache(num_ctx) + model_weights
        При num_ctx=32768 × 6 parallel → phi3.5 = 47GB, victoria = 50GB → OOM → 503 → CB OPEN.
        При num_ctx=16384 × 6 parallel → phi3.5 = 21GB, victoria = 40GB → 128GB RAM → OK.
        """
        options = {}
        try:
            # SAFE CONTEXT: 32768 is safe for Qwen3.5-35B-A3B on 128GB Mac Studio.
            # Qwen3.5-35B-A3B uses only 2 KV heads (GQA) + head_dim=256 + 40 layers →
            # KV per slot: 2 × 40 × 2 × 256 × 2 = 82KB/token → 2.7GB at 32K × 6 slots = 16GB
            # Model weights Q4_K_M: ~21GB + KV 16GB + compute 6GB → ~43GB total → 128GB OK.
            SAFE_MAX_CTX = 32768

            model_lower = model_name.lower()
            if "tinyllama" in model_lower or "moondream" in model_lower or "nomic" in model_lower:
                options["num_ctx"] = 4096  # Small models need only small context
            elif "phi3.5" in model_lower or "phi3" in model_lower:
                # §53 библии: phi3.5 immortal с адаптивным контекстом 16384.
                # С OLLAMA_NUM_PARALLEL=6: 6 × 3.5GB KV = 21GB + 2GB weights = 23GB → на 128GB OK.
                options["num_ctx"] = 16384
            else:
                options["num_ctx"] = SAFE_MAX_CTX

            import psutil

            ram = psutil.virtual_memory()
            available_gb = ram.available / (1024**3)

            logger.info(
                f"🧠 [ADAPTIVE CONTEXT] Model: {model_name} | RAM Available: {available_gb:.1f}GB | Selected num_ctx: {options['num_ctx']}"
            )
        except Exception as e:
            logger.debug(f"Failed to calculate adaptive context: {e}")

        return options

    @staticmethod
    def _should_disable_thinking(model_name: Optional[str]) -> bool:
        if not model_name:
            return False
        lowered = model_name.lower()
        # Victoria aliases are now backed by Qwen 3.6 and should also suppress thinking traces.
        return "qwen3" in lowered or "victoria-wisdom-v3.5" in lowered

    def _determine_task_type(self, prompt: str, category: Optional[str] = None) -> str:
        """Определяет тип задачи для сбора данных"""
        prompt_lower = prompt.lower()

        if category == "coding" or "код" in prompt_lower or "программируй" in prompt_lower:
            return "coding"
        elif category == "reasoning" or "подумай" in prompt_lower or "логика" in prompt_lower:
            return "reasoning"
        else:
            return "general"

    async def _trigger_predictive_warmup(
        self, model_name: str, node_url: str, history: Optional[list] = None
    ):
        """Упреждающий прогрев модели в Ollama на случай падения MLX, включая KV-Cache."""
        try:
            # Если есть история, используем её для прогрева KV-Cache
            prompt = " "
            if history:
                # Берем последние 2-3 сообщения для прогрева контекста
                context_slice = history[-3:] if len(history) > 3 else history
                prompt = "\n".join(
                    [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in context_slice]
                )
                prompt += "\nassistant: "

            warmup_payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 1},  # Минимальная генерация только для прогрева
            }
            if self._should_disable_thinking(model_name):
                warmup_payload["think"] = False

            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"{node_url}/api/generate", json=warmup_payload)
            logger.info(
                "🔥 [WARMUP] Triggered KV-Cache warmup for %s in Ollama (context len: %d)",
                model_name,
                len(history) if history else 0,
            )
        except Exception as e:
            logger.debug("Predictive warmup failed for %s: %s", model_name, e)
