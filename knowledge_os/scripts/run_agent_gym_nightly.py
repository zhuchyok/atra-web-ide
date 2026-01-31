#!/usr/bin/env python3
"""Nightly Agent Gym runner with regression detection."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_gym.scenarios import (  # noqa: E402
    ScenarioContext,
    load_scenarios,
    run_scenarios,
)

DEFAULT_SCENARIOS = Path("agent_gym/configs/sample_scenarios.json")
DEFAULT_REPORT = Path("agent_gym/reports/latest.json")
DEFAULT_BASELINE = Path("agent_gym/reports/baseline.json")
DEFAULT_DIFF = Path("agent_gym/reports/nightly_diff.json")
DEFAULT_METRICS = Path("metrics/agent_gym_regressions.prom")

# Metric rules: direction = "higher" (больше лучше) или "lower" (меньше лучше)
METRIC_RULES: Dict[str, Dict[str, Any]] = {
    "signals_total": {"direction": "higher", "rel": 15.0, "abs": 15.0},
    "unique_symbols": {"direction": "higher", "rel": 15.0, "abs": 5.0},
    "avg_quality": {"direction": "higher", "rel": 5.0, "abs": 0.5},
    "avg_confidence": {"direction": "higher", "rel": 5.0, "abs": 0.5},
    "limit_fill_ratio": {"direction": "higher", "rel": 5.0, "abs": 2.0},
    "market_fallback_ratio": {"direction": "higher", "rel": 5.0, "abs": 2.0},
    "limit_timeout": {"direction": "lower", "rel": 10.0, "abs": 3.0},
    "market_failed": {"direction": "lower", "rel": 10.0, "abs": 2.0},
    "sl_created": {"direction": "higher", "rel": 10.0, "abs": 5.0},
    "tp_created": {"direction": "higher", "rel": 10.0, "abs": 5.0},
    "auto_fix_sl": {"direction": "higher", "rel": 0.0, "abs": 2.0},
    "auto_fix_tp": {"direction": "higher", "rel": 0.0, "abs": 2.0},
}

DEFAULT_RULE = {"direction": "higher", "rel": 10.0, "abs": 2.0}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nightly Agent Gym regression checker.")
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS, help="Путь к JSON со сценариями.")
    parser.add_argument("--db", type=Path, default=Path("trading.db"), help="Путь к trading.db.")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT, help="Файл отчёта текущего прогона.")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="Базовый отчёт для сравнения.")
    parser.add_argument("--diff-output", type=Path, default=DEFAULT_DIFF, help="Файл для сохранения diff.")
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=DEFAULT_METRICS,
        help="Prometheus-метрики с количеством регрессий.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="После прогона обновить baseline отчётом текущего запуска.",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Возвращать ненулевой код выхода при обнаружении регрессий.",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Печатать diff в stdout (для CI/cron логов).",
    )
    return parser.parse_args()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float))


def load_report(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def run_agent_gym_report(scenarios_path: Path, db_path: Path) -> Dict[str, Any]:
    scenarios = load_scenarios(scenarios_path)
    context = ScenarioContext(db_path=db_path)
    results = run_scenarios(scenarios, context)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenarios_path": str(scenarios_path),
        "results": results,
    }


def evaluate_delta(
    metric: str,
    new_value: float,
    old_value: float,
) -> Tuple[float, Optional[float], Dict[str, Any]]:
    """Возвращает delta, delta_pct и rule для метрики."""
    rule = METRIC_RULES.get(metric, DEFAULT_RULE)
    delta = new_value - old_value
    delta_pct: Optional[float] = None
    if old_value not in (0, None):
        try:
            delta_pct = (delta / old_value) * 100 if old_value != 0 else None
        except ZeroDivisionError:
            delta_pct = None
    return delta, delta_pct, rule


def assess_change(delta: float, delta_pct: Optional[float], rule: Dict[str, Any]) -> Tuple[bool, bool]:
    """Возвращает флаги (regression, improvement) согласно правилу."""
    direction = rule.get("direction", "higher")
    rel_threshold = float(rule.get("rel", DEFAULT_RULE["rel"]))
    abs_threshold = float(rule.get("abs", DEFAULT_RULE["abs"]))

    # Для очень маленьких абсолютных значений избегаем шумов
    abs_flag = abs(delta) >= abs_threshold
    rel_flag = False
    if delta_pct is not None:
        rel_flag = abs(delta_pct) >= rel_threshold

    if direction == "higher":
        regression = delta < 0 and (abs_flag or (delta_pct is not None and delta_pct <= -rel_threshold))
        improvement = delta > 0 and (abs_flag or (delta_pct is not None and delta_pct >= rel_threshold))
    else:  # lower is better
        regression = delta > 0 and (abs_flag or (delta_pct is not None and delta_pct >= rel_threshold))
        improvement = delta < 0 and (abs_flag or (delta_pct is not None and delta_pct <= -rel_threshold))
    return regression, improvement


def compare_reports(
    new_report: Dict[str, Any],
    baseline_report: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    diff: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "has_baseline": baseline_report is not None,
        "regressions": [],
        "improvements": [],
        "details": [],
        "missing_in_new": [],
        "missing_in_baseline": [],
    }

    if not baseline_report:
        return diff

    baseline_map = {
        item.get("name"): item for item in baseline_report.get("results", [])
    }
    new_map = {item.get("name"): item for item in new_report.get("results", [])}

    # Новые сценарии
    for scenario_name in new_map.keys() - baseline_map.keys():
        diff["missing_in_baseline"].append(scenario_name)

    # Удалённые сценарии
    for scenario_name in baseline_map.keys() - new_map.keys():
        diff["missing_in_new"].append(scenario_name)

    for scenario_name, new_result in new_map.items():
        baseline_result = baseline_map.get(scenario_name)
        scenario_entry = {"scenario": scenario_name, "metrics": []}
        if not baseline_result:
            diff["details"].append({**scenario_entry, "status": "new_scenario"})
            continue

        new_metrics = new_result.get("metrics", {}) or {}
        baseline_metrics = baseline_result.get("metrics", {}) or {}

        for metric, new_value in new_metrics.items():
            if not is_number(new_value):
                continue
            old_value = baseline_metrics.get(metric)
            if not is_number(old_value):
                scenario_entry["metrics"].append(
                    {
                        "metric": metric,
                        "status": "no_baseline",
                        "new": new_value,
                        "old": old_value,
                    }
                )
                continue

            delta, delta_pct, rule = evaluate_delta(metric, float(new_value), float(old_value))
            regression, improvement = assess_change(delta, delta_pct, rule)

            metric_entry = {
                "metric": metric,
                "new": new_value,
                "old": old_value,
                "delta": delta,
                "delta_pct": delta_pct,
                "regression": regression,
                "improvement": improvement,
                "direction": rule.get("direction"),
            }
            scenario_entry["metrics"].append(metric_entry)

            if regression:
                diff["regressions"].append(
                    {
                        "scenario": scenario_name,
                        "metric": metric,
                        "new": new_value,
                        "old": old_value,
                        "delta": delta,
                        "delta_pct": delta_pct,
                    }
                )
            elif improvement:
                diff["improvements"].append(
                    {
                        "scenario": scenario_name,
                        "metric": metric,
                        "new": new_value,
                        "old": old_value,
                        "delta": delta,
                        "delta_pct": delta_pct,
                    }
                )

        diff["details"].append(scenario_entry)

    diff["regression_count"] = len(diff["regressions"])
    diff["improvement_count"] = len(diff["improvements"])
    return diff


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def write_metrics(path: Path, regressions: int, improvements: int) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as fh:
        fh.write("# HELP agent_gym_regressions_total Количество регрессий по итогам Agent Gym.\n")
        fh.write("# TYPE agent_gym_regressions_total gauge\n")
        fh.write(f"agent_gym_regressions_total {regressions}\n")
        fh.write("# HELP agent_gym_improvements_total Количество улучшений по итогам Agent Gym.\n")
        fh.write("# TYPE agent_gym_improvements_total gauge\n")
        fh.write(f"agent_gym_improvements_total {improvements}\n")


def format_summary(diff: Dict[str, Any]) -> str:
    lines = []
    lines.append("=== Agent Gym nightly summary ===")
    lines.append(f"Generated at: {diff.get('generated_at')}")
    lines.append(f"Regressions: {diff.get('regression_count', 0)}")
    lines.append(f"Improvements: {diff.get('improvement_count', 0)}")
    if diff.get("missing_in_new"):
        lines.append(f"Missing in new report: {', '.join(diff['missing_in_new'])}")
    if diff.get("missing_in_baseline"):
        lines.append(f"New scenarios (no baseline): {', '.join(diff['missing_in_baseline'])}")
    if diff.get("regressions"):
        lines.append("Regressions detail:")
        for item in diff["regressions"]:
            metric = item["metric"]
            scenario = item["scenario"]
            delta = item["delta"]
            rel = item["delta_pct"]
            if rel is not None:
                lines.append(f" - {scenario}/{metric}: Δ={delta:.3f} ({rel:.2f}% vs baseline)")
            else:
                lines.append(f" - {scenario}/{metric}: Δ={delta:.3f}")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("agent_gym_nightly")

    logger.info("Running Agent Gym nightly with scenarios=%s", args.scenarios)
    report = run_agent_gym_report(args.scenarios, args.db)
    write_json(args.output, report)
    logger.info("Saved report to %s", args.output)

    baseline_report = load_report(args.baseline)
    diff = compare_reports(report, baseline_report)
    write_json(args.diff_output, diff)
    logger.info(
        "Diff report saved to %s (regressions=%d, improvements=%d)",
        args.diff_output,
        diff.get("regression_count", 0),
        diff.get("improvement_count", 0),
    )

    write_metrics(
        args.metrics_output,
        diff.get("regression_count", 0),
        diff.get("improvement_count", 0),
    )

    if args.print_summary:
        print(format_summary(diff))

    if args.update_baseline or baseline_report is None:
        ensure_parent(args.baseline)
        write_json(args.baseline, report)
        logger.info("Baseline updated at %s", args.baseline)
    elif args.update_baseline:
        shutil.copy2(args.output, args.baseline)
        logger.info("Baseline overwritten from current report.")

    regressions_detected = diff.get("regression_count", 0) > 0
    if args.fail_on_regression and regressions_detected:
        logger.error("Regressions detected and fail-on-regression enabled.")
        sys.exit(2)


if __name__ == "__main__":
    main()


