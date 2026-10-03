import asyncio
import hashlib
import copy
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

# После 3+ повторений одного инструмента с теми же аргументами — принудительное завершение (мировая практика: разрыв цикла)
LOOP_BLOCK_STEPS = 5

# Настройка логирования для терминала
logger = logging.getLogger(__name__)
DEFAULT_TOOL_TIMEOUT_SEC = float(os.getenv("AGENT_TOOL_TIMEOUT_SEC", "30"))
WEB_TOOL_TIMEOUT_SEC = float(os.getenv("AGENT_WEB_TOOL_TIMEOUT_SEC", "20"))
DATA_TOOL_TIMEOUT_SEC = float(os.getenv("AGENT_DATA_TOOL_TIMEOUT_SEC", "20"))
GIT_TOOL_TIMEOUT_SEC = float(os.getenv("AGENT_GIT_TOOL_TIMEOUT_SEC", "30"))
TOOL_RETRY_ATTEMPTS = max(1, int(os.getenv("AGENT_TOOL_RETRY_ATTEMPTS", "2")))
TOOL_RETRY_DELAY_SEC = float(os.getenv("AGENT_TOOL_RETRY_DELAY_SEC", "0.4"))


class AgentAction(BaseModel):
    """Структура действия агента"""

    tool: str
    tool_input: Dict[str, Any]
    thought: str


class AgentFinish(BaseModel):
    """Структура завершения работы агента"""

    output: Any  # Изменено на Any для гибкости
    thought: str


