"""
ReAct Agent Framework - Reasoning + Acting для Victoria и Veronica
Основано на мировых практиках: Think → Act → Observe → Reflect
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Кэш «MLX rate limited»: после 429 от MLX пробуем Ollama первым 60 с (меньше повторных 429)
_mlx_rate_limited_until = 0.0

# Используем ТОЛЬКО MLX API Server (порт 11435)
# Ollama не используется - там нет моделей
MLX_URL = os.getenv("MLX_API_URL", "http://localhost:11435")
# Всегда используем MLX
DEFAULT_LLM_URL = MLX_URL


class ReActState(Enum):
    """Состояния ReAct цикла"""

    THINK = "think"
    ACT = "act"
    OBSERVE = "observe"
    REFLECT = "reflect"
    FINISH = "finish"
    ERROR = "error"


@dataclass
class ReActStep:
    """Один шаг ReAct цикла"""

    state: ReActState
    thought: str = ""
    action: Optional[str] = None
    action_input: Optional[Dict] = None
    result: Any = None  # Результат выполнения действия
    observation: Optional[str] = None
    reflection: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReActMemory:
    """Память ReAct агента"""

    steps: List[ReActStep] = field(default_factory=list)
    goal: str = ""
    current_state: ReActState = ReActState.THINK
    max_iterations: int = 10
    iteration: int = 0


class ReActAgent:
    """
    ReAct Agent - Reasoning + Acting Framework

    Цикл:
    1. Think - рассуждение о ситуации
    2. Act - выполнение инструментов
    3. Observe - обработка результатов
    4. Reflect - обновление понимания
    """

    def __init__(
        self,
        agent_name: str = "Виктория",
        model_name: str = "victoria-wisdom-v3.5:latest",  # Основная модель Виктории; qwq:32b слишком тяжёлая и блокирует Ollama для других запросов
        ollama_url: str = None,
        max_iterations: int = 10,
        system_prompt: Optional[str] = None,
        goal: Optional[str] = None,
    ):
        self.agent_name = agent_name
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.initial_goal = goal

        # Определяем правильные URL для Docker (Ollama и MLX)
        is_docker = (
            os.path.exists("/.dockerenv")
            or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
        )
        if is_docker:
            self.ollama_url = os.getenv("OLLAMA_API_URL", "http://host.docker.internal:11434")
            self.mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
        else:
            self.ollama_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
            self.mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")

        # Для обратной совместимости
        if ollama_url:
            self.ollama_url = ollama_url

        self.max_iterations = max_iterations
        self.memory = ReActMemory(max_iterations=max_iterations)

        # Инициализация Skill Registry для динамических tools
        self.skill_registry = None
        try:
            try:
                from skill_registry import get_skill_registry
            except ImportError:
                from app.skill_registry import get_skill_registry
            self.skill_registry = get_skill_registry()
            logger.info("✅ Skill Registry подключен к ReActAgent")
        except Exception as e:
            logger.warning(f"⚠️ Skill Registry недоступен: {e}")

        # Инициализация Sandbox Manager
        try:
            try:
                from sandbox_manager import get_sandbox_manager
            except ImportError:
                from app.sandbox_manager import get_sandbox_manager
            self.sandbox_manager = get_sandbox_manager()
            logger.info("✅ SandboxManager подключен к ReActAgent")
        except Exception as e:
            self.sandbox_manager = None
            logger.warning(f"⚠️ SandboxManager недоступен: {e}")

        # SafeFileWriter для create_file/write_file (бэкапы, проверка путей)
        try:
            try:
                from file_writer import SafeFileWriter
            except ImportError:
                from app.file_writer import SafeFileWriter
            self.file_writer = SafeFileWriter()
        except Exception as e:
            self.file_writer = None
            logger.warning(f"⚠️ SafeFileWriter недоступен, используется прямая запись: {e}")

        logger.info(
            f"✅ ReActAgent инициализирован: Ollama={self.ollama_url}, MLX={self.mlx_url}, модель={self.model_name}"
        )

    async def think(self, goal: str, context: Dict = None) -> str:
        """
        Think - рассуждение о текущей ситуации
        """
        print("DEBUG_PRINT: think() called")
        # Строим промпт для рассуждения
        prompt = self._build_think_prompt(goal, context)
        print(f"DEBUG_PRINT: think prompt built, length: {len(prompt)}")

        # Генерируем рассуждение через модель
        thought = await self._generate_response(prompt)
        print(f"DEBUG_PRINT: think response received, length: {len(thought) if thought else 0}")

        logger.info(f"🤔 [{self.agent_name}] Think: {thought[:100] if thought else 'None'}...")

        return thought

    def _get_relevant_tools(self, goal: str, all_tools: List[str]) -> List[str]:
        """
        [SINGULARITY 21.34] Progressive Tool Disclosure:
        Фильтрует список доступных инструментов на основе цели задачи для повышения точности.
        """
        goal_lower = goal.lower()

        # Если инструментов мало, отдаем все
        if len(all_tools) <= 5:
            return all_tools

        relevant = []

        # Группы инструментов
        fs_tools = [
            "read_file",
            "write_file",
            "edit_file",
            "list_files",
            "grep_search",
            "batch_read",
            "batch_grep",
            "apply_patch",
            "create_file",
        ]
        web_tools = ["web_search", "fetch_url", "searxng_search", "google_search"]
        system_tools = [
            "execute_command",
            "get_server_status",
            "restart_service",
            "docker_ps",
            "get_logs",
        ]

        # Логика фильтрации
        is_fs_task = any(
            kw in goal_lower
            for kw in [
                "файл",
                "код",
                "директори",
                "папк",
                "read",
                "write",
                "edit",
                "patch",
                "аудит",
                "file",
            ]
        )
        is_web_task = any(
            kw in goal_lower
            for kw in ["найти в сети", "поиск", "интернет", "url", "сайт", "web", "search"]
        )
        is_system_task = any(
            kw in goal_lower
            for kw in [
                "сервер",
                "процесс",
                "docker",
                "контейнер",
                "restart",
                "status",
                "command",
                "log",
            ]
        )

        if is_fs_task:
            relevant.extend([t for t in fs_tools if t in all_tools])
        if is_web_task:
            relevant.extend([t for t in web_tools if t in all_tools])
        if is_system_task:
            relevant.extend([t for t in system_tools if t in all_tools])

        # Всегда добавляем базовые инструменты
        base_tools = ["finish", "ask_question", "think", "delegate_task"]
        relevant.extend([t for t in base_tools if t in all_tools])

        # Если ничего не подошло, отдаем все (fallback)
        if not relevant:
            return all_tools

        # Удаляем дубликаты
        return list(set(relevant))

    async def act(self, thought: str, available_tools: List[str] = None) -> Tuple[str, Dict]:
        """
        Act - выбор и выполнение действия.
        Внедрен паттерн "Silent Thought" (Google Gemini): перед выбором инструмента агент
        проводит внутренний аудит безопасности и целесообразности.
        """
        if available_tools is None:
            # Используем динамические tools из Skill Registry если доступен
            if self.skill_registry:
                available_tools = [
                    skill.name
                    for skill in self.skill_registry.list_skills()
                    if skill.metadata.user_invocable
                ]
                logger.debug(
                    f"🔧 Используются динамические tools из Skill Registry: {len(available_tools)} skills"
                )
            else:
                # Fallback на статический список
                available_tools = [
                    "read_file",  # Чтение файлов
                    "run_terminal_cmd",  # Выполнение команд
                    "python-development",  # Выполнение Python кода (duckdb, pandas, анализ данных)
                    "list_directory",  # Список файлов
                    "create_file",  # Создание файлов
                    "write_file",  # Запись в файлы
                    "search_knowledge",  # Поиск в базе знаний
                    "finish",  # Завершение задачи
                ]

        # [SINGULARITY 21.34] Progressive Tool Disclosure
        available_tools = self._get_relevant_tools(self.initial_goal or "", available_tools)
        logger.info(
            f"🎯 [PROGRESSIVE DISCLOSURE] Filtered to {len(available_tools)} relevant tools"
        )

        # [SILENT THOUGHT] Внутренний аудит перед действием
        silent_audit_prompt = f"""Ты - Виктория. Перед тем как выбрать инструмент, проведи внутренний аудит.
