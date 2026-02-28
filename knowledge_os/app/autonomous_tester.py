import asyncio
import os
import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("autonomous_tester")

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

class AutonomousTester:
    """
    [SINGULARITY 24.0] Autonomous Self-Healing Tester.
    Nightly QA Worker that verifies system stability and fixes broken tests.
    """
    def __init__(self):
        self.test_dir = Path("knowledge_os/tests")
        self.results_dir = Path("logs/test_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    async def run_test_suite(self) -> dict:
        """Runs all pytest suites and captures failures."""
        logger.info("🧪 [TESTER] Running full test suite...")
        try:
            # Запуск pytest с генерацией JSON отчета
            report_file = self.results_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            cmd = f"pytest {self.test_dir} --json-report --json-report-file={report_file}"
            
            # Используем subprocess для запуска тестов
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if report_file.exists():
                with open(report_file, "r") as f:
                    return json.load(f)
            return {"error": "Report file not generated", "stderr": stderr.decode()}
        except Exception as e:
            logger.error(f"❌ [TESTER] Test suite execution failed: {e}")
            return {"error": str(e)}

    async def analyze_failures(self, report: dict):
        """Asks Victoria to analyze failed tests and propose fixes."""
        failures = [test for test in report.get("tests", []) if test.get("outcome") == "failed"]
        if not failures:
            logger.info("✅ [TESTER] All tests passed! No healing needed.")
            return

        logger.info(f"🔍 [TESTER] Found {len(failures)} failures. Initiating AI Healing...")
        
        from knowledge_os.app.ai_core import run_smart_agent_async

        for fail in failures:
            test_name = fail.get("nodeid")
            error_msg = fail.get("call", {}).get("longrepr", "No traceback available")
            
            prompt = f"""### ЗАДАЧА: АВТОНОМНОЕ ИСПРАВЛЕНИЕ ТЕСТА (Self-Healing)
Ты — Анна, QA Engineer. Тест упал, и тебе нужно предложить исправление.

ТЕСТ: {test_name}
ОШИБКА:
{error_msg}

ЗАДАНИЕ:
1. Проанализируй причину падения (баг в коде или устаревший тест).
2. Предложи конкретный bash-скрипт или python-код для исправления.
3. Оформи ответ в формате:
АНАЛИЗ: (кратко)
ИСПРАВЛЕНИЕ: ```bash ... ``` или ```python ... ```
"""
            healing_proposal = await run_smart_agent_async(prompt, expert_name="Анна", category="reasoning")
            logger.info(f"💊 [HEALING] Proposal for {test_name}:\n{healing_proposal}")
            
            # Логируем в БД как задачу для исполнения
            await self.log_healing_task(test_name, healing_proposal)

    async def log_healing_task(self, test_name: str, proposal: str):
        """Logs the healing proposal as a task in DB."""
        try:
            conn = await asyncpg.connect(DB_URL)
            await conn.execute("""
                INSERT INTO tasks (title, description, status, priority, metadata)
                VALUES ($1, $2, 'pending', 'high', $3::jsonb)
            """, 
            f"💊 SELF-HEALING: Fix {test_name}",
            proposal,
            json.dumps({"type": "self_healing", "test": test_name})
            )
            await conn.close()
            logger.info(f"📝 [TESTER] Healing task created for {test_name}")
        except Exception as e:
            logger.error(f"❌ [TESTER] Failed to log task: {e}")

    async def run_cycle(self):
        """Main cycle: Test -> Analyze -> Log Tasks."""
        report = await self.run_test_suite()
        if "error" not in report:
            await self.analyze_failures(report)
        else:
            logger.warning(f"⚠️ [TESTER] Cycle skipped due to error: {report.get('error')}")

if __name__ == "__main__":
    tester = AutonomousTester()
    asyncio.run(tester.run_cycle())
