#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка восстановления из последнего backup/trading.db_*.
Создаёт временный каталог, копирует свежий бэкап, проверяет наличие таблиц и закрывает соединение.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import List


def find_latest_backup(backups_dir: Path) -> Path:
    candidates = sorted(backups_dir.glob("trading.db_*"))
    if not candidates:
        raise FileNotFoundError(f"Не найдено файлов в {backups_dir}")
    return candidates[-1]


def required_tables(conn: sqlite3.Connection) -> List[str]:
    cursor = conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type='table'
        """
    )
    return [row[0] for row in cursor.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Тест восстановления из последнего backup/trading.db_*")
    parser.add_argument("--backups-dir", default="backups")
    parser.add_argument("--required", nargs="+", default=["trades", "signals_log", "risk_flags"])
    args = parser.parse_args()

    backups_dir = Path(args.backups_dir).resolve()
    latest = find_latest_backup(backups_dir)

    with tempfile.TemporaryDirectory(prefix="atra_restore_") as tmp_dir:
        target = Path(tmp_dir) / "trading.db"
        shutil.copy2(latest, target)

        with sqlite3.connect(target) as conn:
            tables = required_tables(conn)
            missing = [name for name in args.required if name not in tables]
            if missing:
                raise RuntimeError(f"В копии отсутствуют таблицы: {', '.join(missing)}")

        print("✅ Restore test passed")
        print(f"Источник: {latest}")
        print(f"Временная копия: {target}")
        print(f"Таблицы: {', '.join(sorted(tables))}")


if __name__ == "__main__":
    main()

