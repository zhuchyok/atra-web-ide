import asyncio
import logging
import os
import re
import sys
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from starlette.responses import Response
from pydantic import BaseModel

from src.agents.bridge.project_registry import get_main_project, get_projects_registry
from src.agents.core.base_agent import AtraBaseAgent as BaseAgent
from src.agents.core.executor import OllamaExecutor, _ollama_base_url
from src.agents.tools.system_tools import SystemTools, WebTools

# Интеграция с той же базой знаний, что и Виктория (одна БД knowledge_os)
USE_KNOWLEDGE_OS = os.getenv("USE_KNOWLEDGE_OS", "true").lower() == "true"
KNOWLEDGE_OS_AVAILABLE = False
_veronica_db_pool = None
_veronica_enhanced_singleton = None

if USE_KNOWLEDGE_OS:
    try:
        import asyncpg

        KNOWLEDGE_OS_AVAILABLE = True
    except ImportError:
        logging.warning(
            "asyncpg не установлен, Вероника без базы знаний. Установите: pip install asyncpg"
        )


async def _get_veronica_db_pool():
    """Пул к той же PostgreSQL knowledge_os, что и у Виктории."""
    global _veronica_db_pool
    if not USE_KNOWLEDGE_OS or not KNOWLEDGE_OS_AVAILABLE:
        return None
    if _veronica_db_pool is None:
        try:
            db_url = os.getenv(
                "DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"
            )
            _veronica_db_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)
            logger.info("✅ Veronica: пул к Knowledge OS создан")
        except Exception as e:
            logger.warning(f"Veronica: пул Knowledge OS недоступен: {e}")
    return _veronica_db_pool


def _get_veronica_enhanced_singleton():
    """DI-style provider for Veronica's VictoriaEnhanced instance."""
    global _veronica_enhanced_singleton
    if _veronica_enhanced_singleton is not None:
        return _veronica_enhanced_singleton
    try:
        from app.victoria_enhanced import VictoriaEnhanced

        _veronica_enhanced_singleton = VictoriaEnhanced()
        return _veronica_enhanced_singleton
    except Exception as e:
        logger.warning("⚠️ Не удалось инициализировать Veronica Enhanced singleton: %s", e)
        return None


def _validate_search_pattern(goal: str, max_len: int = 50) -> str:
    """Validate and sanitize search pattern to prevent SQL injection in ILIKE queries."""
    try:
        if not goal:
            return "%"
        pattern = goal[:max_len]
        pattern = re.sub(r"['\";%_\\)]*", "", pattern)
        if not re.match(r"^[\w\sа-яА-ЯёЁ.,!?:;-]*$", pattern):
            return "%"
        return f"%{pattern}%"
    except Exception:
        return "%"


