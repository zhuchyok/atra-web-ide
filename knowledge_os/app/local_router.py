import os
import httpx
import logging
import asyncio
import time
import hashlib
import asyncpg
import json
from typing import Optional, List, Dict, Tuple, AsyncGenerator
from functools import lru_cache

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

logger = logging.getLogger(__name__)

# Debug mode: VICTORIA_DEBUG=true enables verbose logging
VICTORIA_DEBUG = os.getenv("VICTORIA_DEBUG", "false").lower() in ("true", "1", "yes")
if VICTORIA_DEBUG:
    logger.setLevel(logging.DEBUG)
    logging.getLogger().setLevel(logging.DEBUG)

# Config
MAC_LLM_URL = os.getenv('MAC_LLM_URL', 'http://localhost:11435')  # MacBook через SSH reverse tunnel (11435 -> MacBook:11434)
SERVER_LLM_URL = os.getenv('SERVER_LLM_URL', 'http://localhost:11434')
USE_LOCAL_LLM = os.getenv('USE_LOCAL_LLM', 'true').lower() == 'true'
DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

# Health check cache (120 seconds TTL - увеличен для снижения нагрузки на /api/tags)
_health_cache = {"nodes": [], "timestamp": 0}
_HEALTH_CACHE_TTL = 120  # 2 минуты вместо 30 секунд для снижения rate limiting

# Model mapping with environment overrides for different hardware (Mac Studio)
MODEL_MAP = {
    "coding": os.getenv('MODEL_CODING', "qwen2.5-coder:32b"),
    "reasoning": os.getenv('MODEL_REASONING', "deepseek-r1-distill-llama:70b"),
    "fast": os.getenv('MODEL_FAST', "phi3.5:3.8b"),
    "vision": "moondream",
    "vision_pdf": "llava:7b",
    "default": os.getenv('MODEL_DEFAULT', "phi3.5:3.8b")
}

