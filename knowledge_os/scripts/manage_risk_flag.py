#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI для управления risk_flags (аварийными стопами).

Примеры:
    python3 scripts/manage_risk_flag.py --flag emergency_stop --set --reason "manual stop"
    python3 scripts/manage_risk_flag.py --flag emergency_stop --clear
    python3 scripts/manage_risk_flag.py --list
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from risk_flags_manager import get_default_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Управление risk_flags в trading.db")
    parser.add_argument("--db", default="trading.db", help="Путь к БД (по умолчанию trading.db)")
    parser.add_argument("--flag", help="Название флага (например, emergency_stop)")
    parser.add_argument("--set", action="store_true", help="Установить флаг (value=1)")
    parser.add_argument("--clear", action="store_true", help="Сбросить флаг (value=0)")
    parser.add_argument("--reason", help="Причина установки флага")
    parser.add_argument("--list", action="store_true", help="Вывести все флаги")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manager = get_default_manager(args.db)

    if args.list:
        flags = manager.get_flags()
        if not flags:
            print("risk_flags table empty")
            return
        for flag, info in flags.items():
            print(f"{flag}: value={info.value}, updated_at={info.updated_at.isoformat()}, reason={info.reason}")
        return

    if not args.flag:
        raise SystemExit("Ошибка: требуется --flag (или используйте --list)")

    reason: Optional[str] = args.reason

    if args.set and args.clear:
        raise SystemExit("Ошибка: нельзя одновременно использовать --set и --clear")

    if args.set:
        manager.set_flag(args.flag, True, reason=reason)
        print(f"{args.flag} = 1 (reason={reason})")
    elif args.clear:
        manager.clear_flag(args.flag)
        print(f"{args.flag} = 0 (cleared)")
    else:
        status = manager.is_active(args.flag)
        print(f"{args.flag} status: {status}")


if __name__ == "__main__":
    main()

