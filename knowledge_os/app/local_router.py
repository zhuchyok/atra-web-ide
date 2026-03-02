import asyncio
import hashlib
import json
import logging
import os
import time
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

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
        def record_llm_request(*args, **kwargs): pass

logger = logging.getLogger(__name__)

# Debug mode: VICTORIA_DEBUG=true enables verbose logging
VICTORIA_DEBUG = os.getenv("VICTORIA_DEBUG", "false").lower() in ("true", "1", "yes")
if VICTORIA_DEBUG:
    logger.setLevel(logging.DEBUG)
    logging.getLogger().setLevel(logging.DEBUG)

# Config - Mac Studio (локальная обработка). OLLAMA_BASE_URL используется Victoria/Veronica
_is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
_default_ollama = 'http://host.docker.internal:11434' if _is_docker else 'http://localhost:11434'
def _valid_http_url(url: str) -> bool:
    """True если url — валидный http(s) URL (не 'disabled' и не пустой)."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip().lower()
    return u.startswith("http://") or u.startswith("https://")


OLLAMA_API_URL = os.getenv('OLLAMA_API_URL') or os.getenv('OLLAMA_BASE_URL') or os.getenv('SERVER_LLM_URL') or _default_ollama
_raw_mlx = os.getenv('MLX_API_URL') or os.getenv('MAC_LLM_URL') or ('http://host.docker.internal:11435' if _is_docker else 'http://localhost:11435')
MLX_API_URL = _raw_mlx if _valid_http_url(_raw_mlx) else None  # MLX_API_URL=disabled → None, только Ollama


# [SINGULARITY 21.3] God Mode 128GB: Immortal models and zero-swap
IMMORTAL_MODELS = {
    "nomic-embed-text",
    "nomic-embed-text:latest",
    "victoria-wisdom-30b",
    "victoria-wisdom-30b:latest",
    "moondream",
    "moondream:latest"
}
SWAP_THRESHOLD = float(os.getenv("SWAP_THRESHOLD", "0"))
RAM_RESERVE_GB = float(os.getenv("RAM_RESERVE_GB", "18"))

def _get_keep_alive(model_name: Optional[str] = None):
    """
    Ollama keep_alive из env или адаптивный расчет.
    God Mode: -1 (всегда в памяти) для бессмертных моделей.
    """
    # 1. Проверяем явные настройки в env
    raw = os.getenv("VICTORIA_OLLAMA_KEEP_ALIVE") or os.getenv("OLLAMA_KEEP_ALIVE")
    if raw == "-1":
        return -1

    if model_name and any(m in model_name for m in IMMORTAL_MODELS):
        return -1

    if raw:
        try:
            return int(raw) if str(raw).strip().lstrip("-").isdigit() else raw
        except (ValueError, AttributeError):
            return raw

    # 2. Адаптивная логика если имя модели известно
    if model_name:
        try:
            # Пытаемся получить размер из кэша сканера
            from available_models_scanner import _scan_cache
            if _scan_cache and "ollama_sizes" in _scan_cache:
                size_bytes = _scan_cache["ollama_sizes"].get(model_name, 0)
                if size_bytes > 0:
                    size_gb = size_bytes / (1024**3)
                    # [SINGULARITY 21.3] Агрессивная выгрузка тяжелых моделей при нехватке памяти
                    try:
                        import psutil
                        ram_percent = psutil.virtual_memory().percent
                        if ram_percent > 80:
                            if size_gb > 15: return 60  # 1 мин для тяжелых при RAM > 80%
                            if size_gb > 5: return 300  # 5 мин для средних
                    except ImportError:
                        pass

                    if size_gb > 30: return 60
                    if size_gb > 15: return 300
                    if size_gb > 5: return 600
                    return 3600
        except Exception:
            pass

        # Fallback на эвристику по имени
        key = model_name.lower()
        if "70b" in key or "104b" in key or "next" in key: return 60
        if "32b" in key or "30b" in key or "qwq" in key: return 300
        if "7b" in key or "8b" in key or "14b" in key: return 600
        if "3b" in key or "1b" in key or "tiny" in key or "embedding" in key: return 3600

    return 300  # Дефолт 5 мин
# Обратная совместимость (legacy)
MAC_LLM_URL = MLX_API_URL
SERVER_LLM_URL = OLLAMA_API_URL
USE_LOCAL_LLM = os.getenv('USE_LOCAL_LLM', 'true').lower() == 'true'
DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

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

# Fallback модели (используются если scanner недоступен).
# MLX: только лёгкие — 70b/104b/32b удалены (Metal/память); не подставлять удалённые.
MLX_MODELS_FALLBACK = {
    "reasoning": "phi3.5:3.8b",
    "coding": "phi3.5:3.8b",
    "chat": "phi3.5:3.8b",
    "fast": "phi3.5:3.8b",
    "default": "phi3.5:3.8b",
}

# Мозг и руки — victoria-wisdom-30b.
OLLAMA_MODELS_FALLBACK = {
    "reasoning": os.getenv("MODEL_REASONING", "deepseek-r1:32b"),
    "coding": os.getenv("MODEL_CODER", "qwen3.5:35b"),
    "chat": "victoria-wisdom-30b",
    "fast": os.getenv("MODEL_FAST", "tinyllama:1.1b-chat"),
    "vision": os.getenv("MODEL_VISION", "moondream:latest"),
    "vision_hd": "minicpm-v:latest",
    "thinking": os.getenv("MODEL_THINKING", "lfm2.5-thinking:1.2b"),
    "default": "victoria-wisdom-30b",
    "vip": "victoria-wisdom-30b"
}

# Для обратной совместимости
MLX_MODELS = MLX_MODELS_FALLBACK
OLLAMA_MODELS = OLLAMA_MODELS_FALLBACK

# Legacy MODEL_MAP для обратной совместимости
MODEL_MAP = {
    "coding": os.getenv('MODEL_CODING', OLLAMA_MODELS["coding"]),
    "reasoning": os.getenv('MODEL_REASONING', MLX_MODELS["reasoning"]),
    "fast": "tinyllama:1.1b-chat",
    "vision": OLLAMA_MODELS["vision"],
    "vision_pdf": OLLAMA_MODELS["vision_pdf"],
    "default": os.getenv('MODEL_DEFAULT', OLLAMA_MODELS["default"])
}

# List of task categories that can be handled locally (L1)
LOCAL_TASK_CATEGORIES = [
    "code_audit",
    "log_analysis",
    "unit_test_generation",
    "text_summarization",
    "simple_query",
    "grammar_correction",
    "logic_check"
]


class LocalAIRouter:
    def __init__(self):
        self.use_local = USE_LOCAL_LLM
        is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
        # Используем URL из env (docker-compose). MLX_API_URL=disabled → только Ollama (не добавляем MLX node)
        ollama_url = OLLAMA_API_URL or ("http://host.docker.internal:11434" if is_docker else "http://localhost:11434")
        if not _valid_http_url(ollama_url):
            ollama_url = "http://host.docker.internal:11434" if is_docker else "http://localhost:11434"
        mlx_url = MLX_API_URL or ("http://host.docker.internal:11435" if is_docker else "http://localhost:11435")
        self.nodes = []
        if _valid_http_url(mlx_url):
            self.nodes.append({"name": "Mac Studio (MLX)", "url": mlx_url, "priority": 0, "routing_key": "mlx_studio"})
        self.nodes.append({"name": "Mac Studio (Ollama)", "url": ollama_url, "priority": 1, "routing_key": "ollama_studio"})
        self._active_node = None
        self._performance_cache = {}  # Cache for node performance metrics
        self._cache_ttl = 300  # 5 minutes

        # ML Model for intelligent routing
        self.ml_model = None
        self.ml_model_path = os.path.join(os.path.dirname(__file__), 'ml_router_model.pkl')
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
        expired = [k for k, ts in self._prompt_cache_meta.items() if (now - ts) >= self._prompt_cache_ttl]
        for k in expired:
            self._prompt_cache.pop(k, None)
            self._prompt_cache_meta.pop(k, None)
        if len(self._prompt_cache) >= self._prompt_cache_max:
            # Удаляем самые старые по timestamp
            sorted_keys = sorted(self._prompt_cache_meta.keys(), key=lambda x: self._prompt_cache_meta[x])
            for k in sorted_keys[: max(0, len(self._prompt_cache) - self._prompt_cache_max + 1)]:
                self._prompt_cache.pop(k, None)
                self._prompt_cache_meta.pop(k, None)

    _cached_ml_model = None  # класс-уровень: один экземпляр на процесс (переиспользование при множестве LocalAIRouter)
    _cached_ml_model_path = None

    def _load_ml_model(self):
        """Загружает ML-модель если доступна. Переиспользует кэш на уровне класса (один раз на процесс)."""
        if MLRouterModel and os.path.exists(self.ml_model_path):
            if LocalAIRouter._cached_ml_model_path == self.ml_model_path and LocalAIRouter._cached_ml_model is not None:
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

    async def predict_optimal_route(
        self,
        prompt: str,
        category: Optional[str] = None
    ) -> tuple:
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
                node_metrics=node_metrics
            )

            logger.info(f"🤖 [ML ROUTER] Predicted route: {predicted_route} (confidence: {confidence:.2f})")
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
                            healthy_nodes.append({
                                **node,
                                "latency": latency,
                                "status": "online"
                            })
                            continue  # Успешно, переходим к следующему узлу
                    except Exception:
                        pass  # /health недоступен, пробуем /api/tags

                    # Fallback на /api/tags (если /health недоступен)
                    response = await client.get(f"{node['url']}/api/tags", timeout=2.0)
                    latency = time.time() - start_time
                    if response.status_code == 200:
                        healthy_nodes.append({
                            **node,
                            "latency": latency,
                            "status": "online"
                        })
                except Exception as e:
                    logger.warning(f"⚠️ Node {node['name']} is offline: {e}")

        # Не кэшируем пустой результат — следующая попытка сразу перепроверит
        if not healthy_nodes:
            logger.warning("⚠️ [HEALTH] Нет здоровых узлов, не кэшируем (повторная проверка при следующем запросе)")
            return []

        # Get performance metrics from cache for each node
        performance_metrics = await self._get_node_performance_metrics()

        # Enhance nodes with performance data
        for node in healthy_nodes:
            routing_key = node.get('routing_key', '')
            if routing_key in performance_metrics:
                node['performance_score'] = performance_metrics[routing_key].get('avg_performance', 0.8)
                node['success_rate'] = performance_metrics[routing_key].get('success_rate', 0.9)
            else:
                node['performance_score'] = 0.8  # Default
                node['success_rate'] = 0.9  # Default

        # Sort by: performance_score (higher is better), then priority, then latency
        sorted_nodes = sorted(
            healthy_nodes,
            key=lambda x: (-x.get('performance_score', 0.8), x['priority'], x['latency'])
        )

        # Update cache
        _health_cache = {"nodes": sorted_nodes, "timestamp": current_time}

        return sorted_nodes

    async def _get_node_performance_metrics(self) -> Dict:
        """Получение метрик производительности узлов из semantic_ai_cache"""
        try:
            # Check cache first
            current_time = time.time()
            if hasattr(self, '_performance_cache') and self._performance_cache:
                cache_time = self._performance_cache.get('timestamp', 0)
                if (current_time - cache_time) < self._cache_ttl:
                    return self._performance_cache.get('metrics', {})

            # Try to connect to DB
            try:
                conn = await asyncpg.connect(DB_URL, timeout=2)
            except (asyncpg.PostgresError, OSError, ValueError):
                return {}

            try:
                # Check if columns exist
                columns_exist = await conn.fetchval("""
                    SELECT COUNT(*) FROM information_schema.columns 
                    WHERE table_name = 'semantic_ai_cache' 
                    AND column_name IN ('routing_source', 'performance_score')
                """) == 2

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
                    routing_key = row['routing_source']
                    total = row['total_requests'] or 0
                    successful = row['successful_requests'] or 0
                    result[routing_key] = {
                        'avg_performance': float(row['avg_performance'] or 0.8),
                        'success_rate': (successful / total) if total > 0 else 0.9,
                        'total_requests': total
                    }

                await conn.close()

                # Update cache
                self._performance_cache = {
                    'metrics': result,
                    'timestamp': current_time
                }

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
        complex_keywords = ["подумай", "логика", "архитектура", "стратегия", "анализ", "планирование"]
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
                mlx_models, ollama_models = await get_available_models(mlx_url, ollama_url, force_refresh=force)
                _cached_mlx_models = mlx_models
                _cached_ollama_models = ollama_models
                _models_cache_time = now
                logger.info(f"🔄 [MODEL SCAN] Обновлены модели: MLX={len(mlx_models)}, Ollama={len(ollama_models)}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка сканирования моделей: {e}, используем fallback")

    def _select_model(self, prompt: str, category: Optional[str] = None, use_ollama: bool = False, node_type: Optional[str] = None) -> str:
        """Select the best local model for the task.
        
        ДИНАМИЧЕСКИЙ ВЫБОР: Если available_models_scanner доступен, выбирает из реально доступных моделей.
        Если модель удалена/добавлена, система автоматически адаптируется (кэш обновляется каждые 2 мин).
        
        Args:
            prompt: User prompt
            category: Task category
            use_ollama: If True, use Ollama models (deprecated)
            node_type: Тип узла ('mlx' или 'ollama') - для выбора подходящей модели
        """
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
                stats.get("active_requests", 0) >= stats.get("max_concurrent", 5) or
                stats.get("queue_size", 0) > 0
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

    def should_use_local(self, prompt: str, category: Optional[str] = None, images: Optional[list] = None) -> bool:
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
        if category in ("autonomous_worker", "orchestrator", "general", "research", "reasoning", "coding", "fast"):
            return True

        # Heuristic based on prompt content
        prompt_lower = prompt.lower()
        if any(keyword in prompt_lower for keyword in ["анализ логов", "проверь код", "напиши тест", "суммаризируй", "исправь опечатку"]):
            return True

        # If the prompt is very large (context-heavy) and doesn't require high-level reasoning
        if len(prompt) > 2000 and "архитектура" not in prompt_lower and "стратегия" not in prompt_lower:
            return True

        # По умолчанию для неизвестных категорий — всё равно пробуем локальные модели (приоритет корпорации)
        if category is not None:
            return True

        return False

    async def run_local_llm(self, prompt: str, system_prompt: str = "", category: Optional[str] = None, images: Optional[list] = None, max_retries: int = 2, model: Optional[str] = None, model_hint: Optional[str] = None, is_vip: bool = False) -> Optional[tuple]:
        """
        Запускает локальную LLM модель.
        Приоритет: MLX API Server (HTTP) и Ollama — оба используются (балансировка).
        model: если задан — используем эту модель и перебираем узлы (MLX/Ollama) пока один не ответит.
        model_hint: подсказка для выбора модели (для совместимости с ансамблем).
        is_vip: если True, запрос идет через VIP-коридор (приоритет и лучшие модели).
        
        Returns:
            tuple: (response, routing_source)
        """
        # VIP-коридор: форсируем категорию и приоритет
        if is_vip:
            category = "vip"
            logger.info("🌟 [VIP ROUTE] Запрос через VIP-коридор (Иван/Совет)")

        # Используем подсказку, если модель не задана явно
        if model is None and model_hint:
            model = model_hint

        # МОНСТР-ЛОГИКА: Поддержка форсированного локального роутинга
        if getattr(self, 'force_local', False):
            logger.info("🚀 [MONSTER] Форсирован локальный роутинг для этого запроса.")
        logger.info("[ROUTER] ========== LocalAIRouter.run_local_llm() ==========")
        logger.info("[ROUTER] Input model: %s", model)
        logger.info("[ROUTER] Category: %s", category)
        logger.info("[ROUTER] Prompt length: %d chars", len(prompt))
        logger.info("[ROUTER] Prompt preview: %s...", prompt[:150])

        # 🔄 ДИНАМИЧЕСКОЕ ОБНОВЛЕНИЕ СПИСКА МОДЕЛЕЙ (если истёк TTL)
        # Это позволяет подхватывать новые модели и замечать удалённые
        await self._refresh_available_models()

        # ПРИОРИТЕТ: Использовать MLX API Server и Ollama через HTTP роутинг
        # MLX Router напрямую не используется в контейнере (требует модуль mlx)
        # Вместо этого используем MLX API Server через HTTP (уже настроен в nodes)
        """Call local LLM (Ollama style) with automatic failover, retry logic and node selection."""

        # Модель: параметр вызова, или _preferred_model от воркера (батчи по модели — меньше load/unload)
        initial_model = model or getattr(self, '_preferred_model', None)

        if images and MODEL_MAP.get("vision"):
            model = MODEL_MAP["vision"]
            logger.info("[ROUTER] Using vision model: %s", model)
            initial_model = model  # Vision - принудительно

        # Кэш: только для коротких промптов без изображений
        prompt_cache_key = None
        if len(prompt) <= 1000 and not images:
            raw_key = f"{prompt}|{category or ''}|{model or ''}"
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
                logger.info(f"🤖 [ML ROUTER] Using ML prediction: {ml_predicted_route} (confidence: {ml_confidence:.2f})")
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
                logger.warning(f"⚠️ [MEMORY] Критическая нехватка памяти: {available_mb}MB, запускаем очистку...")
                await self._memory_manager.emergency_memory_cleanup()

        # Discover healthy nodes (with caching)
        healthy_nodes = await self.check_health()
        if not healthy_nodes:
            logger.error("❌ No healthy local nodes found!")
            # Сохраняем решение о fallback в облако
            if get_collector:
                collector = await get_collector()
                await collector.collect_routing_decision(
                    task_type=task_type,
                    prompt_length=len(prompt),
                    category=category,
                    selected_route="cloud",  # Fallback в облако
                    success=False,
                    features={"reason": "no_healthy_nodes", "ml_predicted": ml_predicted_route}
                )
            return None

        # УМНЫЙ ВЫБОР УЗЛА: система сама выбирает лучший источник на основе задачи
        # 1. Load Balancing: выбираем лучший узел на основе загрузки (приоритет)
        if get_load_balancer:
            load_balancer = get_load_balancer()
            best_node = load_balancer.select_best_node(healthy_nodes)
            if best_node and best_node != healthy_nodes[0]:
                # Перемещаем лучший узел в начало
                healthy_nodes.remove(best_node)
                healthy_nodes.insert(0, best_node)
                logger.info(f"⚖️ [LOAD BALANCER] Выбран узел: {best_node['name']} на основе загрузки")

        # 2. ML Prediction: если ML предсказал маршрут, учитываем его
        if ml_predicted_route and ml_predicted_route != "cloud":
            # Сортируем узлы, чтобы предсказанный был первым (но после load balancer)
            predicted_node = None
            other_nodes = []
            for node in healthy_nodes:
                if node.get('routing_key') == ml_predicted_route:
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
        mlx_nodes = [n for n in healthy_nodes if "11435" in n['url'] or "mlx" in n['url'].lower()]
        ollama_nodes = [n for n in healthy_nodes if "11434" in n['url'] or "ollama" in n['url'].lower()]
        other_nodes = [n for n in healthy_nodes if n not in mlx_nodes and n not in ollama_nodes]
        # Логируем раз в 5 мин, если MLX недоступен — чтобы было видно, что задачи идут только в Ollama
        if not mlx_nodes and ollama_nodes:
            _t = time.time()
            if not hasattr(LocalAIRouter, "_last_no_mlx_log") or (_t - LocalAIRouter._last_no_mlx_log) > 300:
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
                logger.info(f"⚖️ [BALANCED] Перемешаны узлы для равномерного использования MLX ({len(mlx_nodes)}) и Ollama ({len(ollama_nodes)})")

        # Умный выбор узла на основе задачи и загрузки
        # Система сама выберет лучший источник (MLX или Ollama) на основе:
        # 1. Типа задачи (reasoning → мощная модель, fast → легкая)
        # 2. Загрузки узла (load balancing)
        # 3. Доступности модели
        # 4. Балансировки между MLX и Ollama

        # УЛУЧШЕНИЕ: Если есть предпочтительный источник (из worker'а), пробуем его первым
        preferred_source = getattr(self, '_preferred_source', None)

        # [SINGULARITY 21.3] God Mode: Victoria Brain always prefers MLX
        if model and "victoria-wisdom-30b" in model.lower():
            preferred_source = 'mlx'
            logger.info("🧠 [GOD MODE] Victoria model detected, forcing MLX priority")

        if preferred_source:
            # Перемещаем предпочтительный узел в начало
            preferred_nodes = [n for n in healthy_nodes if
                              (preferred_source == 'mlx' and ("11435" in n['url'] or "mlx" in n['url'].lower())) or
                              (preferred_source == 'ollama' and ("11434" in n['url'] or "ollama" in n['url'].lower()))]
            if preferred_nodes:
                for node in preferred_nodes:
                    if node in healthy_nodes:
                        healthy_nodes.remove(node)
                        healthy_nodes.insert(0, node)
                logger.info(f"🎯 [PREFERRED] Используем предпочтительный источник: {preferred_source}")

        # Try each node with retry logic
        start_time = time.time()
        for node in healthy_nodes:
            # Определяем, это Ollama или MLX API Server
            is_ollama = "11434" in node['url'] or "ollama" in node['url'].lower()
            is_mlx = "11435" in node['url'] or "mlx" in node['url'].lower()

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
                        logger.debug(f"⚠️ Модель {initial_model} не в fallback для {node_type}, выбираем автоматически")
                        current_model = None

            # 2. Если модель не задана или не совместима - выбираем для этого узла
            if not current_model:
                # [SINGULARITY 21.3] Memory Guard 2.1 (God Mode 128GB)
                if is_ollama:
                    try:
                        import psutil
                        ram = psutil.virtual_memory()
                        # В God Mode выгрузка только если RAM реально кончается (запас RAM_RESERVE_GB)
                        if ram.available < (RAM_RESERVE_GB * 1024**3):
                            logger.warning(f"⚠️ [MEMORY GUARD] Low RAM ({ram.available / 1024**3:.1f}GB), cleaning up...")
                            async with httpx.AsyncClient(timeout=5.0) as unload_client:
                                # Выгружаем только если это не VIP и не Reasoning
                                if category not in ("reasoning", "vip") and not is_vip:
                                    # Выгружаем самую тяжелую не-бессмертную модель
                                    await unload_client.post(f"{node['url']}/api/generate", json={"model": "qwen3.5:35b", "keep_alive": 0})
                    except Exception as mem_err:
                        logger.debug(f"Memory cleanup failed: {mem_err}")

                # ВАЖНО: Для REASONING задач ВСЕГДА используем _select_model()
                # Выбор модели по категории (scanner или fallback; MLX только лёгкие)
                if category == "reasoning":
                    current_model = self._select_model(prompt, category, node_type=node_type)
                    logger.info(f"🎯 [REASONING] Узел: {node_type} | Модель: {current_model} (принудительный выбор для reasoning)")
                else:
                    # Используем простой выбор модели по приоритетам (быстрые модели первыми)
                    # Intelligent router отключён — он выбирает тяжёлые модели и перегружает систему
                    use_intelligent = os.getenv('USE_INTELLIGENT_ROUTER', 'false').lower() in ('true', '1', 'yes')
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
                                optimize_mode = os.getenv('INTELLIGENT_ROUTER_OPTIMIZE', 'speed')
                                optimal_model, _task_cat, confidence = await intelligent_router.select_optimal_model(
                                    prompt=prompt,
                                    category=category or "",
                                    available_models=available_models,
                                    optimize_for=optimize_mode
                                )

                                if optimal_model and confidence > 0.5:
                                    current_model = optimal_model
                                    logger.info(f"🧠 [INTELLIGENT ROUTER] Узел: {node_type} | Модель: {current_model} (confidence: {confidence:.2f})")
                                else:
                                    current_model = self._select_model(prompt, category, node_type=node_type)
                            else:
                                current_model = self._select_model(prompt, category, node_type=node_type)
                        except Exception as e:
                            logger.debug(f"Intelligent router failed: {e}, using fallback")
                            current_model = self._select_model(prompt, category, node_type=node_type)
                    else:
                        # Простой выбор по приоритетам (лёгкие модели первыми)
                        current_model = self._select_model(prompt, category, node_type=node_type)

            # Финальная модель для этого узла
            model = current_model
            logger.info(f"🎯 [SMART SELECTION] Узел: {node['name']} | Модель: {model} | Тип задачи: {category or 'auto'}")

            # Используем /api/chat для Ollama (более современный endpoint)
            if is_ollama or is_mlx:
                node_url = f"{node['url']}/api/chat"
                logger.info(f"🏠 [LOCAL ROUTE] Node: {node['name']} | Model: {model} | Endpoint: /api/chat")

                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False
                }
                payload["keep_alive"] = _get_keep_alive(model)
            else:
                # Для других сервисов используем /api/generate
                node_url = f"{node['url']}/api/generate"
                logger.info(f"🏠 [LOCAL ROUTE] Node: {node['name']} | Model: {model} | Endpoint: /api/generate")

                full_prompt = f"{system_prompt}\n\nUser: {prompt}\nAssistant:"
                payload = {
                    "model": model,
                    "prompt": full_prompt,
                    "stream": False
                }
                payload["keep_alive"] = _get_keep_alive(model)
            if images:
                payload["images"] = images

            # Мониторинг ресурсов перед запросом (особенно для MLX)
            if is_mlx:
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
                load_balancer.start_request(node.get('routing_key', ''))

            # Retry logic with exponential backoff
            for attempt in range(max_retries + 1):
                try:
                    async with httpx.AsyncClient() as client:
                        request_start = time.time()
                        headers = {}
                        if category == "reasoning" or is_vip or str(model).lower() == "victoria-wisdom-30b":
                            headers["X-Request-Priority"] = "high"
                            logger.info(f"🌟 [VIP HEADER] Added X-Request-Priority: high for {category or model or 'VIP'}")
                        else:
                            headers["X-Request-Priority"] = "normal"
                        # Таймаут по метрикам этой модели (load/processing с запасом); у каждой модели свои значения
                        _node_timeout = float(os.getenv("LOCAL_ROUTER_LLM_TIMEOUT", "300"))

                        # Увеличиваем таймаут для reasoning задач (Совет, стратегия)
                        if category == "reasoning":
                            _node_timeout = max(_node_timeout, 600.0)
                            logger.info(f"🕒 [REASONING] Увеличен таймаут до {_node_timeout}с")

                        # МОНСТР-ЛОГИКА: Если форсирован локальный роутинг, увеличиваем таймаут до 10 минут
                        if getattr(self, 'force_local', False):
                            _node_timeout = 600.0
                            logger.info("🚀 [MONSTER] Увеличен таймаут HTTP до 600с для форсированного локального роутинга.")

                        try:
                            from app.model_performance_probe import (
                                get_timeout_estimate_from_metrics_dict,
                            )
                            from available_models_scanner import get_model_metrics
                            _source = "ollama" if node.get("routing_key") == "ollama_studio" else "mlx"
                            if model:
                                _m = get_model_metrics(model, _source)
                                if _m:
                                    _node_timeout = get_timeout_estimate_from_metrics_dict(
                                        max_tokens=2048, metrics_dict=_m
                                    )
                        except Exception:
                            pass

                        # МОНСТР-ЛОГИКА: Если форсирован локальный роутинг или это REASONING/VIP, или используется тяжелая модель, используем стриминг для предотвращения ReadTimeout
                        is_heavy_model = any(heavy in str(model).lower() for heavy in ["32b", "30b", "70b", "104b", "qwq"])
                        if getattr(self, 'force_local', False) or category in ("reasoning", "vip") or is_heavy_model:
                            logger.info(f"🚀 [STREAMING] Использование стриминга для поддержания соединения (Heartbeat) [Model: {model}, Category: {category}]...")
                            full_response = []

                            # Включаем стриминг в полезной нагрузке
                            payload["stream"] = True
                            # Таймаут стриминга: read до 20 мин (первый токен у 30B+ может быть 2–5 мин), connect 60 с
                            _stream_timeout = float(os.getenv("LOCAL_ROUTER_STREAM_READ_TIMEOUT", "1200"))
                            _stream_connect = float(os.getenv("LOCAL_ROUTER_STREAM_CONNECT_TIMEOUT", "60"))

                            async with client.stream("POST", node_url, json=payload, headers=headers, timeout=httpx.Timeout(_stream_timeout, connect=_stream_connect)) as response:
                                if response.status_code == 200:
                                    async for line in response.aiter_lines():
                                        if not line: continue
                                        try:
                                            chunk = json.loads(line)
                                            # Обработка разных форматов Ollama/MLX
                                            if "message" in chunk:
                                                content = chunk["message"].get("content", "")
                                            elif "response" in chunk:
                                                content = chunk.get("response", "")
                                            else:
                                                content = ""

                                            if content:
                                                full_response.append(content)

                                            if chunk.get("done"): break
                                        except Exception:
                                            continue

                                    result = "".join(full_response)
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
                                    logger.error(f"Streaming error: {response.status_code}")
                        else:
                            # Обычный запрос для легких задач
                            response = await client.post(
                                node_url,
                                json=payload,
                                headers=headers,
                                timeout=httpx.Timeout(_node_timeout, connect=30.0)
                            )
                        latency_ms = (time.time() - request_start) * 1000

                        # Load Balancing: обновляем метрики загрузки
                        if get_load_balancer:
                            load_balancer = get_load_balancer()
                            load_balancer.update_node_load(
                                node['name'],
                                node.get('routing_key', ''),
                                latency_ms / 1000.0,  # Конвертируем в секунды
                                success=(response.status_code == 200)
                            )
                            load_balancer.end_request(node.get('routing_key', ''))

                        logger.info("[ROUTER] HTTP response status: %d from %s", response.status_code, node['name'])

                        if response.status_code == 200:
                            result_data = response.json()
                            # Обрабатываем разные форматы ответов
                            if "message" in result_data:
                                # Формат /api/chat
                                result = result_data["message"].get("content", "")
                                logger.info("[ROUTER] Response format: /api/chat, content length: %d", len(result))
                            elif "response" in result_data:
                                # Формат /api/generate
                                result = result_data.get("response", "")
                                logger.info("[ROUTER] Response format: /api/generate, content length: %d", len(result))
                            else:
                                result = str(result_data)
                                logger.info("[ROUTER] Response format: unknown, raw data length: %d", len(result))

                            result = result if isinstance(result, str) else str(result)
                            logger.info("[ROUTER] Response preview: %s...", result[:200] if result else "(empty)")

                            # Защита от эхо: если сервер/модель вернула промпт как ответ — не считаем успехом, пробуем следующий узел
                            if result and self._is_echo_response(result, prompt):
                                logger.warning("[ROUTER] ⚠️ Эхо-ответ от %s (модель вернула промпт), пробуем следующий узел", node['name'])
                                continue

                            if result:
                                routing_source = node.get('routing_key', 'ollama_studio')
                                performance_score = node.get('performance_score', 0.8)
                                logger.info("[ROUTER] ✅ [SUCCESS] Node: %s, Model: %s, Latency: %.2fms, Performance: %.2f",
                                           node['name'], model, latency_ms, performance_score)

                                # Отмечаем использование модели для менеджера памяти
                                if self._memory_manager and node.get('routing_key') == 'local_server' and model:
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
                                            "node_name": node['name'],
                                            "node_priority": node.get('priority', 0),
                                            "attempt": attempt + 1
                                        }
                                    )

                                # Сохраняем информацию об использованной модели для отслеживания
                                # Это будет использовано в worker'е для записи производительности
                                if hasattr(self, '_current_task_id'):
                                    try:
                                        from model_performance_tracker import (
                                            get_performance_tracker,
                                        )
                                        tracker = get_performance_tracker()
                                        # Сохраняем в metadata задачи (будет использовано в worker'е)
                                        self._used_model = model
                                    except:
                                        pass

                                # Сохраняем в кэш при успехе (короткий ответ)
                                if prompt_cache_key and len(result) < 5000:
                                    self._evict_prompt_cache_if_needed()
                                    self._prompt_cache[prompt_cache_key] = (str(result), str(routing_source))
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
                                        output_tokens=out_tokens
                                    )
                                except Exception as metrics_err:
                                    logger.debug(f"Failed to record local metrics: {metrics_err}")

                                return result, routing_source
                            else:
                                logger.warning("[ROUTER] ⚠️ Node %s returned empty response for model %s", node['name'], model)
                        else:
                            # Log error response body for debugging
                            try:
                                error_text = response.text[:500]
                                logger.error("[ROUTER] ❌ Node %s returned HTTP %d: %s", node['name'], response.status_code, error_text)
                            except:
                                logger.error("[ROUTER] ❌ Node %s returned HTTP %d", node['name'], response.status_code)
                except asyncio.TimeoutError:
                    logger.warning("[ROUTER] ⏱️ Timeout: Node %s, Model %s (attempt %d/%d)",
                                  node['name'], model, attempt + 1, max_retries + 1)
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                except httpx.ConnectError as e:
                    logger.error("[ROUTER] ❌ Connection failed to %s: %s", node_url, e)
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                    continue
                except Exception as e:
                    logger.error("[ROUTER] ❌ Exception calling Node %s: %s: %s", node['name'], type(e).__name__, e)
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                    continue

            # If we exhausted retries for this node, try next
            logger.warning(f"⚠️ Node {node['name']} failed after {max_retries + 1} attempts, trying next...")

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
                features={"reason": "all_nodes_failed"}
            )

        return None, None

    async def run_local_llm_streaming(
        self,
        prompt: str,
        system_prompt: str = "",
        category: Optional[str] = None,
        images: Optional[list] = None,
        model: Optional[str] = None,
        is_vip: bool = False
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
            mlx_nodes = [n for n in healthy_nodes if "11435" in n['url'] or "mlx" in n['url'].lower()]
            if mlx_nodes:
                node = mlx_nodes[0]
                logger.info(f"🎯 [VIP STREAM] Выбран MLX узел: {node['name']}")

        if not node:
            node = healthy_nodes[0]

        node_url = f"{node['url']}/api/generate"
        logger.info(f"🌊 [STREAMING] Node: {node['name']} | Model: {model}")

        full_prompt = f"{system_prompt}\n\nUser: {prompt}\nAssistant:"
        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": True
        }
        payload["keep_alive"] = _get_keep_alive(model)
        if images:
            payload["images"] = images

        # VIP Header
        headers = {}
        if category == "reasoning" or is_vip or str(model).lower() == "victoria-wisdom-30b":
            headers["X-Request-Priority"] = "high"
            logger.info(f"🌟 [VIP HEADER] Added X-Request-Priority: high for streaming {category or model or 'VIP'}")

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    'POST',
                    node_url,
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status_code != 200:
                        logger.error(f"❌ [STREAMING] Error: {response.status_code}")
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        try:
                            chunk_data = json.loads(line)
                            if 'response' in chunk_data:
                                yield chunk_data['response']
                            if chunk_data.get('done', False):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"❌ [STREAMING] Error: {e}")
            return

    def _determine_task_type(self, prompt: str, category: Optional[str] = None) -> str:
        """Определяет тип задачи для сбора данных"""
        prompt_lower = prompt.lower()

        if category == "coding" or "код" in prompt_lower or "программируй" in prompt_lower:
            return "coding"
        elif category == "reasoning" or "подумай" in prompt_lower or "логика" in prompt_lower:
            return "reasoning"
        else:
            return "general"
