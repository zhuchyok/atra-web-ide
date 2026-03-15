import asyncio
import logging
import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.join(os.getcwd(), "knowledge_os/app"))

from agent_chaos_injector import get_chaos_injector
from shadow_execution_manager_v2 import get_shadow_manager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ChaosTest")

async def mock_main_func(data):
    """Эмуляция основной стабильной функции."""
    await asyncio.sleep(0.5)
    return f"Processed: {data}"

async def mock_shadow_func(data):
    """Эмуляция новой оптимизированной функции (которую мы будем ломать)."""
    await asyncio.sleep(0.1)
    return f"Processed: {data}"

async def run_chaos_test():
    logger.info("🚀 [CHAOS TEST] Starting Chaos Monkey simulation...")

    injector = get_chaos_injector()
    # Устанавливаем 100% шанс сбоя для теста
    injector.failure_rate = 1.0

    shadow_mgr = get_shadow_manager()

    # Контекст задачи
    context = {"data": "Singularity Data"}

    # 1. Применяем Хаос к контексту теневой функции
    logger.info("🐒 [CHAOS] Injecting failure into shadow context...")
    mutated_context = await injector.apply_chaos(context)

    # 2. Запускаем Shadow Execution
    logger.info("🌑 [SHADOW] Running comparison with chaos...")

    # Если инжектор вставил галлюцинацию, shadow_func вернет ошибку
    async def chaos_shadow_func(d):
        if mutated_context.get("synthetic_hallucination"):
            return mutated_context["result"] # "ERROR: Simulated AI Hallucination"
        if mutated_context.get("tool_access_blocked"):
            raise Exception("Tool access blocked by Chaos Monkey")
        return await mock_shadow_func(d)

    result = await shadow_mgr.execute_shadow(
        "test_chaos_task",
        mock_main_func,
        chaos_shadow_func,
        mutated_context["data"]
    )

    logger.info(f"🏁 [CHAOS TEST] Final result returned to user: {result}")
    logger.info("✅ [CHAOS TEST] Test finished. Check logs for Hot-Swap rejection or error handling.")

if __name__ == "__main__":
    asyncio.run(run_chaos_test())
