#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Экспорт метрик Sharpe/Sortino/MaxDD и др. по торговым режимам (live/backfill/futures).
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from src.shared.utils.datetime_utils import get_utc_now

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from performance_metrics_calculator import PerformanceMetricsCalculator


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Неверный формат даты: {value}") from exc


def _parse_trade_modes(raw_modes: Optional[Iterable[str]]) -> List[Optional[str]]:
    if not raw_modes:
        return [None, "live", "backfill", "futures"]
    trade_modes: List[Optional[str]] = []
    for mode in raw_modes:
        normalized = mode.strip().lower()
        if not normalized:
            continue
        if normalized in {"all", "*", "any"}:
            trade_modes.append(None)
        else:
            trade_modes.append(mode.strip())
    return trade_modes or [None]


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    raise TypeError(f"Не сериализуемый тип: {type(value)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Экспорт метрик производительности по торговым режимам")
    parser.add_argument("--db", default="trading.db", help="Путь к БД SQLite (по умолчанию trading.db)")
    parser.add_argument(
        "--output",
        default="data/reports/performance_live_vs_backfill.json",
        help="Путь к JSON-отчёту (по умолчанию data/reports/performance_live_vs_backfill.json)",
    )
    parser.add_argument("--start-date", type=_parse_datetime, help="Начальная дата (ISO-8601)")
    parser.add_argument("--end-date", type=_parse_datetime, help="Конечная дата (ISO-8601)")
    parser.add_argument(
        "--trade-modes",
        nargs="*",
        help="Список торговых режимов (например: live backfill futures). 'all' = совокупные метрики",
    )
    parser.add_argument(
        "--risk-free-rate",
        type=float,
        default=0.02,
        help="Годовая безрисковая ставка (по умолчанию 0.02 = 2%)",
    )
    args = parser.parse_args()

    trade_modes = _parse_trade_modes(args.trade_modes)
    calculator = PerformanceMetricsCalculator(db_path=args.db)
    logger.info(
        "Выполняю расчёт метрик по режимам: %s",
        ", ".join(mode or "all" for mode in trade_modes),
    )
    metrics_by_mode = calculator.calculate_metrics_by_mode(
        trade_modes=trade_modes,
        user_id=None,
        start_date=args.start_date,
        end_date=args.end_date,
        risk_free_rate=args.risk_free_rate,
    )

    report = {
        "generated_at": get_utc_now().isoformat() + "Z",
        "db_path": str(Path(args.db).resolve()),
        "start_date": args.start_date.isoformat() if args.start_date else None,
        "end_date": args.end_date.isoformat() if args.end_date else None,
        "risk_free_rate": args.risk_free_rate,
        "trade_modes": [mode or "all" for mode in trade_modes],
        "metrics": metrics_by_mode,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=_json_default)
        fh.write("\n")

    logger.info("Отчёт сохранён: %s", output_path.resolve())


if __name__ == "__main__":
    main()