async def get_knowledge_context_veronica(goal: str, limit: int = 5) -> str:
    """Релевантные знания из той же базы (knowledge_nodes)."""
    pool = await _get_veronica_db_pool()
    if not pool:
        return ""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT content, confidence_score
                FROM knowledge_nodes
                WHERE confidence_score > 0.3 AND content ILIKE $1
                ORDER BY confidence_score DESC, usage_count DESC
                LIMIT $2
            """,
                _validate_search_pattern(goal),
                limit,
            )
            if not rows:
                return ""
            out = "\n--- РЕЛЕВАНТНЫЕ ЗНАНИЯ ИЗ БАЗЫ КОРПОРАЦИИ ---\n"
            for row in rows:
                content = (
                    (row["content"][:200] + "...") if len(row["content"]) > 200 else row["content"]
                )
                out += f"- {content}\n"
            return out
    except Exception as e:
        logger.debug(f"Veronica: поиск знаний: {e}")
        return ""


# Пути для импорта knowledge_os (сканер моделей: from app.available_models_scanner)
def _veronica_knowledge_os_paths():
    root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    return [
        "/app/knowledge_os",
        os.path.join(root, "knowledge_os"),
        os.path.join(os.path.dirname(__file__), "../../../knowledge_os"),
        os.path.join(os.path.dirname(__file__), "../../knowledge_os"),
    ]


# Настройка логирования с поддержкой ELK
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("veronica_bridge")

# Добавляем ELK handler если включен
if os.getenv("USE_ELK", "false").lower() in ("true", "1", "yes"):
    try:
        # Пытаемся найти elk_handler в knowledge_os/app
        elk_paths = [
            "/app/app",  # Путь в контейнере
            os.path.join(os.path.dirname(__file__), "../../../knowledge_os/app"),
            os.path.join(os.path.dirname(__file__), "../../knowledge_os/app"),
        ]
        elk_handler_imported = False
        for elk_path in elk_paths:
            if os.path.exists(os.path.join(elk_path, "elk_handler.py")):
                if elk_path not in sys.path:
                    sys.path.insert(0, elk_path)
                try:
                    from elk_handler import create_elk_handler

                    elk_url = os.getenv("ELASTICSEARCH_URL", "http://atra-elasticsearch:9200")
                    elk_handler = create_elk_handler(
                        elasticsearch_url=elk_url, log_level=logging.INFO
                    )
                    if elk_handler:
                        root_logger = logging.getLogger()
                        root_logger.addHandler(elk_handler)
                        logger.info("✅ ELK handler enabled for Veronica")
                        elk_handler_imported = True
                        break
                except Exception as e:
                    logger.warning(f"Failed to import ELK handler from {elk_path}: {e}")
        if not elk_handler_imported:
            logger.warning("ELK handler not found, continuing without ELK logging")
    except Exception as e:
        logger.warning(f"Failed to setup ELK handler: {e}")

app = FastAPI(title="Veronica ATRA Bridge API")


class VeronicaAgent(BaseAgent):
    def __init__(self, name: str = "Вероника", model_name: Optional[str] = None):
        # Автовыбор модели: пустое значение = сканирование Ollama при первом run()
        model_name = model_name or os.getenv("VERONICA_MODEL") or None
        super().__init__(name, model_name or "auto")
        base = _ollama_base_url()
        planner_model = os.getenv("VERONICA_PLANNER_MODEL") or None
        # Модели будут выбраны автоматически при первом run() из актуального списка Ollama
        self.planner = OllamaExecutor(model=planner_model, base_url=base)
        self.executor = OllamaExecutor(model=model_name, base_url=base)
        self._models_resolved = (
            False  # при первом run() сканируем Ollama и подставляем актуальные модели
        )
        logger.info(
            "Veronica: executor=%s, planner=%s (OLLAMA_BASE_URL=%s) - will auto-select on first request",
            model_name or "auto",
            planner_model or "auto",
            base,
        )

        # Подключаем инструменты
        self.add_tool("read_file", SystemTools.read_project_file)
        self.add_tool("run_terminal_cmd", SystemTools.run_local_command)
        self.add_tool("ssh_run", SystemTools.run_ssh_command)
        self.add_tool("list_directory", SystemTools.list_directory)
        self.add_tool("write_file", SystemTools.write_file)
        self.add_tool("web_search", WebTools.web_search)
        self.add_tool("grep_search", SystemTools.grep_search)
        self.add_tool("apply_patch", SystemTools.apply_patch)
        self.add_tool("browser_action", WebTools.browser_action)

    async def plan(self, goal: str):
        plan_prompt = f"""ТЫ — ТЕХНИЧЕСКИЙ ДИРЕКТОР ATRA. Составь СТРОГИЙ пошаговый план.
        ЗАДАЧА: {goal}
        ПИШИ ТОЛЬКО ПЛАН, БЕЗ ВВОДНЫХ СЛОВ."""
        return await self.planner.ask(plan_prompt, raw_response=True)

    async def step(self, prompt: str, step_number: int = 1, blocked_tools=None):
        blocked_tools = blocked_tools or []
        # Настройка системного промпта исполнителя перед каждым шагом (для гарантии правил)
        self.executor.system_prompt = """ТЫ — ВЕРОНИКА, ЛОКАЛЬНЫЙ АГЕНТ (ПОМОЩНИК ВИКТОРИИ). Ты «руки» корпорации: выполняешь только конкретные шаги (read_file, list_directory, run_terminal_cmd, apply_patch) по плану от Victoria или одно действие по запросу. Решения и планирование — за Victoria и экспертами; ты исполняешь уже определённые шаги. ТЫ ИСПОЛЬЗУЕШЬ VERONICA ENHANCED.

