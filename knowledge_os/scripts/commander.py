import asyncio
import sys
import os
import json
import logging

# Добавляем корень проекта в пути
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.core.base_agent import AtraBaseAgent, AgentAction, AgentFinish
from src.agents.core.executor import OllamaExecutor, _ollama_base_url
from src.agents.tools.system_tools import SystemTools, WebTools

class VictoriaAgent(AtraBaseAgent):
    """Реальная реализация агента Виктории, использующая Ollama / MLX"""
    
    def __init__(self, name: str, model_name: str = None):
        # Автовыбор модели: None = сканирование Ollama при первом запросе
        model_name = model_name or os.getenv("VICTORIA_MODEL") or None
        super().__init__(name, model_name or "auto")
        base = _ollama_base_url()
        planner_model = os.getenv("VICTORIA_PLANNER_MODEL") or None
        self.planner = OllamaExecutor(model=planner_model, base_url=base)
        self.executor = OllamaExecutor(model=model_name, base_url=base)
        
        # Регистрация системных инструментов
        self.add_tool("read_file", SystemTools.read_project_file)
        self.add_tool("run_terminal_cmd", SystemTools.run_local_command)
        self.add_tool("ssh_run", SystemTools.run_ssh_command)
        self.add_tool("list_directory", SystemTools.list_directory)
        self.add_tool("web_search", WebTools.web_search)

    async def plan(self, goal: str):
        # Если цель "повтори", мы не очищаем память, а используем её для контекста
        if goal.lower() not in ["повтори", "еще раз", "давай заново"]:
            self.memory = []
            self.executed_commands_hash = [] # Сброс истории команд только при новой задаче
            
        print(f"🧠 [DeepSeek-R1] Виктория прорабатывает стратегию...")
        plan_prompt = f"""ТЫ — ТЕХНИЧЕСКИЙ ДИРЕКТОР ATRA. Составь СТРОГИЙ пошаговый план.
ЗАДАЧА: {goal}
БАЗА ДАННЫХ: /root/atra/trading.db
ПЛАН (пример):
1. DROP TABLE IF EXISTS rejected_signals;
2. CREATE TABLE rejected_signals (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT, reason TEXT, strategy TEXT);
3. PRAGMA table_info(rejected_signals);
ОБЯЗАТЕЛЬНО: Проверь, что в CREATE TABLE именно те поля, которые просил Босс.
ПИШИ ТОЛЬКО ПЛАН, БЕЗ ВВОДНЫХ СЛОВ."""
        # Получаем RAW текст
        return await self.planner.ask(plan_prompt, raw_response=True)

    async def step(self, prompt: str):
        # Ограничиваем историю последних 10 сообщений, чтобы не перегружать контекст 7B модели
        context_memory = self.memory[-10:] if len(self.memory) > 10 else self.memory
        return await self.executor.ask(prompt, history=context_memory)

    async def run(self, goal: str, max_steps: int = 500) -> str:
        # 1. Глубокое планирование (DeepSeek)
        raw_plan = await self.plan(goal)
        print(f"📋 СТРАТЕГИЯ СФОРМИРОВАНА.\n")
        
        # 2. Исполнение (Qwen)
        enhanced_goal = f"ТВОЙ ПЛАН ОТ ГЕНШТАБА:\n{raw_plan}\n\nПРИСТУПАЙ К ВЫПОЛНЕНИЮ ЦЕЛИ: {goal}"
        return await super().run(enhanced_goal, max_steps)

async def main():
    print("\n" + "="*50)
    print("🤖 ATRA COMMAND CENTER (Autonomous Agent)")
    print("="*50)
    print("Я готов выполнять твои задачи через Ollama.")
    print("Brain: phi3.5:3.8b | Hands: qwen2.5-coder:32b")
    print("Для выхода напиши 'exit' или 'выход'.\n")

    agent = VictoriaAgent(name="Victoria")
    
    # ОЧЕНЬ ЖЕСТКИЙ ПРОМПТ ДЛЯ ИСПОЛНИТЕЛЯ
    agent.executor.system_prompt = """ТЫ — ВИКТОРИЯ, TEAM LEAD КОРПОРАЦИИ ATRA. ТЫ ИСПОЛЬЗУЕШЬ VICTORIA ENHANCED.

🌟 ТВОИ VICTORIA ENHANCED ВОЗМОЖНОСТИ:
- ReAct Framework: Reasoning + Acting для сложных задач
- Extended Thinking: Глубокое рассуждение для сложных проблем
- Swarm Intelligence: Параллельная работа команды экспертов
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

Твоя задача — управлять командой из 40+ экспертов для решения задач Босса.

ПРАВИЛО "АНТИ-ПЛЕЙСХОЛДЕР":
НИКОГДА не используй в командах слова 'table_name', 'your_command', 'команда'. Это ПРИМЕРЫ. 
Если ты не знаешь точного имени — сначала найди его (ls, grep, .tables), а потом делай.

ТВОЯ КОМАНДА:
1. 🔧 Сергей (DevOps) - серверы, SSH, безопасность.
2. 💻 Игорь (Backend) - Python, базы данных, API.
3. 🧠 Дмитрий (ML) - нейросети, обучение моделей.
4. 📊 Максим (Analyst) - данные, Rust-модуль, бэктесты.
5. 🧪 Анна (QA) - тесты, валидация результатов.
6. ⚠️ Мария (Risk Manager) - проверка опасных команд.

ПРАВИЛА "МАКСИМУМ":
1. АВТОНОМНОСТЬ: Никогда не проси Босса "сделать это самому". Используй инструменты.
2. ПРОВЕРКА: Перед завершением ВСЕГДА проверяй результат (PRAGMA, SELECT, ls).
3. БЕЗОПАСНОСТЬ: Если команда опасная (DROP, rm, убить процесс) — сначала напиши мысль от Марии.
4. ЗНАНИЯ: Если ты узнала что-то важное (путь к файлу, схема БД), пиши в конце мысли: KNOWLEDGE: {"files_found": ["path/to/file"]}

ИНСТРУМЕНТЫ:
- ssh_run: для серверов 185.177.216.15 и 46.149.66.170.
- apply_patch: для безопасного изменения кода.
- grep_search: для быстрого поиска по проекту.

ФОРМАТ ОТВЕТА (JSON):
{
  "thought": "Виктория (Team Lead): 'Игорь, создай таблицу. Мария, проверь риски...'",
  "tool": "ssh_run",
  "tool_input": { "host": "185.177.216.15", "command": "sqlite3 ..." }
}
"""

    while True:
        try:
            user_input = input("👤 Ты: ")
            if user_input.lower() in ['exit', 'выход', 'quit']:
                print("👋 До связи, Босс!")
                break

            if not user_input.strip():
                continue

            print("\n⚙️  Агент Виктория думает...")
            # Запускаем основной цикл агента
            final_output = await agent.run(user_input)
            
            print(f"\n✅ Ответ Виктории:\n{final_output}\n")
            print("-" * 50)
            
        except KeyboardInterrupt:
            print("\n👋 До связи, Босс!")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {str(e)}")

if __name__ == "__main__":
    # Настройка логирования для видимости шагов агента
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    asyncio.run(main())