Твоя мысль: {thought}
Доступные инструменты: {available_tools}

Проверь:
1. Безопасность: не повредит ли это действие систему?
2. Целесообразность: это кратчайший путь к цели?
3. Параметры: все ли данные у тебя есть?

Выдай краткий вердикт (только для внутреннего использования).
"""
        try:
            silent_audit = await self._generate_response(silent_audit_prompt, max_tokens=100)
            logger.info(f"🤫 [SILENT THOUGHT] Audit: {silent_audit.strip()}")
        except Exception as e:
            logger.debug(f"Silent thought failed: {e}")

        # Строим промпт для выбора действия
        prompt = self._build_act_prompt(thought, available_tools)

        # Генерируем действие через модель
        response = await self._generate_response(prompt)

        # Парсим действие из ответа
        action, action_input = self._parse_action(response, available_tools)

        logger.info(f"🎯 [{self.agent_name}] Act: {action} with {action_input}")

        return action, action_input

    async def observe(self, action: str, action_input: Dict, result: Any) -> str:
        """
        Observe - обработка результатов действия
        """
        # Формируем наблюдение
        observation = f"Действие '{action}' выполнено. Результат: {str(result)[:500]}"

        logger.info(f"👀 [{self.agent_name}] Observe: {observation[:100]}...")

        return observation

    async def reflect(self, goal: str, steps: List[ReActStep]) -> str:
        """
        Reflect - обновление понимания на основе всех шагов.
        Внедрена логика "Self-Correction" (OpenAI Pattern): если последнее действие
        было ошибочным, агент обязан проанализировать причину и предложить другой путь.
        """
        # Проверяем на наличие ошибок в последних шагах
        last_step = steps[-1] if steps else None
        error_context = ""
        if (
            last_step
            and last_step.observation
            and (
                "error" in last_step.observation.lower()
                or "failed" in last_step.observation.lower()
            )
        ):
            error_context = f"\nВНИМАНИЕ: Последнее действие '{last_step.action}' завершилось ошибкой. Проанализируй причину и предложи альтернативный вариант."

        # Строим промпт для рефлексии
        prompt = self._build_reflect_prompt(goal, steps)
        if error_context:
            prompt += error_context

        # Генерируем рефлексию
        reflection = await self._generate_response(prompt)

        logger.info(f"💭 [{self.agent_name}] Reflect: {reflection[:100]}...")

        return reflection

    async def run(self, goal: str, context: Dict = None) -> Dict:
        """
        Запустить полный ReAct цикл
        """
        print(f"DEBUG_PRINT: run() started for goal: {goal[:50]}")
        self.memory.goal = goal
        self.memory.current_state = ReActState.THINK
        self.memory.iteration = 0

        logger.info(f"🚀 [{self.agent_name}] Начинаю ReAct цикл для: {goal[:80]}")

        while self.memory.iteration < self.memory.max_iterations:
            self.memory.iteration += 1
            print(
                f"DEBUG_PRINT: Iteration {self.memory.iteration}, state: {self.memory.current_state}"
            )

            try:
                # 1. Think
                if self.memory.current_state == ReActState.THINK:
                    print("DEBUG_PRINT: Entering think state")
                    thought = await self.think(goal, context)
                    print(
                        f"DEBUG_PRINT: Think finished, thought length: {len(thought) if thought else 0}"
                    )
                    step = ReActStep(state=ReActState.THINK, thought=thought)
                    self.memory.steps.append(step)
                    self.memory.current_state = ReActState.ACT
                    print("DEBUG_PRINT: State changed to ACT")

                # 2. Act
                elif self.memory.current_state == ReActState.ACT:
                    print("DEBUG_PRINT: Entering act state")
                    last_step = self.memory.steps[-1]
                    action, action_input = await self.act(last_step.thought)
                    print(f"DEBUG_PRINT: Act finished, action: {action}")

                    # Проверяем, не финальное ли это действие
                    if action == "finish":
                        output_text = (action_input or {}).get(
                            "output", (action_input or {}).get("result", "")
                        )
                        if isinstance(output_text, str):
                            output_text = output_text.strip()
                        else:
                            output_text = str(output_text).strip() if output_text else ""
                        # Пустой output при finish: даём одну итерацию на исправление
                        if (
                            not output_text
                            and self.memory.iteration < self.memory.max_iterations - 1
                        ):
                            step = ReActStep(
                                state=ReActState.ACT, action=action, action_input=action_input
                            )
                            step.observation = (
                                "Задача не завершена: ты вызвал finish без параметра output. "
                                "ОБЯЗАТЕЛЬНО вызови finish снова с параметром output — краткое описание сделанного и, "
                                "если создавал файлы, пути к ним."
                            )
                            self.memory.steps.append(step)
                            self.memory.current_state = ReActState.REFLECT
                            continue
                        self.memory.current_state = ReActState.FINISH
                        step = ReActStep(
                            state=ReActState.ACT, action=action, action_input=action_input
                        )
                        step.observation = output_text  # чтобы Victoria Enhanced могла взять результат из последнего шага
                        self.memory.steps.append(step)
                        break

                    # Выполняем действие с логикой "At Most Once" (Perplexity Pattern)
                    # Если инструмент упал, мы даем одну попытку на самоисправление в Observe/Reflect,
                    # но не зацикливаемся на одной и той же ошибке.
                    try:
                        result = await self._execute_action(action, action_input)
                    except Exception as action_exc:
                        logger.warning(f"⚠️ Action {action} failed: {action_exc}")
                        result = f"Error executing {action}: {str(action_exc)}"

                    step = ReActStep(state=ReActState.ACT, action=action, action_input=action_input)
                    step.result = result  # Сохраняем результат для Observe
                    self.memory.steps.append(step)
                    self.memory.current_state = ReActState.OBSERVE

                # 3. Observe
                elif self.memory.current_state == ReActState.OBSERVE:
                    last_step = self.memory.steps[-1]
                    # Используем реальный результат из предыдущего шага
                    actual_result = getattr(last_step, "result", None) or "Результат получен"
                    observation = await self.observe(
                        last_step.action, last_step.action_input, actual_result
                    )

                    last_step.observation = observation
                    self.memory.current_state = ReActState.REFLECT

                # 4. Reflect
                elif self.memory.current_state == ReActState.REFLECT:
                    reflection = await self.reflect(goal, self.memory.steps)

                    last_step = self.memory.steps[-1]
                    last_step.reflection = reflection

                    # Решаем, продолжать или завершить
                    if self._should_finish(reflection):
                        self.memory.current_state = ReActState.FINISH
                        break
                    else:
                        self.memory.current_state = ReActState.THINK

                # 5. Finish
                elif self.memory.current_state == ReActState.FINISH:
                    break

            except Exception as e:
                import traceback

                error_details = traceback.format_exc()
                logger.error(f"❌ [{self.agent_name}] Ошибка в ReAct цикле: {e}\n{error_details}")
                self.memory.current_state = ReActState.ERROR
                break

        # Формируем финальный результат
        return self._build_result()

    def _build_think_prompt(self, goal: str, context: Dict = None) -> str:
        """Построить промпт для Think"""
        system_context = ""
        if self.system_prompt:
            system_context = f"{self.system_prompt}\n\n"

        try:
            from configs.victoria_common import PROMPT_RUSSIAN_ONLY
        except ImportError:
            PROMPT_RUSSIAN_ONLY = "КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском языке! Все ответы, объяснения и комментарии должны быть на русском!"

        # --- AI RESEARCH UPGRADE (Singularity 10.0) ---
        # Интегрируем принципы Anthropic, OpenAI и Google
        ai_research_principles = """