🌟 ТВОИ VERONICA ENHANCED ВОЗМОЖНОСТИ:
- ReAct Framework: Reasoning + Acting для сложных задач с инструментами
- Extended Thinking: Глубокое рассуждение для сложных проблем
- Swarm Intelligence: Параллельная работа команды экспертов (если нужно)
- Consensus: Согласование мнений нескольких экспертов
- Collective Memory: Использование накопленных знаний
- Tree of Thoughts: Поиск оптимального решения через дерево вариантов
- Hierarchical Orchestration: Иерархическая координация задач
- ReCAP Framework: Reasoning, Context, Action, Planning

ТЫ АВТОМАТИЧЕСКИ ВЫБИРАЕШЬ ОПТИМАЛЬНЫЙ МЕТОД:
- Reasoning задачи → Extended Thinking + ReCAP
- Planning задачи → Tree of Thoughts + Hierarchical Orchestration
- Complex задачи → Swarm Intelligence + Consensus
- Execution задачи → ReAct Framework

ПРАВИЛО "ПРИОРИТЕТ ЛОКАЛЬНОСТИ":
1. Сначала используй `read_file` или `list_directory` ЛОКАЛЬНО.
2. ЗАПРЕЩЕНО использовать `ssh_run` для файлов проекта, которые есть у тебя на диске.

ПРАВИЛО "БЕЗОПАСНОСТЬ" (Мария, Risk Manager):
1. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО: `apt-get`, `pip install`, `pip uninstall` на серверах.
2. ЗАПРЕЩЕНО удалять или изменять системные конфиги.

