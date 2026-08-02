import asyncio
import hashlib
import json
import logging
import os
import re
import sys
import time
import traceback
from typing import Any, Optional

import aiohttp
from pydantic import ValidationError

from .base_agent import AgentAction, AgentFinish

logger = logging.getLogger(__name__)

# Debug mode: VICTORIA_DEBUG=true enables verbose logging
VICTORIA_DEBUG = os.getenv("VICTORIA_DEBUG", "false").lower() in ("true", "1", "yes")

# Мировая практика: только эти инструменты существуют. Любой другой = отклоняем и просим повторить.
ALLOWED_TOOLS = {"finish", "read_file", "list_directory", "run_terminal_cmd", "ssh_run"}

# === MODEL FALLBACK CONFIGURATION ===
# Ordered list of fallback models from smallest to largest
FALLBACK_MODELS_OLLAMA = [
    "phi3.5:3.8b",  # Fast, stable
    "tinyllama:1.1b-chat",  # Very small, always works
    "glm-4.7-flash:q8_0",  # Medium, good quality
    "victoria-wisdom-v3.5:latest",  # Large, may crash on limited RAM
]


class DynamicSemaphore:
    """[SINGULARITY 21.14] Semaphore with dynamic limit adjustment"""

    def __init__(self, initial_limit: int = 5):
        self.limit = initial_limit
        self.current_count = 0
        self._condition = asyncio.Condition()
        logger.info(f"[ADAPTIVE] Initialized DynamicSemaphore with limit {initial_limit}")

    async def __aenter__(self):
        async with self._condition:
            while self.current_count >= self.limit:
                await self._condition.wait()
            self.current_count += 1
            return self

    async def __aexit__(self, exc_type, exc, tb):
        async with self._condition:
            self.current_count = max(0, self.current_count - 1)
            self._condition.notify_all()
        # При CancelledError убеждаемся что слот освобождён — не подавляем исключение
        return False

    def set_limit(self, new_limit: int):
        old_limit = self.limit
        self.limit = max(1, new_limit)
        if self.limit != old_limit:
            logger.info(f"[ADAPTIVE] Concurrency limit changed: {old_limit} -> {self.limit}")
            # We don't need to notify here because waiters will be notified on next release
            # but notify_all doesn't hurt if we want immediate re-check

    @property
    def active_slots(self):
        return self.current_count


FALLBACK_MODELS_MLX = [
    "victoria-wisdom-v3.5",  # Основная модель Victoria в MLX (приоритет 1)
    "phi3.5:3.8b",
    "qwen2.5:3b",
    "tinyllama:1.1b-chat",
    "phi3:mini-4k",
    "victoria-wisdom-v3.5:latest",
]

# Models that are known to crash on resource-limited systems
RESOURCE_HEAVY_MODELS = {
    "victoria-wisdom-v3.5:latest",
    "qwq:32b",
    "deepseek-r1-distill-llama:70b",
    "llama3.3:70b",
    "command-r-plus:104b",
}


def _ollama_base_url() -> str:
    return (
        os.getenv("OLLAMA_BASE_URL") or os.getenv("MAC_STUDIO_LLM_URL") or "http://localhost:11434"
    )


def _mlx_base_url() -> str:
    """Get MLX API Server URL (default: 11435)"""
    is_docker = (
        os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
    )
    if is_docker:
        return os.getenv("MLX_BASE_URL", "http://host.docker.internal:11435")
    return os.getenv("MLX_BASE_URL", "http://localhost:11435")


def _is_victoria_wisdom(model: Optional[str]) -> bool:
    """True for victoria-wisdom* (brain/hands tags)."""
    return bool(model) and "victoria-wisdom" in (model or "").lower()


def _normalize_model_for_backend(model: str, base_url: str, mlx_url: str) -> str:
    """
    World practice: one logical model, backend-specific ids.
    MLX registry uses untagged victoria-wisdom-v3.5; Ollama often has :latest.
    """
    if not model:
        return model
    base = (base_url or "").rstrip("/")
    mlx = (mlx_url or "").rstrip("/")
    if base == mlx or ":11435" in base:
        if model.endswith(":latest"):
            return model[: -len(":latest")]
    return model


def _wisdom_mlx_primary_enabled() -> bool:
    """MLX-first for wisdom (default on). Opt out: VICTORIA_WISDOM_MLX_PRIMARY=false."""
    return os.getenv("VICTORIA_WISDOM_MLX_PRIMARY", "true").lower() in ("1", "true", "yes")


