# -*- coding: utf-8 -*-
"""
Отправляет последний отчёт daily_quality_report в Telegram.

Ищет свежий JSON в каталоге data/reports, формирует человекочитаемое сообщение
и отправляет его основному пользователю (по умолчанию из user_data.json).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from telegram_bot_core import notify_user  # noqa: E402
REPORT_DIR = ROOT / "data" / "reports"
USER_DATA_PATH = ROOT / "user_data.json"


def _find_latest_report(directory: Path) -> Optional[Path]:
    if not directory.exists():
        return None
    reports = sorted(directory.glob("daily_quality_report_*.json"))
    return reports[-1] if reports else None


def _format_percentage(value: Optional[float]) -> str:
    if value is None:
        return "—"
    try:
        return f"{value * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _build_message(report: Dict[str, Any]) -> str:
    fb = report.get("false_breakout", {})
    mtf = report.get("mtf_confirmation", {})
    sizing = report.get("position_sizing", {})

    lines = []
    lines.append("📊 Ежедневный отчёт качества ATRA")
    lines.append(f"Окно: {report.get('window_hours', 24)} ч.")
    lines.append("")

    lines.append("🛡️ False Breakout Detector")
    lines.append(f"• Событий: {fb.get('total_events', 0)}")
    lines.append(f"• Pass-rate: {_format_percentage(fb.get('pass_rate'))}")
    lines.append("")

    lines.append("📐 MTF Confirmation")
    lines.append(f"• Событий: {mtf.get('total_events', 0)}")
    lines.append(f"• Confirmation: {_format_percentage(mtf.get('confirmation_rate'))}")
    lines.append("")

    lines.append("🔧 Adaptive sizing vs baseline")
    lines.append(f"• Событий: {sizing.get('events_total', 0)}")
    lines.append(f"• Совпало с trades: {sizing.get('matched_events', 0)}")
    uplift = sizing.get("uplift_vs_baseline")
    if uplift is not None:
        lines.append(f"• Uplift: {uplift:+.2f} USDT")
    else:
        lines.append("• Uplift: —")

    return "\n".join(lines)


async def _send_report(user_id: int, message: str) -> None:
    await notify_user(user_id, message, parse_mode="Markdown")


def _load_default_user_id() -> Optional[int]:
    if not USER_DATA_PATH.exists():
        return None
    try:
        data = json.loads(USER_DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    # Предпочитаем явный ключ default_user_id, если есть
    default_id = data.get("settings", {}).get("default_user_id")
    if isinstance(default_id, (int, str)) and str(default_id).isdigit():
        return int(default_id)

    # Иначе ищем первый числовой ключ верхнего уровня (типичный user id)
    for key in data.keys():
        if key.isdigit():
            return int(key)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Отправка daily_quality_report в Telegram")
    parser.add_argument("--user-id", type=int, default=None, help="ID пользователя Telegram (если не задан, берём из user_data)")
    args = parser.parse_args()

    report_path = _find_latest_report(REPORT_DIR)
    if not report_path or not report_path.exists():
        raise SystemExit(f"Отчёт не найден в {REPORT_DIR}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    message = _build_message(report)

    user_id = args.user_id
    if user_id is None:
        user_id = _load_default_user_id()
        if user_id is None:
            raise SystemExit("Не удалось определить user_id. Передайте --user-id.")

    asyncio.run(_send_report(int(user_id), message))
    print(f"✅ Отчёт отправлен пользователю {user_id}. Файл: {report_path.name}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

