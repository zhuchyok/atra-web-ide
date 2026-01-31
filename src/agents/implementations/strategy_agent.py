import logging
import asyncio
from typing import Dict, Any, Optional
from ..core.base_agent import AtraBaseAgent, AgentAction, AgentFinish
from ..core.executor import OllamaExecutor
from ..tools.system_tools import SystemTools

logger = logging.getLogger(__name__)

class StrategyAgent(AtraBaseAgent):
    """
    Автономный агент для анализа рынка и оптимизации параметров стратегии.
    """
    
    def __init__(self, model_name: str = None):
        # Автовыбор модели: None = сканирование Ollama при первом запросе
        super().__init__(name="StrategyAgent", model_name=model_name)
        self.executor = OllamaExecutor(model=model_name)
        
        # Инструменты для стратегии
        self.add_tool("read_config", SystemTools.read_project_file)
        self.add_tool("run_backtest", self._run_backtest_tool)
        self.add_tool("update_param", self._update_config_param)

    async def _run_backtest_tool(self, symbol: str, days: int = 7) -> str:
        """Инструмент для запуска бэктеста через Rust"""
        cmd = f"python3 scripts/run_backtests_rust.py --symbol {symbol} --days {days}"
        return await SystemTools.run_local_command(cmd)

    async def _update_config_param(self, param_name: str, value: Any) -> str:
        """Инструмент для обновления параметров в config.py"""
        # В реальной реализации здесь будет умная замена через AST или sed
        logger.info(f"⚙️ StrategyAgent updating {param_name} to {value}")
        return f"Successfully updated {param_name} to {value} (simulated)"

    async def step(self, prompt: str):
        # Аналогично AuditAgent, но с другим контекстом
        return await self.executor.ask(prompt)

    async def optimize_risk(self, symbol: str):
        """Задача: проанализировать волатильность и предложить оптимальный Stop Loss"""
        goal = f"""Проанализируй волатильность {symbol} за последние 24 часа. 
1. Прочитай текущий config.py.
2. Запусти бэктест с разными значениями SL (от 0.5% до 2%).
3. Если найдешь значение лучше текущего — обнови параметр в конфиге.
"""
        return await self.run(goal)

