#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Инфраструктурный health-check.

Собирает оперативную информацию о БД, risk-флагах, процессах, бэкапах и логах.
Поставляет данные как для самостоятельного использования, так и для комбинированного отчёта.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "trading.db"
DEFAULT_BACKUPS = PROJECT_ROOT / "backups"
DEFAULT_BOT_PID = PROJECT_ROOT / "bot.pid"
DEFAULT_BOT_LOG = PROJECT_ROOT / "bot.log"
DEFAULT_LOCK = PROJECT_ROOT / "atra.lock"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _check_db(db_path: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {"path": str(db_path), "connected": False}
    if not db_path.exists():
        info["error"] = "not_found"
        return info

    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("SELECT 1")
        info["connected"] = True
    except sqlite3.Error as exc:
        info["error"] = str(exc)
    return info


def _load_risk_flags(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    flags: Dict[str, Dict[str, Any]] = {}
    try:
        rows = conn.execute(
            "SELECT flag, value, updated_at, COALESCE(reason,'') FROM risk_flags"
        ).fetchall()
    except sqlite3.Error:
        return flags

    for flag, value, updated_at, reason in rows:
        flags[flag] = {
            "value": bool(value),
            "updated_at": updated_at,
            "reason": reason or "",
        }
    return flags


def _load_signals_info(conn: sqlite3.Connection) -> Dict[str, Any]:
    info: Dict[str, Any] = {"count": 0, "last_entry": None}
    try:
        count_row = conn.execute("SELECT COUNT(*) FROM signals_log").fetchone()
        info["count"] = int(count_row[0]) if count_row else 0
    except sqlite3.Error:
        return info

    if info["count"] > 0:
        try:
            row = conn.execute(
                """
                SELECT symbol, entry_time, result
                FROM signals_log
                ORDER BY datetime(created_at) DESC
                LIMIT 1
                """
            ).fetchone()
            if row:
                info["last_entry"] = {
                    "symbol": row[0],
                    "entry_time": row[1],
                    "result": row[2],
                }
        except sqlite3.Error:
            pass
    return info


def _check_backups(backups_dir: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {"path": str(backups_dir), "latest": None}
    if not backups_dir.exists():
        result["error"] = "not_found"
        return result

    candidates = sorted(backups_dir.glob("trading.db_*"))
    if not candidates:
        result["error"] = "no_backups"
        return result

    latest = candidates[-1]
    stat = latest.stat()
    age_seconds = max(0, datetime.now().timestamp() - stat.st_mtime)
    result["latest"] = {
        "file": latest.name,
        "modified_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "age_hours": round(age_seconds / 3600, 2),
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
    }
    return result


def _check_process(pid_file: Path, lock_file: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "pid_file": str(pid_file),
        "lock_file": str(lock_file),
        "running": False,
        "pid": None,
    }

    pid: Optional[int] = None
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            info["pid"] = pid
        except (ValueError, OSError):
            info["pid_error"] = "invalid_pid_file"

    def _ping(pid_value: int) -> bool:
        try:
            if pid_value <= 0:
                return False
            os.kill(pid_value, 0)
            return True
        except OSError:
            return False

    if pid and _ping(pid):
        info["running"] = True
        return info

    # fallback: try pgrep main.py
    try:
        proc = subprocess.run(
            ["pgrep", "-f", "main.py"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        pids = [int(line) for line in proc.stdout.strip().splitlines() if line.strip().isdigit()]
        if pids:
            info["running"] = True
            info["pid"] = pids[0]
    except (FileNotFoundError, ValueError, subprocess.SubprocessError):
        info["pgrep"] = "unavailable"

    if lock_file.exists():
        info["lock_exists"] = True
        try:
            info["lock_mtime"] = datetime.fromtimestamp(lock_file.stat().st_mtime).isoformat(
                timespec="seconds"
            )
        except OSError:
            pass
    else:
        info["lock_exists"] = False

    return info


def _read_last_log_line(path: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return info
    try:
        stat = path.stat()
        info["size_mb"] = round(stat.st_size / (1024 * 1024), 2)
        info["modified_iso"] = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()
        info["last_line"] = lines[-1].strip() if lines else ""
    except OSError as exc:
        info["error"] = str(exc)
    return info


def collect_infra_status(
    db_path: Path = DEFAULT_DB,
    backups_dir: Path = DEFAULT_BACKUPS,
    bot_pid_file: Path = DEFAULT_BOT_PID,
    bot_log_path: Path = DEFAULT_BOT_LOG,
    lock_file: Path = DEFAULT_LOCK,
) -> Dict[str, Any]:
    status: Dict[str, Any] = {
        "generated_at": _utc_now(),
        "db": _check_db(db_path),
        "backups": _check_backups(backups_dir),
        "process": _check_process(bot_pid_file, lock_file),
        "logs": {"bot": _read_last_log_line(bot_log_path)},
    }

    if status["db"]["connected"]:
        try:
            with sqlite3.connect(db_path) as conn:
                status["risk_flags"] = _load_risk_flags(conn)
                status["signals_log"] = _load_signals_info(conn)
        except sqlite3.Error as exc:
            status["db"]["error"] = str(exc)
    else:
        status["risk_flags"] = {}
        status["signals_log"] = {"count": None, "last_entry": None}

    # cron snapshot (best effort)
    try:
        proc = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if proc.returncode == 0:
            lines = [
                line.strip()
                for line in proc.stdout.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            status["cron"] = {
                "entries": lines,
                "contains_quality": any("run_daily_quality_report.sh" in line for line in lines),
                "contains_risk": any("run_risk_status_report.sh" in line for line in lines),
            }
        else:
            status["cron"] = {"error": proc.stderr.strip() or "crontab_unavailable"}
    except (FileNotFoundError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        status["cron"] = {"error": "crontab_unavailable"}

    return status


def format_infra_status(status: Dict[str, Any]) -> str:
    def _yes_no(value: bool) -> str:
        return "✅" if value else "⚠️"

    lines = []
    lines.append("=== Infrastructure Health ===")
    lines.append(f"Generated at: {status.get('generated_at')}")
    lines.append("")

    db = status.get("db", {})
    lines.append(f"DB: {_yes_no(db.get('connected', False))} ({db.get('path')})")
    if "error" in db:
        lines.append(f"  Error: {db['error']}")

    backups = status.get("backups", {})
    latest = backups.get("latest")
    if latest:
        lines.append(
            f"Backup: ✅ {latest['file']} (age {latest['age_hours']}h, {latest['size_mb']} MB)"
        )
    else:
        lines.append(f"Backup: ⚠️ {backups.get('error', 'no data')}")

    process = status.get("process", {})
    lines.append(
        f"main.py process: {_yes_no(process.get('running', False))}"
        + (f" (pid {process.get('pid')})" if process.get("pid") else "")
    )
    if process.get("lock_exists"):
        lines.append(f"  Lock file mtime: {process.get('lock_mtime')}")

    signals = status.get("signals_log", {})
    lines.append(f"Signals log count: {signals.get('count')}")
    if signals.get("last_entry"):
        entry = signals["last_entry"]
        lines.append(
            f"  Last: {entry.get('entry_time')} {entry.get('symbol')} ({entry.get('result')})"
        )

    flags = status.get("risk_flags", {})
    if flags:
        active = [name for name, meta in flags.items() if meta.get("value")]
        lines.append(f"Risk flags: {len(active)} active")
        for name in active:
            meta = flags[name]
            lines.append(f"  • {name} ({meta.get('updated_at')}) — {meta.get('reason')}")
    else:
        lines.append("Risk flags: нет данных")

    log_info = status.get("logs", {}).get("bot", {})
    if log_info.get("exists"):
        lines.append(
            f"bot.log: {log_info.get('size_mb')} MB, updated {log_info.get('modified_iso')}"
        )
        last_line = log_info.get("last_line") or ""
        if last_line:
            lines.append(f"  Last line: {last_line[:200]}")
    else:
        lines.append("bot.log: отсутствует")

    cron = status.get("cron", {})
    if "entries" in cron:
        lines.append(f"Cron entries: {len(cron['entries'])}")
        lines.append(
            f"  run_daily_quality_report.sh: {_yes_no(cron.get('contains_quality', False))}"
        )
        lines.append(
            f"  run_risk_status_report.sh: {_yes_no(cron.get('contains_risk', False))}"
        )
    else:
        lines.append(f"Cron: {cron.get('error', 'нет данных')}")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Инфраструктурный health-check")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--backups-dir", default=str(DEFAULT_BACKUPS))
    parser.add_argument("--bot-pid", default=str(DEFAULT_BOT_PID))
    parser.add_argument("--bot-log", default=str(DEFAULT_BOT_LOG))
    parser.add_argument("--lock-file", default=str(DEFAULT_LOCK))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    status = collect_infra_status(
        db_path=Path(args.db),
        backups_dir=Path(args.backups_dir),
        bot_pid_file=Path(args.bot_pid),
        bot_log_path=Path(args.bot_log),
        lock_file=Path(args.lock_file),
    )
    if args.format == "json":
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(format_infra_status(status))


if __name__ == "__main__":
    main()

