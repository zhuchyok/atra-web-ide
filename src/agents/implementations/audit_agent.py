import asyncio
import logging
import os

from ..core.base_agent import AgentAction, AgentFinish, AtraBaseAgent
from ..core.executor import OllamaExecutor
from ..tools.system_tools import SystemTools

logger = logging.getLogger(__name__)


class AuditAgent(AtraBaseAgent):
    """
    Автономный агент для аудита и мониторинга системы ATRA.
    """

    def __init__(self, model_name: str = None):
        # Автовыбор модели: None = сканирование Ollama при первом запросе
        super().__init__(name="AuditAgent", model_name=model_name)

        # [SINGULARITY 20.0] Mirror Wisdom Architecture
        self.model_name = model_name or os.getenv("VICTORIA_MODEL", "victoria-wisdom-v3.5")
        self.executor = OllamaExecutor(model=self.model_name)

        # Регистрация инструментов
        self.add_tool("read_file", SystemTools.read_project_file)
        self.add_tool("run_terminal_cmd", SystemTools.run_local_command)
        self.add_tool("ssh_run", SystemTools.run_ssh_command)

    async def plan(self, goal: str):
        # В будущем здесь будет LLM-планировщик
        return ["Check server availability", "Inspect main.log", "Verify DB health"]

    async def step(self, prompt: str, step_number: int = 1, blocked_tools: list[str] = None):
        """Выполнение одного шага через OllamaExecutor"""
        # Преобразуем историю памяти для Ollama
        history = []
        for m in self.memory:
            # Пропускаем системные сообщения, так как они добавляются в OllamaExecutor.ask
            if m.get("role") == "system":
                continue
            history.append({"role": m.get("role", "user"), "content": m.get("content", "")})

        print(f"🤖 [AuditAgent] Calling executor.ask for step {step_number}...")
        try:
            # [STRICT] Добавляем инструкцию о формате в каждый шаг, чтобы избежать галлюцинаций
            step_prompt = (
                prompt
                + '\n\nОТВЕТЬ СТРОГО В ФОРМАТЕ JSON: {"thought": "...", "tool": "...", "tool_input": {...}}'
            )
            result = await self.executor.ask(
                step_prompt, history=history, blocked_tools=blocked_tools
            )

            # [SINGULARITY 20.0] Logging and Debugging
            model_name = getattr(self.executor, "model", "unknown")
            print(f"🤖 [STEP {step_number}] Model: {model_name} | Result type: {type(result)}")

            if isinstance(result, (AgentAction, AgentFinish)):
                # Если это AgentFinish, но мы на первом шаге и нет реальных действий - это галлюцинация
                if isinstance(result, AgentFinish) and step_number <= 2:
                    print(
                        f"⚠️ [STEP {step_number}] Model tried to finish too early. Forcing action."
                    )
                    return AgentAction(
                        tool="run_terminal_cmd",
                        tool_input={
                            "command": "docker ps --format 'table {{.Names}}\t{{.Status}}'"
                        },
                        thought="Мне нужно начать с проверки статуса Docker-контейнеров.",
                    )
                return result
            elif isinstance(result, dict) and "error" in result:
                # Возвращаем ошибку как словарь, чтобы BaseAgent её обработал
                print(f"❌ [STEP {step_number}] Executor returned error: {result['error']}")
                return result
            else:
                # Обработка ошибки парсинга или неожиданного формата
                output = (
                    f"Error: {result.get('error') if isinstance(result, dict) else str(result)}"
                )
                print(f"❌ [STEP {step_number}] Unexpected result format: {output}")
                return AgentFinish(output=output, thought="I encountered an error.")
        except Exception as e:
            print(f"❌ [STEP {step_number}] Exception in executor.ask: {str(e)}")
            return {"error": str(e)}

    async def run_full_audit(self):
        """Запуск полного автономного аудита системы на Mac Studio"""
        goal = """Выполни полный аудит системы ATRA на локальной машине (Mac Studio):
1. Проверь статус всех Docker-контейнеров.
2. Проверь наличие критических ошибок в логах (/Users/bikos/Documents/atra-web-ide/*.log).
3. Убедись, что база данных PostgreSQL (knowledge_os) доступна и содержит свежие данные в таблице knowledge_nodes.
4. Проверь использование ресурсов (CPU, RAM, Swap).

ВНИМАНИЕ: НЕ подключайся к внешним серверам (185.177.216.15, 46.149.66.170). Работай только локально.
"""
        print(f"🚀 [AuditAgent] Starting full audit with goal: {goal}")
        try:
            result = await self.run(goal)
            print(f"✅ [AuditAgent] Audit finished. Result: {result}")
            return result
        except Exception as e:
            print(f"❌ [AuditAgent] Audit failed with error: {str(e)}")
            raise


if __name__ == "__main__":
    # Пример запуска (в реальной системе будет вызываться через оркестратор)
    agent = AuditAgent()
    asyncio.run(agent.run_full_audit())
