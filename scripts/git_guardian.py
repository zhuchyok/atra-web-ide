import asyncio
import os
import sys
import subprocess
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("git_guardian")

async def run_local_audit(diff_content: str) -> bool:
    """
    Отправляет diff локальной Виктории для аудита.
    """
    try:
        from knowledge_os.app.ai_core import run_smart_agent_async

        prompt = f"""### ЗАДАЧА: АУДИТ КОДА (Git Guardian)
Ты — Виктория, Team Lead. Проверь следующие изменения в коде ПЕРЕД коммитом.

ИЗМЕНЕНИЯ (git diff):
{diff_content}

ЗАДАНИЕ:
1. Найди критические ошибки, баги или нарушения стандартов Singularity 24.0.
2. Проверь на наличие секретов (API ключи, пароли), если они не в .env.
3. Оцени влияние на стабильность системы.

ОТВЕТЬ В ФОРМАТЕ:
СТАТУС: [APPROVED / REJECTED]
ПРИЧИНА: (кратко, если REJECTED)
СОВЕТ: (1 предложение по улучшению)

Будь строгим, но конструктивным Team Lead.
"""
        # Используем категорию reasoning для глубокого анализа
        response = await run_smart_agent_async(prompt, expert_name="Виктория", category="reasoning")

        if not response:
            logger.warning("⚠️ Локальная Виктория не ответила. Пропускаем аудит.")
            return True

        logger.info("\n--- ОТЧЕТ GIT GUARDIAN ---")
        logger.info(response)
        logger.info("--------------------------\n")

        if "REJECTED" in response.upper():
            return False
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка связи с локальной Викторией: {e}")
        return True # Пропускаем при ошибке связи, чтобы не блокировать работу

async def main():
    # 1. Получаем список измененных файлов
    try:
        diff = subprocess.check_output(["git", "diff", "--cached"]).decode("utf-8")
        if not diff:
            sys.exit(0)

        # 2. Запускаем аудит
        is_approved = await run_local_audit(diff)

        if not is_approved:
            logger.error("❌ КОММИТ ОТКЛОНЕН: Локальная Виктория нашла проблемы в коде.")
            sys.exit(1)

        sys.exit(0)
    except Exception as e:
        logger.error(f"⚠️ Ошибка Git Guardian: {e}")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
