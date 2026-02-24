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
        model_name: str = "qwq:32b",  # Самая мощная reasoning модель после удаления 70B/104B
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
        # Строим промпт для рассуждения
        prompt = self._build_think_prompt(goal, context)

        # Генерируем рассуждение через модель
        thought = await self._generate_response(prompt)

        logger.info(f"🤔 [{self.agent_name}] Think: {thought[:100]}...")

        return thought

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
                    "list_directory",  # Список файлов
                    "create_file",  # Создание файлов
                    "write_file",  # Запись в файлы
                    "search_knowledge",  # Поиск в базе знаний
                    "finish",  # Завершение задачи
                ]

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
        self.memory.goal = goal
        self.memory.current_state = ReActState.THINK
        self.memory.iteration = 0

        logger.info(f"🚀 [{self.agent_name}] Начинаю ReAct цикл для: {goal[:80]}")

        while self.memory.iteration < self.memory.max_iterations:
            self.memory.iteration += 1

            try:
                # 1. Think
                if self.memory.current_state == ReActState.THINK:
                    thought = await self.think(goal, context)
                    step = ReActStep(state=ReActState.THINK, thought=thought)
                    self.memory.steps.append(step)
                    self.memory.current_state = ReActState.ACT

                # 2. Act
                elif self.memory.current_state == ReActState.ACT:
                    last_step = self.memory.steps[-1]
                    action, action_input = await self.act(last_step.thought)

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
            "run_terminal_cmd": "Выполняет команду в терминале. Параметры: command (команда для выполнения)",
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

        # УЛУЧШЕННЫЙ ПАРСИНГ (Singularity 10.0): Ищем JSON в markdown блоках или просто в тексте

        # 1. Пробуем найти JSON в markdown блоках ```json ... ```
        # Сингулярность 10.0: Максимально жадный поиск до конца блока или ответа
        json_blocks = re.findall(r'```(?:json)?\s*(\{.*?"action"\s*:.*)', response_clean, re.DOTALL)

        # Если не нашли в блоках, ищем просто по тексту
        if not json_blocks:
            json_blocks = re.findall(r'(\{\s*"action"\s*:.*)', response_clean, re.DOTALL)

        if json_blocks:
            # Пробуем парсить блоки с конца (обычно финальное действие в конце)
            for block in reversed(json_blocks):
                try:
                    block_clean = block.strip()

                    # 1. Убираем закрывающие тройные кавычки, если они есть
                    if "```" in block_clean:
                        block_clean = block_clean.split("```")[0].strip()

                    # 2. Пытаемся найти корректный конец JSON по балансу скобок
                    balance = 0
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
                                balance += 1
                            elif char == "}":
                                balance -= 1
                                if balance == 0:
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

                    action_data = json.loads(block_to_parse)
                    action = action_data.get("action")
                    action_input = action_data.get("input", {})

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

                    if action in available_tools:
                        logger.info(f"✅ Парсинг действия (полный JSON): {action}")
                        return action, action_input if isinstance(action_input, dict) else {}
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ [ПАРСИНГ] Ошибка парсинга полного JSON: {e}")

        # Fallback 1: Ищем action и input отдельно (самый простой поиск)
        action_match = re.search(r'"action"\s*:\s*"([^"]+)"', response_clean)
        if action_match:
            action = action_match.group(1)
            if action in available_tools:
                # Пытаемся найти input рядом
                input_match = re.search(r'"input"\s*:\s*(\{.*?\})', response_clean, re.DOTALL)
                if input_match:
                    try:
                        action_input = json.loads(input_match.group(1))
                        logger.info(f"✅ Парсинг действия (простой fallback): {action}")
                        return action, action_input if isinstance(action_input, dict) else {}
                    except:
                        pass
                return action, {}

        # По умолчанию - finish
        if "finish" in response_clean.lower() or "final answer" in response_clean.lower():
            return "finish", {"output": response_clean}

        logger.warning(f"⚠️ Не удалось распарсить действие из ответа: {response_clean[:200]}...")
        return "finish", {"output": f"Ошибка парсинга ответа модели. Ответ: {response_clean[:500]}"}

    async def _execute_action(self, action: str, action_input: Dict) -> Any:
        """Выполнить действие с реальными инструментами"""
        logger.info(f"🔧 [{self.agent_name}] Выполняю действие: {action}")

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
            return f"Error: Неизвестное действие '{action}'"
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения действия {action}: {e}")
            return f"Error: {str(e)}"

    def _should_finish(self, reflection: str) -> bool:
        """Определить, нужно ли завершить цикл"""
        finish_keywords = ["цель достигнута", "задача выполнена", "готово", "завершено", "успешно"]
        return any(keyword in reflection.lower() for keyword in finish_keywords)

    async def _generate_response(self, prompt: str) -> str:
        """Генерировать ответ через модель с динамическим выбором из доступных"""
        import httpx

        # Динамический выбор моделей через сканер
        is_docker = (
            os.path.exists("/.dockerenv")
            or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
        )
        ollama_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://host.docker.internal:11434" if is_docker else "http://localhost:11434",
        )
        mlx_url = os.getenv(
            "MLX_API_URL",
            "http://host.docker.internal:11435" if is_docker else "http://localhost:11435",
        )

        # КЭШИРОВАНИЕ СПИСКА МОДЕЛЕЙ (Сингулярность 10.0: Оптимизация скорости)
        if not hasattr(self, "_models_to_try_cache"):
            models_to_try = [self.model_name]
            try:
                try:
                    from available_models_scanner import scan_and_select_models
                except ImportError:
                    from app.available_models_scanner import scan_and_select_models
                selection = await scan_and_select_models(mlx_url, ollama_url)

                # Добавляем лучшие модели из Ollama и MLX в список попыток
                if selection.ollama_best and selection.ollama_best not in models_to_try:
                    models_to_try.append(selection.ollama_best)

                # Добавляем остальные доступные модели из Ollama
                for m in selection.ollama_models:
                    if m not in models_to_try:
                        models_to_try.append(m)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка сканирования моделей в ReActAgent: {e}")
                # Fallback на статический список если сканер не сработал
                fallback_models = [
                    "qwen2.5-coder:32b",
                    "glm-4.7-flash:q8_0",
                    "qwq:32b",
                    "tinyllama:1.1b-chat",
                ]
                for m in fallback_models:
                    if m not in models_to_try:
                        models_to_try.append(m)
            self._models_to_try_cache = models_to_try

        models_to_try = self._models_to_try_cache

        # Таймаут 1200с для тяжелых локальных моделей (qwq:32b, qwen3-coder-next:latest)
        request_timeout_sec = 1200.0

        logger.info(f"🔍 [GENERATE] Модели для попытки: {models_to_try}")

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(request_timeout_sec, connect=60.0)
        ) as client:
            for model in models_to_try:
                # Определяем URL для модели (MLX или Ollama)
                # В данной реализации пробуем оба источника
                urls = [self.ollama_url, self.mlx_url]

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
                        elif response.status_code == 404:
                            logger.warning(f"⚠️ [GENERATE] 404 на {llm_url} модель={model}")
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
