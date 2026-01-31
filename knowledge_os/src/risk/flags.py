#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite-backed manager for risk circuit breaker flags.

Используется risk_manager/devops для установки/сброса аварийных флагов.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS risk_flags (
    flag TEXT PRIMARY KEY,
    value INTEGER NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason TEXT
);
"""


@dataclass
class RiskFlag:
    flag: str
    value: bool
    updated_at: datetime
    reason: Optional[str]


class RiskFlagsManager:
    def __init__(self, db_path: str = "trading.db") -> None:
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(SCHEMA_SQL)
                conn.commit()
            logger.debug("risk_flags table ensured in %s", self.db_path)
        except Exception as e:
            logger.error("❌ Ошибка создания таблицы risk_flags в %s: %s", self.db_path, e)
            raise

    def set_flag(self, flag: str, value: bool, reason: Optional[str] = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO risk_flags (flag, value, updated_at, reason)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(flag) DO UPDATE SET
                    value=excluded.value,
                    updated_at=CURRENT_TIMESTAMP,
                    reason=excluded.reason
                """,
                (flag, int(value), reason),
            )
            conn.commit()
        logger.info("risk flag %s set to %s (reason=%s)", flag, value, reason)

    def clear_flag(self, flag: str) -> None:
        self.set_flag(flag, False, reason="manual reset")

    def get_flags(self) -> Dict[str, RiskFlag]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT flag, value, updated_at, reason FROM risk_flags").fetchall()
        flags: Dict[str, RiskFlag] = {}
        for row in rows:
            flags[row["flag"]] = RiskFlag(
                flag=row["flag"],
                value=bool(row["value"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                reason=row["reason"],
            )
        return flags

    def is_active(self, flag: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Убеждаемся, что таблица существует
                self._ensure_table()
                row = conn.execute(
                    "SELECT value FROM risk_flags WHERE flag = ?", (flag,)
                ).fetchone()
            return bool(row[0]) if row else False
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                logger.warning("⚠️ Таблица risk_flags не существует, создаем...")
                try:
                    self._ensure_table()
                    return False  # После создания таблицы флаг не активен
                except Exception as create_err:
                    logger.error("❌ Ошибка создания таблицы risk_flags: %s", create_err)
                    return False
            else:
                logger.error("❌ Ошибка проверки флага %s: %s", flag, e)
                return False
        except Exception as e:
            logger.error("❌ Неожиданная ошибка проверки флага %s: %s", flag, e)
            return False


def get_default_manager(db_path: str = "trading.db") -> RiskFlagsManager:
    return RiskFlagsManager(db_path=db_path)


