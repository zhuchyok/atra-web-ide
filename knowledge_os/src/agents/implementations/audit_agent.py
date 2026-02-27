import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

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

        # [SINGULARITY 20.0] Hybrid Strategist/Executor Architecture
        # Strategist (Wisdom) lives on MLX (11435), Executor (Qwen3) on Ollama (11434)
        self.strategist_model = os.getenv("VICTORIA_STRATEGIST_MODEL", "victoria-wisdom-30b")
        self.executor_model = os.getenv("VICTORIA_EXECUTOR_MODEL", "qwen3-coder:30b")

        self.strategist_executor = OllamaExecutor(
            model=self.strategist_model, base_url="http://localhost:11435"
        )
        self.worker_executor = OllamaExecutor(
            model=self.executor_model, base_url="http://localhost:11434"
        )

        # По умолчанию используем стратега для планирования и воркера для шагов
        self.executor = self.worker_executor

        # Регистрация инструментов
        self.add_tool("read_file", SystemTools.read_project_file)
        self.add_tool("run_terminal_cmd", SystemTools.run_local_command)
        self.add_tool("ssh_run", SystemTools.run_ssh_command)
        self.add_tool("generate_sop_skill", SystemTools.generate_sop_skill)

    async def plan(self, goal: str):
        # В будущем здесь будет LLM-планировщик
        return ["Check server availability", "Inspect main.log", "Verify DB health"]

    async def step(
        self, prompt: str, step_number: int = 1, blocked_tools: Optional[List[str]] = None
    ):
        """Выполнение одного шага через OllamaExecutor"""
        # Преобразуем историю памяти для Ollama
        history = []
        for m in self.memory:
            history.append({"role": m["role"], "content": m["content"]})

        result = await self.executor.ask(prompt, history=history, blocked_tools=blocked_tools)

        # [SINGULARITY 20.0] Logging and Debugging
        model_name = getattr(self.executor, "model", "unknown")
        print(f"🤖 [STEP {step_number}] Model: {model_name} | Result: {type(result)}")

        if isinstance(result, (AgentAction, AgentFinish)):
            return result
        else:
            # Обработка ошибки парсинга
            return AgentFinish(
                output=f"Error: {result.get('error') if isinstance(result, dict) else str(result)}",
                thought="I encountered an error.",
            )

    async def scan_logs_for_errors(self, log_path: str, keywords: List[str] = None) -> List[str]:
        """План «аудит» п.3.1: сканирование логов на наличие ошибок."""
        keywords = keywords or ["ERROR", "Exception", "Critical", "Timeout", "404", "500"]
        errors = []
        try:
            if os.path.exists(log_path):
                with open(log_path) as f:
                    # Читаем последние 500 строк
                    lines = f.readlines()[-500:]
                    for line in lines:
                        if any(k in line for k in keywords):
                            errors.append(line.strip())
        except Exception as e:
            logger.error(f"Ошибка при сканировании лога {log_path}: {e}")
        return errors

    async def self_heal(self, error_pattern: str):
        """План «аудит» п.3.2: попытка автоматического исправления известных ошибок."""
        healing_registry = {
            "database connection": "scripts/system_auto_recovery.sh --fix-db",
            "ollama connection": "scripts/system_auto_recovery.sh --restart-ollama",
            "redis connection": "scripts/system_auto_recovery.sh --restart-redis",
            "victoria-agent": "docker-compose restart victoria-agent",
            "expert-worker": "docker-compose restart expert-worker",
            "429 too many requests": "scripts/system_auto_recovery.sh --fix-rate-limits",
            "readtimeout": "scripts/system_auto_recovery.sh --check-models",
        }

        for pattern, cmd in healing_registry.items():
            if pattern in error_pattern.lower():
                logger.info(f"🩹 [SELF-HEAL] Обнаружена ошибка '{pattern}', запускаю: {cmd}")
                try:
                    await SystemTools.run_local_command(cmd)
                    return True
                except Exception as e:
                    logger.error(f"❌ Ошибка при выполнении команды восстановления: {e}")
        return False

    async def scan_interaction_logs(self) -> List[str]:
        """План «аудит» п.3.1: сканирование interaction_logs на наличие аномалий."""
        anomalies = []
        try:
            from app.db_pool import get_pool

            pool = await get_pool()
            async with pool.acquire() as conn:
                # Ищем последние 20 записей с низким качеством или ошибками
                rows = await conn.fetch("""
                    SELECT query, response, error_msg
                    FROM interaction_logs
                    WHERE (error_msg IS NOT NULL AND error_msg != '')
                    OR (metadata->>'quality_score')::float < 0.4
                    ORDER BY created_at DESC
                    LIMIT 20
                """)
                for r in rows:
                    anomalies.append(
                        f"Query: {r['query']} | Error: {r['error_msg'] or 'Low quality'}"
                    )
        except Exception as e:
            logger.debug(f"Interaction logs scan skip: {e}")
        return anomalies

    async def run_full_audit(self, blocked_tools: Optional[List[str]] = None):
        """Запуск полного автономного аудита системы"""
        logger.info("🕵️ [AUDIT] Запуск гибридного аудита: Стратег (Wisdom) + Исполнитель (Qwen3)")

        # 1. Сканируем логи файлов (Исполнитель)
        log_files = ["victoria_bot.log", "victoria_server.log", "knowledge_os/logs/main.log"]
        all_errors = []
        for log in log_files:
            errors = await self.scan_logs_for_errors(log)
            if errors:
                all_errors.extend(errors)
                # Пытаемся исправить последнюю ошибку (Исполнитель)
                await self.self_heal(errors[-1])

        # 2. Сканируем interaction_logs (Исполнитель)
        anomalies = await self.scan_interaction_logs()
        all_errors.extend(anomalies)

        # 3. Формируем отчет для Стратега (Wisdom)
        goal = f"""Выполни полный аудит системы ATRA:
1. Проверь статус инфраструктуры (Docker, Ollama, DB).
2. Проанализируй ошибки в логах и БД на Mac Studio. Найдено аномалий: {len(all_errors)}.
3. Предложи улучшения для предотвращения повторных сбоев.
"""
        # Переключаем исполнителя на Стратега для финального анализа и планирования
        old_executor = self.executor
        self.executor = self.strategist_executor
        try:
            result = await self.run(goal, blocked_tools=blocked_tools)
            return result
        finally:
            self.executor = old_executor


if __name__ == "__main__":
    # Пример запуска (в реальной системе будет вызываться через оркестратор)
    agent = AuditAgent()
    asyncio.run(agent.run_full_audit())
