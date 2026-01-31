#!/usr/bin/env python3
import sqlite3
import logging
from datetime import datetime
from typing import List, Tuple, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_reconcile")

DB_PATH = "trading.db"


def fetch_all(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list:
    cur = conn.cursor()
    cur.execute(query, params)
    return cur.fetchall()


def execute(conn: sqlite3.Connection, query: str, params: tuple = ()) -> int:
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    return cur.rowcount


def reconcile(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Приводит к согласованности:
    - accepted_signals (pending/accepted) ↔ active_positions (open)
    - Закрывает зависшие open позиции, у которых нет соответствующих принятых сигналов
    - Обновляет signals_log для последних PENDING/OPEN при необходимости
    """
    fixes = {
        "closed_orphan_positions": 0,
        "reopened_missing_positions": 0,
        "signals_marked_closed": 0,
        "signals_marked_open": 0,
    }

    # Получим открытые позиции
    open_positions = fetch_all(
        conn,
        """
        SELECT symbol, direction, accepted_by, status, created_at
        FROM active_positions
        WHERE UPPER(IFNULL(status,'open')) LIKE 'OPEN%'
        """,
    )
    # Для каждой проверим наличие свежего принятого сигнала
    for sym, direction, user_id, status, created_at in open_positions:
        rows = fetch_all(
            conn,
            """
            SELECT status, signal_time
            FROM accepted_signals
            WHERE symbol = ? AND user_id = ?
            ORDER BY signal_time DESC
            LIMIT 1
            """,
            (sym, int(user_id) if user_id is not None else -1),
        )
        if rows:
            sig_status, sig_time = rows[0]
            # Если последний сигнал закрыт/expired — позиция не должна быть open
            if (sig_status or "").lower() in ("closed", "expired"):
                cnt = execute(
                    conn,
                    """
                    UPDATE active_positions
                    SET status='closed', created_at=created_at
                    WHERE symbol=? AND accepted_by=? AND UPPER(IFNULL(status,'open')) LIKE 'OPEN%'
                    """,
                    (sym, str(user_id)),
                )
                fixes["closed_orphan_positions"] += cnt
                # И signals_log -> CLOSED для последнего OPEN/PENDING по символу и юзеру
                cnt2 = execute(
                    conn,
                    """
                    UPDATE signals_log
                    SET result='CLOSED'
                    WHERE rowid = (
                        SELECT rowid FROM signals_log
                        WHERE symbol = ? AND user_id = ? AND UPPER(IFNULL(result,'OPEN')) LIKE 'OPEN%'
                        ORDER BY created_at DESC LIMIT 1
                    )
                    """,
                    (sym, int(user_id)),
                )
                fixes["signals_marked_closed"] += cnt2
        else:
            # Нет записей accepted_signals — закрываем зависшую позицию
            cnt = execute(
                conn,
                """
                UPDATE active_positions
                SET status='closed', created_at=created_at
                WHERE symbol=? AND accepted_by=? AND UPPER(IFNULL(status,'open')) LIKE 'OPEN%'
                """,
                (sym, str(user_id)),
            )
            fixes["closed_orphan_positions"] += cnt

    # Для последних принятых сигналов (accepted) убеждаемся, что есть open позиция
    accepted = fetch_all(
        conn,
        """
        SELECT symbol, user_id, status
        FROM accepted_signals
        WHERE status IN ('accepted','in_progress')
        ORDER BY signal_time DESC
        """,
    )
    for sym, user_id, st in accepted:
        pos = fetch_all(
            conn,
            """
            SELECT 1 FROM active_positions
            WHERE symbol=? AND accepted_by=? AND UPPER(IFNULL(status,'open')) LIKE 'OPEN%'
            LIMIT 1
            """,
            (sym, str(user_id)),
        )
        if not pos:
            # Попробуем найти запись signals_log и выставить OPEN (мягко)
            cnt = execute(
                conn,
                """
                UPDATE signals_log
                SET result='OPEN'
                WHERE rowid = (
                    SELECT rowid FROM signals_log
                    WHERE symbol=? AND user_id=? AND (result IS NULL OR UPPER(result) LIKE 'PENDING%')
                    ORDER BY created_at DESC LIMIT 1
                )
                """,
                (sym, int(user_id)),
            )
            fixes["signals_marked_open"] += cnt
            # Позицию не создаём без факта исполнения, оставляем как задача для синка из биржи

    return fixes


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        result = reconcile(conn)
        logger.info("✅ DB reconcile finished: %s", result)
    except Exception as e:
        logger.error("❌ DB reconcile failed: %s", e)
    finally:
        conn.close()


if __name__ == "__main__":
    main()