ПРИНЦИПЫ МЫШЛЕНИЯ (AI Research):
1. ПРЯМОТА И ЧЕСТНОСТЬ (OpenAI): Будь прямолинейна, избегай пустой лести. Если задача сложная или требует много времени, не проси подтверждения — делай максимум возможного прямо сейчас. Частичное выполнение лучше, чем уточняющие вопросы.
2. КРИТИЧЕСКОЕ МЫШЛЕНИЕ (Anthropic): Не соглашайся автоматически. Ставь под сомнение предпосылки, если это ведет к лучшему решению. Предлагай альтернативные точки зрения.
3. ТОЧНОСТЬ В ДЕТАЛЯХ (Google): При написании кода проявляй "архитектурное" внимание к деталям. Код должен быть не просто рабочим, а эстетичным и модульным.
4. КОНТРОЛЬ ОБЪЕМА (Yap Score): Твой целевой Yap Score = 8192 (будь максимально подробной и обстоятельной в анализе, но лаконичной в финальных инструкциях).
5. ЭФФЕКТИВНОСТЬ ПРАВОК (Aider): При редактировании существующих файлов ВСЕГДА предпочитай инструмент smart-patch вместо полной перезаписи. Это экономит ресурсы и предотвращает ошибки парсинга.
6. ЦЕПОЧКА РАССУЖДЕНИЙ: Всегда начинай с глубокого внутреннего анализа (Think), прежде чем переходить к действию (Act).
"""

        prompt = f"""{system_context}Ты - {self.agent_name}, эксперт по решению задач.

{PROMPT_RUSSIAN_ONLY}

{ai_research_principles}

ЦЕЛЬ: {goal}
"""

        if context:
            # Добавляем историю чата если есть
            if isinstance(context, dict) and "chat_history" in context:
                prompt += f"ИСТОРИЯ ЧАТА (для контекста):\n{context['chat_history']}\n\n"
            else:
                prompt += f"КОНТЕКСТ:\n{context}\n\n"

        if self.memory.steps:
            prompt += "ИСТОРИЯ ШАГОВ:\n"
            for i, step in enumerate(self.memory.steps[-3:], 1):  # Последние 3 шага
                prompt += f"{i}. {step.state.value}: {step.thought[:200]}\n"
            prompt += "\n"

        # Проверяем, требует ли задача создания файлов
        file_creation_keywords = [
            "создай файл",
            "create_file",
            "write_file",
            "создай html",
            "создай сайт",
            "создай страницу",
            "напиши файл",
            ".html",
            ".py",
            ".js",
            "создай бота",
            "бота для телеграм",
            "aiogram",
            "пуллинг",
            "telegram bot",
        ]
        requires_file_creation = any(keyword in goal.lower() for keyword in file_creation_keywords)

        if requires_file_creation:
            prompt += """КРИТИЧЕСКИ ВАЖНО: Эта задача требует СОЗДАНИЯ ФАЙЛА!
