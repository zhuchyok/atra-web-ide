import aiohttp
import asyncio
import json
import logging
import os
import time
import traceback
from typing import List, Dict, Any, Optional, Tuple
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
    "phi3.5:3.8b",      # Fast, stable
    "tinyllama:1.1b-chat",  # Very small, always works
    "glm-4.7-flash:q8_0",   # Medium, good quality
    "qwen2.5-coder:32b",    # Large, may crash on limited RAM
]

FALLBACK_MODELS_MLX = [
    "phi3.5:3.8b",
    "qwen2.5:3b",
    "tinyllama:1.1b-chat",
    "phi3:mini-4k",
    "qwen2.5-coder:32b",
]

# Models that are known to crash on resource-limited systems
RESOURCE_HEAVY_MODELS = {
    "qwen2.5-coder:32b", "qwq:32b", "deepseek-r1-distill-llama:70b", 
    "llama3.3:70b", "command-r-plus:104b"
}

def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL") or os.getenv("MAC_STUDIO_LLM_URL") or "http://localhost:11434"

def _mlx_base_url() -> str:
    """Get MLX API Server URL (default: 11435)"""
    is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
    if is_docker:
        return os.getenv("MLX_BASE_URL", "http://host.docker.internal:11435")
    return os.getenv("MLX_BASE_URL", "http://localhost:11435")


