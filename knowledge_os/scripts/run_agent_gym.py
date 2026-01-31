#!/usr/bin/env python3
"""Run Agent Gym simulations."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.shared.utils.datetime_utils import get_utc_now

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_gym.scenarios import load_scenarios, run_scenarios, ScenarioContext  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent Gym — оффлайн симуляции агентов.")
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=Path("agent_gym/configs/sample_scenarios.json"),
        help="JSON-файл с описанием сценариев.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("trading.db"),
        help="Путь к базе данных SQLite для анализа.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("agent_gym/reports/latest.json"),
        help="Файл для сохранения отчёта.",
    )
    parser.add_argument(
        "--print",
        dest="print_summary",
        action="store_true",
        help="Печатать отчёт в stdout.",
    )
    return parser.parse_args()


def ensure_output_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def build_report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "generated_at": get_utc_now().isoformat(),
        "results": results,
    }
    return summary


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("agent_gym")

    scenarios = load_scenarios(args.scenarios)
    logger.info("Loaded %d scenario(s) from %s", len(scenarios), args.scenarios)

    context = ScenarioContext(db_path=args.db)
    results = run_scenarios(scenarios, context)
    report = build_report(results)

    ensure_output_dir(args.output)
    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    logger.info("Report saved to %s", args.output)

    if args.print_summary:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

