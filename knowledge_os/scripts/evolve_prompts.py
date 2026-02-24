#!/usr/bin/env python3
"""Эволюция промптов агентов на основе lessons learned."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.evolution_engine import evolve_agent_prompts, get_evolution_engine  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Эволюция промптов агентов")
    parser.add_argument(
        "--agent",
        type=str,
        help="Имя агента для эволюции (если не указано, то все агенты)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Применить эволюцию автоматически",
    )
    parser.add_argument(
        "--min-gain",
        type=float,
        default=0.05,
        help="Минимальный прирост производительности для применения (по умолчанию 0.05 = 5%%)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("evolve_prompts")

    engine = get_evolution_engine()
    engine.min_performance_gain = args.min_gain

    logger.info("🔬 Запуск эволюции промптов...")

    if args.agent:
        logger.info("📝 Эволюция для агента: %s", args.agent)
        results = evolve_agent_prompts(agent=args.agent)
    else:
        logger.info("📝 Эволюция для всех агентов")
        results = evolve_agent_prompts()

    if not results:
        logger.info("ℹ️ Нет результатов эволюции")
        return

    logger.info("📊 Получено %d результатов эволюции", len(results))

    for result in results:
        logger.info(
            "📈 %s: v%s → v%s (gain=%.2f%%, apply=%s)",
            result.agent,
            result.original_version,
            result.new_version,
            result.performance_gain * 100,
            result.should_apply,
        )
        logger.info("   Улучшения: %s", ", ".join(result.improvements[:3]))

        if args.apply and result.should_apply:
            logger.info("✅ Применение эволюции для %s...", result.agent)
            success = engine.apply_evolution(result)
            if success:
                logger.info("✅ Эволюция применена для %s", result.agent)
            else:
                logger.warning("⚠️ Не удалось применить эволюцию для %s", result.agent)
        elif result.should_apply:
            logger.info("💡 Для применения используйте --apply")


if __name__ == "__main__":
    main()