class OllamaExecutor:
    """Исполнитель запросов к Ollama / MLX API с автоматическим fallback"""
    
    def __init__(self, model: str = None, base_url: Optional[str] = None):
        # Автовыбор модели: если не указана, будет выбрана при первом запросе через сканирование Ollama
        self.model = model or os.getenv("VICTORIA_MODEL") or os.getenv("VERONICA_MODEL") or "auto"
        self.base_url = base_url or _ollama_base_url()
        self._model_resolved = False  # Флаг: модель уже выбрана из актуального списка
        
        # === FALLBACK CONFIGURATION ===
        self._failed_models: set = set()  # Models that have failed in this session
        self._fallback_attempts = 0
        self._max_fallback_attempts = 3
        self._last_successful_model: Optional[str] = None
        
        # MLX URL for fallback
        self._mlx_url = _mlx_base_url()
        self._use_mlx_fallback = os.getenv("USE_MLX_FALLBACK", "true").lower() == "true"
        
        logger.info(f"[EXECUTOR_INIT] ========== OllamaExecutor initialization ==========")
        logger.info(f"[EXECUTOR_INIT] Primary model: {self.model}")
        logger.info(f"[EXECUTOR_INIT] Ollama URL: {self.base_url}")
        logger.info(f"[EXECUTOR_INIT] MLX URL: {self._mlx_url}")
        logger.info(f"[EXECUTOR_INIT] MLX fallback enabled: {self._use_mlx_fallback}")
        
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
                        models = [m.get('name', '') for m in data.get('models', [])]
                        return model in models or any(model in m for m in models)
        except Exception as e:
            logger.debug(f"[MODEL_CHECK] Failed to check {model} on {base_url}: {e}")
        return False

    async def _get_fallback_model(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get next available fallback model.
        Returns: (model_name, base_url) or (None, None) if no fallback available
        """
        logger.info(f"[FALLBACK] ========== Finding fallback model ==========")
        logger.info(f"[FALLBACK] Failed models this session: {self._failed_models}")
        logger.info(f"[FALLBACK] Fallback attempts: {self._fallback_attempts}/{self._max_fallback_attempts}")
        
        if self._fallback_attempts >= self._max_fallback_attempts:
            logger.error(f"[FALLBACK] Max fallback attempts reached ({self._max_fallback_attempts})")
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
        
        logger.error(f"[FALLBACK] ❌ No available fallback models found")
        return None, None

    async def ask(
        self,
        prompt: str,
        history: List[Dict[str, str]] = None,
        raw_response: bool = False,
        phase: Optional[str] = None,
        blocked_tools: Optional[List[str]] = None,
        model: Optional[str] = None,
        system: Optional[str] = None,
    ) -> Any:
        """
        Send request to LLM with automatic fallback on model crash.
        phase: опционально — понимание цели / план / шаг N, логируется при таймауте.
        blocked_tools: инструменты, которые нельзя выбирать (заблокированы из-за цикла).
        model: переопределить модель для этого запроса.
        system: переопределить системный промпт.
        """
        return await self._ask_with_fallback(
            prompt=prompt,
            history=history,
            raw_response=raw_response,
            model=model or self.model,
            base_url=self.base_url,
            is_retry=False,
            phase=phase,
            blocked_tools=blocked_tools,
            system_override=system,
        )

    async def _ask_with_fallback(
        self,
        prompt: str,
        history: List[Dict[str, str]],
        raw_response: bool,
        model: str,
        base_url: str,
        is_retry: bool = False,
        phase: Optional[str] = None,
        blocked_tools: Optional[List[str]] = None,
        system_override: Optional[str] = None,
    ) -> Any:
        """Internal method with fallback support"""
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
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": { "temperature": 0.1 }
        }
        # Адаптивный keep_alive на основе веса модели (Singularity 10.0)
        def get_smart_keep_alive(m_name: str) -> Any:
            raw = os.getenv("VICTORIA_OLLAMA_KEEP_ALIVE") or os.getenv("OLLAMA_KEEP_ALIVE")
            if raw:
                try:
                    return int(raw) if str(raw).strip().lstrip("-").isdigit() else raw
                except: return raw
            
            key = (m_name or "").lower()
            if "70b" in key or "104b" in key or "next" in key: return 60
            if "32b" in key or "30b" in key or "qwq" in key: return 300
            if "7b" in key or "8b" in key or "14b" in key: return 600
            if "3b" in key or "1b" in key or "tiny" in key or "embedding" in key: return 3600
            return 300

        payload["keep_alive"] = get_smart_keep_alive(model)
        
        # === DETAILED DEBUG LOGGING ===
        logger.info(f"[LLM_CALL] ========== OllamaExecutor.ask() ==========")
        logger.info(f"[LLM_CALL] Model: {model}")
        logger.info(f"[LLM_CALL] URL: {url}")
        logger.info(f"[LLM_CALL] Is retry/fallback: {is_retry}")
        logger.info(f"[LLM_CALL] Failed models this session: {self._failed_models}")
        logger.info(f"[LLM_CALL] Prompt length: {len(prompt)} chars")
        logger.info(f"[LLM_CALL] Prompt preview: {prompt[:200]}...")
        if VICTORIA_DEBUG:
            logger.debug(f"[LLM_CALL] Full payload: {json.dumps(payload, ensure_ascii=False)[:1000]}")
        
        start_time = time.time()
        
        # Таймаут на один вызов LLM: настраивается через OLLAMA_EXECUTOR_TIMEOUT (по умолчанию 300 с)
        # connect=30 — стабильность из контейнера к host.docker.internal (не обрывать долгие ответы)
        _exec_timeout = float(os.getenv("OLLAMA_EXECUTOR_TIMEOUT", "300"))
        timeout = aiohttp.ClientTimeout(total=_exec_timeout, connect=30.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                logger.info(f"[LLM_CALL] Sending request to {url}...")
                async with session.post(url, json=payload) as response:
                    elapsed = time.time() - start_time
                    logger.info(f"[LLM_RESPONSE] HTTP Status: {response.status}, Time: {elapsed:.2f}s")
                    
                    if response.status == 200:
                        result = await response.json()
                        content = result.get('message', {}).get('content', '')
                        
                        # === SUCCESS LOGGING ===
                        logger.info(f"[LLM_RESPONSE] ✅ Success!")
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
                            "Metal error"
                        ]
                        
                        is_crash = any(ind.lower() in error_body.lower() for ind in crash_indicators)
                        
                        if is_crash or response.status == 500:
                            logger.warning(f"[LLM_CRASH] ⚠️ Model {model} crashed! Attempting fallback...")
                            self._failed_models.add(model)
                            self._fallback_attempts += 1
                            
                            # Try fallback
                            fallback_model, fallback_url = await self._get_fallback_model()
                            if fallback_model and fallback_url:
                                logger.info(f"[LLM_FALLBACK] 🔄 Retrying with model: {fallback_model} on {fallback_url}")
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
                    elapsed, model, phase_info,
                )
                
                # Timeout on large model - try fallback
                if model in RESOURCE_HEAVY_MODELS:
                    logger.warning(f"[LLM_TIMEOUT] Large model {model} timed out, trying fallback...")
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
                    logger.info(f"[LLM_FALLBACK] Ollama connection failed, trying MLX...")
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

    def _parse_response(self, content: str, blocked_tools: Optional[List[str]] = None) -> Any:
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
            except:
                pass

        # Пробуем распарсить как JSON
        try:
            start_idx = clean_content.find('{')
            end_idx = clean_content.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = clean_content[start_idx:end_idx+1]
                logger.info(f"[LLM_PARSE] Found JSON block at [{start_idx}:{end_idx+1}]")
                
                # Пытаемся распарсить как стандартный JSON
                try:
                    data = json.loads(json_str)
                    logger.info(f"[LLM_PARSE] JSON parsed successfully, keys: {list(data.keys())}")
                except json.JSONDecodeError as je:
                    logger.warning(f"[LLM_PARSE] JSON decode failed: {je}, trying ast.literal_eval")
                    # Если модель выдала одинарные кавычки (Python style), пробуем исправить
                    import ast
                    try:
                        data = ast.literal_eval(json_str)
                        logger.info(f"[LLM_PARSE] ast.literal_eval succeeded")
                    except Exception as ae:
                        # Если совсем всё плохо - возвращаем как текст для разбора Агентом
                        logger.error(f"[LLM_PARSE] Failed to parse JSON: {ae}")
                        logger.error(f"[LLM_PARSE] Raw JSON string: {json_str[:500]}")
                        return AgentFinish(output=clean_content, thought="Failed to parse JSON")
                
                thought = data.get("thought", "Рассуждаю...")
                tool_input = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}

                # Чужой формат (tool_execution, final_output) — не наш API, завершаем с подсказкой
                if "tool_execution" in data or "final_output" in data:
                    logger.warning(f"[LLM_PARSE] Invalid format detected: tool_execution/final_output")
                    return AgentFinish(
                        output="Используй только формат: {\"thought\": \"...\", \"tool\": \"один из: finish, read_file, list_directory, run_terminal_cmd, ssh_run\", \"tool_input\": {...}}. Других полей нет.",
                        thought=thought,
                    )

                # Если это наш формат
                if "tool" in data and "tool_input" in data:
                    raw_tool = data.get("tool")
                    tool_name = str(raw_tool).strip().lower() if raw_tool and not isinstance(raw_tool, list) else ""
                    # tool как массив или неизвестный инструмент — отклоняем (мировая практика: strict schema)
                    if isinstance(raw_tool, list):
                        tool_name = (raw_tool[0] if raw_tool else "") or "unknown"
                    
                    logger.info(f"[LLM_PARSE] Detected tool: '{tool_name}', thought: '{thought[:50]}...'")
                    
                    if tool_name not in ALLOWED_TOOLS:
                        bad = raw_tool if isinstance(raw_tool, str) else (raw_tool[0] if isinstance(raw_tool, list) and raw_tool else raw_tool)
                        logger.warning(f"[LLM_PARSE] Unknown tool '{bad}' rejected")
                        return AgentFinish(
                            output=f"Доступны только: finish, read_file, list_directory, run_terminal_cmd, ssh_run. Ты указал: {bad}. Ответь одним JSON с tool: finish и tool_input: {{\"output\": \"твой краткий ответ\"}}.",
                            thought=thought,
                        )
                    if blocked_tools and tool_name in blocked_tools:
                        logger.warning(f"[LLM_PARSE] Blocked tool '{tool_name}' rejected (cycle prevention)")
                        allowed = sorted(ALLOWED_TOOLS - set(blocked_tools))
                        return AgentFinish(
                            output=f"Инструмент {tool_name} заблокирован из-за цикла. Используй только: {', '.join(allowed)}. Ответь JSON с tool: finish или другим доступным инструментом.",
                            thought=thought,
                        )
                    if data["tool"] == "finish" or (data.get("tool") == "" and not tool_input):
                        out = (tool_input.get("output") if tool_input else None) or thought or "Готово"
                        logger.info(f"[LLM_PARSE] Returning AgentFinish: {str(out)[:100]}...")
                        return AgentFinish(output=out if isinstance(out, str) else str(out), thought=thought)
                    if tool_input is not None:
                        logger.info(f"[LLM_PARSE] Returning AgentAction: tool={tool_name}, input={str(tool_input)[:100]}")
                        return AgentAction(tool=tool_name, tool_input=data["tool_input"], thought=thought)
                
                # Ищем инструмент во вложенных полях (action, next_step, step)
                for key in ["action", "next_step", "step"]:
                    if key in data and isinstance(data[key], dict):
                        nested = data[key]
                        if "tool" in nested and "tool_input" in nested:
                            logger.info(f"[LLM_PARSE] Found nested tool in '{key}': {nested['tool']}")
                            return AgentAction(tool=str(nested["tool"]), tool_input=nested["tool_input"], thought=thought)
                        if "command" in nested:
                            host = nested.get("host", "185.177.216.15")
                            logger.info(f"[LLM_PARSE] Found nested command in '{key}': {nested['command'][:50]}")
                            return AgentAction(tool="ssh_run", tool_input={"host": host, "command": nested["command"]}, thought=thought)

                # Исправляем галлюцинации формата (если есть command вместо tool)
                if "command" in data:
                    host = data.get("host", "185.177.216.15")
                    logger.info(f"[LLM_PARSE] Found top-level command: {data['command'][:50]}")
                    return AgentAction(tool="ssh_run", tool_input={"host": host, "command": data["command"]}, thought=thought)

                # Если это любой другой JSON
                msg = data.get("response") or data.get("message") or data.get("output") or str(data)
                logger.info(f"[LLM_PARSE] Returning generic JSON response: {str(msg)[:100]}")
                return AgentFinish(output=msg, thought=thought)
            else:
                logger.warning(f"[LLM_PARSE] No JSON block found in content")
            
        except Exception as e:
            logger.error(f"[LLM_PARSE] ❌ Ошибка парсинга: {e}")
            logger.error(f"[LLM_PARSE] Content was: {content[:500]}")
            return AgentFinish(output=clean_content, thought=f"Parser Error: {str(e)}")
            
        # Если не JSON или парсинг не удался - возвращаем как есть
        logger.info(f"[LLM_PARSE] Returning raw text response")
        return AgentFinish(output=clean_content, thought="Текстовый ответ")
