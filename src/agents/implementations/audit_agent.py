import asyncio
import logging
from ..core.base_agent import AtraBaseAgent, AgentAction, AgentFinish
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
        self.executor = OllamaExecutor(model=model_name)
        
        # Регистрация инструментов
        self.add_tool("read_file", SystemTools.read_project_file)
        self.add_tool("run_terminal_cmd", SystemTools.run_local_command)
        self.add_tool("ssh_run", SystemTools.run_ssh_command)

    async def plan(self, goal: str):
        # В будущем здесь будет LLM-планировщик
        return ["Check server availability", "Inspect main.log", "Verify DB health"]

    async def step(self, prompt: str):
        """Выполнение одного шага через OllamaExecutor"""
        # Преобразуем историю памяти для Ollama
        history = []
        for m in self.memory:
            history.append({"role": "user", "content": m["input"]})
            history.append({"role": "assistant", "content": m["output"]})
            
        result = await self.executor.ask(prompt, history=history)
        
        if isinstance(result, (AgentAction, AgentFinish)):
            return result
        else:
            # Обработка ошибки парсинга
            return AgentFinish(output=f"Error: {result.get('error')}", thought="I encountered an error.")

    async def run_full_audit(self):
        """Запуск полного автономного аудита системы"""
        goal = """Выполни полный аудит системы ATRA:
1. Проверь статус бота на 185.177.216.15.
2. Проверь наличие ошибок в nightly_learner.log на 46.149.66.170.
3. Убедись, что база данных trading.db на локальной машине содержит свежие сигналы.
"""
        return await self.run(goal)

if __name__ == "__main__":
    # Пример запуска (в реальной системе будет вызываться через оркестратор)
    agent = AuditAgent()
    asyncio.run(agent.run_full_audit())

