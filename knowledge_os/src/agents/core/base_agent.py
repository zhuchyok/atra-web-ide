import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

# Настройка логирования для терминала
logger = logging.getLogger(__name__)


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
        # Временно заблокированные инструменты (цикл): tool_name -> step до которого блок
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

    async def run(
        self, goal: str, max_steps: int = 500, blocked_tools: Optional[List[str]] = None
    ) -> str:
        logger.info(f"\n🚀 ЗАДАЧА: {goal}")
        self._blocked_tools.clear()

        if blocked_tools:
            for tool in blocked_tools:
                self._blocked_tools[tool] = max_steps + 1
            logger.info(f"🔒 Заблокированы инструменты: {', '.join(blocked_tools)}")

        # Мы не стираем память полностью, а добавляем контекст знаний
        knowledge_context = self._get_context_summary()
        self.memory = [
            {"role": "system", "content": f"Ты уже знаешь следующее о проекте: {knowledge_context}"}
        ]

        current_input = goal
        steps_taken = 0

        while steps_taken < max_steps:
            steps_taken += 1
            logger.info(f"\n--- ШАГ {steps_taken} ---")

            result = await self.step(
                current_input,
                step_number=steps_taken,
                blocked_tools=self._get_blocked_tools_for_step(steps_taken),
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
                self.memory.append(
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
                # Генерируем хэш команды для проверки на циклы
                cmd_hash = f"{result.tool}:{json.dumps(result.tool_input, sort_keys=True)}"
                if self.executed_commands_hash.count(cmd_hash) >= 2:
                    block_until = steps_taken + 5
                    self._blocked_tools[result.tool] = block_until
                    logger.warning(
                        "⚠️ ОСТАНОВКА: Ты повторяешь команду %s уже 3-й раз с теми же аргументами. СМЕНИ СТРАТЕГИЮ!",
                        result.tool,
                    )
                    logger.warning(
                        "🔒 Блокируем %s до шага %s. Принудительное завершение.",
                        result.tool,
                        block_until,
                    )
                    return "Обнаружен цикл повторяющихся действий. Задача не может быть выполнена текущими средствами. Смени стратегию или используй другой инструмент (read_file, finish и т.д.)."
                if (
                    result.tool in self._blocked_tools
                    and steps_taken <= self._blocked_tools[result.tool]
                ):
                    self.memory.append(
                        {
                            "role": "user",
                            "content": f"Инструмент {result.tool} заблокирован. Выбери другой или finish.",
                        }
                    )
                    current_input = self.memory[-1]["content"]
                    continue
                self.executed_commands_hash.append(cmd_hash)
                print(f"🛠  Инструмент: {result.tool}")
                print(
                    f"📝 Аргументы: {json.dumps(result.tool_input, indent=2, ensure_ascii=False)}"
                )

                if result.tool in self.tools:
                    try:
                        observation = await self.tools[result.tool](**result.tool_input)
                        obs_str = str(observation)
                        print(
                            f"👀 Результат: {obs_str[:300]}..."
                            if len(obs_str) > 300
                            else f"👀 Результат: {obs_str}"
                        )

                        self.memory.append(
                            {
                                "role": "user",
                                "content": f"Observation from {result.tool}: {observation}",
                            }
                        )
                        current_input = "Результат получен. Продолжай выполнение задачи."
                    except Exception as e:
                        error_msg = f"Ошибка при вызове {result.tool}: {str(e)}"
                        logger.error(f"❌ {error_msg}")
                        self.memory.append({"role": "user", "content": error_msg})
                        current_input = f"Произошла ошибка: {error_msg}. Попробуй другой способ."
                else:
                    error_msg = f"Инструмент {result.tool} не найден."
                    logger.error(f"❌ {error_msg}")
                    self.memory.append({"role": "user", "content": error_msg})
                    current_input = f"Ошибка: инструмента {result.tool} не существует. Используй только доступные инструменты."

        return f"Превышен лимит шагов ({max_steps}). Упростите запрос или разбейте задачу на части."
