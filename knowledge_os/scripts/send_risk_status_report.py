#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отправляет оперативный risk-отчёт в Telegram.

Использует функции из report_risk_status.py для подготовки данных.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Any, Dict, Optional

from report_infra_status import (  # noqa: E402
    collect_infra_status,
)
from report_risk_status import collect_risk_status  # noqa: E402
from telegram_bot_core import notify_user  # noqa: E402

USER_DATA_PATH = PROJECT_ROOT / "user_data.json"


def _load_default_user_id() -> Optional[int]:
    if not USER_DATA_PATH.exists():
        return None
    try:
        data = json.loads(USER_DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    default_id = data.get("settings", {}).get("default_user_id")
    if isinstance(default_id, (int, str)) and str(default_id).isdigit():
        return int(default_id)

    for key in data.keys():
        if key.isdigit():
            return int(key)
    return None


def _build_message(data) -> str:
    flags = data["flags"]
    flag_lines = []
    active_flags = []
    for name, info in flags.items():
        if info.value:
            emoji = "🛑"
            active_flags.append(name)
        else:
            emoji = "✅"
        flag_lines.append(f"{emoji} {name} — {info.value} (обновлён {info.updated_at.isoformat()})")
    if not flag_lines:
        flag_lines.append("✅ нет активных флагов")

    live_stats = data["live_stats"]
    deposits = data["deposits"]
    message_lines = [
        "🛡️ *ATRA Risk Status*",
        f"_Обновлено:_ {data['generated_at']}",
        "",
        "*Флаги:*",
        *flag_lines,
        "",
    ]
    if active_flags:
        message_lines.extend([
            "⚠️ Активны критические флаги:",
            *[f"• {name}" for name in active_flags],
            "",
        ])
    message_lines.extend([
        "*Метрики:*",
        f"• MaxDD: {data['max_drawdown_pct']:.2f}%" if data['max_drawdown_pct'] is not None else "• MaxDD: n/a",
        f"• Дневной убыток ({data['hours']}ч): {data['daily_loss_pct']:.2f}%",
        f"• WEAK_SETUP подряд (>{data['weak_limit']}): {'да' if data['weak_setup_streak'] else 'нет'}",
        "",
        "*Live-сигналы:*",
        f"• Всего: {live_stats['total_live_signals']}",
        f"• Последний: {live_stats['last_live_entry'] or '—'} ({live_stats['last_live_symbol'] or '—'})",
        "",
        "*Депозиты:*",
    ])
    for user_id, deposit in deposits.items():
        warning = " ⚠️" if deposit <= 0 else ""
        message_lines.append(f"• {user_id}: {deposit} USDT{warning}")

    return "\n".join(message_lines)


async def _send(user_id: int, message: str) -> None:
    await notify_user(user_id, message, parse_mode=None)


def _format_infra_short(data: Dict[str, Any]) -> str:
    def _flag(ok: bool) -> str:
        return "✅" if ok else "⚠️"

    lines = [
        "=== Infrastructure ===",
        f"DB: {_flag(data.get('db', {}).get('connected', False))}",
    ]

    backup = data.get("backups", {})
    latest = backup.get("latest")
    if latest:
        lines.append(
            f"Backup: ✅ {latest.get('file')} ({latest.get('age_hours')}h, {latest.get('size_mb')} MB)"
        )
    else:
        lines.append(f"Backup: ⚠️ {backup.get('error', 'нет данных')}")

    process = data.get("process", {})
    running = process.get("running", False)
    pid = process.get("pid")
    lines.append(f"main.py: {_flag(running)}" + (f" (pid {pid})" if pid else ""))

    signals = data.get("signals_log", {})
    count = signals.get("count")
    if count is not None:
        lines.append(f"Signals: {count} записей")
        last = signals.get("last_entry")
        if last:
            lines.append(
                f"  Last: {last.get('entry_time')} {last.get('symbol')} ({last.get('result')})"
            )
    else:
        lines.append("Signals: нет данных")

    flags = data.get("risk_flags", {})
    active = [name for name, meta in flags.items() if meta.get("value")]
    lines.append(f"Risk flags: {len(active)} активных")
    if active:
        lines.extend([f"  • {name}" for name in active])

    cron = data.get("cron", {})
    if "entries" in cron:
        lines.append(f"Cron: {len(cron['entries'])} записей")
        lines.append(
            f"  run_daily_quality_report.sh: {_flag(cron.get('contains_quality', False))}"
        )
        lines.append(
            f"  run_risk_status_report.sh: {_flag(cron.get('contains_risk', False))}"
        )
    else:
        lines.append(f"Cron: {cron.get('error', 'нет данных')}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Отправка risk status отчёта в Telegram")
    parser.add_argument("--db", default="trading.db")
    parser.add_argument(
        "--performance-report",
        default="data/reports/performance_live_vs_backfill.json",
    )
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--weak-limit", type=int, default=10)
    parser.add_argument("--user-id", type=int, default=None, help="ID получателя в Telegram (по умолчанию берём из user_data)")
    parser.add_argument(
        "--include-infra",
        action="store_true",
        help="Добавить инфраструктурный health-check к сообщению",
    )
    parser.add_argument("--backups-dir", default="backups")
    parser.add_argument("--bot-pid", default="bot.pid")
    parser.add_argument("--bot-log", default="bot.log")
    parser.add_argument("--lock-file", default="atra.lock")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Не отправлять сообщение в Telegram, только сформировать текст и вывести в stdout.",
    )
    args = parser.parse_args()

    data = collect_risk_status(
        db_path=args.db,
        performance_report=Path(args.performance_report),
        hours=args.hours,
        weak_limit=args.weak_limit,
    )
    message = _build_message(data)
    if args.include_infra:
        infra = collect_infra_status(
            db_path=Path(args.db),
            backups_dir=Path(args.backups_dir),
            bot_pid_file=Path(args.bot_pid),
            bot_log_path=Path(args.bot_log),
            lock_file=Path(args.lock_file),
        )
        message += "\n\n" + _format_infra_short(infra)
    if args.dry_run:
        print("=== Risk Status (dry run) ===")
        print(message)
        print("=== End ===")
        return

    user_id = args.user_id if args.user_id is not None else _load_default_user_id()
    if user_id is None:
        raise SystemExit("Не удалось определить user_id. Передайте --user-id или настройте user_data.json.")
    asyncio.run(_send(int(user_id), message))
    print(f"✅ Risk status отправлен пользователю {user_id}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

