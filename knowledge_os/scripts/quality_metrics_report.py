#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отчёт по качеству фильтров сигналов (False Breakout + MTF confirmation).

Пример использования:
    python scripts/quality_metrics_report.py --hours 12
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.db import Database


def _print_section(title: str, summary: Dict[str, Any]) -> None:
    print("=" * 80)
    print(title)
    print("=" * 80)
    print(f"Интервал: последние {summary.get('window_hours')} ч.")
    print(f"Всего событий: {summary.get('total_events')}")

    if 'pass_rate' in summary:
        pass_rate = summary.get('pass_rate')
        print(f"Доля прошедших: {pass_rate:.2%}" if pass_rate is not None else "Доля прошедших: неизвестно")
        print(f"Средняя уверенность: {summary.get('avg_confidence')}")
        print(f"Средний порог: {summary.get('avg_threshold')}")
        print(f"Средняя волатильность (%): {summary.get('avg_volatility_pct')}")
        print(f"Средний recent pass-rate: {summary.get('avg_recent_pass_rate')}")
    else:
        conf_rate = summary.get('confirmation_rate')
        err_rate = summary.get('error_rate')
        print(f"Доля подтверждений: {conf_rate:.2%}" if conf_rate is not None else "Доля подтверждений: неизвестно")
        print(f"Доля ошибок: {err_rate:.2%}" if err_rate is not None else "Доля ошибок: неизвестно")

    breakdown = summary.get('regime_breakdown') or []
    if breakdown:
        print("\nРазбивка по режимам:")
        for item in breakdown:
            if 'pass_rate' in item:
                rate = item.get('pass_rate')
                rate_str = f"{rate:.2%}" if rate is not None else "n/a"
            else:
                rate = item.get('confirmation_rate')
                rate_str = f"{rate:.2%}" if rate is not None else "n/a"
            print(f"  • {item.get('regime'):<16} | total={item.get('total'):>4} | rate={rate_str}")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Отчёт по качеству фильтров сигналов")
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Глубина окна анализа в часах (по умолчанию: 24)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Вывести отчёт в формате JSON",
    )
    args = parser.parse_args()

    db = Database()
    fb_summary = db.get_false_breakout_summary(hours=args.hours)
    mtf_summary = db.get_mtf_confirmation_summary(hours=args.hours)

    if args.json:
        print(json.dumps({"false_breakout": fb_summary, "mtf_confirmation": mtf_summary}, ensure_ascii=False, indent=2))
        return

    _print_section("False Breakout Detector", fb_summary)
    _print_section("MTF Confirmation", mtf_summary)


if __name__ == "__main__":
    main()