Ты ДОЛЖЕН использовать инструмент create_file или write_file в следующем шаге Act.
НЕ завершай задачу (finish) пока файл не создан!

ПРОАНАЛИЗИРУЙ ситуацию и подумай:
1. Какой файл нужно создать?
2. Какое содержимое должно быть в файле?
3. Какой путь использовать для файла?

ТВОЕ РАССУЖДЕНИЕ:"""
        else:
            prompt += """ПРОАНАЛИЗИРУЙ ситуацию и подумай, что нужно сделать дальше.

ТВОЕ РАССУЖДЕНИЕ:"""

        return prompt

    def _build_act_prompt(self, thought: str, available_tools: List[str]) -> str:
        """Построить промпт для Act"""
        # Детальное описание инструментов
        tools_descriptions = {
            "read_file": "Читает содержимое файла. Параметры: file_path (путь к файлу)",
            "run_terminal_cmd": "Выполняет shell-команду в терминале. Параметры: command (команда для выполнения)",
            "python-development": "Выполняет Python код. Параметры: code (Python код для выполнения), file_path (необязательно, путь для сохранения скрипта). Используй для анализа данных, duckdb, pandas, pyarrow.",
            "execute_python": "Алиас python-development. Параметры: code (Python код), file_path (необязательно).",
            "list_directory": "Показывает список файлов в директории. Параметры: directory или path (путь к директории)",
            "create_file": "Создает НОВЫЙ файл с содержимым. Параметры: file_path (путь), content (содержимое)",
            "smart-patch": "Применяет точечные изменения к СУЩЕСТВУЮЩЕМУ файлу (SEARCH/REPLACE). Параметры: file_path (путь), patch_content (строка с блоками <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE). Используй для правок кода.",
            "write_file": "Записывает содержимое в файл (создает или перезаписывает). Параметры: file_path (путь), content (содержимое)",
            "search_knowledge": "Ищет информацию в базе знаний. Параметры: query (поисковый запрос)",
            "finish": "Завершает выполнение задачи. Параметры: output (обязательный — краткое описание выполненного и, при создании файлов, пути к ним). Не вызывай finish без output.",
        }

        tools_desc = "\n".join(
            [
                f"- {tool}: {tools_descriptions.get(tool, 'Описание недоступно')}"
                for tool in available_tools
            ]
        )

        # Проверяем, требует ли задача создания файлов
        file_creation_keywords = [
            "создай файл",
            "create_file",
            "write_file",
            "создай html",
            "создай сайт",
            "создай страницу",
            "напиши файл",
            ".html",
            ".py",
            ".js",
            "создай бота",
            "бота для телеграм",
            "aiogram",
            "пуллинг",
            "telegram bot",
        ]
        requires_file_creation = any(
            keyword in thought.lower() or keyword in self.memory.goal.lower()
            for keyword in file_creation_keywords
        )

        try:
            from configs.victoria_common import PROMPT_RUSSIAN_ONLY
        except ImportError:
            PROMPT_RUSSIAN_ONLY = "КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском языке! Все ответы должны быть на русском!"
        prompt = """Ты - {agent_name}.

{PROMPT_RUSSIAN_ONLY}

РАССУЖДЕНИЕ: {thought}

ДОСТУПНЫЕ ИНСТРУМЕНТЫ:
{tools_desc}

{file_creation_warning}

ВЫБЕРИ действие и верни ТОЛЬКО JSON в блоке ```json ... ``` (без лишнего текста):
```json
{{
  "action": "название_инструмента",
  "input": {{
    "параметр": "значение"
  }}
}}
```

{finish_warning}

ВАЖНО для create_file/write_file:
- Если создаешь HTML/код файл, ВСЁ содержимое должно быть в параметре "content"
- Используй экранирование для переносов строк: \\n
- Используй экранирование для кавычек: \\"
- Пример для HTML файла:
```json
{{
  "action": "create_file",
  "input": {{
    "file_path": "index.html",
    "content": "<!DOCTYPE html>\\n<html>\\n<head>\\n<title>Привет</title>\\n</head>\\n<body>\\n<h1>Привет от Victoria</h1>\\n</body>\\n</html>"
  }}
}}
```

Пример для простого файла:
```json
{{
  "action": "create_file",
  "input": {{
    "file_path": "test.txt",
    "content": "привет"
  }}
}}
```

Пример для выполнения команды:
```json
{{
  "action": "run_terminal_cmd",
  "input": {{
    "command": "ls -la"
  }}
}}
```

ТВОЙ ВЫБОР (верни ТОЛЬКО JSON в блоке ```json ... ```, ВСЁ содержимое файла в content):""".format(
            agent_name=self.agent_name,
            PROMPT_RUSSIAN_ONLY=PROMPT_RUSSIAN_ONLY,
            thought=thought,
            tools_desc=tools_desc,
            file_creation_warning="⚠️ КРИТИЧЕСКИ ВАЖНО: Эта задача требует СОЗДАНИЯ ФАЙЛА! Ты ДОЛЖЕН использовать create_file или write_file, НЕ finish! ⚠️"
            if requires_file_creation
            else "",
            finish_warning="🚫 ЗАПРЕЩЕНО использовать finish пока файл не создан! Используй create_file! 🚫"
            if requires_file_creation
            else "",
        )

        return prompt

    def _build_reflect_prompt(self, goal: str, steps: List[ReActStep]) -> str:
        """Построить промпт для Reflect"""
        prompt = f"""Ты - {self.agent_name}.

ЦЕЛЬ: {goal}

