#!/usr/bin/env python3
"""
Test script for Enhanced Orchestrator V2 (phases 1-5).

Runs run_phases_1_to_5 for 2-3 sample tasks (simple, complex, multi-dept) and prints results.
Add repo root or knowledge_os/app to sys.path for imports.
"""

import asyncio
import json
import logging
import os
import sys

# Add paths for imports
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "knowledge_os"))
sys.path.insert(0, os.path.join(_root, "knowledge_os", "app"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    try:
        from app.enhanced_orchestrator_v2 import EnhancedOrchestratorV2
    except ImportError:
        from enhanced_orchestrator_v2 import EnhancedOrchestratorV2

    orch = EnhancedOrchestratorV2()

    tasks = [
        {
            "name": "Simple",
            "description": "Проверить статус API и вернуть OK.",
            "metadata": {"source": "test"},
            "task_type_hint": "simple",
        },
        {
            "name": "Complex",
            "description": "Проанализировать кодовую базу проекта, выявить технический долг, предложить рефакторинг и приоритизировать задачи по критичности и трудозатратам. Учесть тесты и документацию.",
            "metadata": {"source": "test"},
            "task_type_hint": "complex",
        },
        {
            "name": "Multi-dept",
            "description": "Организовать релиз: координация разработки, тестирования, документации и деплоя. Согласовать сроки с отделами и подготовить чеклист.",
            "metadata": {"source": "test"},
            "task_type_hint": "multi_dept",
        },
    ]

    print("=" * 60)
    print("Enhanced Orchestrator V2 — Phases 1-5")
    print("=" * 60)

    for t in tasks:
        print(f"\n--- Task: {t['name']} ---")
        try:
            result = await orch.run_phases_1_to_5(
                description=t["description"],
                metadata=t["metadata"],
                task_type_hint=t.get("task_type_hint"),
            )
            print(json.dumps(result, indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")
            logger.exception("run_phases_1_to_5 failed")

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