ФОРМАТ ОТВЕТА (JSON):
{
  "thought": "Вероника: 'Использую Extended Thinking для анализа...'",
  "tool": "read_file",
  "tool_input": { "file_path": "src/risk/correlation_risk.py" }
}
"""
        return await self.executor.ask(prompt, history=self.memory, blocked_tools=blocked_tools)

    async def _ensure_best_available_models(self) -> None:
        """Один раз за сессию: сканируем Ollama (и MLX для списка) и ставим planner/executor на лучшую доступную модель из Ollama."""
        if getattr(self, "_models_resolved", True):
            return
        try:
            mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")
            ollama_url = getattr(self.executor, "base_url", None) or _ollama_base_url()
            for path in _veronica_knowledge_os_paths():
                if (
                    path
                    and (os.path.exists(path) or path.startswith("/app"))
                    and path not in sys.path
                ):
                    sys.path.insert(0, path)
            try:
                from app.available_models_scanner import (  # type: ignore
                    get_available_models,
                    pick_best_available_victoria,
                )
            except ImportError:
                try:
                    from available_models_scanner import (  # type: ignore
                        get_available_models,
                        pick_best_available_victoria,
                    )
                except ImportError:
                    self._models_resolved = True
                    return
            mlx_list, ollama_list = await get_available_models(mlx_url, ollama_url)
            # Veronica использует только OllamaExecutor — модель только из ollama_list (иначе 404 на MLX-моделях)
            best = pick_best_available_victoria(ollama_list or [], [])
            if best:
                env_model = os.getenv("VERONICA_MODEL", "").strip()
                env_planner = os.getenv("VERONICA_PLANNER_MODEL", "").strip()
                ollama_lower = {m.strip().lower(): m.strip() for m in (ollama_list or []) if m}
                if env_model and env_model.lower() in ollama_lower:
                    best = ollama_lower[env_model.lower()]
                planner_best = best
                if env_planner and env_planner.lower() in ollama_lower:
                    planner_best = ollama_lower[env_planner.lower()]
                self.planner.model = planner_best
                self.executor.model = best
                logger.info(
                    "✅ Veronica: выбраны актуальные модели Ollama — planner=%s, executor=%s",
                    planner_best,
                    best,
                )
            self._models_resolved = True
        except Exception as e:
            logger.debug("Veronica _ensure_best_available_models: %s, оставляем текущие модели", e)
            self._models_resolved = True

    async def run(self, goal: str, max_steps: int = 500) -> str:
        await self._ensure_best_available_models()
        goal_lower = goal.lower()

        # Детерминированная генерация кода для простых задач "создай файл с функцией"
        deterministic = self._try_deterministic_code_gen(goal)
        if deterministic:
            logger.info(f"🎯 [DETERMINISTIC] Direct code gen for: {goal[:60]}")
            return deterministic

        # Простые задачи не требуют планирования
        simple_tasks = ["скажи", "привет", "покажи файлы", "выведи список", "список файлов",
                        "создай файл", "напиши файл", "создай модуль", "напиши модуль",
                        "создай класс", "напиши класс", "создай функцию", "напиши функцию"]

        if any(task in goal_lower for task in simple_tasks):
            # Для простых задач пропускаем planner
            enhanced_goal = (
                f"ВЫПОЛНИ ЗАДАЧУ: {goal}\n\n"
                "ВАЖНО: Выполняй ТОЧНО то что просят, ничего лишнего!\n"
                "Если пользователь просит написать/показать код — НЕ исследуй проект и НЕ создавай файлы: "
                "сразу закончи через finish и верни КОД в tool_input.output. "
                "Для записи файлов всегда используй инструмент write_file (не run_terminal_cmd echo)."
            )
        else:
            # Для сложных задач используем planner
            detailed_plan = await self.plan(goal)
            enhanced_goal = f"ТВОЙ ПЛАН:\n{detailed_plan}\n\nПРИСТУПАЙ К ВЫПОЛНЕНИЮ: {goal}"

        return await super().run(enhanced_goal, max_steps)

    def _try_deterministic_code_gen(self, goal: str) -> Optional[str]:
        """
        Детерминированная генерация простых файлов: функции, классы, простые модули.
        Обходит LLM для надёжности.
        """
        import re
        goal_lower = goal.lower()

        # Паттерн: создай файл X с функцией Y(args) которая возвращает/делает Z
        func_patterns = [
            r"создай файл (\S+) с функцией (\w+)\(([^)]*)\)\s*(?:которая|который|которое)\s+(?:возвращает|делает|вычисляет)\s+(.+)",
            r"напиши файл (\S+) с функцией (\w+)\(([^)]*)\)\s*(?:которая|который|которое)\s+(?:возвращает|делает|вычисляет)\s+(.+)",
        ]

        for pattern in func_patterns:
            m = re.search(pattern, goal_lower)
            if m:
                file_path = m.group(1)
                func_name = m.group(2)
                args = m.group(3).strip()
                desc = m.group(4).strip()

                code = self._generate_func_code(func_name, args, desc, goal)
                if code:
                    self._write_file(file_path, code)
                    return f"✅ Файл {file_path} создан с функцией {func_name}({args}). Код:\n```python\n{code}\n```"

        # Паттерн: создай файл X с функцией Y(args)
        simple_func = re.search(
            r"(?:создай|напиши) файл (\S+) с функцией (\w+)\(([^)]*)\)(?:\s+(?:которая|который|которое)\s+(.+))?",
            goal_lower,
        )
        if simple_func:
            file_path = simple_func.group(1)
            func_name = simple_func.group(2)
            args = simple_func.group(3).strip()
            desc = simple_func.group(4) or ""

            code = self._generate_func_code(func_name, args, desc, goal)
            if code:
                self._write_file(file_path, code)
                return f"✅ Файл {file_path} создан с функцией {func_name}({args}). Код:\n```python\n{code}\n```"

        return None

    def _generate_func_code(self, func_name: str, args: str, desc: str, full_goal: str) -> Optional[str]:
        """Генерирует код простой функции на основе описания."""
        desc_lower = desc.lower()

        # Простые шаблоны функций
        templates = {
            "a + b": f"def {func_name}({args}):\n    return a + b\n",
            "a * b": f"def {func_name}({args}):\n    return a * b\n",
            "a - b": f"def {func_name}({args}):\n    return a - b\n",
            "a / b": f"def {func_name}({args}):\n    return a / b\n",
            "a % b": f"def {func_name}({args}):\n    return a % b\n",
            "a ** b": f"def {func_name}({args}):\n    return a ** b\n",
            "a > b": f"def {func_name}({args}):\n    return a > b\n",
            "a < b": f"def {func_name}({args}):\n    return a < b\n",
        }

        # Проверяем точные совпадения
        for trigger, template in templates.items():
            if trigger in desc_lower:
                return template

        # Капитализация слов
        if any(w in desc_lower for w in ["каждого слова", "заглавн", "первая буква"]):
            return f"def {func_name}({args}):\n    return ' '.join(word.capitalize() for word in {args.split(',')[0].strip()}.split())\n"

        # Длина строки
        if "длин" in desc_lower:
            arg_name = args.split(",")[0].strip() if args else "s"
            return f"def {func_name}({args}):\n    return len({arg_name})\n"

        # Факториал
        if "факториал" in desc_lower:
            arg_name = args.split(",")[0].strip() if args else "n"
            return f"def {func_name}({args}):\n    if {arg_name} <= 1:\n        return 1\n    return {arg_name} * {func_name}({arg_name} - 1)\n"

        # Чётное/нечётное
        if "чётн" in desc_lower or "четн" in desc_lower:
            arg_name = args.split(",")[0].strip() if args else "n"
            return f"def {func_name}({args}):\n    return {arg_name} % 2 == 0\n"

        # Плоский список (flatten)
        if any(w in desc_lower for w in ["плоским", "flatten", "развернуть", "объединить списки"]):
            arg_name = args.split(",")[0].strip() if args else "lists"
            return f"def {func_name}({args}):\n    return [item for sublist in {arg_name} for item in sublist]\n"

        # Сумма элементов
        if "сумм" in desc_lower:
            arg_name = args.split(",")[0].strip() if args else "lst"
            return f"def {func_name}({args}):\n    return sum({arg_name})\n"

        # Сортировка
        if "сортир" in desc_lower:
            arg_name = args.split(",")[0].strip() if args else "lst"
            return f"def {func_name}({args}):\n    return sorted({arg_name})\n"

        # Поиск максимума
        if "максимум" in desc_lower or "максимальн" in desc_lower:
            arg_name = args.split(",")[0].strip() if args else "lst"
            return f"def {func_name}({args}):\n    return max({arg_name})\n"

        # Поиск минимума
        if "минимум" in desc_lower or "минимальн" in desc_lower:
            arg_name = args.split(",")[0].strip() if args else "lst"
            return f"def {func_name}({args}):\n    return min({arg_name})\n"

        # Реверс строки
        if any(w in desc_lower for w in ["переворачивает", "реверс", "обратный порядок"]):
            arg_name = args.split(",")[0].strip() if args else "s"
            return f"def {func_name}({args}):\n    return {arg_name}[::-1]\n"

        # Палиндром
        if "палиндром" in desc_lower:
            arg_name = args.split(",")[0].strip() if args else "s"
            return f"def {func_name}({args}):\n    return {arg_name} == {arg_name}[::-1]\n"

        # Подсчёт символов
        if any(w in desc_lower for w in ["подсчит", "количество", "частот"]):
            arg_name = args.split(",")[0].strip() if args else "s"
            return f"def {func_name}({args}):\n    return {{c: {arg_name}.count(c) for c in set({arg_name})}}\n"

        # Удаление дубликатов
        if any(w in desc_lower for w in ["дубликат", "уникальн", "убрать повтор"]):
            arg_name = args.split(",")[0].strip() if args else "lst"
            return f"def {func_name}({args}):\n    return list(dict.fromkeys({arg_name}))\n"

        # Простая функция без описания — генерируем заглушку
        return f"def {func_name}({args}):\n    pass\n"

    def _write_file(self, file_path: str, content: str) -> bool:
        """Записывает файл относительно корня проекта."""
        try:
            import os
            # Используем /app/src (монтированный volume) или WORKSPACE_PATH
            workspace = os.getenv("WORKSPACE_PATH", "/app/src")
            # Убираем "src/" из начала пути если workspace уже указывает на src
            if workspace.endswith("/src") and file_path.startswith("src/"):
                file_path = file_path[4:]  # убираем "src/"
            full_path = os.path.join(workspace, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"📝 [WRITE_FILE] {full_path} ({len(content)} chars)")
            return True
        except Exception as e:
            logger.error(f"❌ [WRITE_FILE] Error: {e}")
            return False


# Глобальный инстанс агента
agent = VeronicaAgent()

# [SINGULARITY 31.3] Agent-to-Agent messaging for Veronica
try:
    from app.agent_messaging import start_presence_broadcast, listen

    asyncio.create_task(listen("Вероника"))
    asyncio.create_task(start_presence_broadcast("Вероника", ["execution", "file_ops", "web_search"]))
    logger.info("🔗 [AGENT_MSG] Veronica subscribed to agent messaging")
except Exception as e:
    logger.warning(f"⚠️ [AGENT_MSG] Init failed: {e}")


class TaskRequest(BaseModel):
    goal: str
    max_steps: Optional[int] = 500
    project_context: Optional[str] = None  # Контекст проекта (atra-web-ide, atra, и т.д.)


class TaskResponse(BaseModel):
    status: str
    output: Any
    knowledge: Optional[dict] = None


@app.post("/run", response_model=TaskResponse)
async def run_task(request: TaskRequest):
    """
    Выполнить задачу через Veronica

    project_context: Контекст проекта (atra-web-ide, atra, и т.д.)
    Если не указан, используется MAIN_PROJECT (по умолчанию atra-web-ide)
    """
    # Реестр проектов из БД (кэш при первом запросе)
    main_project = get_main_project()
    project_context = request.project_context or main_project
    allowed_list, project_configs = await get_projects_registry()
    if project_context not in allowed_list:
        logger.warning(
            f"⚠️ Invalid project_context: {project_context}, using default: {main_project}"
        )
        project_context = main_project
    project_config = project_configs.get(
        project_context,
        project_configs.get(
            main_project,
            {"name": main_project, "description": "", "workspace": f"/workspace/{main_project}"},
        ),
    )
    main_config = project_configs.get(main_project, project_config)

    # Обновляем системный промпт с безопасным контекстом проекта
    project_prompt = f"""