class AtraBaseAgent(ABC):
    """
    Базовый класс для всех автономных агентов ATRA.
    """

    def __init__(self, name: str, model_name: str = None):
        self.name = name
        # Автовыбор модели: None = сканирование Ollama при первом запросе
        self.model_name = model_name or "auto"
        self.memory: List[Dict[str, str]] = []
        self.tools: Dict[str, Any] = {}
        # История выполненных команд для предотвращения циклов
        self.executed_commands_hash: List[str] = []
        # Временно заблокированные инструменты: tool_name -> step_number до которого блок (включительно)
        self._blocked_tools: Dict[str, int] = {}
        # Долгосрочные знания о проекте, которые не стираются между run()
        self.project_knowledge: Dict[str, Any] = {
            "files_found": [],
            "server_status": {},
            "last_errors": [],
            "database_schema": {},
        }

    def add_tool(self, name: str, func: Any):
        self.tools[name] = func

    @abstractmethod
    async def plan(self, goal: str) -> List[str]:
        pass

    def _get_blocked_tools_for_step(self, step_number: int) -> List[str]:
        """Список инструментов, заблокированных на текущем шаге (для передачи в промпт executor)."""
        return [t for t, until in self._blocked_tools.items() if until >= step_number]

    @abstractmethod
    async def step(
        self, prompt: str, step_number: int = 1, blocked_tools: Optional[List[str]] = None
    ) -> Union[AgentAction, AgentFinish, Dict[str, Any]]:
        """step_number — номер шага в run(), передаётся для логов при таймауте. blocked_tools — исключить из выбора модели."""
        pass

    def _get_context_summary(self) -> str:
        """Формирует краткую сводку накопленных знаний для промпта"""
        summary = "\n--- НАКОПЛЕННЫЕ ЗНАНИЯ (Project Knowledge) ---\n"
        if self.project_knowledge["files_found"]:
            summary += f"Файлы: {', '.join(self.project_knowledge['files_found'][:10])}\n"
        if self.project_knowledge["database_schema"]:
            summary += f"Схема БД: {json.dumps(self.project_knowledge['database_schema'])}\n"
        if self.project_knowledge["server_status"]:
            summary += f"Серверы: {json.dumps(self.project_knowledge['server_status'])}\n"
        return summary

    @staticmethod
    def _tool_timeout_for(tool_name: str) -> float:
        if tool_name == "web_search":
            return WEB_TOOL_TIMEOUT_SEC
        if tool_name == "db_query":
            return DATA_TOOL_TIMEOUT_SEC
        if tool_name.startswith("git_"):
            return GIT_TOOL_TIMEOUT_SEC
        return DEFAULT_TOOL_TIMEOUT_SEC

    @staticmethod
    def _is_retryable_tool_error(tool_name: str, text: str) -> bool:
        if not text:
            return False
        msg = text.lower()
        retry_markers = (
            "timeout",
            "timed out",
            "temporarily",
            "try again",
            "connection reset",
            "connection refused",
            "service unavailable",
            "502",
            "503",
            "504",
            "network",
        )
        # Tool contract: retries are mainly for web/git/sql classes.
        if tool_name == "web_search" or tool_name == "db_query" or tool_name.startswith("git_"):
            return any(marker in msg for marker in retry_markers)
        return False

    @staticmethod
    def _make_tool_audit(tool_name: str, tool_input: Dict[str, Any], latency_ms: int, status: str) -> Dict[str, Any]:
        args_raw = json.dumps(tool_input or {}, sort_keys=True, ensure_ascii=False)
        return {
            "tool": tool_name,
            "args_hash": hashlib.sha1(args_raw.encode("utf-8")).hexdigest(),
            "latency_ms": latency_ms,
            "status": status,
            "ts_ms": int(time.time() * 1000),
        }

    async def _call_tool_with_policy(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        timeout_sec = self._tool_timeout_for(tool_name)
        attempts_total = TOOL_RETRY_ATTEMPTS
        last_error = ""
        start_total = time.monotonic()

        for attempt in range(1, attempts_total + 1):
            call_started = time.monotonic()
            try:
                raw_result = await asyncio.wait_for(
                    self.tools[tool_name](**tool_input),
                    timeout=timeout_sec,
                )
                result_text = str(raw_result)
                if self._is_retryable_tool_error(tool_name, result_text) and attempt < attempts_total:
                    last_error = result_text
                    await asyncio.sleep(TOOL_RETRY_DELAY_SEC)
                    continue
                latency_ms = int((time.monotonic() - call_started) * 1000)
                status = "error" if result_text.lower().startswith(("error", "ошибка", "exception")) else "ok"
                payload: Dict[str, Any] = {
                    "tool": tool_name,
                    "status": status,
                    "audit": self._make_tool_audit(tool_name, tool_input, latency_ms, status),
                }
                payload["audit"]["attempt"] = attempt
                payload["audit"]["attempts_total"] = attempts_total
                payload["audit"]["timeout_sec"] = timeout_sec
                if status == "ok":
                    payload["tool_result"] = result_text
                else:
                    payload["tool_error"] = result_text
                return payload
            except asyncio.TimeoutError:
                last_error = f"Tool timeout after {int(timeout_sec)}s"
                if attempt < attempts_total:
                    await asyncio.sleep(TOOL_RETRY_DELAY_SEC)
                    continue
            except Exception as e:
                last_error = str(e)
                if self._is_retryable_tool_error(tool_name, last_error) and attempt < attempts_total:
                    await asyncio.sleep(TOOL_RETRY_DELAY_SEC)
                    continue
                break

        total_latency = int((time.monotonic() - start_total) * 1000)
        audit = self._make_tool_audit(tool_name, tool_input, total_latency, "error")
        audit["attempt"] = attempts_total
        audit["attempts_total"] = attempts_total
        audit["timeout_sec"] = timeout_sec
        return {
            "tool": tool_name,
            "status": "error",
            "tool_error": last_error or "Unknown tool execution error",
            "audit": audit,
        }

    async def run(self, goal: str, max_steps: int = 500) -> str:
        logger.info(f"\n🚀 ЗАДАЧА: {goal}")
        # [v149.13] Per-run изоляция: агент — синглтон, и конкурентные run() затирали
        # друг другу self.memory/_blocked_tools (чужой контекст → чужой ответ).
        # Решение по мировой практике: shallow-клон на запуск (executors/planner общие,
        # они stateless; память и блокировки — свои у каждого run).
        agent = copy.copy(self)
        agent._blocked_tools = {}
        agent.executed_commands_hash = []

        # Мы не стираем память полностью, а добавляем контекст знаний
        knowledge_context = agent._get_context_summary()
        agent.memory = [
            {"role": "system", "content": f"Ты уже знаешь следующее о проекте: {knowledge_context}"}
        ]

        current_input = goal
        steps_taken = 0

        while steps_taken < max_steps:
            steps_taken += 1
            logger.info("[TRACE] run: step %s (max %s)", steps_taken, max_steps)
            logger.info(f"\n--- ШАГ {steps_taken} ---")

            result = await agent.step(
                current_input,
                step_number=steps_taken,
                blocked_tools=agent._get_blocked_tools_for_step(steps_taken),
            )

            # Если возникла ошибка в step (не JSON и т.д.)
            if isinstance(result, dict) and "error" in result:
                logger.error(f"❌ Ошибка шага: {result['error']}")
                return f"Сбой агента: {result['error']}"

            # Сохраняем ответ в память
            if isinstance(result, (AgentAction, AgentFinish)):
                content_to_save = {
                    "thought": result.thought,
                    "tool": getattr(result, "tool", "finish"),
                    "tool_input": getattr(result, "tool_input", {}),
                }
                agent.memory.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(content_to_save, ensure_ascii=False),
                    }
                )

                print(f"🤔 Мысль: {result.thought}")

            # Финал
            if isinstance(result, AgentFinish):
                logger.info("✅ Готово!")
                return str(result.output)

            # Действие
            if isinstance(result, AgentAction):
                # Автоматическая коррекция: ssh_run для локальных команд → run_terminal_cmd
                if result.tool == "ssh_run" and result.tool_input:
                    command = result.tool_input.get("command", "")
                    host = result.tool_input.get("host", "")
                    # Локальные команды (docker exec, ls, cat, find, pwd и т.д.)
                    local_commands = ["docker exec", "ls", "cat", "find", "pwd", "grep", "echo"]
                    if any(cmd in command for cmd in local_commands) or host in [
                        "localhost",
                        "127.0.0.1",
                    ]:
                        logger.warning(
                            "⚠️ Автокоррекция: ssh_run → run_terminal_cmd для локальной команды"
                        )
                        result = AgentAction(
                            tool="run_terminal_cmd",
                            tool_input={"command": command},
                            thought=result.thought + " (исправлено: локальная команда)",
                        )

                # Генерируем хэш команды для проверки на циклы
                cmd_hash = f"{result.tool}:{json.dumps(result.tool_input, sort_keys=True)}"
                if agent.executed_commands_hash.count(cmd_hash) >= 2:
                    # Принудительная блокировка повторяющегося инструмента (разрыв цикла)
                    block_until = steps_taken + LOOP_BLOCK_STEPS
                    agent._blocked_tools[result.tool] = block_until
                    logger.warning(
                        "⚠️ ОСТАНОВКА: Ты повторяешь команду %s уже 3-й раз с теми же аргументами. СМЕНИ СТРАТЕГИЮ!",
                        result.tool,
                    )
                    logger.warning(
                        "🔒 Блокируем %s до шага %s. Принудительное завершение.",
                        result.tool,
                        block_until,
                    )
                    return "Обнаружен цикл повторяющихся действий. Задача не может быть выполнена текущими средствами. Смени стратегию или используй другой инструмент (например read_file для просмотра файла, finish для завершения)."
                # Проверка: модель вернула инструмент, который сейчас заблокирован (на случай если step() не исключил его из промпта)
                if (
                    result.tool in agent._blocked_tools
                    and steps_taken <= agent._blocked_tools[result.tool]
                ):
                    block_until = agent._blocked_tools[result.tool]
                    error_msg = (
                        f"Инструмент {result.tool} заблокирован до шага {block_until}. "
                        "Выбери другой: read_file, run_terminal_cmd, ssh_run, write_file или finish."
                    )
                    logger.warning("⚠️ %s", error_msg)
                    agent.memory.append({"role": "user", "content": error_msg})
                    current_input = error_msg
                    continue

                agent.executed_commands_hash.append(cmd_hash)
                # Нормализация: LLM может вернуть cmd вместо command для run_terminal_cmd
                tool_input = dict(result.tool_input) if result.tool_input else {}
                if (
                    result.tool == "run_terminal_cmd"
                    and "command" not in tool_input
                    and "cmd" in tool_input
                ):
                    tool_input["command"] = tool_input.pop("cmd", "")
                elif result.tool == "run_terminal_cmd" and "command" not in tool_input:
                    tool_input["command"] = tool_input.get("cmd", "")
                print(f"🛠  Инструмент: {result.tool}")
                print(f"📝 Аргументы: {json.dumps(tool_input, indent=2, ensure_ascii=False)}")

                if result.tool in agent.tools:
                    observation = await agent._call_tool_with_policy(result.tool, tool_input)
                    obs_payload = json.dumps(observation, ensure_ascii=False)
                    obs_preview = obs_payload if len(obs_payload) <= 300 else obs_payload[:300] + "..."
                    print(f"👀 Результат: {obs_preview}")
                    obs_for_memory = (
                        obs_payload if len(obs_payload) <= 3000 else obs_payload[:3000] + "...[truncated]"
                    )
                    agent.memory.append(
                        {
                            "role": "user",
                            "content": f"Observation from {result.tool}: {obs_for_memory}",
                        }
                    )
                    if observation.get("status") == "ok":
                        current_input = "Результат получен. Продолжай выполнение задачи."
                    else:
                        current_input = (
                            "Инструмент вернул ошибку. Проанализируй tool_error и выбери другой ход или исправь аргументы."
                        )
                else:
                    error_msg = f"Инструмент {result.tool} не найден."
                    logger.error(f"❌ {error_msg}")
                    missing_payload = {
                        "tool": result.tool,
                        "status": "error",
                        "tool_error": error_msg,
                        "audit": agent._make_tool_audit(result.tool, tool_input, 0, "error"),
                    }
                    agent.memory.append(
                        {
                            "role": "user",
                            "content": f"Observation from {result.tool}: {json.dumps(missing_payload, ensure_ascii=False)}",
                        }
                    )
                    current_input = f"Ошибка: инструмента {result.tool} не существует. Используй только доступные инструменты."

        return f"Превышен лимит шагов ({max_steps}). Упростите запрос или разбейте задачу на части."
