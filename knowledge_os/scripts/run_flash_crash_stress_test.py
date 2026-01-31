#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flash crash stress-test runner.

Simulates резкое падение цены и широкой ликвидности для оценки поведения risk/circuit breaker.
Пока использует заглушки; интеграция с настоящим движком (order book / execution simulator) планируется отдельно.
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class FlashCrashScenario:
    symbol: str
    drop_pct: float
    duration: timedelta
    spread_multiplier: float
    volume_drop_pct: float


@dataclass
class FlashCrashResult:
    generated_at: datetime
    scenario: FlashCrashScenario
    base_price: float
    final_price: float
    max_drawdown_pct: float
    fill_ratio: float
    new_spread_pct: float
    avg_slippage_pct: float
    triggered_warning: bool
    triggered_stop: bool
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Запуск стресс-теста flash crash (падение цены на X% за ограниченное время).",
    )
    parser.add_argument("--symbol", default="BTCUSDT", help="Тестируемый символ (по умолчанию BTCUSDT)")
    parser.add_argument(
        "--drop-pct",
        type=float,
        default=15.0,
        help="Процент падения цены (по умолчанию 15%)",
    )
    parser.add_argument(
        "--duration-min",
        type=int,
        default=10,
        help="Длительность падения в минутах (по умолчанию 10)",
    )
    parser.add_argument(
        "--spread-mult",
        type=float,
        default=3.0,
        help="Во сколько раз увеличить спред (по умолчанию x3)",
    )
    parser.add_argument(
        "--volume-drop-pct",
        type=float,
        default=50.0,
        help="Процент снижения ликвидности/объёма (по умолчанию 50%)",
    )
    parser.add_argument(
        "--output",
        default="data/reports/stress_flash_crash.json",
        help="Путь для сохранения отчёта (по умолчанию data/reports/stress_flash_crash.json)",
    )
    return parser.parse_args()


def run_flash_crash_simulation(scenario: FlashCrashScenario) -> FlashCrashResult:
    from simulators.order_book_simulator import simulate_flash_crash  # noqa: WPS433

    metrics = simulate_flash_crash(
        symbol=scenario.symbol,
        drop_pct=scenario.drop_pct,
        duration=scenario.duration,
        spread_multiplier=scenario.spread_multiplier,
        volume_drop_pct=scenario.volume_drop_pct,
    )

    notes = (
        "Flash crash симуляция выполнена на синтетическом ордербуке "
        "(спред x{spread}, падение цены {drop}%). "
        "fill_ratio={fill:.2f}.".format(
            spread=scenario.spread_multiplier,
            drop=scenario.drop_pct,
            fill=metrics["fill_ratio"],
        )
    )

    return FlashCrashResult(
        generated_at=datetime.utcnow(),
        scenario=scenario,
        base_price=metrics["base_price"],
        final_price=metrics["final_price"],
        max_drawdown_pct=metrics["max_drawdown_pct"],
        fill_ratio=metrics["fill_ratio"],
        new_spread_pct=metrics["new_spread_pct"],
        avg_slippage_pct=metrics["avg_slippage_pct"],
        triggered_warning=metrics["triggered_warning"],
        triggered_stop=metrics["triggered_stop"],
        notes=notes,
    )


def save_report(result: FlashCrashResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": result.generated_at.isoformat() + "Z",
        "scenario": {
            "symbol": result.scenario.symbol,
            "drop_pct": result.scenario.drop_pct,
            "duration_seconds": result.scenario.duration.total_seconds(),
            "spread_multiplier": result.scenario.spread_multiplier,
            "volume_drop_pct": result.scenario.volume_drop_pct,
        },
        "base_price": result.base_price,
        "final_price": result.final_price,
        "max_drawdown_pct": result.max_drawdown_pct,
        "fill_ratio": result.fill_ratio,
        "new_spread_pct": result.new_spread_pct,
        "avg_slippage_pct": result.avg_slippage_pct,
        "triggered_warning": result.triggered_warning,
        "triggered_stop": result.triggered_stop,
        "notes": result.notes,
    }
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
    logger.info("Flash crash отчёт сохранён: %s", output_path.resolve())


def main() -> None:
    args = parse_args()
    scenario = FlashCrashScenario(
        symbol=args.symbol,
        drop_pct=args.drop_pct,
        duration=timedelta(minutes=args.duration_min),
        spread_multiplier=args.spread_mult,
        volume_drop_pct=args.volume_drop_pct,
    )
    result = run_flash_crash_simulation(scenario)
    save_report(result, Path(args.output))


if __name__ == "__main__":
    main()

