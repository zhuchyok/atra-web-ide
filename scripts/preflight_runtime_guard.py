#!/usr/bin/env python3
"""
Runtime preflight guard for ATRA:
1) Secret drift checks (Postgres password vs PgBouncer userlist).
2) Syntax gate for critical runtime modules.
3) Runtime health snapshot (containers + queue/stale/throughput).
4) Contract enforce signal from orchestrator logs.
5) Synthetic alerts from telegram-notifications (Telegram + ntfy).
6) Evolution/mutation degraded-mode guard + distillation progress snapshot.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_OS = ROOT / "knowledge_os"
sys.path.insert(0, str(ROOT / "knowledge_os" / "app"))
from distillation_tail_metrics import DISTILL_CAMPAIGN_PROGRESS_SQL

CRITICAL_FILES = [
    ROOT / "knowledge_os/app/smart_worker_autonomous.py",
    ROOT / "knowledge_os/app/enhanced_orchestrator.py",
    ROOT / "knowledge_os/app/telegram_notifications_worker.py",
    ROOT / "src/agents/bridge/victoria_server.py",
    ROOT / "knowledge_os/app/ai_core.py",
]

CRITICAL_CONTAINERS = [
    "victoria-agent",
    "knowledge_os_orchestrator",
    "knowledge_os_worker",
    "knowledge_evolution",
    "knowledge_postgres",
    "knowledge_pgbouncer",
    "telegram-notifications",
]

STALE_THRESHOLD_MINUTES = int(os.getenv("RUNTIME_STALE_THRESHOLD_MINUTES", "45"))


@dataclass
class CmdResult:
    code: int
    out: str
    err: str


def run(cmd: str, timeout: int = 60) -> CmdResult:
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return CmdResult(code=proc.returncode, out=proc.stdout.strip(), err=proc.stderr.strip())


def parse_env_password(env_path: Path) -> str | None:
    if not env_path.exists():
        return None
    data = env_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"^POSTGRES_PASSWORD=(.+)$", data, flags=re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip()


def parse_pgbouncer_userlist_password(userlist_path: Path, username: str = "admin") -> str | None:
    if not userlist_path.exists():
        return None
    data = userlist_path.read_text(encoding="utf-8", errors="ignore")
    # Format: "admin" "secret"
    m = re.search(rf'"{re.escape(username)}"\s+"([^"]+)"', data)
    if not m:
        return None
    return m.group(1)


def syntax_gate() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    ok = True
    for file_path in CRITICAL_FILES:
        cmd = f"python3 -m py_compile {shlex.quote(str(file_path))}"
        res = run(cmd, timeout=120)
        passed = res.code == 0
        ok = ok and passed
        results.append(
            {
                "file": str(file_path.relative_to(ROOT)),
                "ok": passed,
                "stderr": res.err if not passed else "",
            }
        )
    return {"ok": ok, "files": results}


def parse_container_health(ps_output: str) -> dict[str, Any]:
    status_by_name: dict[str, str] = {}
    for line in ps_output.splitlines():
        if "|" not in line:
            continue
        name, status = line.split("|", 1)
        status_by_name[name.strip()] = status.strip()

    def _resolve_status(container: str) -> str:
        if container in status_by_name:
            return status_by_name[container]
        for running_name, running_status in status_by_name.items():
            if running_name.startswith(f"{container}-") or running_name.endswith(f"_{container}"):
                return running_status
        return "missing"

    critical = []
    all_ok = True
    for name in CRITICAL_CONTAINERS:
        status = _resolve_status(name)
        healthy = ("Up" in status) and ("unhealthy" not in status.lower())
        critical.append({"container": name, "status": status, "ok": healthy})
        all_ok = all_ok and healthy

    return {"ok": all_ok, "critical": critical}


def db_metrics() -> dict[str, Any]:
    metrics: dict[str, Any] = {}

    q_queue = (
        "docker exec knowledge_postgres psql -U admin -d knowledge_os -t -A -F '|' "
        "-c \"SELECT "
        "COUNT(*) FILTER (WHERE status='pending'),"
        "COUNT(*) FILTER (WHERE status='in_progress'),"
        "COUNT(*) FILTER (WHERE status='completed'),"
        "COUNT(*) FILTER (WHERE status='failed') "
        "FROM tasks;\""
    )
    r_queue = run(q_queue, timeout=90)
    if r_queue.code == 0 and r_queue.out:
        pending, in_progress, completed, failed = [int(x) for x in r_queue.out.split("|")[:4]]
        metrics["queue"] = {
            "pending": pending,
            "in_progress": in_progress,
            "completed_total": completed,
            "failed_total": failed,
        }
    else:
        metrics["queue_error"] = r_queue.err or r_queue.out

    q_stale = (
        "docker exec knowledge_postgres psql -U admin -d knowledge_os -t -A "
        f"-c \"SELECT COUNT(*) FROM tasks WHERE status='in_progress' "
        f"AND updated_at < NOW() - INTERVAL '{STALE_THRESHOLD_MINUTES} minutes';\""
    )
    r_stale = run(q_stale, timeout=90)
    if r_stale.code == 0 and r_stale.out:
        stale_count = int(r_stale.out.strip())
        metrics["stale_in_progress"] = stale_count
        metrics["stale_threshold_minutes"] = STALE_THRESHOLD_MINUTES
        # Keep legacy key for compatibility with existing reports/dashboards.
        metrics["stale_in_progress_45m"] = stale_count
    else:
        metrics["stale_error"] = r_stale.err or r_stale.out

    q_10m = (
        "docker exec knowledge_postgres psql -U admin -d knowledge_os -t -A -F '|' "
        "-c \"SELECT "
        "COUNT(*) FILTER (WHERE status='completed'),"
        "COUNT(*) FILTER (WHERE status='failed') "
        "FROM tasks "
        "WHERE updated_at > NOW() - INTERVAL '10 minutes';\""
    )
    r_10m = run(q_10m, timeout=90)
    if r_10m.code == 0 and r_10m.out:
        comp_10m, fail_10m = [int(x) for x in r_10m.out.split("|")[:2]]
        error_rate = (fail_10m / max(comp_10m + fail_10m, 1))
        metrics["throughput_10m"] = {"completed_10m": comp_10m, "failed_10m": fail_10m, "error_rate_10m": round(error_rate, 4)}
    else:
        metrics["throughput_error"] = r_10m.err or r_10m.out

    return metrics


def contract_enforce_signal() -> dict[str, Any]:
    cmd = "docker logs --since 15m knowledge_os_orchestrator 2>&1"
    r = run(cmd, timeout=90)
    if r.code != 0:
        return {"ok": False, "source": "orchestrator_logs", "error": r.err or r.out}
    lines = [ln for ln in r.out.splitlines() if "[ROLLOUT]" in ln]
    if not lines:
        # Fallback for low-traffic windows: read authoritative flags from Redis.
        rr = run(
            "docker exec knowledge_os_redis redis-cli -s /data/redis.sock MGET system:contract_rollout_mode system:contract_enforce",
            timeout=90,
        )
        if rr.code != 0:
            return {
                "ok": False,
                "source": "orchestrator_logs",
                "reason": "no_rollout_lines_15m",
                "redis_error": rr.err or rr.out,
            }
        vals = [ln.strip() for ln in rr.out.splitlines() if ln.strip()]
        mode = vals[0] if len(vals) >= 1 else ""
        enforce = vals[1] if len(vals) >= 2 else ""
        ok = (mode == "enforce") and (enforce == "1")
        return {
            "ok": ok,
            "source": "redis_fallback",
            "mode": mode or "unknown",
            "enforce": enforce or "unknown",
            "reason": "no_rollout_lines_15m",
        }
    last = lines[-1]
    mode_match = re.search(r"mode=([a-zA-Z_]+)", last)
    mode = mode_match.group(1) if mode_match else "unknown"
    return {"ok": mode == "enforce", "mode": mode, "line": last}


def synthetic_alerts() -> dict[str, Any]:
    probe = r"""
