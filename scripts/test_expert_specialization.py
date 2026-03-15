import asyncio
import os
import sys
import logging

# Добавляем пути к модулям
sys.path.insert(0, os.path.join(os.getcwd(), "knowledge_os/app"))
from ai_core import run_smart_agent_async_impl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_specialization():
    print("🧪 Тестирование Deep Expert Specialization (Singularity 21.17)")

    # Тест 1: Игорь (Backend)
    print("\n--- ТЕСТ 1: Игорь (@backend_developer) ---")
    res_igor = await run_smart_agent_async_impl(
        prompt="Как правильно организовать импорты в FastAPI проекте?",
        expert_name="Игорь",
        category="general"
    )
    print(f"Результат Игоря (первые 200 симв):\n{res_igor[:200]}...")

    # Тест 2: Анна (QA)
    print("\n--- ТЕСТ 2: Анна (@qa_engineer) ---")
    res_anna = await run_smart_agent_async_impl(
        prompt="Как правильно организовать импорты в FastAPI проекте?",
        expert_name="Анна",
        category="general"
    )
    print(f"Результат Анны (первые 200 симв):\n{res_anna[:200]}...")

    # Проверка логов на наличие "Injected specialization"
    print("\n✅ Тест завершен. Проверьте логи на наличие меток [EXPERT DNA] и [SUCCESS RETRIEVAL].")

if __name__ == "__main__":
    asyncio.run(test_specialization())