ВЫПОЛНЕННЫЕ ШАГИ:
"""

        for i, step in enumerate(steps, 1):
            prompt += f"\n{i}. {step.state.value.upper()}\n"
            if step.thought:
                prompt += f"   Мысль: {step.thought[:150]}\n"
            if step.action:
                prompt += f"   Действие: {step.action}\n"
            if step.observation:
                prompt += f"   Наблюдение: {step.observation[:150]}\n"

        # Рефлексия при ошибках: явно просим проанализировать и попробовать другой подход
        last_obs = (steps[-1].observation or "") if steps else ""
        has_error = (
            "Error:" in last_obs
            or "ошибка" in last_obs.lower()
            or "не удалось" in last_obs.lower()
            or "требуется одобрение" in last_obs.lower()
        )
        if has_error:
            prompt += """

ВНИМАНИЕ: Последнее действие вернуло ошибку. Проанализируй причину:
1. Что пошло не так?
2. Какой другой подход можно попробовать?
3. Нужно ли прочитать файл/каталог перед записью, выбрать другой путь или скорректировать действие?

ТВОЯ РЕФЛЕКСИЯ (с предложением исправления):"""
        else:
            prompt += """

ПРОАНАЛИЗИРУЙ прогресс и реши:
1. Достигнута ли цель?
2. Что нужно сделать дальше?
3. Есть ли ошибки, которые нужно исправить?