# Ollama модели
OLLAMA_MODELS = {
    "fast": "phi3.5:3.8b",
    "vision": "moondream",
    "vision_pdf": "llava:7b",
    "coding": "glm-4.7-flash:q8_0",
    "reasoning": "glm-4.7-flash:q8_0",
    "default": "phi3.5:3.8b"
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
        import os
        is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
        if is_docker:
            ollama_url = "http://host.docker.internal:11434"
            mlx_url = "http://host.docker.internal:11435"
        else:
            ollama_url = "http://localhost:11434"
            mlx_url = "http://localhost:11435"
        self.nodes = [
            {"name": "Mac Studio (MLX)", "url": mlx_url, "priority": 0, "routing_key": "mlx_studio"},
            {"name": "MacBook (Ollama)", "url": ollama_url, "priority": 0, "routing_key": "local_mac"},
            {"name": "Server (Light)", "url": SERVER_LLM_URL, "priority": 0, "routing_key": "local_server"}
        ]
        self._active_node = None
        self._performance_cache = {}  # Cache for node performance metrics
        self._cache_ttl = 300  # 5 minutes
        
        # ML Model for intelligent routing
        self.ml_model = None
        self.ml_model_path = os.path.join(os.path.dirname(__file__), 'ml_router_model.pkl')
        self._load_ml_model()
        
        # Model Memory Manager для оптимизации памяти (ленивая инициализация)
        self._memory_manager = None
        self._memory_manager_url = SERVER_LLM_URL
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
    
    def _load_ml_model(self):
        """Загружает ML-модель если доступна"""
        if MLRouterModel and os.path.exists(self.ml_model_path):
            try:
                self.ml_model = MLRouterModel()
                self.ml_model.load(self.ml_model_path)
                logger.info("✅ [ML ROUTER] ML model loaded successfully")
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
    
    def _select_model(self, prompt: str, category: Optional[str] = None, use_ollama: bool = False, node_type: Optional[str] = None) -> str:
        """Select the best local model for the task.
        Система автоматически выбирает модель на основе типа задачи, независимо от источника (MLX/Ollama).
        
        Args:
            prompt: User prompt
            category: Task category
            use_ollama: If True, use Ollama models (deprecated - система сама выберет)
            node_type: Тип узла ('mlx' или 'ollama') - для выбора подходящей модели
        """
        prompt_lower = prompt.lower()
        
        # Выбираем модель на основе задачи, а не источника
        # Оба источника (MLX и Ollama) поддерживают одинаковые модели
        
        # Reasoning задачи - нужна мощная модель
        if category == "reasoning" or "подумай" in prompt_lower or "логика" in prompt_lower or "планир" in prompt_lower:
            # Пробуем найти reasoning модель в доступных источниках
            if node_type == "mlx":
                return "deepseek-r1-distill-llama:70b"  # MLX модель
            else:
                return OLLAMA_MODELS.get("reasoning", "command-r-plus:104b")  # Ollama модель
        
        # Coding задачи - нужна специализированная модель для кода
        if "код" in prompt_lower or "программируй" in prompt_lower or category == "coding":
            if node_type == "mlx":
                return "qwen2.5-coder:32b"  # MLX модель
            else:
                return OLLAMA_MODELS.get("coding", "glm-4.7-flash:q8_0")  # Ollama модель
        
        # Быстрые задачи - легкая модель
        if category == "fast" or len(prompt) < 300:
            if node_type == "mlx":
                return "phi3.5:3.8b"  # MLX модель
            else:
                return OLLAMA_MODELS.get("fast", "phi3.5:3.8b")  # Ollama модель
        
        # Vision задачи
        if category == "vision" or "изображен" in prompt_lower or "картинк" in prompt_lower:
            return OLLAMA_MODELS.get("vision", "moondream")  # Vision только в Ollama
        
        # По умолчанию - выбираем на основе доступности
        if node_type == "mlx":
            return "phi3.5:3.8b"  # MLX модель по умолчанию
        else:
            return OLLAMA_MODELS.get("default", "phi3.5:3.8b")  # Ollama модель по умолчанию
    
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

    async def run_local_llm(self, prompt: str, system_prompt: str = "", category: Optional[str] = None, images: Optional[list] = None, max_retries: int = 2, model: Optional[str] = None) -> Optional[tuple]:
        """
        Запускает локальную LLM модель.
        Приоритет: MLX API Server (HTTP) и Ollama — оба используются (балансировка).
        model: если задан — используем эту модель и перебираем узлы (MLX/Ollama) пока один не ответит.
        
        Returns:
            tuple: (response, routing_source)
        """
        logger.info("[ROUTER] ========== LocalAIRouter.run_local_llm() ==========")
        logger.info("[ROUTER] Input model: %s", model)
        logger.info("[ROUTER] Category: %s", category)
        logger.info("[ROUTER] Prompt length: %d chars", len(prompt))
        logger.info("[ROUTER] Prompt preview: %s...", prompt[:150])
        
        # ПРИОРИТЕТ: Использовать MLX API Server и Ollama через HTTP роутинг
        # MLX Router напрямую не используется в контейнере (требует модуль mlx)
        # Вместо этого используем MLX API Server через HTTP (уже настроен в nodes)
        # АВТОМАТИЧЕСКИ включаем туннель для MacBook при первом использовании
        if ("localhost:11435" in MAC_LLM_URL or "127.0.0.1:11435" in MAC_LLM_URL) and not self._tunnel_checked:
            try:
                from tunnel_manager import ensure_tunnel, get_tunnel_status
                # Проверяем и автоматически создаем туннель если нужно
                status_before = get_tunnel_status()
                logger.info(f"🔍 Проверка SSH tunnel для MacBook (статус: {status_before})...")
                await ensure_tunnel()
                status_after = get_tunnel_status()
                if status_after == "активен" and status_before != "активен":
                    logger.info("✅ SSH tunnel для MacBook автоматически включен!")
                elif status_after == "активен":
                    logger.debug("✅ SSH tunnel для MacBook уже активен")
                self._tunnel_checked = True
            except Exception as e:
                logger.warning(f"⚠️ Tunnel check failed: {e}")
                self._tunnel_checked = True  # Помечаем как проверенный, чтобы не повторять
        """Call local LLM (Ollama style) with automatic failover, retry logic and node selection."""
        if not model:
            model = self._select_model(prompt, category)
            logger.info("[ROUTER] Model selected by _select_model(): %s", model)
        if images and MODEL_MAP.get("vision"):
            model = MODEL_MAP["vision"]
            logger.info("[ROUTER] Using vision model: %s", model)
        
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
            
            # ИНТЕЛЛЕКТУАЛЬНЫЙ ВЫБОР МОДЕЛИ на основе мировых практик (или переданная модель — Victoria)
            node_type = "mlx" if is_mlx else "ollama" if is_ollama else "unknown"
            
            # 1. Переданная модель (Victoria: лучшая из Ollama+MLX) — используем для всех узлов
            current_model = model
            # 2. Проверяем рекомендованную модель (из предыдущих попыток)
            recommended_model = getattr(self, '_recommended_model', None)
            if recommended_model and not current_model:
                current_model = recommended_model
                logger.info(f"🎯 [ROUTER] Используем рекомендованную модель: {current_model}")
            if not current_model:
                # 3. Используем интеллектуальный роутер на основе мировых практик
                try:
                    from intelligent_model_router import get_intelligent_router
                    intelligent_router = get_intelligent_router()
                    
                    # Получаем доступные модели для этого узла
                    available_models = []
                    if is_mlx:
                        # MLX модели
                        available_models = ['qwen2.5-coder:32b', 'deepseek-r1-distill-llama:70b', 'phi3.5:3.8b']
                    elif is_ollama:
                        # Ollama модели
                        available_models = ['glm-4.7-flash:q8_0', 'phi3.5:3.8b']
                    
                    if available_models:
                        # Выбираем оптимальную модель (возвращает model, TaskCategory, confidence)
                        optimal_model, _task_cat, confidence = await intelligent_router.select_optimal_model(
                            prompt=prompt,
                            category=category or "",
                            available_models=available_models,
                            optimize_for='balanced'  # Баланс качества, скорости и стоимости
                        )
                        
                        if optimal_model and confidence > 0.5:
                            current_model = optimal_model
                            logger.info(f"🧠 [INTELLIGENT ROUTER] Выбрана модель: {current_model} (confidence: {confidence:.2f})")
                        else:
                            current_model = self._select_model(prompt, category, node_type=node_type)
                            logger.debug(f"Intelligent router confidence too low ({confidence:.2f}), using fallback: {current_model}")
                    else:
                        current_model = self._select_model(prompt, category, node_type=node_type)
                except Exception as e:
                    logger.debug(f"Intelligent router failed: {e}, using fallback")
                    current_model = self._select_model(prompt, category, node_type=node_type)
            
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
                        # Чат с Викторией использует приоритет HIGH
                        headers = {"X-Request-Priority": "high"}
                        response = await client.post(
                            node_url,
                            json=payload,
                            headers=headers,
                            timeout=120.0  # Reduced from 300 to 120 seconds
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
                            
                            logger.info("[ROUTER] Response preview: %s...", result[:200] if result else "(empty)")
                            
                            if result:
                                routing_source = node.get('routing_key', 'local_mac' if node['name'].startswith("MacBook") else 'local_server')
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
                                        from model_performance_tracker import get_performance_tracker
                                        tracker = get_performance_tracker()
                                        # Сохраняем в metadata задачи (будет использовано в worker'е)
                                        self._used_model = model
                                    except:
                                        pass
                                
                                # Сохраняем в кэш при успехе (короткий ответ)
                                if prompt_cache_key and len(result) < 5000:
                                    self._evict_prompt_cache_if_needed()
                                    self._prompt_cache[prompt_cache_key] = (result, routing_source)
                                    self._prompt_cache_meta[prompt_cache_key] = time.time()
                                # Return (response, routing_source) tuple
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
        model: Optional[str] = None
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
        
        Yields:
            Response chunks as strings
        """
        # Убеждаемся, что туннель активен перед использованием MacBook
        if "localhost:11435" in MAC_LLM_URL or "127.0.0.1:11435" in MAC_LLM_URL:
            try:
                from tunnel_manager import ensure_tunnel
                await ensure_tunnel()
            except Exception as e:
                logger.debug(f"Tunnel check failed: {e}")
        
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
        
        # Select best node (use first one, load balancer would be ideal but keep it simple for streaming)
        node = healthy_nodes[0]
        node_url = f"{node['url']}/api/generate"
        logger.info(f"🌊 [STREAMING] Node: {node['name']} | Model: {model}")
        
        full_prompt = f"{system_prompt}\n\nUser: {prompt}\nAssistant:"
        payload = {
            "model": model,
            "prompt": full_prompt,
            "stream": True
        }
        if images:
            payload["images"] = images
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    'POST',
                    node_url,
                    json=payload
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