docker exec telegram-notifications sh -lc "python - <<'PY'
import asyncio
import json
import telegram_notifications_worker as t

async def main():
    tg = await t.send_telegram('ATRA preflight synthetic alert: telegram')
    nt = await t.send_ntfy('ATRA preflight synthetic alert: ntfy', title='ATRA Preflight')
    print(json.dumps({'telegram_ok': bool(tg), 'ntfy_ok': bool(nt)}))

asyncio.run(main())
PY"
""".strip()
    r = run(probe, timeout=180)
    if r.code != 0:
        return {"ok": False, "error": r.err or r.out}

    # Find last JSON line
    obj = None
    for line in reversed(r.out.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if not obj:
        return {"ok": False, "error": "no_json_result", "raw_tail": r.out[-600:]}

    return {
        "ok": bool(obj.get("telegram_ok") or obj.get("ntfy_ok")),
        "telegram_ok": bool(obj.get("telegram_ok")),
        "ntfy_ok": bool(obj.get("ntfy_ok")),
    }


def evolution_health_signal() -> dict[str, Any]:
    """Validate mutation loop health and degraded fallback behavior."""
    r = run("docker logs --since 20m knowledge_evolution 2>&1", timeout=120)
    if r.code != 0:
        return {"ok": False, "error": r.err or r.out}

    lines = r.out.splitlines()
    has_cycle = any("[EVOLUTION]" in ln for ln in lines)
    limactl_error = any("No such file or directory: 'limactl'" in ln for ln in lines)
    fallback_active = any("Using local process fallback" in ln for ln in lines)
    improvement_seen = any("Improvement found!" in ln for ln in lines)

    # World-practice policy:
    # - If limactl is missing, degraded fallback must be active (fail-fast with safe degrade).
    # - Do not fail only because no cycle happened in a short log window:
    #   evolution interval can be hours; absence in 20m is not an incident by itself.
    ok = (not limactl_error) or fallback_active
    degraded = limactl_error and fallback_active

    return {
        "ok": ok,
        "degraded_mode": degraded,
        "has_cycle": has_cycle,
        "recent_cycle_present": has_cycle,
        "reason": "ok" if ok else "limactl_missing_without_fallback",
        "limactl_error_seen": limactl_error,
        "fallback_active_seen": fallback_active,
        "improvement_seen": improvement_seen,
    }


def distillation_progress_snapshot() -> dict[str, Any]:
    """Capture distillation progress from knowledge_nodes metadata."""
    campaign_sql = DISTILL_CAMPAIGN_PROGRESS_SQL.replace('"', '\\"')
    q = (
        "docker exec knowledge_postgres psql -U admin -d knowledge_os -t -A -F '|' "
        f"-c \"{campaign_sql};\""
    )
    r = run(q, timeout=120)
    if r.code != 0 or not r.out:
        return {"ok": False, "error": r.err or r.out}

    parts = r.out.split("|")
    if len(parts) < 4:
        return {"ok": False, "error": f"unexpected_sql_output: {r.out[:200]}"}

    done, in_progress, retry, eligible = [int(x) for x in parts[:4]]
    return {
        "ok": True,
        "campaign_done": done,
        "campaign_in_progress": in_progress,
        "campaign_retry": retry,
        "eligible_now": eligible,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ATRA runtime preflight guard")
    parser.add_argument("--strict", action="store_true", help="Fail on any non-green check.")
    parser.add_argument("--output", default="", help="Optional path for JSON report.")
    args = parser.parse_args()

    report: dict[str, Any] = {"ok": True}

    # 1) Secret drift
    env_pwd = parse_env_password(KNOWLEDGE_OS / ".env")
    pgb_pwd = parse_pgbouncer_userlist_password(KNOWLEDGE_OS / "pgbouncer/userlist.txt", username="admin")
    secret_ok = bool(env_pwd and pgb_pwd and env_pwd == pgb_pwd)
    report["secret_drift"] = {
        "ok": secret_ok,
        "knowledge_os_env_postgres_password_present": bool(env_pwd),
        "pgbouncer_admin_password_present": bool(pgb_pwd),
        "match": secret_ok,
    }

    # 2) Syntax gate
    report["syntax_gate"] = syntax_gate()

    # 3) Runtime health
    ps = run("docker ps --format \"{{.Names}}|{{.Status}}\"", timeout=60)
    report["container_health"] = parse_container_health(ps.out if ps.code == 0 else "")
    report["db_metrics"] = db_metrics()

    # 4) Contract enforce
    report["contract_enforce"] = contract_enforce_signal()

    # 5) Synthetic alerts
    report["synthetic_alerts"] = synthetic_alerts()
    report["evolution_health"] = evolution_health_signal()
    report["distillation_snapshot"] = distillation_progress_snapshot()

    checks = [
        report["secret_drift"].get("ok", False),
        report["syntax_gate"].get("ok", False),
        report["container_health"].get("ok", False),
        report["contract_enforce"].get("ok", False),
        report["synthetic_alerts"].get("ok", False),
        report["evolution_health"].get("ok", False),
        report["distillation_snapshot"].get("ok", False),
    ]

    # Soft gates from DB metrics
    queue = report["db_metrics"].get("queue", {})
    stale = report["db_metrics"].get("stale_in_progress", -1)
    queue_ok = (queue.get("pending", 0) >= 0) and (queue.get("in_progress", 0) >= 0)
    stale_ok = stale == 0
    checks.extend([queue_ok, stale_ok])

    report["ok"] = all(checks)
    report["gate_summary"] = {
        "secret_drift_ok": report["secret_drift"].get("ok", False),
        "syntax_ok": report["syntax_gate"].get("ok", False),
        "containers_ok": report["container_health"].get("ok", False),
        "contract_enforce_ok": report["contract_enforce"].get("ok", False),
        "synthetic_alerts_ok": report["synthetic_alerts"].get("ok", False),
        "evolution_health_ok": report["evolution_health"].get("ok", False),
        "evolution_degraded_mode": report["evolution_health"].get("degraded_mode", False),
        "distillation_snapshot_ok": report["distillation_snapshot"].get("ok", False),
        "distill_eligible_now": report["distillation_snapshot"].get("eligible_now", -1),
        "stale_in_progress": stale,
        "stale_threshold_minutes": report["db_metrics"].get("stale_threshold_minutes", STALE_THRESHOLD_MINUTES),
    }

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if args.strict and not report["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
