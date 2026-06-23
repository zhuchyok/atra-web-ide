#!/usr/bin/env python3
"""
Boot incident guard.

Runs periodically (or manually) and writes a post-boot diagnostic slice:
- boot timestamp and uptime
- panic / hard-restart evidence from unified logs
- docker health snapshot
- task queue KPIs from knowledge_postgres

It stores state to avoid duplicating the same boot incident.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.getenv("ATRA_ROOT", Path(__file__).resolve().parents[1]))
AUDIT_DIR = ROOT / "docs" / "audits" / "boot_incidents"
STATE_FILE = ROOT / ".cache" / "boot_guard_state.json"

CRITICAL_CONTAINERS = [
    "victoria-agent",
    "knowledge_os_orchestrator",
    "knowledge_os_worker",
    "knowledge_evolution",
    "knowledge_nightly",
    "knowledge_rest",
    "knowledge_postgres",
    "knowledge_pgbouncer",
    "knowledge_os_redis",
    "performance-watchdog",
]

STALE_THRESHOLD_MINUTES = int(os.getenv("RUNTIME_STALE_THRESHOLD_MINUTES", "45"))


def run_cmd(args: list[str], timeout: int = 20) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:  # pragma: no cover
        return 1, "", str(exc)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_boot_info() -> dict[str, Any]:
    code, out, err = run_cmd(["sysctl", "-n", "kern.boottime"])
    if code != 0:
        return {"ok": False, "error": err or out}

    # format: { sec = 1780556440, usec = 372236 } Thu Jun  4 10:00:40 2026
    sec_match = re.search(r"sec\s*=\s*(\d+)", out)
    boot_sec = int(sec_match.group(1)) if sec_match else 0
    if boot_sec <= 0:
        return {"ok": False, "error": f"cannot_parse_boottime:{out}"}

    boot_dt = datetime.fromtimestamp(boot_sec, tz=timezone.utc)
    uptime_sec = int(datetime.now(timezone.utc).timestamp() - boot_sec)
    return {
        "ok": True,
        "boot_sec": boot_sec,
        "boot_utc": boot_dt.isoformat(),
        "uptime_sec": uptime_sec,
        "uptime_h": round(uptime_sec / 3600.0, 2),
        "raw": out,
    }


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_panic_evidence(hours: int = 24) -> dict[str, Any]:
    shutdown_predicate = 'process == "powerd" AND eventMessage CONTAINS[c] "Previous shutdown cause"'
    panic_predicate = 'eventMessage CONTAINS[c] "panic" OR process == "DumpPanic"'

    s_code, s_out, s_err = run_cmd(
        ["/usr/bin/log", "show", "--style", "compact", "--last", f"{hours}h", "--predicate", shutdown_predicate],
        timeout=90,
    )
    p_code, p_out, p_err = run_cmd(
        ["/usr/bin/log", "show", "--style", "compact", "--last", f"{hours}h", "--predicate", panic_predicate],
        timeout=180,
    )

    if s_code != 0 and p_code != 0:
        return {"ok": False, "error": (s_err or s_out or "") + " | " + (p_err or p_out or "")}

    shutdown_lines = [ln for ln in s_out.splitlines() if ln.strip()] if s_code == 0 else []
    panic_lines = [ln for ln in p_out.splitlines() if ln.strip()] if p_code == 0 else []
    lines = shutdown_lines + panic_lines
    tail = lines[-120:] if len(lines) > 120 else lines

    # Exclude echo lines that only contain our CLI arguments.
    has_previous_shutdown_cause = any(
        ("Previous shutdown cause" in ln) and ("args: '/usr/bin/log'" not in ln)
        for ln in shutdown_lines
    )
    has_dump_panic = any("DumpPanic" in ln for ln in panic_lines)
    no_paniclog = any("No paniclog data found in local device" in ln for ln in panic_lines)

    return {
        "ok": True,
        "has_previous_shutdown_cause": has_previous_shutdown_cause,
        "has_dump_panic_events": has_dump_panic,
        "no_paniclog_data": no_paniclog,
        "tail_lines": tail,
    }


def get_container_health() -> dict[str, Any]:
    code, out, err = run_cmd(["docker", "ps", "--format", "{{.Names}}|{{.Status}}"], timeout=30)
    if code != 0:
        return {"ok": False, "error": err or out}

    statuses: dict[str, str] = {}
    for line in out.splitlines():
        if "|" not in line:
            continue
        name, status = line.split("|", 1)
        statuses[name] = status

    rows: list[dict[str, Any]] = []
    all_ok = True
    for name in CRITICAL_CONTAINERS:
        status = statuses.get(name, "NOT RUNNING")
        healthy = ("Up" in status) and ("unhealthy" not in status.lower())
        rows.append({"container": name, "status": status, "ok": healthy})
        all_ok = all_ok and healthy
    return {"ok": all_ok, "rows": rows}


def _parse_pipe_numbers(payload: str, expected: int) -> list[int] | None:
    if "|" not in payload:
        return None
    parts = [p.strip() for p in payload.split("|")]
    if len(parts) < expected:
        return None
    try:
        return [int(x) for x in parts[:expected]]
    except ValueError:
        return None


def get_queue_metrics() -> dict[str, Any]:
    sql_queue = (
        "SELECT COUNT(*) FILTER (WHERE status='pending'),"
        "COUNT(*) FILTER (WHERE status='in_progress'),"
        "COUNT(*) FILTER (WHERE status='completed'),"
        "COUNT(*) FILTER (WHERE status='failed') FROM tasks;"
    )
    sql_stale = (
        "SELECT COUNT(*) FROM tasks WHERE status='in_progress' "
        f"AND updated_at < NOW() - INTERVAL '{STALE_THRESHOLD_MINUTES} minutes';"
    )
    sql_10m = (
        "SELECT COUNT(*) FILTER (WHERE status='completed'),"
        "COUNT(*) FILTER (WHERE status='failed') "
        "FROM tasks WHERE updated_at > NOW() - INTERVAL '10 minutes';"
    )

    def psql(sql: str) -> tuple[int, str, str]:
        return run_cmd(
            [
                "docker",
                "exec",
                "knowledge_postgres",
                "psql",
                "-U",
                "admin",
                "-d",
                "knowledge_os",
                "-At",
                "-F",
                "|",
                "-c",
                sql,
            ],
            timeout=40,
        )

    q_code, q_out, q_err = psql(sql_queue)
    s_code, s_out, s_err = psql(sql_stale)
    t_code, t_out, t_err = psql(sql_10m)

    if q_code != 0 or s_code != 0 or t_code != 0:
        return {
            "ok": False,
            "error": {
                "queue": q_err or q_out,
                "stale": s_err or s_out,
                "throughput": t_err or t_out,
            },
        }

    queue = _parse_pipe_numbers(q_out, 4)
    stale = int(s_out.strip()) if s_out.strip().isdigit() else None
    tp = _parse_pipe_numbers(t_out, 2)

    if queue is None or stale is None or tp is None:
        return {"ok": False, "error": "cannot_parse_psql_output"}

    completed_10m, failed_10m = tp
    denom = max(1, completed_10m + failed_10m)
    return {
        "ok": True,
        "pending": queue[0],
        "in_progress": queue[1],
        "completed_total": queue[2],
        "failed_total": queue[3],
        "stale_in_progress": stale,
        "stale_threshold_minutes": STALE_THRESHOLD_MINUTES,
        # Keep legacy key for compatibility with historical report readers.
        "stale_in_progress_45m": stale,
        "completed_10m": completed_10m,
        "failed_10m": failed_10m,
        "error_rate_10m": round(failed_10m / denom, 4),
    }


def classify_incident(evidence: dict[str, Any]) -> str:
    if not evidence.get("ok"):
        return "unknown"
    if evidence.get("has_previous_shutdown_cause"):
        return "shutdown_cause_recorded"
    if evidence.get("has_dump_panic_events") and evidence.get("no_paniclog_data"):
        return "hard_restart_no_paniclog"
    if evidence.get("has_dump_panic_events"):
        return "panic_or_hard_restart"
    return "unknown"


def write_report(report: dict[str, Any]) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = AUDIT_DIR / f"boot_incident_{ts}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path = AUDIT_DIR / "latest.json"
    latest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Boot incident guard")
    parser.add_argument("--force", action="store_true", help="Emit report even if boot already processed")
    parser.add_argument("--hours", type=int, default=24, help="Log lookback window for panic evidence")
    args = parser.parse_args()

    boot = get_boot_info()
    if not boot.get("ok"):
        print(json.dumps({"ok": False, "stage": "boot_info", "error": boot.get("error")}, ensure_ascii=False))
        return 1

    state = load_state()
    boot_sec = int(boot["boot_sec"])
    last_boot_sec = int(state.get("last_boot_sec", 0) or 0)
    if (not args.force) and boot_sec == last_boot_sec:
        print(json.dumps({"ok": True, "skipped": True, "reason": "boot_already_processed", "boot_sec": boot_sec}, ensure_ascii=False))
        return 0

    evidence = get_panic_evidence(hours=args.hours)
    health = get_container_health()
    queue = get_queue_metrics()

    report = {
        "ok": True,
        "generated_utc": utc_now_iso(),
        "boot": boot,
        "classification": classify_incident(evidence),
        "panic_evidence": evidence,
        "container_health": health,
        "queue_kpi": queue,
    }

    report_path = write_report(report)
    state["last_boot_sec"] = boot_sec
    state["last_report"] = str(report_path)
    state["updated_utc"] = utc_now_iso()
    save_state(state)

    print(json.dumps({"ok": True, "report": str(report_path), "classification": report["classification"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
