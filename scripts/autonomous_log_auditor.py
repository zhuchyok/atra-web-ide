import asyncio
import os
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("log_auditor")

# Пути к логам
LOG_FILES = [
    Path("victoria_bot_supervisor.log"),
    Path("knowledge_os/logs/evolution.log"),
    # Можно добавить другие логи
]

async def audit_logs():
    """
    [SINGULARITY 24.0] Autonomous Log Auditor.
    Виктория анализирует собственные логи, находит ошибки и предлагает решения.
    """
    logger.info("🔍 [LOG AUDITOR] Starting autonomous log audit...")

    try:
        from knowledge_os.app.ai_core import run_smart_agent_async

        all_errors = []
        for log_path in LOG_FILES:
            if log_path.exists():
                with open(log_path, "r", encoding="utf-8") as f:
                    # Читаем последние 100 строк
                    lines = f.readlines()[-100:]
                    errors = [l for l in lines if "ERROR" in l or "Exception" in l or "failed" in l.lower()]
                    if errors:
                        all_errors.append(f"LOG: {log_path}\n" + "".join(errors))

        if not all_errors:
            logger.info("✅ [LOG AUDITOR] No critical errors found in recent logs.")
            return

        error_context = "\n---\n".join(all_errors)

        audit_prompt = f"""### ЗАДАЧА: АВТОНОМНЫЙ АУДИТ ЛОГОВ
Ты — Виктория, Team Lead. Проанализируй следующие ошибки из логов системы и предложи конкретные действия по их исправлению.

ЛОГИ ОШИБОК:
{error_context}

ЗАДАНИЕ:
1. Классифицируй ошибки (инфраструктурные, логические, синтаксические).
2. Найди повторяющиеся паттерны.
3. Предложи исправления (код, конфиг или команды).
4. Если ошибка уже исправлена в ходе текущей сессии, отметь это.

ОТВЕТЬ КРАТКО И ПО ДЕЛУ.
"""

        analysis = await run_smart_agent_async(audit_prompt, category="reasoning")

        if analysis:
            logger.info(f"📊 [LOG AUDITOR] Analysis complete:\n{analysis}")
            # Сохраняем отчет в базу знаний или файл
            report_path = Path(f"docs/log_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(f"# Autonomous Log Audit Report ({datetime.now().isoformat()})\n\n{analysis}")
            logger.info(f"💾 [LOG AUDITOR] Report saved to {report_path}")

    except Exception as e:
        logger.error(f"❌ [LOG AUDITOR] Audit failed: {e}")

if __name__ == "__main__":
    asyncio.run(audit_logs())
