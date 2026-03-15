import asyncio
import logging
import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.join(os.getcwd(), "knowledge_os/app"))

from codebase_mutation_engine import get_mutation_engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RecursiveTest")

async def run_recursive_test():
    logger.info("🚀 [RECURSIVE TEST] Starting validation of Recursive Testing cycle...")

    engine = get_mutation_engine()

    # 1. Симулируем патч БЕЗ теста (должен быть отклонен)
    logger.info("❌ TEST 1: Patch without test (should be rejected)")
    patch_no_test = {
        "old_code": "# placeholder_for_test_1",
        "new_code": "def new_function_no_test():\n    return True",
        "decision": "apply",
        "confidence": 1.0
    }

    # Создаем временный файл для теста
    test_file = "temp_test_recursive.py"
    with open(test_file, "w") as f:
        f.write("# placeholder_for_test_1\n")

    try:
        is_safe = await engine._verify_patch_safety(test_file, patch_no_test)
        logger.info(f"Result for Test 1: {'Safe' if is_safe else 'Rejected (Correct)'}")

        # 2. Симулируем патч С тестом (должен быть принят)
        logger.info("✅ TEST 2: Patch with embedded test (should be accepted)")
        patch_with_test = {
            "old_code": "# placeholder_for_test_1",
            "new_code": "def new_function_with_test():\n    return True\n\ndef test_new_function():\n    assert new_function_with_test() == True",
            "decision": "apply",
            "confidence": 1.0
        }

        is_safe_2 = await engine._verify_patch_safety(test_file, patch_with_test)
        logger.info(f"Result for Test 2: {'Safe (Correct)' if is_safe_2 else 'Rejected'}")

    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists(f"{test_file}.tmp"):
            os.remove(f"{test_file}.tmp")

if __name__ == "__main__":
    asyncio.run(run_recursive_test())
