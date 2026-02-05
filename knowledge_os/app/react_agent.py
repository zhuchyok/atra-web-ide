"""
ReAct Agent Framework - Reasoning + Acting для Victoria и Veronica
Основано на мировых практиках: Think → Act → Observe → Reflect
"""

import os
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

# Кэш «MLX rate limited»: после 429 от MLX пробуем Ollama первым 60 с (меньше повторных 429)
_mlx_rate_limited_until = 0.0

# Используем ТОЛЬКО MLX API Server (порт 11435)
# Ollama не используется - там нет моделей
MLX_URL = os.getenv('MLX_API_URL', 'http://localhost:11435')
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
        model_name: str = "deepseek-r1-distill-llama:70b",
        ollama_url: str = None,
        max_iterations: int = 10,
        system_prompt: Optional[str] = None,
        goal: Optional[str] = None
    ):
        self.agent_name = agent_name
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.initial_goal = goal
        
        # Определяем правильный URL для Docker (ТОЛЬКО MLX API Server)
        is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
        if is_docker:
            mlx_url = os.getenv('MLX_API_URL', 'http://host.docker.internal:11435')
        else:
            mlx_url = os.getenv('MLX_API_URL', 'http://localhost:11435')
        
        # Всегда используем MLX API Server (Ollama не используется)
        if ollama_url:
            # Если передан URL, используем его (но это должен быть MLX)
            self.ollama_url = ollama_url
        else:
            self.ollama_url = mlx_url
        
        self.max_iterations = max_iterations
        self.memory = ReActMemory(max_iterations=max_iterations)
        
        # Инициализация Skill Registry для динамических tools
        self.skill_registry = None
        try:
            from app.skill_registry import get_skill_registry
            self.skill_registry = get_skill_registry()
            logger.info("✅ Skill Registry подключен к ReActAgent")
        except Exception as e:
            logger.warning(f"⚠️ Skill Registry недоступен: {e}")

        # SafeFileWriter для create_file/write_file (бэкапы, проверка путей)
        try:
            from app.file_writer import SafeFileWriter
            self.file_writer = SafeFileWriter()
        except ImportError:
            self.file_writer = None
            logger.warning("⚠️ SafeFileWriter недоступен, используется прямая запись")
        
        logger.info(f"✅ ReActAgent инициализирован: URL={self.ollama_url}, модель={self.model_name}")
    
    async def think(self, goal: str, context: Dict = None) -> str:
        """
        Think - рассуждение о текущей ситуации
        
        Args:
            goal: Цель задачи
            context: Контекст из предыдущих шагов
        
        Returns:
            Мысль/рассуждение агента
        """
        # Строим промпт для рассуждения
        prompt = self._build_think_prompt(goal, context)
        
        # Генерируем рассуждение через модель
        thought = await self._generate_response(prompt)
        
        logger.info(f"🤔 [{self.agent_name}] Think: {thought[:100]}...")
        
        return thought
    
    async def act(self, thought: str, available_tools: List[str] = None) -> Tuple[str, Dict]:
        """
        Act - выбор и выполнение действия
        
        Args:
            thought: Рассуждение из Think
            available_tools: Доступные инструменты
        
        Returns:
            (action_name, action_input)
        """
        if available_tools is None:
            # Используем динамические tools из Skill Registry если доступен
            if self.skill_registry:
                available_tools = [skill.name for skill in self.skill_registry.list_skills() if skill.metadata.user_invocable]
                logger.debug(f"🔧 Используются динамические tools из Skill Registry: {len(available_tools)} skills")
            else:
                # Fallback на статический список
                available_tools = [
                "read_file",      # Чтение файлов
                "run_terminal_cmd",  # Выполнение команд
                "list_directory",    # Список файлов
                "create_file",       # Создание файлов
                "write_file",        # Запись в файлы
                "search_knowledge",  # Поиск в базе знаний
                "finish"             # Завершение задачи
            ]
        
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
        
        Args:
            action: Выполненное действие
            action_input: Входные данные действия
            result: Результат выполнения
        
        Returns:
            Наблюдение/описание результата
        """
        # Формируем наблюдение
        observation = f"Действие '{action}' выполнено. Результат: {str(result)[:500]}"
        
        logger.info(f"👀 [{self.agent_name}] Observe: {observation[:100]}...")
        
        return observation
    
    async def reflect(self, goal: str, steps: List[ReActStep]) -> str:
        """
        Reflect - обновление понимания на основе всех шагов
        
        Args:
            goal: Исходная цель
            steps: Все выполненные шаги
        
        Returns:
            Рефлексия/выводы
        """
        # Строим промпт для рефлексии
        prompt = self._build_reflect_prompt(goal, steps)
        
        # Генерируем рефлексию
        reflection = await self._generate_response(prompt)
        
        logger.info(f"💭 [{self.agent_name}] Reflect: {reflection[:100]}...")
        
        return reflection
    
    async def run(self, goal: str, context: Dict = None) -> Dict:
        """
        Запустить полный ReAct цикл
        
        Args:
            goal: Цель задачи
            context: Начальный контекст
        
        Returns:
            Результат выполнения с полной историей
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
                    step = ReActStep(
                        state=ReActState.THINK,
                        thought=thought
                    )
                    self.memory.steps.append(step)
                    self.memory.current_state = ReActState.ACT
                
                # 2. Act
                elif self.memory.current_state == ReActState.ACT:
                    last_step = self.memory.steps[-1]
                    action, action_input = await self.act(last_step.thought)
                    
                    # Проверяем, не финальное ли это действие
                    if action == "finish":
                        output_text = (action_input or {}).get("output", (action_input or {}).get("result", ""))
                        if isinstance(output_text, str):
                            output_text = output_text.strip()
                        else:
                            output_text = str(output_text).strip() if output_text else ""
                        # Пустой output при finish: даём одну итерацию на исправление
                        if not output_text and self.memory.iteration < self.memory.max_iterations - 1:
                            step = ReActStep(
                                state=ReActState.ACT,
                                action=action,
                                action_input=action_input
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
                            state=ReActState.ACT,
                            action=action,
                            action_input=action_input
                        )
                        step.observation = output_text  # чтобы Victoria Enhanced могла взять результат из последнего шага
                        self.memory.steps.append(step)
                        break
                    
                    # Выполняем действие
                    result = await self._execute_action(action, action_input)
                    
                    step = ReActStep(
                        state=ReActState.ACT,
                        action=action,
                        action_input=action_input
                    )
                    step.result = result  # Сохраняем результат для Observe
                    self.memory.steps.append(step)
                    self.memory.current_state = ReActState.OBSERVE
                
                # 3. Observe
                elif self.memory.current_state == ReActState.OBSERVE:
                    last_step = self.memory.steps[-1]
                    # Используем реальный результат из предыдущего шага
                    actual_result = getattr(last_step, 'result', None) or "Результат получен"
                    observation = await self.observe(
                        last_step.action,
                        last_step.action_input,
                        actual_result
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
                logger.error(f"❌ [{self.agent_name}] Ошибка в ReAct цикле: {e}")
                self.memory.current_state = ReActState.ERROR
                break
        
        # Формируем финальный результат
        return self._build_result()
    
    def _build_think_prompt(self, goal: str, context: Dict = None) -> str:
        """Построить промпт для Think"""
        system_context = ""
        if self.system_prompt:
            system_context = f"{self.system_prompt}\n\n"
        
        prompt = f"""{system_context}Ты - {self.agent_name}, эксперт по решению задач.

КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском языке! Все ответы, объяснения и комментарии должны быть на русском!

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
        file_creation_keywords = ["создай файл", "create_file", "write_file", "создай html", 
                                  "создай сайт", "создай страницу", "напиши файл", ".html", ".py", ".js",
                                  "создай бота", "бота для телеграм", "aiogram", "пуллинг", "telegram bot"]
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
            "create_file": "Создает новый файл с содержимым. Параметры: file_path (путь), content (содержимое)",
            "write_file": "Записывает содержимое в файл (создает или перезаписывает). Параметры: file_path (путь), content (содержимое)",
            "search_knowledge": "Ищет информацию в базе знаний. Параметры: query (поисковый запрос)",
            "finish": "Завершает выполнение задачи. Параметры: output (обязательный — краткое описание выполненного и, при создании файлов, пути к ним). Не вызывай finish без output."
        }
        
        tools_desc = "\n".join([
            f"- {tool}: {tools_descriptions.get(tool, 'Описание недоступно')}"
            for tool in available_tools
        ])
        
        # Проверяем, требует ли задача создания файлов
        file_creation_keywords = ["создай файл", "create_file", "write_file", "создай html", 
                                  "создай сайт", "создай страницу", "напиши файл", ".html", ".py", ".js",
                                  "создай бота", "бота для телеграм", "aiogram", "пуллинг", "telegram bot"]
        requires_file_creation = any(keyword in thought.lower() or keyword in self.memory.goal.lower() 
                                    for keyword in file_creation_keywords)
        
        prompt = f"""Ты - {self.agent_name}.

КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском языке! Все ответы должны быть на русском!

РАССУЖДЕНИЕ: {thought}

ДОСТУПНЫЕ ИНСТРУМЕНТЫ:
{tools_desc}

{"⚠️ КРИТИЧЕСКИ ВАЖНО: Эта задача требует СОЗДАНИЯ ФАЙЛА! Ты ДОЛЖЕН использовать create_file или write_file, НЕ finish! ⚠️" if requires_file_creation else ""}

ВЫБЕРИ действие и верни ТОЛЬКО JSON (без текста до/после):
{{"action": "название_инструмента", "input": {{"параметр": "значение"}}}}

{"🚫 ЗАПРЕЩЕНО использовать finish пока файл не создан! Используй create_file! 🚫" if requires_file_creation else ""}

ВАЖНО для create_file/write_file:
- Если создаешь HTML/код файл, ВСЁ содержимое должно быть в параметре "content"
- Используй экранирование для переносов строк: \\n
- Используй экранирование для кавычек: \\"
- Пример для HTML файла:
{{"action": "create_file", "input": {{"file_path": "index.html", "content": "<!DOCTYPE html>\\n<html>\\n<head>\\n<title>Привет</title>\\n</head>\\n<body>\\n<h1>Привет от Victoria</h1>\\n</body>\\n</html>"}}}}

Пример для простого файла:
{{"action": "create_file", "input": {{"file_path": "test.txt", "content": "привет"}}}}

Пример для выполнения команды:
{{"action": "run_terminal_cmd", "input": {{"command": "ls -la"}}}}

ТВОЙ ВЫБОР (только JSON, ВСЁ содержимое файла в content):"""
        
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
            "Error:" in last_obs or "ошибка" in last_obs.lower() or "не удалось" in last_obs.lower()
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
        logger.info(f"🔍 [ПАРСИНГ] Полный ответ модели (первые 500 символов): {response[:500]}")
        logger.info(f"🔍 [ПАРСИНГ] Длина ответа: {len(response)} символов")
        
        # Очищаем ответ от лишнего текста
        response_clean = response.strip()
        
        # УЛУЧШЕННЫЙ ПАРСИНГ: Сначала пробуем полный JSON парсинг (самый надежный)
        # Ищем JSON объект, который может содержать многострочный контент
        # Используем более гибкий подход - находим начало JSON и парсим до конца
        
        # Паттерн 1: Ищем полный JSON объект с учетом вложенных объектов и многострочного контента
        # Ищем от {"action" до последней закрывающей скобки
        json_start_pattern = r'\{\s*"action"\s*:\s*"([^"]+)"'
        json_start_match = re.search(json_start_pattern, response_clean)
        
        if json_start_match:
            start_pos = json_start_match.start()
            # Находим начало JSON объекта
            brace_count = 0
            in_string = False
            escape_next = False
            json_end_pos = start_pos
            
            for i in range(start_pos, len(response_clean)):
                char = response_clean[i]
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end_pos = i + 1
                            break
            
            if brace_count == 0 and json_end_pos > start_pos:
                try:
                    json_str = response_clean[start_pos:json_end_pos]
                    logger.info(f"🔍 [ПАРСИНГ] Извлеченный JSON (первые 500 символов): {json_str[:500]}")
                    logger.info(f"🔍 [ПАРСИНГ] Длина извлеченного JSON: {len(json_str)} символов")
                    
                    action_data = json.loads(json_str)
                    action = action_data.get('action', 'finish')
                    action_input = action_data.get('input', {})
                    
                    logger.info(f"🔍 [ПАРСИНГ] Action: {action}, Input keys: {list(action_input.keys()) if isinstance(action_input, dict) else 'N/A'}")
                    
                    # Если input - строка, пробуем распарсить как JSON
                    if isinstance(action_input, str):
                        try:
                            action_input = json.loads(action_input)
                            logger.info(f"🔍 [ПАРСИНГ] Input распарсен как JSON")
                        except:
                            logger.info(f"🔍 [ПАРСИНГ] Input не JSON, используем как строку")
                            pass
                    
                    # JSON уже автоматически декодирует экранированные символы (\n, \t, \" и т.д.)
                    # Не нужно делать дополнительный replace - это может испортить данные
                    # Если content содержит буквальные \n (не переносы строк), это уже обработано JSON парсером
                    
                    if action in available_tools:
                        logger.info(f"✅ Парсинг действия (полный JSON): {action} с параметрами: {list(action_input.keys()) if isinstance(action_input, dict) else 'N/A'}")
                        if isinstance(action_input, dict) and "content" in action_input:
                            content = action_input['content']
                            logger.info(f"   📄 Content length: {len(content)} символов")
                            logger.info(f"   📄 Content preview (первые 200 символов): {repr(content[:200])}")
                            # Проверяем, не обрезан ли контент
                            if len(content) < 50 and "html" in action_input.get("file_path", "").lower():
                                logger.warning(f"⚠️ [ПАРСИНГ] Подозрение на обрезанный контент! Длина: {len(content)}, файл: {action_input.get('file_path')}")
                                logger.warning(f"⚠️ [ПАРСИНГ] Полный content: {repr(content)}")
                        return action, action_input if isinstance(action_input, dict) else {}
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ [ПАРСИНГ] Ошибка парсинга полного JSON: {e}")
                    logger.debug(f"🔍 [ПАРСИНГ] Проблемный JSON (первые 500 символов): {json_str[:500] if 'json_str' in locals() else 'N/A'}")
                    logger.debug(f"Ошибка парсинга полного JSON: {e}, пробуем другие методы")
        
        # Паттерн 2: Стандартные JSON паттерны (fallback)
        json_patterns = [
            r'\{[^{}]*"action"[^{}]*"input"[^{}]*\{[^{}]*\}[^{}]*\}',  # Вложенный JSON
            r'\{"action"\s*:\s*"[^"]+",\s*"input"\s*:\s*\{[^}]+\}\}',  # Строгий формат
            r'\{[^}]*"action"[^}]*"input"[^}]*\}',  # Простой формат
        ]
        
        for pattern in json_patterns:
            json_match = re.search(pattern, response_clean, re.DOTALL)
            if json_match:
                try:
                    action_data = json.loads(json_match.group())
                    action = action_data.get('action', 'finish')
                    action_input = action_data.get('input', {})
                    
                    # Если input - строка, пробуем распарсить как JSON
                    if isinstance(action_input, str):
                        try:
                            action_input = json.loads(action_input)
                        except:
                            pass
                    
                    # Декодируем экранированные символы в content если есть
                    if isinstance(action_input, dict) and "content" in action_input:
                        if isinstance(action_input["content"], str):
                            action_input["content"] = action_input["content"].replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'")
                    
                    if action in available_tools:
                        logger.info(f"✅ Парсинг действия: {action} с параметрами: {list(action_input.keys()) if isinstance(action_input, dict) else 'N/A'}")
                        return action, action_input if isinstance(action_input, dict) else {}
                except json.JSONDecodeError as e:
                    logger.debug(f"Ошибка парсинга JSON: {e}, пробуем следующий паттерн")
                    continue
        
        # Fallback 1: Ищем action и input отдельно
        action_match = re.search(r'"action"\s*:\s*"([^"]+)"', response_clean)
        if action_match:
            action = action_match.group(1)
            # Ищем input объект
            input_match = re.search(r'"input"\s*:\s*(\{[^}]+\})', response_clean, re.DOTALL)
            if input_match:
                try:
                    action_input = json.loads(input_match.group(1))
                    if action in available_tools:
                        logger.info(f"✅ Парсинг действия (fallback): {action} с параметрами: {action_input}")
                        return action, action_input if isinstance(action_input, dict) else {}
                except:
                    pass
        
        # Fallback 2: Ищем название действия в тексте и извлекаем параметры
        for tool in available_tools:
            if tool.lower() in response_clean.lower():
                # Пытаемся извлечь параметры из текста
                action_input = {}
                
                # Для create_file ищем file_path и content
                if tool == "create_file" or tool == "write_file":
                    file_path_match = re.search(r'file_path["\']?\s*[:=]\s*["\']?([^"\'\s]+)', response_clean)
                    # Ищем content - может быть многострочным, ищем до конца строки или следующего ключа
                    content_patterns = [
                        r'content["\']?\s*[:=]\s*["\']([^"\']*(?:\\.[^"\']*)*)["\']',  # В кавычках с экранированием
                        r'content["\']?\s*[:=]\s*["\']([^"\']+)',  # В кавычках простой
                        r'content["\']?\s*[:=]\s*([^\s,}]+)',  # Без кавычек
                    ]
                    content_match = None
                    for pattern in content_patterns:
                        content_match = re.search(pattern, response_clean, re.DOTALL)
                        if content_match:
                            break
                    
                    if file_path_match:
                        action_input["file_path"] = file_path_match.group(1)
                    if content_match:
                        # Декодируем экранированные символы
                        content = content_match.group(1)
                        content = content.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'")
                        action_input["content"] = content
                
                # Для run_terminal_cmd ищем command
                elif tool == "run_terminal_cmd":
                    # Ищем команду после "command" или просто команду в тексте
                    cmd_match = re.search(r'command["\']?\s*[:=]\s*["\']?([^"\']+)', response_clean)
                    if cmd_match:
                        action_input["command"] = cmd_match.group(1).strip()
                    else:
                        # Пробуем найти команду в тексте (ls, echo, cat и т.д.)
                        cmd_pattern = r'(ls|cat|echo|grep|find|mkdir|touch|python|docker)\s+[^\s"]+'
                        cmd_found = re.search(cmd_pattern, response_clean)
                        if cmd_found:
                            action_input["command"] = cmd_found.group(0)
                
                # Для read_file ищем file_path
                elif tool == "read_file":
                    file_path_match = re.search(r'file_path["\']?\s*[:=]\s*["\']?([^"\'\s]+)', response_clean)
                    if file_path_match:
                        action_input["file_path"] = file_path_match.group(1)
                
                if action_input:
                    logger.info(f"✅ Парсинг действия (fallback 2): {tool} с параметрами: {action_input}")
                    return tool, action_input
                else:
                    logger.warning(f"⚠️ Найдено действие {tool}, но параметры не извлечены")
                    return tool, {}
        
        # По умолчанию - finish
        logger.warning(f"⚠️ Не удалось распарсить действие из ответа: {response_clean[:200]}")
        return "finish", {}
    
    async def _execute_action(self, action: str, action_input: Dict) -> Any:
        """Выполнить действие с реальными инструментами"""
        logger.info(f"🔧 [{self.agent_name}] Выполняю действие: {action} с параметрами: {action_input}")
        
        # Пробуем найти skill в реестре
        if self.skill_registry:
            skill = self.skill_registry.get_skill(action)
            if skill and skill.handler:
                try:
                    # Выполняем через skill handler
                    if asyncio.iscoroutinefunction(skill.handler):
                        result = await skill.handler(**action_input)
                    else:
                        result = skill.handler(**action_input)
                    logger.info(f"✅ Skill выполнен: {action}")
                    return result
                except Exception as e:
                    logger.error(f"❌ Ошибка выполнения skill {action}: {e}")
                    return f"Error: {str(e)}"
            elif skill:
                # Skill найден, но нет handler - используем инструкции
                logger.debug(f"📝 Skill найден без handler, используем инструкции: {action}")
            else:
                # Skill не найден - публикуем событие SKILL_NEEDED
                try:
                    from app.event_bus import get_event_bus, Event, EventType
                    event_bus = get_event_bus()
                    event = Event(
                        event_id=f"skill_needed_{action}",
                        event_type=EventType.SKILL_NEEDED,
                        payload={
                            "skill_name": action,
                            "action_input": action_input,
                            "context": "ReActAgent execution"
                        },
                        source="react_agent"
                    )
                    await event_bus.publish(event)
                    logger.info(f"📢 Событие SKILL_NEEDED опубликовано для: {action}")
                except Exception as e:
                    logger.debug(f"Не удалось опубликовать событие SKILL_NEEDED: {e}")
        
        try:
            # Интеграция с реальными инструментами
            if action == "read_file":
                file_path = action_input.get("file_path", action_input.get("path", ""))
                if not file_path:
                    return "Error: file_path не указан"
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    logger.info(f"✅ Файл прочитан: {file_path} ({len(content)} символов)")
                    return content
                except FileNotFoundError:
                    return f"Error: Файл '{file_path}' не найден"
                except Exception as e:
                    return f"Error: {str(e)}"
            
            elif action == "run_terminal_cmd":
                # Пробуем разные варианты ключей
                command = action_input.get("command") or action_input.get("cmd") or action_input.get("command_text", "")
                # Если command не найден, пробуем взять первый параметр или весь input как строку
                if not command and action_input:
                    # Если action_input - строка, используем её как команду
                    if isinstance(action_input, str):
                        command = action_input
                    # Если это словарь с одним ключом, используем значение
                    elif len(action_input) == 1:
                        command = list(action_input.values())[0]
                    # Или пробуем найти команду в тексте
                    elif "ls" in str(action_input) or "cat" in str(action_input) or "grep" in str(action_input):
                        # Извлекаем команду из текста
                        import re
                        cmd_match = re.search(r'(ls|cat|grep|find|echo|mkdir|touch|python|docker)\s+[^\s"]+', str(action_input))
                        if cmd_match:
                            command = cmd_match.group(0)
                
                if not command:
                    return f"Error: command не указан. Получены параметры: {action_input}"
                try:
                    import subprocess
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False
                    )
                    output = f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
                    logger.info(f"✅ Команда выполнена: {command[:50]}...")
                    return output
                except subprocess.TimeoutExpired:
                    return "Error: Команда превысила таймаут (30s)"
                except Exception as e:
                    return f"Error: {str(e)}"
            
            elif action == "list_directory":
                directory = action_input.get("directory", action_input.get("path", "."))
                try:
                    files = os.listdir(directory)
                    result = "\n".join(files)
                    logger.info(f"✅ Список файлов получен: {directory} ({len(files)} файлов)")
                    return result
                except Exception as e:
                    return f"Error: {str(e)}"
            
            elif action == "create_file" or action == "write_file":
                file_path = action_input.get("file_path", action_input.get("path", ""))
                content = action_input.get("content", action_input.get("text", ""))
                overwrite = action_input.get("overwrite", True)  # create_file обычно перезаписывает

                logger.info(f"🔍 [CREATE_FILE] file_path: {file_path}, content length: {len(content) if isinstance(content, str) else 'N/A'}")
                if not file_path:
                    return "Error: file_path не указан"
                if not content:
                    logger.warning(f"⚠️ [CREATE_FILE] Контент пустой! action_input: {action_input}")
                    return "Error: content не указан"
                if not isinstance(content, str):
                    content = str(content)

                # Approval check для критичных файлов (AGENT_APPROVAL_REQUIRED=true)
                # Интеграция HITL: request_approval создаёт запрос для будущего UI; агент получает понятное сообщение
                try:
                    from app.approval_manager import requires_approval_for_write, is_approval_required
                    if is_approval_required():
                        need, reason = requires_approval_for_write(file_path)
                        if need:
                            # Создаём запрос на одобрение (HITL) для UI/Telegram
                            try:
                                from app.human_in_the_loop import get_hitl
                                hitl = get_hitl()
                                req = await hitl.request_approval(
                                    action=action,
                                    description=f"Запись в {file_path}: {len(content)} символов",
                                    agent_name=self.agent_name,
                                    proposed_result={"file_path": file_path, "content_preview": content[:200]},
                                    context={"reason": reason, "critical_file": True},
                                )
                                return (
                                    f"Error: {reason} Требуется одобрение пользователя. "
                                    f"Запрос создан: {req.request_id}. "
                                    f"(Можно попробовать другой путь или отключить: AGENT_APPROVAL_REQUIRED=false)"
                                )
                            except Exception as hitl_err:
                                logger.debug("HITL request_approval: %s", hitl_err)
                            return (
                                f"Error: {reason} требует подтверждения пользователя. "
                                f"(Отключить: AGENT_APPROVAL_REQUIRED=false)"
                            )
                except ImportError:
                    pass

                if self.file_writer:
                    result = self.file_writer.write_file(file_path, content, overwrite=overwrite)
                    if result.get("success"):
                        logger.info(f"✅ [CREATE_FILE] {result.get('message', '')}")
                        return result["message"]
                    return f"Error: {result.get('error', 'unknown')}"
                # Fallback: прямая запись (без SafeFileWriter)
                try:
                    os.makedirs(os.path.dirname(file_path), exist_ok=True) if os.path.dirname(file_path) else None
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    return f"Файл '{file_path}' успешно создан ({len(content)} символов)"
                except Exception as e:
                    logger.error(f"❌ [CREATE_FILE] Ошибка создания файла: {e}")
                    return f"Error: {str(e)}"
            
            elif action == "search_knowledge":
                query = action_input.get("query", action_input.get("q", ""))
                if not query:
                    return "Error: query не указан"
                
                # Интеграция с Knowledge OS
                try:
                    from app.main import search_knowledge
                    domain = action_input.get("domain")
                    result = await search_knowledge(query, domain=domain)
                    logger.info(f"✅ Поиск в базе знаний выполнен: {query}")
                    return result
                except Exception as e:
                    logger.error(f"❌ Ошибка поиска в базе знаний: {e}")
                    return f"Error: {str(e)}"
            
            elif action == "finish":
                output = action_input.get("output", action_input.get("result", ""))
                return output
            
            else:
                return f"Error: Неизвестное действие '{action}'. Доступные: read_file, run_terminal_cmd, list_directory, create_file, write_file, search_knowledge, finish"
        
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения действия {action}: {e}")
            return f"Error: {str(e)}"
    
    def _should_finish(self, reflection: str) -> bool:
        """Определить, нужно ли завершить цикл"""
        finish_keywords = [
            "цель достигнута",
            "задача выполнена",
            "готово",
            "завершено",
            "успешно"
        ]
        
        reflection_lower = reflection.lower()
        return any(keyword in reflection_lower for keyword in finish_keywords)
    
    async def _generate_response(self, prompt: str) -> str:
        """Генерировать ответ через модель с fallback на доступные модели"""
        import httpx
        
        # Список моделей для fallback (от быстрых к мощным)
        # ВАЖНО: tinyllama исключена - используется только для внутренней коммуникации агентов
        fallback_models = [
            "phi3:mini-4k",
            "qwen2.5:3b",
            "phi3.5:3.8b",
            "qwen2.5-coder:32b",
            "deepseek-r1-distill-llama:70b",
            "llama3.3:70b"
        ]
        
        # Начинаем с основной модели, затем fallback
        models_to_try = [self.model_name] + [m for m in fallback_models if m != self.model_name]
        
        # Используем ТОЛЬКО MLX API Server (Ollama не используется)
        # В Docker используем host.docker.internal
        is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
        if is_docker:
            mlx_url = os.getenv('MLX_API_URL', 'http://host.docker.internal:11435')
        else:
            mlx_url = os.getenv('MLX_API_URL', 'http://localhost:11435')
        
        # ИСПОЛЬЗУЕМ ТОЛЬКО MLX API Server (порт 11435)
        # Ollama не используется - там нет моделей
        urls_to_try = []
        # Всегда используем MLX URL (проверяем и localhost и host.docker.internal)
        if "11435" in self.ollama_url or "mlx" in self.ollama_url.lower():
            # Используем настроенный MLX URL
            urls_to_try = [self.ollama_url]
        else:
            # Если URL не содержит 11435, используем дефолтный MLX URL
            is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
            if is_docker:
                urls_to_try = [os.getenv('MLX_API_URL', 'http://host.docker.internal:11435')]
            else:
                urls_to_try = [os.getenv('MLX_API_URL', 'http://localhost:11435')]
        
        if not urls_to_try:
            # Используем MLX URL по умолчанию
            urls_to_try = [mlx_url]
        
        # После недавнего 429 от MLX — пробуем Ollama первым (меньше повторных 429)
        global _mlx_rate_limited_until
        if time.time() < _mlx_rate_limited_until:
            ollama_url_early = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
            if os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true':
                ollama_url_early = os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
            if ollama_url_early not in urls_to_try:
                urls_to_try.insert(0, ollama_url_early)
                logger.info(f"🔄 [RATE LIMIT CACHE] Недавний 429 от MLX — сначала пробуем Ollama: {ollama_url_early}")
        
        # Проверяем загрузку MLX для простых задач (Task Distribution)
        # Простые задачи могут использовать Ollama при перегрузке MLX
        # category не доступен в этом контексте, используем только длину промпта
        is_simple_task = len(prompt) < 500
        use_ollama_fallback = False
        
        if is_simple_task:
            try:
                from app.mlx_request_queue import get_request_queue
                queue = get_request_queue()
                stats = queue.get_stats()
                mlx_overloaded = (
                    stats.get("active_requests", 0) >= stats.get("max_concurrent", 5) or
                    stats.get("queue_size", 0) > 3  # Если очередь > 3, используем Ollama для простых
                )
                if mlx_overloaded:
                    use_ollama_fallback = True
                    logger.info(
                        f"🔄 [SMART ROUTING] MLX перегружен, простая задача Task Distribution → Ollama "
                        f"(активных: {stats.get('active_requests')}/{stats.get('max_concurrent')}, "
                        f"очередь: {stats.get('queue_size')})"
                    )
            except Exception as e:
                logger.debug(f"⚠️ Не удалось проверить загрузку MLX: {e}")
        
        # Если простая задача и MLX перегружен, добавляем Ollama в список
        if use_ollama_fallback:
            ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
            is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
            if is_docker:
                ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
            if ollama_url not in urls_to_try:
                urls_to_try.insert(0, ollama_url)  # Приоритет Ollama для простых задач
                logger.info(f"🔄 [OLLAMA SMART] Добавлен Ollama для простой задачи: {ollama_url}")
        
        # Логируем какие URL будем пробовать
        logger.info(f"🔍 [GENERATE] Использую MLX API Server (приоритет) и Ollama (fallback): {urls_to_try}")
        logger.info(f"🔍 [GENERATE] Модели для попытки: {models_to_try[:3]}... (всего {len(models_to_try)})")
        
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                for llm_url in urls_to_try:
                    for model in models_to_try:
                        try:
                            logger.debug(f"🔍 [GENERATE] Пробую модель {model} на {llm_url}...")
                            
                            # Определяем приоритет и модель
                            is_ollama = "11434" in llm_url or "ollama" in llm_url.lower()
                            is_mlx = "11435" in llm_url or "mlx" in llm_url.lower()
                            
                            # Для Ollama используем phi3.5:3.8b для простых задач
                            model_to_use = model
                            if is_ollama and is_simple_task:
                                model_to_use = "phi3.5:3.8b"  # Быстрая Ollama модель
                                logger.debug(f"🔄 [OLLAMA SMART] Используем phi3.5:3.8b для простой задачи")
                            
                            # MLX API Server использует формат Ollama API
                            # Task Distribution использует приоритет MEDIUM (может подождать)
                            headers = {}
                            if is_mlx:
                                headers["X-Request-Priority"] = "medium"  # Task Distribution - средний приоритет
                            
                            response = await client.post(
                                f"{llm_url}/api/generate",
                                json={
                                    "model": model_to_use,
                                    "prompt": prompt,
                                    "stream": False,
                                    "options": {
                                        "temperature": 0.7,
                                        "num_predict": 2048
                                    }
                                },
                                headers=headers if headers else None,
                                timeout=httpx.Timeout(120.0, connect=10.0)
                            )
                        
                            if response.status_code == 200:
                                result = response.json().get('response', '')
                                if result:
                                    source = "MLX" if "11435" in llm_url else "Ollama"
                                    if model != self.model_name or llm_url != self.ollama_url:
                                        logger.info(f"✅ ReActAgent использует {source} модель: {model} (URL: {llm_url})")
                                    logger.info(f"✅ [GENERATE] Модель вернула ответ длиной {len(result)} символов")
                                    return result
                                else:
                                    logger.warning(f"⚠️ [GENERATE] Модель {model} вернула пустой ответ (status 200, но response пустой)")
                            elif response.status_code == 429:
                                # Rate limit - для MLX пробуем Ollama fallback и кэшируем на 60 с
                                if is_mlx and not is_ollama:
                                    _mlx_rate_limited_until = time.time() + 60  # global уже выше в функции
                                    logger.warning(f"⚠️ [RATE LIMIT] MLX rate limit на {llm_url}, пробуем Ollama fallback...")
                                    # Добавляем Ollama в список для следующей попытки
                                    ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
                                    is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
                                    if is_docker:
                                        ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
                                    if ollama_url not in urls_to_try:
                                        urls_to_try.append(ollama_url)
                                        logger.info(f"🔄 [FALLBACK] Добавлен Ollama для обработки rate limit: {ollama_url}")
                                else:
                                    try:
                                        error_body = response.text[:200]
                                        logger.warning(f"⚠️ [RATE LIMIT] Rate limit на {llm_url}: {error_body}")
                                    except:
                                        pass
                                continue
                            elif response.status_code >= 500:
                                # Серверная ошибка - для MLX пробуем Ollama fallback
                                if is_mlx and not is_ollama:
                                    logger.warning(f"⚠️ [SERVER ERROR] MLX серверная ошибка {response.status_code} на {llm_url}, пробуем Ollama fallback...")
                                    # Добавляем Ollama в список для следующей попытки
                                    ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
                                    is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
                                    if is_docker:
                                        ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
                                    if ollama_url not in urls_to_try:
                                        urls_to_try.append(ollama_url)
                                        logger.info(f"🔄 [FALLBACK] Добавлен Ollama для обработки серверной ошибки: {ollama_url}")
                                else:
                                    try:
                                        error_body = response.text[:200]
                                        logger.warning(f"⚠️ [SERVER ERROR] Серверная ошибка {response.status_code} на {llm_url}: {error_body}")
                                    except:
                                        pass
                                continue
                            elif response.status_code == 404:
                                logger.debug(f"Модель {model} недоступна на {llm_url} (404), пробуем следующую...")
                                continue
                            else:
                                logger.warning(f"Ошибка генерации с моделью {model} на {llm_url}: {response.status_code}")
                                try:
                                    error_body = response.text[:200]
                                    logger.warning(f"⚠️ [GENERATE] Тело ошибки: {error_body}")
                                except:
                                    pass
                                continue
                        except Exception as e:
                            logger.warning(f"⚠️ [GENERATE] Ошибка при использовании модели {model} на {llm_url}: {e}")
                            continue
                
                # Если все модели недоступны
                logger.error(f"❌ Все модели недоступны для ReActAgent (пробовали {len(urls_to_try)} URL, {len(models_to_try)} моделей)")
                logger.error(f"❌ [GENERATE] Не удалось получить ответ от модели. Возвращаю пустую строку.")
                return ""
        except Exception as e:
            logger.error(f"Ошибка запроса к модели: {e}")
            return ""
    
    def _build_result(self) -> Dict:
        """Построить финальный результат.
        
        Важно: при action=finish ответ модели лежит в step.observation (output),
        а не в reflection. Reflection заполняется только после цикла Think→Act→Observe→Reflect.
        """
        last_step = self.memory.steps[-1] if self.memory.steps else None
        final_output = None
        if last_step:
            # При finish: ответ в observation (модель передала output в finish)
            if getattr(last_step, "action", None) == "finish" and getattr(last_step, "observation", None):
                final_output = (last_step.observation or "").strip()
            # Иначе: ответ в reflection (цикл Reflect завершил задачу)
            if not final_output:
                final_output = (getattr(last_step, "reflection", None) or "").strip()
            if not final_output:
                final_output = None
        return {
            "agent": self.agent_name,
            "goal": self.memory.goal,
            "status": self.memory.current_state.value,
            "iterations": self.memory.iteration,
            "steps": [
                {
                    "state": step.state.value,
                    "thought": step.thought,
                    "action": step.action,
                    "observation": step.observation,
                    "reflection": step.reflection
                }
                for step in self.memory.steps
            ],
            "final_reflection": final_output,
            "response": final_output,  # для совместимости с Victoria Enhanced
        }


async def main():
    """Пример использования"""
    agent = ReActAgent(agent_name="Виктория", model_name="deepseek-r1-distill-llama:70b")
    
    result = await agent.run("Найди информацию о системе отслеживания моделей")
    
    print("Результат ReAct цикла:")
    print(f"Статус: {result['status']}")
    print(f"Итераций: {result['iterations']}")
    print(f"Шагов: {len(result['steps'])}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