class OllamaExecutor:
    """Исполнитель запросов к Ollama / MLX API с автоматическим fallback"""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        # Автовыбор модели: если не указана, будет выбрана при первом запросе через сканирование Ollama
        self.model: str = (
            model or os.getenv("VICTORIA_MODEL") or os.getenv("VERONICA_MODEL") or "auto"
        )
        self.base_url: str = base_url or _ollama_base_url()
        self._model_resolved = False  # Флаг: модель уже выбрана из актуального списка

        # === FALLBACK CONFIGURATION ===
        self._failed_models: set = set()  # Models that have failed in this session
        self._fallback_attempts = 0
        self._max_fallback_attempts = 3
        self._last_successful_model: Optional[str] = None

        # MLX URL for fallback
        self._mlx_url = _mlx_base_url()
        self._use_mlx_fallback = os.getenv("USE_MLX_FALLBACK", "true").lower() == "true"

        # === CACHE CONFIGURATION [SINGULARITY 21.13] ===
        self.use_semantic_cache = os.getenv("VICTORIA_USE_SEMANTIC_CACHE", "true").lower() == "true"
        self._local_hash_cache: dict[str, str] = {}  # L1: Exact match (in-memory)
        self._cache_manager = None  # L2: SemanticAICache (lazy load)
        self._cache_threshold = float(os.getenv("VICTORIA_CACHE_THRESHOLD", "0.95"))

        # === ADAPTIVE CONCURRENCY [SINGULARITY 21.14] ===
        self._semaphore = DynamicSemaphore(
            initial_limit=int(os.getenv("VICTORIA_MAX_CONCURRENT", "5"))
        )
        self._monitor_task: Optional[asyncio.Task[Any]] = None
        self._start_monitor()

        logger.info("[EXECUTOR_INIT] ========== OllamaExecutor initialization ==========")
        logger.info(f"[EXECUTOR_INIT] Primary model: {self.model}")
        logger.info(f"[EXECUTOR_INIT] Ollama URL: {self.base_url}")
        logger.info(f"[EXECUTOR_INIT] MLX URL: {self._mlx_url}")
        logger.info(f"[EXECUTOR_INIT] MLX fallback enabled: {self._use_mlx_fallback}")
        logger.info(f"[EXECUTOR_INIT] Semantic cache enabled: {self.use_semantic_cache}")

        self.system_prompt = """ТЫ — ВИКТОРИЯ, TEAM LEAD ATRA. Отвечай на русском.

СТРОГО: Ответ — ОДИН JSON, без текста до/после. Поле "tool" — ТОЛЬКО одно из: finish, read_file, list_directory, run_terminal_cmd, ssh_run. Других инструментов НЕТ (нет web_search, git_run, web_check, websocket и т.д.).

ФОРМАТ: {"thought": "...", "tool": "...", "tool_input": {...}}

ИНСТРУМЕНТЫ (только эти):
1. finish - ЗАВЕРШИТЬ задачу. Используй СРАЗУ для простых вопросов!
   {"tool": "finish", "tool_input": {"output": "ответ"}}
2. read_file - прочитать файл. Путь ТОЛЬКО реальный: frontend/src/App.svelte, package.json (НЕ /path/to/!)
   {"tool": "read_file", "tool_input": {"file_path": "frontend/src/App.svelte"}}
3. list_directory - список файлов. Директория: "." или "frontend" (НЕ /path/to/repository!)
   {"tool": "list_directory", "tool_input": {"directory": "."}}
4. run_terminal_cmd - ЛОКАЛЬНАЯ команда (ls, cat, find, docker — НЕ ssh!)
   {"tool": "run_terminal_cmd", "tool_input": {"command": "ls -la"}}
5. ssh_run - УДАЛЁННЫЙ сервер (только с реальным host!)
   {"tool": "ssh_run", "tool_input": {"host": "IP", "command": "команда"}}

ЗАПРЕЩЕНО: web_search, web_edit, git_run, write_file, web_review — таких инструментов НЕТ! Не выдумывай пути /path/to/ — используй реальные: ., frontend, backend. Ответ — ОДИН JSON, без текста до/после.

ПРАВИЛА ВЫПОЛНЕНИЯ:
- Простые вопросы ("привет", "скажи привет") → СРАЗУ finish
- "покажи файлы" / "выведи список файлов" → run_terminal_cmd "ls -la", затем finish
- ЛОКАЛЬНЫЕ команды (ls, cat, find, docker exec) → run_terminal_cmd (НЕ ssh_run!)
- УДАЛЁННЫЕ серверы (по IP адресу) → ssh_run с host
- НЕ придумывай дополнительные условия! Выполняй ТОЧНО то что просят
- После получения результата команды → СРАЗУ finish с результатом

ВАЖНО: docker exec, ls, cat, find - это ЛОКАЛЬНЫЕ команды! Используй run_terminal_cmd!

ПРИМЕРЫ ПРАВИЛЬНЫХ ОТВЕТОВ:
Q: "скажи привет"
A: {"thought": "Простое приветствие", "tool": "finish", "tool_input": {"output": "Привет! Я Виктория."}}

Q: "выведи список файлов"
A: {"thought": "Нужно выполнить ls", "tool": "run_terminal_cmd", "tool_input": {"command": "ls -la"}}
(После получения результата → finish с выводом команды)

Q: "покажи файлы в текущей директории"
A: {"thought": "Выполню ls для текущей директории", "tool": "run_terminal_cmd", "tool_input": {"command": "ls -la"}}
"""

    async def _check_model_available(self, base_url: str, model: str) -> bool:
        """Check if a model is available on the given server"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.get(f"{base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [m.get("name", "") for m in data.get("models", [])]
                        return model in models or any(model in m for m in models)
        except Exception as e:
            logger.debug(f"[MODEL_CHECK] Failed to check {model} on {base_url}: {e}")
        return False

    async def _get_fallback_model(self) -> tuple[Optional[str], Optional[str]]:
        """
        Get next available fallback model.
        Returns: (model_name, base_url) or (None, None) if no fallback available
        """
        logger.info("[FALLBACK] ========== Finding fallback model ==========")
        logger.info(f"[FALLBACK] Failed models this session: {self._failed_models}")
        logger.info(
            f"[FALLBACK] Fallback attempts: {self._fallback_attempts}/{self._max_fallback_attempts}"
        )

        if self._fallback_attempts >= self._max_fallback_attempts:
            logger.error(
                f"[FALLBACK] Max fallback attempts reached ({self._max_fallback_attempts})"
            )
            return None, None

        # Try MLX first (more stable for large models)
        if self._use_mlx_fallback:
            for model in FALLBACK_MODELS_MLX:
                if model not in self._failed_models:
                    if await self._check_model_available(self._mlx_url, model):
                        logger.info(f"[FALLBACK] ✅ Found MLX model: {model}")
                        return model, self._mlx_url

        # Try Ollama (smaller models are more stable)
        for model in FALLBACK_MODELS_OLLAMA:
            if model not in self._failed_models:
                if await self._check_model_available(self.base_url, model):
                    logger.info(f"[FALLBACK] ✅ Found Ollama model: {model}")
                    return model, self.base_url

        logger.error("[FALLBACK] ❌ No available fallback models found")
        return None, None

    async def _get_cache_manager(self):
        """Lazy load SemanticAICache from knowledge_os"""
        if self._cache_manager is not None:
            return self._cache_manager

        try:
            # Try to import from knowledge_os
            sys.path.insert(0, os.path.join(os.getcwd(), "knowledge_os/app"))
            from semantic_cache import (
                SemanticAICache,  # type: ignore # [SINGULARITY 21.13] Dynamic import from knowledge_os
            )

            self._cache_manager = SemanticAICache(db_url=os.getenv("DATABASE_URL"))
            logger.info("[CACHE] ✅ SemanticAICache manager initialized")
        except Exception as e:
            logger.debug(f"[CACHE] Failed to initialize SemanticAICache: {e}")
            self.use_semantic_cache = False

        return self._cache_manager

    def _is_cacheable(self, prompt: str) -> bool:
        """Check if the prompt is suitable for caching (no dynamic commands)"""
        if not prompt:
            return False

        lower_prompt = prompt.lower()

        # [SINGULARITY 21.13] Dynamic patterns that should NEVER be cached
        non_cacheable = [
            "ls",
            "cat",
            "grep",
            "status",
            "docker ps",
            "docker logs",
            "date",
            "time",
            "pwd",
            "find",
            "ps aux",
            "top",
            "df -h",
            "git status",
            "git log",
            "git diff",
            "ping",
            "pong",
        ]

        # Check for exact word matches to avoid false positives (e.g. "catalog" containing "cat")
        for pattern in non_cacheable:
            if re.search(rf"\b{re.escape(pattern)}\b", lower_prompt):
                return False

        # Don't cache very short prompts (usually greetings or simple pings)
        if len(prompt) < 10:
            return False

        return True

    async def ask(
        self,
        prompt: str,
        history: Optional[list[dict[str, str]]] = None,
        raw_response: bool = False,
        phase: Optional[str] = None,
        blocked_tools: Optional[list[str]] = None,
        model: Optional[str] = None,
        system: Optional[str] = None,
        expert_name: str = "Виктория",
    ) -> Any:
        """
        Send request to LLM with automatic fallback on model crash.
        phase: опционально — понимание цели / план / шаг N, логируется при таймауте.
        blocked_tools: инструменты, которые нельзя выбирать (заблокированы из-за цикла).
        model: переопределить модель для этого запроса.
        system: переопределить системный промпт.
        expert_name: имя эксперта для семантического кэша.
        """
        # === HYBRID CACHE CHECK [SINGULARITY 21.13] ===
        cache_key = f"{expert_name}:{model or self.model}:{system or ''}:{prompt}"
        if self.use_semantic_cache and self._is_cacheable(prompt):
            # L1: Exact Match (Hash)
            hash_key = hashlib.md5(cache_key.encode()).hexdigest()
            if hash_key in self._local_hash_cache:
                logger.info(f"[CACHE_HIT] 🎯 L1 (Hash) hit for expert {expert_name}")
                cached_content = self._local_hash_cache[hash_key]
                if raw_response:
                    return cached_content
                return self._parse_response(cached_content, blocked_tools=blocked_tools)

            # L2: Semantic Match (Vector)
            cache_mgr = await self._get_cache_manager()
            if cache_mgr:
                try:
                    # We use a combined key for semantic search to include context
                    semantic_query = f"Context: {system or ''}\nPrompt: {prompt}"
                    cached_response = await cache_mgr.get_cached_response(
                        semantic_query, expert_name
                    )
                    if cached_response:
                        logger.info(f"[CACHE_HIT] 🏆 L2 (Semantic) hit for expert {expert_name}")
                        # Update L1 for even faster access next time
                        self._local_hash_cache[hash_key] = cached_response
                        if raw_response:
                            return cached_response
                        return self._parse_response(cached_response, blocked_tools=blocked_tools)
                except Exception as ce:
                    logger.debug(f"[CACHE_ERROR] Semantic lookup failed: {ce}")

        # === ADAPTIVE CONCURRENCY [SINGULARITY 21.14] ===
        # Ensure monitor is running
        self._start_monitor()

        req_model = model or self.model
        req_base = self.base_url
        # World practice (brain on specialized accelerator): wisdom → MLX when healthy.
        if (
            _wisdom_mlx_primary_enabled()
            and self._use_mlx_fallback
            and _is_victoria_wisdom(req_model)
            and req_base.rstrip("/") != self._mlx_url.rstrip("/")
        ):
            try:
                timeout = aiohttp.ClientTimeout(total=2.0, connect=1.0)
                async with aiohttp.ClientSession(timeout=timeout) as _sess:
                    async with _sess.get(f"{self._mlx_url.rstrip('/')}/health") as _resp:
                        if _resp.status == 200:
                            req_base = self._mlx_url
                            req_model = _normalize_model_for_backend(
                                req_model, req_base, self._mlx_url
                            )
                            logger.info(
                                "[LLM_ROUTE] wisdom MLX-primary model=%s url=%s",
                                req_model,
                                req_base,
                            )
            except Exception as _route_err:
                logger.debug("[LLM_ROUTE] MLX primary probe skipped: %s", _route_err)

        async with self._semaphore:
            logger.info(
                f"[ADAPTIVE] Slot acquired. Active requests: {self._semaphore.active_slots}/{self._semaphore.limit}"
            )
            try:
                response = await self._ask_with_fallback(
                    prompt=prompt,
                    history=history,
                    raw_response=raw_response,
                    model=req_model,
                    base_url=req_base,
                    is_retry=False,
                    phase=phase,
                    blocked_tools=blocked_tools,
                    system_override=system,
                )
            except asyncio.CancelledError:
                logger.warning("[ADAPTIVE] Task cancelled — semaphore slot released")
                raise

        # === SAVE TO CACHE ===
        # Only save if it's a successful string response and cacheable
        if (
            self.use_semantic_cache
            and self._is_cacheable(prompt)
            and isinstance(response, (str, AgentAction, AgentFinish))
        ):
            # Extract raw content for caching
            content_to_cache = None
            if isinstance(response, str):
                content_to_cache = response
            elif isinstance(response, AgentFinish):
                # Reconstruct JSON for caching
                content_to_cache = json.dumps(
                    {
                        "thought": response.thought,
                        "tool": "finish",
                        "tool_input": {"output": response.output},
                    },
                    ensure_ascii=False,
                )
            elif isinstance(response, AgentAction):
                content_to_cache = json.dumps(
                    {
                        "thought": response.thought,
                        "tool": response.tool,
                        "tool_input": response.tool_input,
                    },
                    ensure_ascii=False,
                )

            if content_to_cache and len(content_to_cache) > 10:
                # Basic error filtering
                error_keywords = ["ошибка", "error", "не могу", "не удалось", "failed"]
                if not any(kw in content_to_cache.lower() for kw in error_keywords):
                    # Save to L1
                    hash_key = hashlib.md5(cache_key.encode()).hexdigest()
                    self._local_hash_cache[hash_key] = content_to_cache

                    # Save to L2 (background task)
                    cache_mgr = await self._get_cache_manager()
                    if cache_mgr:
                        semantic_query = f"Context: {system or ''}\nPrompt: {prompt}"
                        asyncio.create_task(
                            cache_mgr.save_to_cache(
                                semantic_query, content_to_cache, expert_name, priority="medium"
                            )
                        )
                        logger.debug(
                            f"[CACHE_SAVE] Saved response for {expert_name} to semantic cache"
                        )

        return response

    def _start_monitor(self):
        """Start background task to monitor Mac Studio hardware and adjust concurrency"""
        if self._monitor_task is not None:
            return

        try:
            loop = asyncio.get_running_loop()
            self._monitor_task = loop.create_task(self._monitor_loop())
            logger.info("[ADAPTIVE] Background monitor task started")
        except RuntimeError:
            # No running loop, will be started on first request
            pass

    async def _monitor_loop(self):
        """Periodically check hardware and adjust semaphore limit"""
        while True:
            try:
                # Lazy import to avoid circular dependencies
                sys.path.insert(0, os.path.join(os.getcwd(), "knowledge_os/app"))
                from mac_studio_monitor import (
                    get_mac_studio_monitor,  # type: ignore # [SINGULARITY 21.14] Dynamic import from knowledge_os
                )

                monitor = get_mac_studio_monitor()
                stats = await monitor.get_full_stats()

                # Logic for limit adjustment
                new_limit = 5  # Default

                # 1. Thermal Level check
                thermal_level = int(
                    stats.get("hardware", {}).get("temperature", {}).get("thermal_level", "0")
                )
                if thermal_level >= 2:
                    new_limit = 1
                elif thermal_level >= 1:
                    new_limit = 2

                # 2. RAM check
                ram_percent = stats.get("hardware", {}).get("ram", {}).get("percent", 0)
                if ram_percent > 95:
                    new_limit = 1
                elif ram_percent > 90:
                    new_limit = min(new_limit, 2)

                # 3. MLX Load check (if available)
                try:
                    from mlx_monitor import (
                        get_mlx_monitor,  # type: ignore # [SINGULARITY 21.14] Dynamic import from knowledge_os
                    )

                    mlx_monitor = get_mlx_monitor()
                    health_score = mlx_monitor.get_health_score()
                    if health_score < 0.3:
                        new_limit = 1
                    elif health_score < 0.6:
                        new_limit = min(new_limit, 3)
                except Exception:
                    pass

                self._semaphore.set_limit(new_limit)

            except Exception as e:
                logger.debug(f"[ADAPTIVE] Monitor loop error: {e}")

            await asyncio.sleep(15)  # Check every 15 seconds

    async def _ask_with_fallback(
        self,
        prompt: str,
        history: Optional[list[dict[str, str]]],
        raw_response: bool,
        model: str,
        base_url: str,
        is_retry: bool = False,
        phase: Optional[str] = None,
        blocked_tools: Optional[list[str]] = None,
        system_override: Optional[str] = None,
    ) -> Any:
        """Internal method with fallback support"""
        model = _normalize_model_for_backend(model, base_url, self._mlx_url)
        url = f"{base_url}/api/chat"
        system_content = system_override or self.system_prompt
        if blocked_tools:
            allowed = sorted(ALLOWED_TOOLS - set(blocked_tools))
            system_content += (
                f"\n\n⚠️ ЗАПРЕЩЕНО использовать (заблокированы из-за цикла): {', '.join(sorted(blocked_tools))}. "
                f"Доступны ТОЛЬКО: {', '.join(allowed)}. Ответь JSON с tool из доступных или finish."
            )
        messages = [{"role": "system", "content": system_content}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        # keep_alive: политика из ollama_keep_alive_policy
        # При живом MLX → 60с (руки), при падении MLX → -1 (immortal fallback)

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1, "enable_thinking": True},
        }

        # Адаптивный keep_alive на основе веса модели (Singularity 10.0)
        def get_smart_keep_alive(m_name: str) -> Any:
            raw = os.getenv("VICTORIA_OLLAMA_KEEP_ALIVE") or os.getenv("OLLAMA_KEEP_ALIVE")
            if raw:
                try:
                    return int(raw) if str(raw).strip().lstrip("-").isdigit() else raw
                except Exception:
                    return raw

            key = (m_name or "").lower()
            # Большие модели (>20GB): короткий TTL чтобы не блокировать Ollama scheduler
            if "wisdom" in key or "35b" in key or "qwen3.5" in key:
                return 60
            if "70b" in key or "104b" in key or "next" in key:
                return 60
            if "32b" in key or "30b" in key or "qwq" in key:
                return 120
            if "7b" in key or "8b" in key or "14b" in key:
                return 300
            # phi3.5 (17GB), lfm2.5, другие средние — не держать часами
            if "phi3" in key or "phi3.5" in key or "17gb" in key:
                return 120
            if "3b" in key or "1b" in key or "tiny" in key or "embedding" in key:
                return 300
            return 120

        payload["keep_alive"] = get_smart_keep_alive(model)

        # === DETAILED DEBUG LOGGING ===
        logger.info("[LLM_CALL] ========== OllamaExecutor.ask() ==========")
        logger.info(f"[LLM_CALL] Model: {model}")
        logger.info(f"[LLM_CALL] URL: {url}")
        logger.info(f"[LLM_CALL] Is retry/fallback: {is_retry}")
        logger.info(f"[LLM_CALL] Failed models this session: {self._failed_models}")
        logger.info(f"[LLM_CALL] Prompt length: {len(prompt)} chars")
        logger.info(f"[LLM_CALL] Prompt preview: {prompt[:200]}...")
        if VICTORIA_DEBUG:
            logger.debug(
                f"[LLM_CALL] Full payload: {json.dumps(payload, ensure_ascii=False)[:1000]}"
            )

        start_time = time.time()

        # Таймаут на один вызов LLM: настраивается через OLLAMA_EXECUTOR_TIMEOUT (по умолчанию 300 с)
        # connect=30 — стабильность из контейнера к host.docker.internal (не обрывать долгие ответы)
        # Без sock_read: executor использует stream:False — весь ответ буферизуется Ollama перед отправкой.
        # При sock_read=120 35B модель silent-timeout-ится во время генерации (>2 мин). total достаточно.
        _exec_timeout = float(os.getenv("OLLAMA_EXECUTOR_TIMEOUT", "300"))
        timeout = aiohttp.ClientTimeout(total=_exec_timeout, connect=30.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                logger.info(f"[LLM_CALL] Sending request to {url}...")
                async with session.post(url, json=payload) as response:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[LLM_RESPONSE] HTTP Status: {response.status}, Time: {elapsed:.2f}s"
                    )

                    if response.status == 200:
                        result = await response.json()
                        content = result.get("message", {}).get("content", "")

                        # === SUCCESS LOGGING ===
                        logger.info("[LLM_RESPONSE] ✅ Success!")
                        logger.info(f"[LLM_RESPONSE] Model used: {model}")
                        logger.info(f"[LLM_RESPONSE] Content length: {len(content)} chars")
                        logger.info(f"[LLM_RESPONSE] Content preview: {content[:300]}...")
                        if VICTORIA_DEBUG:
                            logger.debug(f"[LLM_RESPONSE] Full content: {content[:2000]}")

                        # Mark this model as successful
                        self._last_successful_model = model

                        if raw_response:
                            return content
                        return self._parse_response(content, blocked_tools=blocked_tools)
                    else:
                        # Model crashed or error
                        error_body = await response.text()
                        logger.error(f"[LLM_ERROR] HTTP {response.status}: {error_body[:500]}")

                        # Check for model crash indicators
                        crash_indicators = [
                            "model runner has unexpectedly stopped",
                            "resource limitations",
                            "internal error",
                            "out of memory",
                            "CUDA error",
                            "Metal error",
                        ]

                        is_busy = response.status in (429, 503) or any(
                            x in (error_body or "").lower()
                            for x in ("server busy", "maximum pending", "queue is full")
                        )
                        if is_busy:
                            logger.warning(
                                "[LLM_BUSY] model=%s backend=%s http=%s — transient overload; fallback...",
                                model,
                                "mlx"
                                if base_url.rstrip("/") == self._mlx_url.rstrip("/")
                                else "ollama",
                                response.status,
                            )
                            self._failed_models.add(model)
                            self._fallback_attempts += 1
                            if self._use_mlx_fallback and base_url != self._mlx_url:
                                fallback_model, fallback_url = await self._get_fallback_model()
                                if fallback_model and fallback_url:
                                    return await self._ask_with_fallback(
                                        prompt=prompt,
                                        history=history,
                                        raw_response=raw_response,
                                        model=fallback_model,
                                        base_url=fallback_url,
                                        is_retry=True,
                                        phase=phase,
                                        blocked_tools=blocked_tools,
                                        system_override=system_override,
                                    )

                        is_crash = any(
                            ind.lower() in error_body.lower() for ind in crash_indicators
                        )

                        if is_crash or response.status == 500:
                            logger.warning(
                                f"[LLM_CRASH] ⚠️ Model {model} crashed! Attempting fallback..."
                            )
                            self._failed_models.add(model)
                            self._fallback_attempts += 1

                            # Try fallback
                            fallback_model, fallback_url = await self._get_fallback_model()
                            if fallback_model and fallback_url:
                                logger.info(
                                    f"[LLM_FALLBACK] 🔄 Retrying with model: {fallback_model} on {fallback_url}"
                                )
                                return await self._ask_with_fallback(
                                    prompt=prompt,
                                    history=history,
                                    raw_response=raw_response,
                                    model=fallback_model,
                                    base_url=fallback_url,
                                    is_retry=True,
                                    phase=phase,
                                    blocked_tools=blocked_tools,
                                    system_override=system_override,
                                )

                        return {"error": f"Ollama HTTP {response.status}: {error_body[:200]}"}

            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                phase_info = f" phase={phase}" if phase else ""
                logger.error(
                    "[LLM_ERROR] ⏱️ Timeout after %.2fs for model %s%s",
                    elapsed,
                    model,
                    phase_info,
                )

                # Client timeout ≠ confirmed 503 busy (SRE taxonomy).
                logger.warning(
                    "[LLM_TIMEOUT] model=%s backend=%s elapsed=%.1fs reason=client_timeout "
                    "(not confirmed busy); trying fallback...",
                    model,
                    "mlx" if base_url.rstrip("/") == self._mlx_url.rstrip("/") else "ollama",
                    elapsed,
                )
                self._failed_models.add(model)
                self._fallback_attempts += 1

                if self._use_mlx_fallback and base_url != self._mlx_url:
                    fallback_model, fallback_url = await self._get_fallback_model()
                    if fallback_model and fallback_url:
                        return await self._ask_with_fallback(
                            prompt=prompt,
                            history=history,
                            raw_response=raw_response,
                            model=fallback_model,
                            base_url=fallback_url,
                            is_retry=True,
                            phase=phase,
                            blocked_tools=blocked_tools,
                        )

                # Timeout on large model - try fallback (legacy path)
                if model in RESOURCE_HEAVY_MODELS:
                    logger.warning(
                        f"[LLM_TIMEOUT] Large model {model} timed out, trying fallback..."
                    )
                    self._failed_models.add(model)
                    self._fallback_attempts += 1

                    fallback_model, fallback_url = await self._get_fallback_model()
                    if fallback_model and fallback_url:
                        return await self._ask_with_fallback(
                            prompt=prompt,
                            history=history,
                            raw_response=raw_response,
                            model=fallback_model,
                            base_url=fallback_url,
                            is_retry=True,
                            phase=phase,
                            blocked_tools=blocked_tools,
                        )

                return {"error": f"Timeout: модель {model} не ответила за {int(_exec_timeout)} с"}

            except aiohttp.ClientConnectorError as e:
                logger.error(f"[LLM_ERROR] 🔌 Connection failed to {url}: {e}")

                # If Ollama is down, try MLX
                if self._use_mlx_fallback and base_url != self._mlx_url:
                    logger.info("[LLM_FALLBACK] Ollama connection failed, trying MLX...")
                    fallback_model, fallback_url = await self._get_fallback_model()
                    if fallback_model and fallback_url:
                        return await self._ask_with_fallback(
                            prompt=prompt,
                            history=history,
                            raw_response=raw_response,
                            model=fallback_model,
                            base_url=fallback_url,
                            is_retry=True,
                            phase=phase,
                            blocked_tools=blocked_tools,
                        )

                return {"error": f"Connection failed to {url}: {e}"}

            except Exception as e:
                logger.error(f"[LLM_ERROR] ❌ Exception: {type(e).__name__}: {e}")
                logger.error(f"[LLM_ERROR] Traceback: {traceback.format_exc()}")
                return {"error": str(e)}

    def _parse_response(self, content: str, blocked_tools: Optional[list[str]] = None) -> Any:
        logger.info(f"[LLM_PARSE] Parsing response ({len(content)} chars)...")

        # Убираем лишние пробелы и возможные теги <think>
        clean_content = content.strip()
        if "</think>" in clean_content:
            clean_content = clean_content.split("</think>")[-1].strip()
            logger.info(f"[LLM_PARSE] Removed <think> tags, now {len(clean_content)} chars")

        # Интеллектуальное обновление знаний (если Агент написал это в тексте)
        # Формат: KNOWLEDGE: {"key": "value"}
        if "KNOWLEDGE:" in clean_content:
            try:
                k_part = clean_content.split("KNOWLEDGE:")[1].strip().split("\n")[0]
                knowledge_update = json.loads(k_part)
                # Это будет обработано в базовом классе (нужна связь)
                logger.debug(f"🧠 Найдено обновление знаний: {knowledge_update}")
            except Exception:
                pass

        # Пробуем распарсить как JSON
        try:
            start_idx = clean_content.find("{")
            end_idx = clean_content.rfind("}")

            if start_idx != -1 and end_idx != -1:
                json_str = clean_content[start_idx : end_idx + 1]
                logger.info(f"[LLM_PARSE] Found JSON block at [{start_idx}:{end_idx + 1}]")

                # Пытаемся распарсить как стандартный JSON
                try:
                    data = json.loads(json_str)
                    logger.info(f"[LLM_PARSE] JSON parsed successfully, keys: {list(data.keys())}")
                except json.JSONDecodeError as je:
                    logger.warning(f"[LLM_PARSE] JSON decode failed: {je}")
                    # Если модель выдала одинарные кавычки (Python style), пробуем исправить
                    import ast

                    try:
                        data = ast.literal_eval(json_str)
                        logger.info("[LLM_PARSE] ast.literal_eval succeeded")
                    except Exception as ae:
                        # Если совсем всё плохо - возвращаем как текст для разбора Агентом
                        logger.error(f"[LLM_PARSE] Failed to parse JSON: {ae}")
                        logger.error(f"[LLM_PARSE] Raw JSON string: {json_str[:500]}")
                        return AgentFinish(output=clean_content, thought="Failed to parse JSON")

                thought = data.get("thought", "Рассуждаю...")
                tool_input = (
                    data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
                )

                # Чужой формат (tool_execution, final_output) — не наш API, завершаем с подсказкой
                if "tool_execution" in data or "final_output" in data:
                    logger.warning(
                        "[LLM_PARSE] Invalid format detected: tool_execution/final_output"
                    )
                    return AgentFinish(
                        output='Используй только формат: {"thought": "...", "tool": "один из: finish, read_file, list_directory, run_terminal_cmd, ssh_run", "tool_input": {...}}. Других полей нет.',
                        thought=thought,
                    )

                # Если это наш формат
                if "tool" in data and "tool_input" in data:
                    raw_tool = data.get("tool")
                    tool_name = (
                        str(raw_tool).strip().lower()
                        if raw_tool and not isinstance(raw_tool, list)
                        else ""
                    )
                    # tool как массив или неизвестный инструмент — отклоняем (мировая практика: strict schema)
                    if isinstance(raw_tool, list):
                        tool_name = (raw_tool[0] if raw_tool else "") or "unknown"

                    logger.info(
                        f"[LLM_PARSE] Detected tool: '{tool_name}', thought: '{thought[:50]}...'"
                    )

                    if tool_name not in ALLOWED_TOOLS:
                        bad = (
                            raw_tool
                            if isinstance(raw_tool, str)
                            else (
                                raw_tool[0] if isinstance(raw_tool, list) and raw_tool else raw_tool
                            )
                        )
                        logger.warning(f"[LLM_PARSE] Unknown tool '{bad}' rejected")
                        return AgentFinish(
                            output=f'Доступны только: finish, read_file, list_directory, run_terminal_cmd, ssh_run. Ты указал: {bad}. Ответь одним JSON с tool: finish и tool_input: {{"output": "твой краткий ответ"}}.',
                            thought=thought,
                        )
                    if blocked_tools and tool_name in blocked_tools:
                        logger.warning(
                            f"[LLM_PARSE] Blocked tool '{tool_name}' rejected (cycle prevention)"
                        )
                        allowed = sorted(ALLOWED_TOOLS - set(blocked_tools))
                        return AgentFinish(
                            output=f"Инструмент {tool_name} заблокирован из-за цикла. Используй только: {', '.join(allowed)}. Ответь JSON с tool: finish или другим доступным инструментом.",
                            thought=thought,
                        )
                    if data["tool"] == "finish" or (data.get("tool") == "" and not tool_input):
                        out = (
                            (tool_input.get("output") if tool_input else None)
                            or thought
                            or "Готово"
                        )
                        logger.info(f"[LLM_PARSE] Returning AgentFinish: {str(out)[:100]}...")
                        return AgentFinish(
                            output=out if isinstance(out, str) else str(out), thought=thought
                        )
                    if tool_input is not None:
                        logger.info(
                            f"[LLM_PARSE] Returning AgentAction: tool={tool_name}, input={str(tool_input)[:100]}"
                        )
                        return AgentAction(
                            tool=tool_name, tool_input=data["tool_input"], thought=thought
                        )

                # Ищем инструмент во вложенных полях (action, next_step, step)
                for key in ["action", "next_step", "step"]:
                    if key in data and isinstance(data[key], dict):
                        nested = data[key]
                        if "tool" in nested and "tool_input" in nested:
                            logger.info(
                                f"[LLM_PARSE] Found nested tool in '{key}': {nested['tool']}"
                            )
                            return AgentAction(
                                tool=str(nested["tool"]),
                                tool_input=nested["tool_input"],
                                thought=thought,
                            )
                        if "command" in nested:
                            host = nested.get("host", "185.177.216.15")
                            logger.info(
                                f"[LLM_PARSE] Found nested command in '{key}': {nested['command'][:50]}"
                            )
                            return AgentAction(
                                tool="ssh_run",
                                tool_input={"host": host, "command": nested["command"]},
                                thought=thought,
                            )

                # Исправляем галлюцинации формата (если есть command вместо tool)
                if "command" in data:
                    host = data.get("host", "185.177.216.15")
                    logger.info(f"[LLM_PARSE] Found top-level command: {data['command'][:50]}")
                    return AgentAction(
                        tool="ssh_run",
                        tool_input={"host": host, "command": data["command"]},
                        thought=thought,
                    )

                # Если это любой другой JSON
                msg = data.get("response") or data.get("message") or data.get("output") or str(data)
                logger.info(f"[LLM_PARSE] Returning generic JSON response: {str(msg)[:100]}")
                return AgentFinish(output=msg, thought=thought)
            else:
                logger.warning("[LLM_PARSE] No JSON block found in content")

        except Exception as e:
            logger.error(f"[LLM_PARSE] ❌ Ошибка парсинга: {e}")
            logger.error(f"[LLM_PARSE] Content was: {content[:500]}")
            return AgentFinish(output=clean_content, thought=f"Parser Error: {str(e)}")

        # Если не JSON или парсинг не удался - возвращаем как есть
        logger.info("[LLM_PARSE] Returning raw text response")
        return AgentFinish(output=clean_content, thought="Текстовый ответ")