ТВОЯ РЕФЛЕКСИЯ:"""

        return prompt

    def _parse_action(self, response: str, available_tools: List[str]) -> Tuple[str, Dict]:
        """Парсить действие из ответа модели"""
        import json
        import re

        # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ для отладки
        try:
            logger.info(f"🔍 [ПАРСИНГ] Полный ответ модели (первые 500 символов): {response[:500]}")
            logger.info(f"🔍 [ПАРСИНГ] Длина ответа: {len(response)} символов")
        except Exception:
            pass

        # Очищаем ответ от лишнего текста
        response_clean = response.strip()

        # Сингулярность 10.0: Удаляем <think>...</think> блоки перед парсингом
        if "<think>" in response_clean:
            # Используем более надежное регулярное выражение для удаления всех блоков <think>
            response_clean = re.sub(
                r"<think>.*?</think>", "", response_clean, flags=re.DOTALL
            ).strip()
            # Если тег <think> открыт, но не закрыт (бывает при обрыве генерации)
            response_clean = re.sub(r"<think>.*", "", response_clean, flags=re.DOTALL).strip()

        # [SINGULARITY 21.6] Fix: Try to find ANY JSON block if the specific "action" pattern fails
        json_blocks = re.findall(r"```(?:json)?\s*([\{\[].*?)```", response_clean, re.DOTALL)

        # [SINGULARITY 21.26] Fix: If the model returns JSON with trailing backticks but not in a proper block
        if not json_blocks and "```" in response_clean:
            # Try to find JSON between backticks or before backticks
            json_blocks = re.findall(r"([\{\[].*?)(?:```|$)", response_clean, re.DOTALL)

        # Если не нашли в блоках, ищем просто по тексту
        if not json_blocks:
            # [SINGULARITY 21.27] Fix: Handle case where JSON is not enclosed in backticks at all
            # We look for something that looks like a JSON object or array
            # Starting with { or [ and ending with } or ]
            json_blocks = re.findall(r"([\{\[].*[\}\]])", response_clean, re.DOTALL)

            # If still not found, fallback to greedier match
            if not json_blocks:
                json_blocks = re.findall(r"([\{\[].*)", response_clean, re.DOTALL)

        if json_blocks:
            # Пробуем парсить блоки с конца (обычно финальное действие в конце)
            for block in reversed(json_blocks):
                try:
                    block_clean = block.strip()

                    # 1. Убираем закрывающие тройные кавычки, если они есть
                    if "```" in block_clean:
                        block_clean = block_clean.split("```")[0].strip()

                    # 2. Пытаемся найти корректный конец JSON по балансу скобок
                    balance_curly = 0
                    balance_square = 0
                    last_valid_index = -1
                    in_string = False
                    escape_next = False

                    for i, char in enumerate(block_clean):
                        if escape_next:
                            escape_next = False
                            continue
                        if char == "\\":
                            escape_next = True
                            continue
                        if char == '"' and not escape_next:
                            in_string = not in_string
                            continue
                        if not in_string:
                            if char == "{":
                                balance_curly += 1
                            elif char == "}":
                                balance_curly -= 1
                            elif char == "[":
                                balance_square += 1
                            elif char == "]":
                                balance_square -= 1

                            if balance_curly == 0 and balance_square == 0:
                                last_valid_index = i
                                break

                    if last_valid_index != -1:
                        block_to_parse = block_clean[: last_valid_index + 1]
                    else:
                        # Если баланс не сошелся, пробуем «дозакрыть»
                        block_to_parse = block_clean
                        if block_to_parse.count("{") > block_to_parse.count("}"):
                            block_to_parse += "}" * (
                                block_to_parse.count("{") - block_to_parse.count("}")
                            )
                        if block_to_parse.count("[") > block_to_parse.count("]"):
                            block_to_parse += "]" * (
                                block_to_parse.count("[") - block_to_parse.count("]")
                            )

                    action_data = json.loads(block_to_parse)

                    # Если это список, берем первый элемент (если он есть)
                    if isinstance(action_data, list) and action_data:
                        action_data = action_data[0]

                    if not isinstance(action_data, dict):
                        continue

                    action = action_data.get("action")
                    action_input = action_data.get("input", {})

                    # [SINGULARITY 21.8] Модель может вернуть action "answer" с input.text вместо finish с output
                    if action == "answer":
                        text = (action_input or {}) if isinstance(action_input, dict) else {}
                        out = (text.get("text") or "").strip()
                        logger.info("✅ Парсинг действия: answer → finish с output из input.text")
                        return "finish", {"output": out or "(пустой ответ)"}

                    if action and action in available_tools:
                        logger.info(f"✅ Парсинг действия (улучшенный баланс): {action}")
                        return action, action_input if isinstance(action_input, dict) else {}
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка парсинга блока: {e}")
                    continue

        # 3. Старый надежный метод с подсчетом скобок (если регулярки не сработали)
        json_start_pattern = r'\{\s*"action"\s*:\s*"([^"]+)"'
        json_start_match = re.search(json_start_pattern, response_clean)

        if json_start_match:
            start_pos = json_start_match.start()
            brace_count = 0
            in_string = False
            escape_next = False
            json_end_pos = start_pos

            for i in range(start_pos, len(response_clean)):
                char = response_clean[i]
                if escape_next:
                    escape_next = False
                    continue
                if char == "\\":
                    escape_next = True
                    continue
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                if not in_string:
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_end_pos = i + 1
                            break

            if brace_count == 0 and json_end_pos > start_pos:
                try:
                    json_str = response_clean[start_pos:json_end_pos]
                    action_data = json.loads(json_str)
                    action = action_data.get("action", "finish")
                    action_input = action_data.get("input", {})

                    if action == "answer":
                        text = (action_input or {}) if isinstance(action_input, dict) else {}
                        out = (text.get("text") or "").strip()
                        logger.info("✅ Парсинг действия: answer → finish с output из input.text")
                        return "finish", {"output": out or "(пустой ответ)"}

                    if action in available_tools:
                        logger.info(f"✅ Парсинг действия (полный JSON): {action}")
                        return action, action_input if isinstance(action_input, dict) else {}
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ [ПАРСИНГ] Ошибка парсинга полного JSON: {e}")

        # Fallback 1: Ищем action и input отдельно (самый простой поиск)
        action_match = re.search(r'"action"\s*:\s*"([^"]+)"', response_clean)
        if action_match:
            action = action_match.group(1)
            if action == "answer":
                input_match = re.search(r'"input"\s*:\s*(\{.*?\})', response_clean, re.DOTALL)
                if input_match:
                    try:
                        action_input = json.loads(input_match.group(1))
                        out = (
                            (action_input or {}).get("text", "")
                            if isinstance(action_input, dict)
                            else ""
                        )
                        logger.info(
                            "✅ Парсинг действия (fallback): answer → finish с output из input.text"
                        )
                        return "finish", {"output": (out or "").strip() or "(пустой ответ)"}
                    except Exception:
                        pass
            if action in available_tools:
                # Пытаемся найти input рядом
                input_match = re.search(r'"input"\s*:\s*(\{.*?\})', response_clean, re.DOTALL)
                if input_match:
                    try:
                        action_input = json.loads(input_match.group(1))
                        logger.info(f"✅ Парсинг действия (простой fallback): {action}")
                        return action, action_input if isinstance(action_input, dict) else {}
                    except Exception:
                        pass
                return action, {}

        # По умолчанию - finish
        if "finish" in response_clean.lower() or "final answer" in response_clean.lower():
            return "finish", {"output": response_clean}

        # [SINGULARITY 21.8] Последняя попытка: извлечь "answer" с input.text по шаблону
        try:
            input_match = re.search(
                r'"input"\s*:\s*\{\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
                response_clean,
                re.DOTALL,
            )
            if input_match and '"action"' in response_clean and '"answer"' in response_clean:
                text = input_match.group(1).encode("utf-8").decode("unicode_escape")
                logger.info("✅ Парсинг действия (regex): answer → finish с output из input.text")
                return "finish", {"output": (text or "").strip() or "(пустой ответ)"}
        except Exception:
            pass

        logger.warning(f"⚠️ Не удалось распарсить действие из ответа: {response_clean[:200]}...")
        return "finish", {"output": f"Ошибка парсинга ответа модели. Ответ: {response_clean[:500]}"}

    async def _execute_action(self, action: str, action_input: Dict) -> Any:
        """Выполнить действие с реальными инструментами"""
        logger.info(f"🔧 [{self.agent_name}] Выполняю действие: {action}")

        # Python-код: запись во временный файл + выполнение
        if action in ["python-development", "execute_python", "run_python", "python_exec"]:
            code = (
                action_input.get("code")
                or action_input.get("content")
                or action_input.get("script")
                or ""
            )
            file_path = action_input.get("file_path", "/tmp/_react_agent_exec.py")
            if not code:
                return "Error: не передан Python код (ожидается поле code или content)"
            try:
                import os as _os
                import subprocess
                import tempfile

                _os.makedirs(
                    _os.path.dirname(file_path) if _os.path.dirname(file_path) else "/tmp",
                    exist_ok=True,
                )
                with open(file_path, "w", encoding="utf-8") as _f:
                    _f.write(code)
                result = subprocess.run(
                    ["python3", file_path],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                output = result.stdout or ""
                err = result.stderr or ""
                if result.returncode != 0:
                    return f"STDOUT:\n{output}\nSTDERR (exit {result.returncode}):\n{err}"
                return f"STDOUT:\n{output}" + (f"\nSTDERR:\n{err}" if err.strip() else "")
            except subprocess.TimeoutExpired:
                return "Error: Python скрипт превысил таймаут 120 секунд"
            except Exception as e:
                return f"Error executing Python: {str(e)}"

        # [SINGULARITY 21.6] Прямое выполнение системных команд через Shell (Cursor-like)
        if action in [
            "run_terminal_cmd",
            "execute_command",
            "shell_run",
            "code-analysis",
            "code-documentation",
            "internal-comms",
        ]:
            command = action_input.get("command") or action_input.get("cmd") or ""

            # Если это псевдо-инструменты, преобразуем их в реальные действия или логи
            if action == "code-analysis":
                command = f"ls -R {action_input.get('file_path', '.')}"
            elif action == "code-documentation":
                command = f"cat {action_input.get('file_path', 'README.md')}"
            elif action == "internal-comms":
                return f"Internal Communication Sent: {action_input.get('message', '')}"

            if not command:
                return "Error: command не указан"

            logger.info(f"💻 [SYSTEM] Выполнение системной команды: {command}")
            try:
                import subprocess

                # Используем zsh для соответствия среде пользователя
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    executable="/bin/zsh",
                )
                output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\nEXIT CODE: {result.returncode}"
                logger.info(f"✅ [SYSTEM] Команда выполнена (code {result.returncode})")
                return output
            except Exception as e:
                logger.error(f"❌ [SYSTEM] Ошибка выполнения команды: {e}")
                return f"Error executing command: {str(e)}"

        # [SINGULARITY 21.6] Прямое чтение файлов
        if action == "read_file":
            file_path = action_input.get("file_path", action_input.get("path", ""))
            if not file_path:
                return "Error: file_path не указан"
            try:
                with open(file_path, encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"Error reading file {file_path}: {str(e)}"

        # [SINGULARITY 21.6] Прямое создание/запись файлов
        if action in ["create_file", "write_file"]:
            file_path = action_input.get("file_path", "")
            content = action_input.get("content", "")
            if not file_path:
                return "Error: file_path не указан"
            try:
                os.makedirs(os.path.dirname(file_path), exist_ok=True) if os.path.dirname(
                    file_path
                ) else None
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"Файл '{file_path}' успешно создан/обновлен"
            except Exception as e:
                return f"Error writing file {file_path}: {str(e)}"

        # --- SMART PATCH IMPLEMENTATION (Singularity 10.0) ---
        if action == "smart-patch" or action == "patch_file":
            file_path = action_input.get("file_path", "")
            patch_content = action_input.get("patch_content", "")
            if not file_path or not patch_content:
                return "Error: file_path и patch_content обязательны"

            try:
                import re

                if not os.path.exists(file_path):
                    return f"Error: Файл {file_path} не найден"

                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                # Парсим блоки SEARCH/REPLACE
                # Формат: <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE
                pattern = r"<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE"
                matches = re.findall(pattern, patch_content, re.DOTALL)

                if not matches:
                    return "Error: Не найдено валидных блоков SEARCH/REPLACE"

                new_content = content
                applied_count = 0
                for search_block, replace_block in matches:
                    if search_block in new_content:
                        new_content = new_content.replace(search_block, replace_block)
                        applied_count += 1
                    else:
                        # Пробуем найти с обрезанными пробелами если точное совпадение не сработало
                        search_stripped = search_block.strip()
                        if search_stripped in new_content:
                            # Находим оригинальный блок с такими же границами
                            # Это упрощенная версия, в идеале нужно более точное сопоставление
                            new_content = new_content.replace(
                                search_stripped, replace_block.strip()
                            )
                            applied_count += 1
                        else:
                            logger.warning(f"⚠️ Блок SEARCH не найден в {file_path}")

                if applied_count > 0:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    return f"Успешно применено {applied_count} патчей к {file_path}"
                else:
                    return f"Error: Ни один блок SEARCH не найден в {file_path}. Проверь точность кода в блоке SEARCH."
            except Exception as e:
                return f"Error при применении патча: {str(e)}"

        # Сингулярность 10.0: Если действие search_knowledge, подмешиваем AI Research если запрос релевантен
        if action == "search_knowledge":
            query = action_input.get("query", "").lower()
            ai_keywords = [
                "anthropic",
                "google",
                "openai",
                "deepseek",
                "meta",
                "llama",
                "claude",
                "gemini",
                "gpt-4",
                "gpt-5",
                "research",
                "исследования",
            ]
            if any(kw in query for kw in ai_keywords):
                logger.info(f"🧠 [AI RESEARCH] Перехват search_knowledge для AI тематики: {query}")
                try:
                    import asyncpg

                    db_url = os.getenv("DATABASE_URL")
                    if db_url:
                        conn = await asyncpg.connect(db_url)
                        try:
                            rows = await conn.fetch(
                                """SELECT kn.content, kn.metadata->>'title' as title
                                   FROM knowledge_nodes kn
                                   JOIN domains d ON d.id = kn.domain_id
                                   WHERE (d.name = 'AI Research' OR kn.metadata->>'source' = 'external_docs_indexer')
                                     AND (kn.content ILIKE $1 OR kn.metadata::text ILIKE $1)
                                   ORDER BY kn.confidence_score DESC NULLS LAST
                                   LIMIT 3""",
                                f"%{query[:30]}%",
                            )
                            if rows:
                                results = []
                                for r in rows:
                                    results.append(f"### {r['title']}\n{r['content']}")
                                return "\n\n".join(results)
                        finally:
                            await conn.close()
                except Exception as e:
                    logger.debug(f"AI Research search_knowledge fallback error: {e}")

        if self.skill_registry:
            skill = self.skill_registry.get_skill(action)
            if skill and skill.handler:
                try:
                    if asyncio.iscoroutinefunction(skill.handler):
                        result = await skill.handler(**action_input)
                    else:
                        result = skill.handler(**action_input)
                    return result
                except Exception as e:
                    logger.error(f"❌ Ошибка выполнения skill {action}: {e}")
                    return f"Error: {str(e)}"

        try:
            if action == "read_file":
                file_path = action_input.get("file_path", action_input.get("path", ""))
                if not file_path:
                    return "Error: file_path не указан"
                with open(file_path, encoding="utf-8") as f:
                    return f.read()
            elif action == "run_terminal_cmd":
                command = action_input.get("command") or action_input.get("cmd") or ""
                if not command:
                    return "Error: command не указан"

                # Если доступен SandboxManager, выполняем в песочнице
                if self.sandbox_manager:
                    logger.info(
                        f"🧪 [SANDBOX] Перенаправление команды в песочницу {self.agent_name}"
                    )
                    sb_result = await self.sandbox_manager.run_in_sandbox(self.agent_name, command)
                    if "error" in sb_result:
                        return f"Sandbox Error: {sb_result['error']}"
                    return f"STDOUT: {sb_result.get('output', '')}\nEXIT CODE: {sb_result.get('exit_code', 0)}"

                # Fallback на локальное выполнение (если Docker недоступен)
                import subprocess

                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=30
                )
                return f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            elif action == "list_directory":
                directory = action_input.get("directory", action_input.get("path", "."))
                return "\n".join(os.listdir(directory))
            elif action == "create_file" or action == "write_file":
                file_path = action_input.get("file_path", "")
                content = action_input.get("content", "")
                if not file_path:
                    return "Error: file_path не указан"
                os.makedirs(os.path.dirname(file_path), exist_ok=True) if os.path.dirname(
                    file_path
                ) else None
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"Файл '{file_path}' успешно создан"
            elif action == "finish":
                return action_input.get("output", "")
            elif action in ["python-development", "execute_python", "run_python", "python_exec"]:
                # Fallback Python executor (дублирует основной обработчик выше)
                code = (
                    action_input.get("code")
                    or action_input.get("content")
                    or action_input.get("script")
                    or ""
                )
                file_path = action_input.get("file_path", "/tmp/_react_agent_exec.py")
                if not code:
                    return "Error: не передан Python код"
                import subprocess as _sp

                with open(file_path, "w", encoding="utf-8") as _f:
                    _f.write(code)
                r = _sp.run(["python3", file_path], capture_output=True, text=True, timeout=120)
                out = r.stdout or ""
                err = r.stderr or ""
                if r.returncode != 0:
                    return f"STDOUT:\n{out}\nSTDERR (exit {r.returncode}):\n{err}"
                return f"STDOUT:\n{out}" + (f"\nSTDERR:\n{err}" if err.strip() else "")
            return f"Error: Неизвестное действие '{action}'"
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения действия {action}: {e}")
            return f"Error: {str(e)}"

    def _should_finish(self, reflection: str) -> bool:
        """Определить, нужно ли завершить цикл"""
        finish_keywords = ["цель достигнута", "задача выполнена", "готово", "завершено", "успешно"]
        return any(keyword in reflection.lower() for keyword in finish_keywords)

    async def _generate_response(self, prompt: str, max_tokens: int = 2048) -> str:
        """Генерировать ответ через модель с динамическим выбором из доступных"""
        import httpx

        # [SINGULARITY 21.15] Определение типа задачи для выбора между Мозгом (MLX) и Руками (Ollama)
        # Если в промпте есть "ТВОЕ РАССУЖДЕНИЕ" или "ВЫБЕРИ действие", это шаг исполнения (руки).
        # Если промпт про стратегию или архитектуру — это мозг.
        is_reasoning_task = any(
            kw in prompt.lower() for kw in ["стратегия", "архитектура", "план", "анализ"]
        )

        # [SINGULARITY 21.25] Принудительное использование Ollama если указано в промпте
        force_ollama = "[force_ollama]" in prompt or "preferred_source: ollama" in prompt.lower()
        if force_ollama:
            logger.info("⚡ [REACT] Принудительное использование Ollama (force_ollama)")
            is_reasoning_task = False

        # [SINGULARITY 21.6] Force Wisdom 30B for all steps if configured
        _force_model = os.getenv("VICTORIA_FORCE_STEP_MODEL")
        if _force_model:
            logger.info(f"🎯 [GOD MODE] Forcing model {_force_model} for ReAct step")
            models_to_try = [_force_model]
        else:
            # [SINGULARITY 21.28] Fix: Initialize _models_to_try_cache if not present
            if not hasattr(self, "_models_to_try_cache"):
                # По умолчанию используем модель, переданную в конструктор
                self._models_to_try_cache = [self.model_name]

                # Попытка добавить альтернативные модели (Ollama)
                try:
                    import httpx

                    # Не блокируем инициализацию долгим сканированием, просто добавляем базовые
                    # В будущем здесь можно сделать асинхронное сканирование
                    pass
                except Exception:
                    pass

            models_to_try = self._models_to_try_cache

        # Таймаут на LLM вызов
        request_timeout_sec = float(os.getenv("SMART_WORKER_LLM_TIMEOUT", "600"))

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(request_timeout_sec, connect=60.0)
        ) as client:
            for model in models_to_try:
                # [SINGULARITY 21.15] Балансировка Мозг/Руки:
                # Для задач размышления (reasoning) — MLX первым.
                # Для задач действия (acting/steps) — Ollama первым, чтобы не забивать мозг.
                if is_reasoning_task:
                    urls = [u for u in [self.mlx_url, self.ollama_url] if u]
                else:
                    urls = [u for u in [self.ollama_url, self.mlx_url] if u]

                for llm_url in urls:
                    if not llm_url:
                        continue
                    try:
                        logger.debug(f"🔍 [GENERATE] Пробую модель {model} на {llm_url}...")
                        response = await client.post(
                            f"{llm_url}/api/generate",
                            json={
                                "model": model,
                                "prompt": prompt,
                                "stream": False,
                                "options": {"temperature": 0.7, "num_predict": 2048},
                            },
                            timeout=httpx.Timeout(request_timeout_sec, connect=60.0),
                        )

                        if response.status_code == 200:
                            result = response.json().get("response", "")
                            if result:
                                logger.info(
                                    f"✅ [GENERATE] Модель {model} вернула ответ ({len(result)} симв.)"
                                )
                                return result
                        elif response.status_code == 503:
                            logger.warning(
                                f"⚠️ [GENERATE] 503 Service Unavailable на {llm_url}, пробуем следующую URL..."
                            )
                            continue
                        elif response.status_code == 404:
                            logger.warning(f"⚠️ [GENERATE] 404 на {llm_url} модель={model}")
                            continue
                    except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout) as e:
                        logger.warning(
                            f"⏱️ [GENERATE] Таймаут на {llm_url} ({repr(e)}), пробуем следующую URL..."
                        )
                        continue
                    except Exception as e:
                        logger.warning(f"⚠️ [GENERATE] Ошибка модели {model}: {repr(e)}")
                        continue

        logger.error("❌ Все модели недоступны")
        return "Извините, сейчас я не могу обработать ваш запрос."

    def _build_result(self) -> Dict:
        """Построить финальный результат"""
        last_step = self.memory.steps[-1] if self.memory.steps else None
        final_output = (
            last_step.observation
            if last_step and last_step.action == "finish"
            else (last_step.reflection if last_step else None)
        )
        return {
            "agent": self.agent_name,
            "goal": self.memory.goal,
            "status": self.memory.current_state.value,
            "iterations": self.memory.iteration,
            "steps": [
                {
                    "state": s.state.value,
                    "thought": s.thought,
                    "action": s.action,
                    "observation": s.observation,
                }
                for s in self.memory.steps
            ],
            "response": final_output,
        }


async def main():
    agent = ReActAgent(agent_name="Виктория", model_name="phi3.5:3.8b")
    result = await agent.run("Привет")
    print(f"Результат: {result['status']}")


if __name__ == "__main__":
    asyncio.run(main())
