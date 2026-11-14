#!/usr/bin/env python3
"""
Single-shot cognitive quality gate for ATRA.

Purpose:
- Keep operational green checks and cognitive checks in one report.
- Fail fast when runtime is healthy but model/routing discipline drifts.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

KEY_CONTAINERS = [
    "victoria-agent",
    "knowledge_os_orchestrator",
    "knowledge_os_worker",
    "knowledge_os-expert-worker-anna-1",
    "knowledge_os-expert-worker-victoria-1",
    "knowledge_os-expert-worker-heavy-1",
    "board-scheduler",
    "knowledge_rest",
]


def run(cmd: str, timeout: int = 30) -> tuple[int, str, str]:
    p = subprocess.run(
        cmd,
        shell=True,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def container_health() -> dict[str, Any]:
    code, out, err = run("docker ps --format '{{.Names}}|{{.Status}}'")
    if code != 0:
        return {"ok": False, "error": err or out, "containers": {}}
    rows: dict[str, str] = {}
    for line in out.splitlines():
        if "|" in line:
            name, status = line.split("|", 1)
            rows[name] = status
    result = {}
    ok = True
    for name in KEY_CONTAINERS:
        status = rows.get(name, "missing")
        healthy = status != "missing" and "unhealthy" not in status.lower()
        result[name] = {"status": status, "ok": healthy}
        ok = ok and healthy
    return {"ok": ok, "containers": result}


def model_env_discipline() -> dict[str, Any]:
    bad_hits: list[dict[str, str]] = []
    for name in KEY_CONTAINERS:
        cmd = (
            f"docker inspect {name} --format '{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}' "
            "| rg 'VICTORIA_.*MODEL|BOARD_CONSULT_.*MODEL' || true"
        )
        _, out, _ = run(cmd)
        for line in out.splitlines():
            if "victoria-wisdom-v3.5" in line:
                bad_hits.append({"container": name, "env": line.strip()})
    return {"ok": len(bad_hits) == 0, "v35_hits": bad_hits}


def task_kpis() -> dict[str, Any]:
    sql = (
        "WITH s AS (SELECT status, completed_at, created_at, "
        "COALESCE((metadata->>'contract_enforce')::boolean,false) AS ce, "
        "COALESCE(metadata->>'parent_goal','') AS parent_goal "
        "FROM tasks), "
        "u AS (SELECT * FROM s WHERE parent_goal NOT LIKE '[LOG_SCANNER]%') "
        "SELECT "
        "(SELECT COUNT(*) FROM s WHERE status='pending'),"
        "(SELECT COUNT(*) FROM s WHERE status='in_progress'),"
        "(SELECT COUNT(*) FROM u WHERE status='pending'),"
        "(SELECT COUNT(*) FROM u WHERE status='in_progress'),"
        "(SELECT COUNT(*) FROM tasks WHERE status='in_progress' "
        " AND last_real_progress_at < NOW()-INTERVAL '15 minutes' "
        " AND COALESCE(metadata->>'parent_goal','') NOT LIKE '[LOG_SCANNER]%'),"
        "(SELECT COUNT(*) FROM s WHERE status='completed' AND completed_at > NOW()-INTERVAL '1 hour'),"
        "(SELECT COUNT(*) FROM s WHERE status='completed' AND completed_at > NOW()-INTERVAL '24 hours'),"
        "(SELECT COUNT(*) FROM s WHERE status='failed' AND created_at > NOW()-INTERVAL '1 hour'),"
        "(SELECT COUNT(*) FROM s WHERE status='failed' AND created_at > NOW()-INTERVAL '24 hours'),"
        "(SELECT COUNT(*) FROM s WHERE status='completed' AND completed_at > NOW()-INTERVAL '24 hours' AND ce),"
        "(SELECT COUNT(*) FROM s WHERE status='completed' AND completed_at > NOW()-INTERVAL '24 hours');"
    )
    cmd = (
        "docker exec knowledge_postgres psql -U admin -d knowledge_os -Atc "
        f"\"{sql}\""
    )
    code, out, err = run(cmd, timeout=60)
    if code != 0 or not out:
        return {"ok": False, "error": err or out}
    parts = out.split("|")
    if len(parts) != 11:
        return {"ok": False, "error": f"unexpected_sql_output:{out}"}
    pending, in_progress, pending_work, in_progress_work, stale, thr1h, thr24h, fail1h, fail24h, c_num, c_den = [
        int(x) for x in parts
    ]
    contract_ratio = 1.0 if c_den == 0 else (c_num / c_den)
    ok = pending_work == 0 and in_progress_work == 0 and stale == 0 and fail1h == 0
    return {
        "ok": ok,
        "pending": pending,
        "in_progress": in_progress,
        "pending_work": pending_work,
        "in_progress_work": in_progress_work,
        "stale_in_progress": stale,
        "throughput_1h": thr1h,
        "throughput_24h": thr24h,
        "failed_1h": fail1h,
        "failed_24h": fail24h,
        "contract_ratio_24h": round(contract_ratio, 4),
        "contract_num_24h": c_num,
        "contract_den_24h": c_den,
    }


def contract_flags() -> dict[str, Any]:
    cmd = (
        "docker exec knowledge_os_redis redis-cli -s /data/redis.sock "
        "MGET system:contract_rollout_mode system:contract_enforce"
    )
    code, out, err = run(cmd)
    if code != 0:
        return {"ok": False, "error": err or out}
    vals = [x.strip() for x in out.splitlines() if x.strip()]
    mode = vals[0] if len(vals) >= 1 else ""
    enforce = vals[1] if len(vals) >= 2 else ""
    return {"ok": True, "mode": mode or "unknown", "enforce": enforce or "unknown"}


def _contract_flags_match_policy(contract: dict[str, Any], routing: dict[str, Any]) -> bool:
    """
    Dynamic contract policy:
    - rollout -> enforce/1
    - canary_only|rollback|insufficient_data -> shadow/0
    """
    mode = str(contract.get("mode", "unknown"))
    enforce = str(contract.get("enforce", "unknown"))
    r_status = str(routing.get("status", ""))
    r_ok = bool(routing.get("ok", False))
    sufficient = bool(routing.get("sufficient_data", False))

    if not sufficient:
        # Недостаточно данных по routing_quality: не считаем enforce drift-ом.
        return True

    expected_rollout = r_ok and r_status == "evaluated"
    if expected_rollout:
        return mode == "enforce" and enforce == "1"
    return mode == "shadow" and enforce == "0"


def queue_health() -> dict[str, Any]:
    def _to_int(v: str, default: int = 0) -> int:
        try:
            return int(v)
        except Exception:
            return default

    def _parse_xinfo_groups(raw: str) -> list[dict[str, str]]:
        lines = [x.strip() for x in (raw or "").splitlines() if x.strip()]
        groups: list[dict[str, str]] = []
        current: dict[str, str] = {}
        for i in range(0, len(lines) - 1, 2):
            key = lines[i]
            value = lines[i + 1]
            if key == "name" and current:
                groups.append(current)
                current = {}
            current[key] = value
        if current:
            groups.append(current)
        # Filter empty artifacts from malformed outputs.
        return [g for g in groups if g]

    streams = ["expert_tasks:overflow", "expert_tasks"]
    if os.getenv("EXPERT_STREAM_DEDICATED", "1").lower() in ("1", "true", "yes"):
        dedicated = [
            x.strip()
            for x in os.getenv("EXPERT_DEDICATED_WORKERS", "Анна,Виктория,heavy").split(",")
            if x.strip()
        ]
        streams.extend([f"expert_tasks:{name}" for name in dedicated])

    details: list[dict[str, Any]] = []
    overall_ok = True

    for stream in streams:
        xinfo_cmd = (
            "docker exec knowledge_os_redis redis-cli -s /data/redis.sock "
            f"XINFO GROUPS stream:{stream}"
        )
        code, out, err = run(xinfo_cmd)
        if code != 0:
            details.append({"stream": stream, "ok": False, "error": err or out or "xinfo_failed"})
            overall_ok = False
            continue

        groups = _parse_xinfo_groups(out)
        target = next((g for g in groups if g.get("name") == "expert_workers"), None)
        if target is None:
            xlen_cmd = (
                "docker exec knowledge_os_redis redis-cli -s /data/redis.sock "
                f"XLEN stream:{stream}"
            )
            c2, out2, err2 = run(xlen_cmd)
            xlen = _to_int(out2 or "0", default=0) if c2 == 0 else 0
            ok = c2 == 0 and xlen == 0
            details.append(
                {
                    "stream": stream,
                    "ok": ok,
                    "missing_group": True,
                    "xlen": xlen,
                    "error": None if ok else (err2 or out2 or "missing_group_with_backlog"),
                }
            )
            overall_ok = overall_ok and ok
            continue

        lag = _to_int(target.get("lag", "0"))
        pending = _to_int(target.get("pending", "0"))
        consumers = _to_int(target.get("consumers", "0"))
        ok = lag == 0 and pending == 0 and consumers >= 1
        details.append(
            {
                "stream": stream,
                "group": "expert_workers",
                "ok": ok,
                "lag": lag,
                "pending": pending,
                "consumers": consumers,
            }
        )
        overall_ok = overall_ok and ok

    # Keep top-level compatibility for dashboards expecting scalar queue metrics.
    lag_sum = sum(int(d.get("lag", 0) or 0) for d in details)
    pending_sum = sum(int(d.get("pending", 0) or 0) for d in details)
    consumers_min = min([int(d.get("consumers", 0) or 0) for d in details if "consumers" in d] or [0])
    return {
        "ok": overall_ok,
        "lag": lag_sum,
        "pending": pending_sum,
        "consumers": consumers_min,
        "streams": details,
    }


def routing_quality() -> dict[str, Any]:
    min_events = int(os.getenv("ROUTING_GATE_MIN_EVENTS", "100"))
    min_win_rate = float(os.getenv("ROUTING_GATE_MIN_WIN_RATE", "0.80"))
    max_regret_rate = float(os.getenv("ROUTING_GATE_MAX_REGRET_RATE", "0.20"))
    # Default tuned for current local hardware/model profile (long-form local LLM latency).
    max_p95_ms = float(os.getenv("ROUTING_GATE_MAX_P95_MS", "450000"))
    include_synthetic = os.getenv("ROUTING_GATE_INCLUDE_SYNTHETIC", "0").lower() in ("1", "true", "yes")
    exclude_prefixes = os.getenv("ROUTING_EXCLUDE_REASON_PREFIXES", "quality_seed_")
    exclude_routes = os.getenv("ROUTING_EXCLUDE_ROUTES", "cloud")
    cmd = (
        "python3 scripts/aggregate_routing_quality.py "
        "--count 500 --window-hours 24 --print-json "
        + (
            "--include-synthetic"
            if include_synthetic
            else f"--exclude-reason-prefixes '{exclude_prefixes}' --exclude-routes '{exclude_routes}'"
        )
    )
    code, out, err = run(cmd, timeout=60)
    if code != 0 or not out:
        return {"ok": False, "error": err or out}
    try:
        snap = json.loads(out.splitlines()[-1])
    except Exception as e:
        return {"ok": False, "error": f"routing_quality_parse_error:{e}"}

    events = int(snap.get("events_total_window", 0) or 0)
    win_rate = float(snap.get("routing_win_rate", 0.0) or 0.0)
    regret_rate = float(snap.get("decision_regret_rate", 0.0) or 0.0)
    p95_ms = float(snap.get("latency_p95_ms", 0.0) or 0.0)
    excluded = int(snap.get("events_synthetic_ignored", 0) or 0)
    route_excluded = int(snap.get("events_excluded_route_ignored", 0) or 0)
    prefixes = snap.get("excluded_reason_prefixes", [])
    routes = snap.get("excluded_routes", [])
    sufficient_data = events >= min_events
    if not sufficient_data:
        return {
            "ok": True,
            "sufficient_data": False,
            "status": "insufficient_data",
            "events_total_window": events,
            "events_synthetic_ignored": excluded,
            "events_excluded_route_ignored": route_excluded,
            "excluded_reason_prefixes": prefixes,
            "excluded_routes": routes,
            "routing_win_rate": win_rate,
            "decision_regret_rate": regret_rate,
            "latency_p95_ms": p95_ms,
            "thresholds": {
                "min_events": min_events,
                "min_win_rate": min_win_rate,
                "max_regret_rate": max_regret_rate,
                "max_p95_ms": max_p95_ms,
            },
        }
    ok = (
        win_rate >= min_win_rate
        and regret_rate <= max_regret_rate
        and p95_ms <= max_p95_ms
    )
    return {
        "ok": ok,
        "sufficient_data": True,
        "status": "evaluated",
        "events_total_window": events,
        "events_synthetic_ignored": excluded,
        "events_excluded_route_ignored": route_excluded,
        "excluded_reason_prefixes": prefixes,
        "excluded_routes": routes,
        "routing_win_rate": win_rate,
        "decision_regret_rate": regret_rate,
        "latency_p95_ms": p95_ms,
        "thresholds": {
            "min_events": min_events,
            "min_win_rate": min_win_rate,
            "max_regret_rate": max_regret_rate,
            "max_p95_ms": max_p95_ms,
        },
    }


def summary_report() -> dict[str, Any]:
    checks = {
        "container_health": container_health(),
        "model_env_discipline": model_env_discipline(),
        "task_kpis": task_kpis(),
        "queue_health": queue_health(),
        "contract_flags": contract_flags(),
        "routing_quality": routing_quality(),
    }
    checks["contract_flags"]["ok"] = _contract_flags_match_policy(
        checks["contract_flags"], checks["routing_quality"]
    )
    operational_pass = (
        checks["container_health"].get("ok", False)
        and checks["task_kpis"].get("ok", False)
        and checks["queue_health"].get("ok", False)
        and checks["contract_flags"].get("ok", False)
    )
    cognitive_pass = (
        checks["model_env_discipline"].get("ok", False)
        and checks["routing_quality"].get("ok", False)
    )
    gate_pass = operational_pass and cognitive_pass
    action = "rollout" if gate_pass else ("canary_only" if operational_pass else "rollback")
    return {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "gate_pass": gate_pass,
        "operational_pass": operational_pass,
        "cognitive_pass": cognitive_pass,
        "recommended_action": action,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="", help="Optional JSON output path")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when gate fails")
    args = parser.parse_args()

    report = summary_report()
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    if args.output:
        out = Path(args.output)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8")

    if args.strict and not report["gate_pass"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