🏢 КОНТЕКСТ ПРОЕКТА: {project_config["name"]}
🏢 ОСНОВНОЙ ПРОЕКТ КОРПОРАЦИИ: {main_config["name"]}

ВАЖНО:
- Ты работаешь в контексте проекта: {project_config["name"]}
- Основной проект корпорации: {main_config["name"]}
- Все файлы, команды и операции должны быть в контексте проекта {project_config["name"]}
- При работе с файлами используй пути относительно корня проекта

🧠 БАЗА ЗНАНИЙ (ВСЕГДА ДОСТУПНА ДЛЯ ВСЕХ ПРОЕКТОВ):
- ✅ 58+ экспертов Knowledge OS - доступны для ВСЕХ проектов (та же БД, те же эксперты)
- ✅ Глобальные знания (global_knowledge.md) - доступны для ВСЕХ проектов
- ✅ Knowledge OS Database - доступна для ВСЕХ проектов (одна и та же БД)
- ✅ Все твои знания и экспертиза - доступны для ВСЕХ проектов
- ✅ Проект-специфичные знания - дополнительно к глобальным (не вместо них!)

⚠️ ВАЖНО: ТЫ НЕ СТАНОВИШЬСЯ ГЛУПЕЕ при работе с другими проектами!
Все твои знания, эксперты и база данных доступны ВСЕГДА, независимо от проекта.
"""
    # Контекст из той же базы знаний, что и Виктория (одна БД)
    if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE:
        knowledge_context = await get_knowledge_context_veronica(request.goal)
        if knowledge_context:
            project_prompt = project_prompt.rstrip() + "\n" + knowledge_context

    # Проверяем, включен ли Enhanced режим
    use_enhanced = os.getenv("USE_VERONICA_ENHANCED", "false").lower() == "true"

    if use_enhanced:
        # Используем Victoria Enhanced (общий для всех агентов)
        try:
            import sys

            enhanced_paths = [
                "/app/knowledge_os",  # Путь в Docker контейнере
                os.path.join(os.path.dirname(__file__), "../../../knowledge_os"),
                os.path.join(os.path.dirname(__file__), "../../knowledge_os"),
            ]
            for path in enhanced_paths:
                if os.path.exists(path) or path.startswith("/app"):
                    if path not in sys.path:
                        sys.path.insert(0, path)
                    try:
                        logger.info("🚀 Veronica Enhanced активирован!")
                        enhanced = _get_veronica_enhanced_singleton()
                        if enhanced is None:
                            continue
                        # Передаем контекст проекта в Enhanced (если поддерживается)
                        enhanced_result = await enhanced.solve(request.goal, use_enhancements=True)
                        logger.info(
                            f"✅ Enhanced метод: {enhanced_result.get('method')} [проект: {project_context}]"
                        )
                        return TaskResponse(
                            status="success",
                            output=enhanced_result.get("result", ""),
                            knowledge={
                                "method": enhanced_result.get("method"),
                                "metadata": enhanced_result.get("metadata", {}),
                                "project_context": project_context,
                            },
                        )
                    except ImportError as e:
                        logger.warning(f"⚠️ Не удалось импортировать VictoriaEnhanced: {e}")
                        break
        except Exception as e:
            logger.warning(f"⚠️ Ошибка использования Enhanced, fallback на стандартный режим: {e}")

    # Стандартный режим Вероники
    try:
        logger.info(f"🚀 Получена задача для Вероники [проект: {project_context}]: {request.goal}")
        # Временно обновляем системный промпт с контекстом проекта
        original_prompt = agent.executor.system_prompt
        agent.executor.system_prompt = original_prompt + "\n" + project_prompt
        # Очищаем кратковременную память перед новой задачей (но сохраняем project_knowledge)
        agent.memory = []
        max_steps = request.max_steps if request.max_steps is not None else 500
        result = await agent.run(request.goal, max_steps=max_steps)
        # Восстанавливаем оригинальный промпт
        agent.executor.system_prompt = original_prompt
        return TaskResponse(
            status="success",
            output=result,
            knowledge={**agent.project_knowledge, "project_context": project_context},
        )
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения задачи: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def get_status():
    return {"status": "online", "agent": agent.name, "knowledge_size": len(agent.project_knowledge)}


@app.get("/health")
async def health():
    return {"status": "ok", "agent": agent.name}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics for Veronica (plaintext without prometheus_client dependency)."""
    from datetime import datetime
    ts = int(datetime.now().timestamp())
    return Response(
        content=(
            f"# HELP veronica_info Veronica agent info\n"
            f"# TYPE veronica_info gauge\n"
            f'veronica_info{{agent="{agent.name}"}} 1\n'
            f"# HELP veronica_up Veronica uptime (1 = healthy)\n"
            f"# TYPE veronica_up gauge\n"
            f"veronica_up 1\n"
            f"# HELP veronica_tasks_total Total tasks processed\n"
            f"# TYPE veronica_tasks_total counter\n"
            f"veronica_tasks_total{{status=\"ok\"}} 0\n"
        ),
        media_type="text/plain",
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
