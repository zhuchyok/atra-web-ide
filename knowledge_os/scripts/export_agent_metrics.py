#!/usr/bin/env python3
"""
Экспорт метрик агентов в Prometheus формат.

Запуск:
    python3 scripts/export_agent_metrics.py
    python3 scripts/export_agent_metrics.py --output metrics/agent_metrics.prom
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.metrics import get_agent_metrics  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Экспорт метрик агентов в Prometheus формат")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("metrics/agent_metrics.prom"),
        help="Путь к файлу для экспорта метрик",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Показать сводку метрик",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    metrics = get_agent_metrics()
    
    # Экспортируем метрики
    output_path = metrics.export_to_file(args.output)
    logger.info("✅ Метрики экспортированы в %s", output_path)
    
    if args.summary:
        summary = metrics.get_metrics_summary()
        logger.info("📊 Сводка метрик:")
        for key, value in summary.items():
            logger.info("  %s: %s", key, value)


if __name__ == "__main__":
    main()

