#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liquidity crisis stress-test runner.

Имитация исчезновения ликвидности (volume drop + spread widening) для проверки поведения risk/circuit breaker.
Текущая версия — заглушка с фиксированным отчётом. Требуется интеграция с фактическим симулятором.
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class LiquidityCrisisScenario:
    symbol: str
    volume_drop_pct: float
    spread_multiplier: float
    depth_loss_pct: float
    duration: timedelta


@dataclass
class LiquidityCrisisResult:
    generated_at: datetime
    scenario: LiquidityCrisisScenario
    base_price: float
    fill_ratio: float
    new_spread_pct: float
    avg_slippage_pct: float
    estimated_unfilled_signals: int
    triggered_stop: bool
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Запуск стресс-теста liquidity crisis.")
    parser.add_argument("--symbol", default="BTCUSDT", help="Тестируемый символ (по умолчанию BTCUSDT)")
    parser.add_argument(
        "--volume-drop-pct",
        type=float,
        default=70.0,
        help="Процент падения объёма (по умолчанию 70%)",
    )
    parser.add_argument(
        "--spread-mult",
        type=float,
        default=4.0,
        help="Во сколько раз увеличить спред (по умолчанию x4)",
    )
    parser.add_argument(
        "--depth-loss-pct",
        type=float,
        default=90.0,
        help="Процент исчезновения глубины книги (по умолчанию 90%)",
    )
    parser.add_argument(
        "--duration-min",
        type=int,
        default=30,
        help="Длительность кризиса в минутах",
    )
    parser.add_argument(
        "--output",
        default="data/reports/stress_liquidity_crisis.json",
        help="Путь для отчёта (по умолчанию data/reports/stress_liquidity_crisis.json)",
    )
    return parser.parse_args()


def run_liquidity_crisis_simulation(scenario: LiquidityCrisisScenario) -> LiquidityCrisisResult:
    from simulators.order_book_simulator import simulate_liquidity_crisis  # noqa: WPS433

    metrics = simulate_liquidity_crisis(
        symbol=scenario.symbol,
        volume_drop_pct=scenario.volume_drop_pct,
        spread_multiplier=scenario.spread_multiplier,
        depth_loss_pct=scenario.depth_loss_pct,
        duration=scenario.duration,
    )

    notes = (
        "Liquidity crisis симуляция (спред x{spread}, depth loss {depth}%, "
        "volume drop {vol}%): fill_ratio={fill:.2f}."
    ).format(
        spread=scenario.spread_multiplier,
        depth=scenario.depth_loss_pct,
        vol=scenario.volume_drop_pct,
        fill=metrics["fill_ratio"],
    )

    return LiquidityCrisisResult(
        generated_at=get_utc_now(),
        scenario=scenario,
        base_price=metrics["base_price"],
        fill_ratio=metrics["fill_ratio"],
        new_spread_pct=metrics["new_spread_pct"],
        avg_slippage_pct=metrics["avg_slippage_pct"],
        estimated_unfilled_signals=metrics["estimated_unfilled_signals"],
        triggered_stop=metrics["triggered_stop"],
        notes=notes,
    )


def save_report(result: LiquidityCrisisResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": result.generated_at.isoformat() + "Z",
        "scenario": {
            "symbol": result.scenario.symbol,
            "volume_drop_pct": result.scenario.volume_drop_pct,
            "spread_multiplier": result.scenario.spread_multiplier,
            "depth_loss_pct": result.scenario.depth_loss_pct,
            "duration_seconds": result.scenario.duration.total_seconds(),
        },
        "base_price": result.base_price,
        "fill_ratio": result.fill_ratio,
        "new_spread_pct": result.new_spread_pct,
        "avg_slippage_pct": result.avg_slippage_pct,
        "estimated_unfilled_signals": result.estimated_unfilled_signals,
        "triggered_stop": result.triggered_stop,
        "notes": result.notes,
    }
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
    logger.info("Liquidity crisis отчёт сохранён: %s", output_path.resolve())


def main() -> None:
    args = parse_args()
    scenario = LiquidityCrisisScenario(
        symbol=args.symbol,
        volume_drop_pct=args.volume_drop_pct,
        spread_multiplier=args.spread_mult,
        depth_loss_pct=args.depth_loss_pct,
        duration=timedelta(minutes=args.duration_min),
    )
    result = run_liquidity_crisis_simulation(scenario)
    save_report(result, Path(args.output))


if __name__ == "__main__":
    main()



