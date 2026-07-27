#!/usr/bin/env python3
"""
Runtime KPI gate monitor for 15m/1h/6h/24h windows.

Collects periodic snapshots from dockerized runtime and writes:
- JSONL samples
- rolling markdown gate summary
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
AUDITS_DIR = ROOT / "docs" / "audits"
sys.path.insert(0, str(ROOT / "knowledge_os" / "app"))
from distillation_tail_metrics import DISTILL_CAMPAIGN_PROGRESS_SQL

CONTAINER_ALIASES = {
    "knowledge_os_orchestrator": ["knowledge_os_orchestrator"],
    "knowledge_os_worker": ["knowledge_os_worker"],
    "knowledge_os-expert-worker-heavy": [
        "knowledge_os-expert-worker-heavy",
        "knowledge_os-expert-worker-heavy-1",
        "knowledge_os-expert-worker-heavy-2",
        "knowledge_os-expert-worker-heavy-3",
    ],
    # compose can name this service as knowledge_os-expert-worker-anna-1
    "expert-worker-anna": ["expert-worker-anna", "knowledge_os-expert-worker-anna"],
    "knowledge_postgres": ["knowledge_postgres"],
    "knowledge_os_redis": ["knowledge_os_redis"],
    "atra-elasticsearch": ["atra-elasticsearch"],
}
CORE_CONTAINERS = list(CONTAINER_ALIASES.keys())
STALE_THRESHOLD_MINUTES = int(os.getenv("RUNTIME_STALE_THRESHOLD_MINUTES", "45"))
DYNAMIC_ALERT_LOG_LOOKBACK_SEC = int(os.getenv("RUNTIME_DYNAMIC_ALERT_LOOKBACK_SEC", "900"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_cmd(args: List[str], timeout_sec: int = 20) -> str:
    return subprocess.check_output(args, text=True, timeout=timeout_sec).strip()


def run_cmd_safe(args: List[str], default: str = "", timeout_sec: int = 20) -> str:
    try:
        return run_cmd(args, timeout_sec=timeout_sec)
    except Exception:
        return default


def run_redis_cli(args: List[str], timeout_sec: int = 8) -> str:
    """Read Redis state with socket-first and TCP fallback, bounded by timeout."""
    socket_cmd = ["docker", "exec", "knowledge_os_redis", "redis-cli", "-s", "/data/redis.sock", *args]
    out = run_cmd_safe(socket_cmd, default="", timeout_sec=timeout_sec)
    if out:
        return out
    tcp_cmd = ["docker", "exec", "knowledge_os_redis", "redis-cli", "-u", "redis://127.0.0.1:6379/0", *args]
    return run_cmd_safe(tcp_cmd, default="", timeout_sec=timeout_sec)


def get_container_statuses() -> Dict[str, str]:
    out = run_cmd(["docker", "ps", "--format", "{{.Names}}|{{.Status}}"])
    rows = {}
    for line in out.splitlines():
        if "|" not in line:
            continue
        name, status = line.split("|", 1)
        rows[name] = status

    def _resolve_status(aliases: List[str]) -> str:
        # Prefer exact match, then docker-compose suffix match (<name>-<index>)
        for alias in aliases:
            if alias in rows:
                return rows[alias]
        for running_name, running_status in rows.items():
            for alias in aliases:
                if running_name.startswith(f"{alias}-"):
                    return running_status
        return "NOT RUNNING"

    return {name: _resolve_status(CONTAINER_ALIASES.get(name, [name])) for name in CORE_CONTAINERS}


def get_task_metrics() -> Dict[str, int]:
    sql = (
        "SELECT 'status', status, count(*)::text FROM tasks GROUP BY status ORDER BY status;"
        "SELECT 'totals',"
        "count(*) FILTER (WHERE status='pending')::text,"
        "count(*) FILTER (WHERE status='in_progress')::text,"
        "count(*) FILTER (WHERE status='completed')::text,"
        "count(*) FILTER (WHERE status='failed')::text FROM tasks;"
        "SELECT 'window',"
        "count(*) FILTER (WHERE status='completed' AND updated_at > NOW()-INTERVAL '10 minutes')::text,"
        "count(*) FILTER (WHERE status='failed' AND updated_at > NOW()-INTERVAL '10 minutes')::text,"
        f"count(*) FILTER (WHERE status='in_progress' "
        f"AND updated_at < NOW()-INTERVAL '{STALE_THRESHOLD_MINUTES} minutes')::text FROM tasks;"
        "SELECT 'gate_window',"
        "count(*) FILTER (WHERE status='completed' AND updated_at > NOW()-INTERVAL '10 minutes' "
        "AND COALESCE(metadata->>'source','') <> 'orchestration_tracking')::text,"
        "count(*) FILTER (WHERE status='failed' AND updated_at > NOW()-INTERVAL '10 minutes' "
        "AND COALESCE(metadata->>'source','') <> 'orchestration_tracking')::text,"
        "count(*) FILTER (WHERE status='cancelled' AND updated_at > NOW()-INTERVAL '10 minutes' "
        "AND COALESCE(metadata->>'source','') <> 'orchestration_tracking' "
        "AND COALESCE(metadata->>'failed_requires_intervention','false')='true')::text "
        "FROM tasks;"
    )
    out = run_cmd(
        [
            "docker",
            "exec",
            "knowledge_postgres",
            "psql",
            "-U",
            "admin",
            "-d",
            "knowledge_os",
            "-Atc",
            sql,
        ]
    )
    statuses: Dict[str, int] = {}
    pending = in_progress = completed = failed = 0
    completed_10m = failed_10m = stale_in_progress = 0
    completed_10m_gate = failed_10m_gate = cancelled_10m_gate = 0
    lines = [x for x in out.splitlines() if x.strip()]
    for line in lines:
        if "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) == 3 and parts[0] == "status":
            status_name, status_cnt = parts[1], parts[2]
            if status_name in {"completed", "failed", "pending", "in_progress", "cancelled"}:
                statuses[status_name] = int(status_cnt)
        elif len(parts) == 5 and parts[0] == "totals":
            pending, in_progress, completed, failed = (int(p) for p in parts[1:5])
        elif len(parts) == 4 and parts[0] == "window":
            completed_10m, failed_10m, stale_in_progress = (
                int(parts[1]),
                int(parts[2]),
                int(parts[3]),
            )
        elif len(parts) == 4 and parts[0] == "gate_window":
            completed_10m_gate, failed_10m_gate, cancelled_10m_gate = (
                int(parts[1]),
                int(parts[2]),
                int(parts[3]),
            )
    denom = completed_10m + failed_10m
    failure_rate_10m = (failed_10m / denom) if denom else 0.0
    denom_gate = completed_10m_gate + failed_10m_gate + cancelled_10m_gate
    failure_rate_10m_gate = (
        (failed_10m_gate + cancelled_10m_gate) / denom_gate if denom_gate else 0.0
    )
    return {
        "pending": pending,
        "in_progress": in_progress,
        "completed_total": completed,
        "failed_total": failed,
        "completed_10m": completed_10m,
        "failed_10m": failed_10m,
        "completed_10m_gate": completed_10m_gate,
        "failed_10m_gate": failed_10m_gate,
        "cancelled_10m_gate": cancelled_10m_gate,
        "stale_in_progress": stale_in_progress,
        "stale_threshold_minutes": STALE_THRESHOLD_MINUTES,
        "failure_rate_10m_pct": round(failure_rate_10m * 100, 2),
        "failure_rate_10m_gate_pct": round(failure_rate_10m_gate * 100, 2),
        **{f"status_{k}": v for k, v in statuses.items()},
    }


def get_distillation_metrics() -> Dict[str, int]:
    out = run_cmd(
        [
            "docker",
            "exec",
            "knowledge_postgres",
            "psql",
            "-U",
            "admin",
            "-d",
            "knowledge_os",
            "-Atc",
            DISTILL_CAMPAIGN_PROGRESS_SQL,
        ]
    )
    line = next((ln for ln in out.splitlines() if "|" in ln), "")
    if not line:
        raise RuntimeError("distillation_metrics_empty")
    parts = line.split("|")
    if len(parts) < 4:
        raise RuntimeError(f"distillation_metrics_invalid:{line[:120]}")
    campaign_done, campaign_in_progress, campaign_retry, eligible_now = (int(x) for x in parts[:4])
    return {
        "campaign_done": campaign_done,
        "campaign_in_progress": campaign_in_progress,
        "campaign_retry": campaign_retry,
        "eligible_now": eligible_now,
    }


def get_contract_flags() -> Tuple[str, str]:
    out = run_redis_cli(["MGET", "system:contract_rollout_mode", "system:contract_enforce"])
    lines = [x.strip() for x in out.splitlines() if x.strip()]
    if len(lines) >= 2:
        return lines[0], lines[1]
    if len(lines) == 1:
        return lines[0], ""
    return "", ""


def get_dynamic_alert_metrics(interval_sec: int) -> Dict[str, int]:
    lookback_sec = max(DYNAMIC_ALERT_LOG_LOOKBACK_SEC, interval_sec + 30)
    lookback_minutes = max(1, int(math.ceil(lookback_sec / 60)))
    log_out = run_cmd_safe(
        [
            "docker",
            "logs",
            "--since",
            f"{lookback_minutes}m",
            "knowledge_os_orchestrator",
        ],
        default="",
    )
    log_l = log_out.lower()
    mounts_denied = log_l.count("mounts denied")
    compose_nonzero = log_l.count("compose returned non-zero")
    no_slot_available = log_l.count("no_slot_available")
    failed_nonzero_rc = log_l.count("failed_nonzero_rc")
    no_live_registry = log_l.count("no live experts found")

    dynamic_slots_raw = run_redis_cli(["GET", "runtime:dynamic_worker_slots"])
    dynamic_slot_count = 0
    dynamic_slot_running = 0
    if dynamic_slots_raw and dynamic_slots_raw not in {"(nil)", "{}", "null"}:
        try:
            state = json.loads(dynamic_slots_raw)
            if isinstance(state, dict):
                dynamic_slot_count = len(state)
                dynamic_slot_running = sum(1 for _, info in state.items() if isinstance(info, dict) and info.get("expert_name"))
        except Exception:
            pass

    alert_count = mounts_denied + no_slot_available + failed_nonzero_rc
    alert_active = int(alert_count > 0)
    return {
        "dynamic_mounts_denied_count": mounts_denied,
        "dynamic_compose_nonzero_count": compose_nonzero,
        "dynamic_no_slot_available_count": no_slot_available,
        "dynamic_failed_nonzero_rc_count": failed_nonzero_rc,
        "dynamic_no_live_registry_count": no_live_registry,
        "dynamic_slot_count": dynamic_slot_count,
        "dynamic_slot_running": dynamic_slot_running,
        "dynamic_alert_count": alert_count,
        "dynamic_alert_active": alert_active,
    }


@dataclass
class WindowResult:
    name: str
    samples: int
    active: bool
    pass_ok: bool
    stability_ok: bool
    throughput_ok: bool
    throughput_eligible: bool
    min_completed_required: int
    reason: str
    completed_delta: int
    completed10m_positive_ratio: float
    max_pending: int
    max_in_progress: int
    max_stale: int
    distill_tail_ok: bool
    max_eligible_now: int
    tail_breach_streak_max: int
    dynamic_alert_ok: bool
    max_dynamic_alert_count: int
    error_rate_gate_ok: bool
    max_failure_rate_10m_gate_pct: float


@dataclass
class SustainedTailSLOResult:
    ok: bool
    sample_count: int
    min_samples_required: int
    max_consecutive_high_watermark_breach: int
    max_allowed_consecutive_breach: int
    above_target_ratio: float
    max_allowed_above_target_ratio: float
    latest_eligible_now: int
    reason: str


def evaluate_window(
    window_name: str,
    window_minutes: int,
    interval_sec: int,
    samples: List[dict],
    min_completed_per_hour: int,
    distill_target: int,
    distill_high_watermark: int,
    distill_consecutive_breach: int,
) -> WindowResult:
    need = max(1, int((window_minutes * 60) / interval_sec))
    bucket = samples[-need:]
    if not bucket:
        return WindowResult(
            window_name,
            0,
            False,
            False,
            False,
            False,
            False,
            0,
            "no_samples",
            0,
            0.0,
            0,
            0,
            False,
            -1,
            0,
            True,
            0,
            True,
            0.0,
        )

    first = bucket[0]
    last = bucket[-1]
    completed_delta = int(last["completed_total"]) - int(first["completed_total"])
    active = completed_delta > 0

    max_pending = max(int(x["pending"]) for x in bucket)
    max_in_progress = max(int(x["in_progress"]) for x in bucket)
    max_stale = max(int(x.get("stale_in_progress", 0)) for x in bucket)
    max_dynamic_alert_count = max(int(x.get("dynamic_alert_count", 0)) for x in bucket)
    dynamic_alert_ok = max_dynamic_alert_count == 0
    max_failure_rate_10m_gate_pct = max(
        float(x.get("failure_rate_10m_gate_pct", x.get("failure_rate_10m_pct", 0.0))) for x in bucket
    )
    error_rate_gate_ok = max_failure_rate_10m_gate_pct <= 1.0
    healthy_all = all(bool(x["containers_healthy"]) for x in bucket)
    enforce_all = all(x["contract_enforce"] == "1" and x["contract_rollout_mode"] == "enforce" for x in bucket)
    positives = sum(1 for x in bucket if int(x["completed_10m"]) >= 1)
    ratio = positives / len(bucket)
    stability_ok = (
        healthy_all
        and enforce_all
        and max_pending <= 20
        and max_in_progress <= 10
        and max_stale == 0
        and dynamic_alert_ok
        and error_rate_gate_ok
    )
    eligible_series = [int(x.get("eligible_now", -1)) for x in bucket]
    max_eligible_now = max(eligible_series) if eligible_series else -1
    current_streak = 0
    tail_breach_streak_max = 0
    for val in eligible_series:
        if val > distill_high_watermark:
            current_streak += 1
            tail_breach_streak_max = max(tail_breach_streak_max, current_streak)
        else:
            current_streak = 0
    distill_tail_ok = tail_breach_streak_max < max(1, distill_consecutive_breach)

    non_improving = 0
    for i in range(1, len(eligible_series)):
        prev, cur = eligible_series[i - 1], eligible_series[i]
        if prev > distill_target and cur >= prev:
            non_improving += 1
    if non_improving >= max(2, distill_consecutive_breach):
        distill_tail_ok = False

    min_completed_required = max(1, int(round((window_minutes / 60.0) * max(1, min_completed_per_hour))))
    throughput_eligible = completed_delta >= min_completed_required
    low_pressure_mode = os.getenv("RUNTIME_KPI_LOW_PRESSURE_MODE", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    low_pressure_window = max_pending <= 1 and max_in_progress <= 1

    if not throughput_eligible:
        # Low traffic windows are not actionable throughput failures.
        # We still fail when base runtime stability is unhealthy.
        pass_ok = bool(stability_ok and distill_tail_ok)
        if not stability_ok:
            reason = "stability_violation" if error_rate_gate_ok else "error_rate_violation"
        elif not distill_tail_ok:
            reason = "distillation_tail_violation"
        else:
            reason = "insufficient_load_n_a"
        return WindowResult(
            window_name,
            len(bucket),
            active,
            pass_ok,
            stability_ok,
            False,
            False,
            min_completed_required,
            reason,
            completed_delta,
            ratio,
            max_pending,
            max_in_progress,
            max_stale,
            distill_tail_ok,
            max_eligible_now,
            tail_breach_streak_max,
            dynamic_alert_ok,
            max_dynamic_alert_count,
            error_rate_gate_ok,
            round(max_failure_rate_10m_gate_pct, 2),
        )

    throughput_ok = ratio >= 0.60
    # Low-pressure windows with healthy system and enough completed work should not fail
    # because completions are bursty (e.g. 3 done in one slot, then idle slots).
    if low_pressure_mode and low_pressure_window and completed_delta >= min_completed_required:
        throughput_ok = True
    pass_ok = bool(stability_ok and throughput_ok and distill_tail_ok)
    if pass_ok:
        reason = "ok"
    elif not distill_tail_ok:
        reason = "distillation_tail_violation"
    else:
        reason = "threshold_violation"
    return WindowResult(
        window_name,
        len(bucket),
        active,
        pass_ok,
        stability_ok,
        throughput_ok,
        True,
        min_completed_required,
        reason,
        completed_delta,
        ratio,
        max_pending,
        max_in_progress,
        max_stale,
        distill_tail_ok,
        max_eligible_now,
        tail_breach_streak_max,
        dynamic_alert_ok,
        max_dynamic_alert_count,
        error_rate_gate_ok,
        round(max_failure_rate_10m_gate_pct, 2),
    )


def evaluate_sustained_tail_slo(
    samples: List[dict],
    distill_target: int,
    distill_high_watermark: int,
    max_consecutive_breach: int,
    max_above_target_ratio: float,
    min_samples_required: int,
) -> SustainedTailSLOResult:
    eligible_series = [int(x.get("eligible_now", -1)) for x in samples if isinstance(x.get("eligible_now"), int)]
    sample_count = len(eligible_series)
    if sample_count < max(1, min_samples_required):
        return SustainedTailSLOResult(
            ok=False,
            sample_count=sample_count,
            min_samples_required=max(1, min_samples_required),
            max_consecutive_high_watermark_breach=0,
            max_allowed_consecutive_breach=max(1, max_consecutive_breach),
            above_target_ratio=0.0,
            max_allowed_above_target_ratio=max(0.0, min(1.0, max_above_target_ratio)),
            latest_eligible_now=eligible_series[-1] if eligible_series else -1,
            reason="insufficient_samples",
        )

    current = 0
    max_streak = 0
    above_target = 0
    for value in eligible_series:
        if value > distill_target:
            above_target += 1
        if value > distill_high_watermark:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0

    ratio = above_target / sample_count
    allowed_streak = max(1, max_consecutive_breach)
    allowed_ratio = max(0.0, min(1.0, max_above_target_ratio))
    streak_ok = max_streak < allowed_streak
    ratio_ok = ratio <= allowed_ratio
    if streak_ok and ratio_ok:
        reason = "ok"
    elif not streak_ok:
        reason = "high_watermark_breach_streak"
    else:
        reason = "above_target_ratio"
    return SustainedTailSLOResult(
        ok=bool(streak_ok and ratio_ok),
        sample_count=sample_count,
        min_samples_required=max(1, min_samples_required),
        max_consecutive_high_watermark_breach=max_streak,
        max_allowed_consecutive_breach=allowed_streak,
        above_target_ratio=round(ratio, 4),
        max_allowed_above_target_ratio=allowed_ratio,
        latest_eligible_now=eligible_series[-1],
        reason=reason,
    )


def write_summary(
    summary_path: Path,
    started_at: datetime,
    samples: List[dict],
    interval_sec: int,
    min_completed_per_hour: int,
    distill_target: int,
    distill_high_watermark: int,
    distill_consecutive_breach: int,
    tail_slo_max_consecutive_breach: int,
    tail_slo_max_above_target_ratio: float,
    tail_slo_min_samples: int,
) -> None:
    windows = [
        ("15m", 15),
        ("1h", 60),
        ("6h", 360),
        ("24h", 1440),
    ]
    results = [
        evaluate_window(
            name,
            mins,
            interval_sec,
            samples,
            min_completed_per_hour,
            distill_target,
            distill_high_watermark,
            distill_consecutive_breach,
        )
        for name, mins in windows
    ]
    sustained_tail = evaluate_sustained_tail_slo(
        samples=samples,
        distill_target=distill_target,
        distill_high_watermark=distill_high_watermark,
        max_consecutive_breach=tail_slo_max_consecutive_breach,
        max_above_target_ratio=tail_slo_max_above_target_ratio,
        min_samples_required=tail_slo_min_samples,
    )
    latest = samples[-1] if samples else {}
    lines = [
        "# Runtime KPI Gate Monitor",
        "",
        f"- started_at_utc: `{started_at.isoformat()}`",
        f"- last_sample_utc: `{latest.get('ts_utc', '-')}`",
        f"- samples_collected: `{len(samples)}`",
        "",
        "## Latest Snapshot",
        f"- pending: `{latest.get('pending', '-')}`",
        f"- in_progress: `{latest.get('in_progress', '-')}`",
        f"- completed_10m: `{latest.get('completed_10m', '-')}`",
        f"- failed_10m: `{latest.get('failed_10m', '-')}`",
        f"- failure_rate_10m_pct: `{latest.get('failure_rate_10m_pct', '-')}`",
        f"- completed_10m_gate: `{latest.get('completed_10m_gate', '-')}`",
        f"- failed_10m_gate: `{latest.get('failed_10m_gate', '-')}`",
        f"- failure_rate_10m_gate_pct: `{latest.get('failure_rate_10m_gate_pct', '-')}`",
        (
            f"- stale_in_progress: `{latest.get('stale_in_progress', '-')}` "
            f"(threshold `{latest.get('stale_threshold_minutes', STALE_THRESHOLD_MINUTES)}m`)"
        ),
        f"- eligible_now: `{latest.get('eligible_now', '-')}`",
        f"- campaign_done: `{latest.get('campaign_done', '-')}`",
        f"- campaign_in_progress: `{latest.get('campaign_in_progress', '-')}`",
        f"- contract_rollout_mode: `{latest.get('contract_rollout_mode', '-')}`",
        f"- contract_enforce: `{latest.get('contract_enforce', '-')}`",
        f"- dynamic_alert_count: `{latest.get('dynamic_alert_count', '-')}`",
        f"- dynamic_mounts_denied_count: `{latest.get('dynamic_mounts_denied_count', '-')}`",
        f"- dynamic_no_slot_available_count: `{latest.get('dynamic_no_slot_available_count', '-')}`",
        f"- dynamic_failed_nonzero_rc_count: `{latest.get('dynamic_failed_nonzero_rc_count', '-')}`",
        f"- dynamic_slot_running: `{latest.get('dynamic_slot_running', '-')}` / `{latest.get('dynamic_slot_count', '-')}`",
        "",
        "## Gate Results",
    ]
    for res in results:
        lines.append(
            f"- {res.name}: pass=`{res.pass_ok}` active=`{res.active}` reason=`{res.reason}` "
            f"stability_ok=`{res.stability_ok}` throughput_ok=`{res.throughput_ok}` "
            f"throughput_eligible=`{res.throughput_eligible}` min_completed_required=`{res.min_completed_required}` "
            f"samples=`{res.samples}` completed_delta=`{res.completed_delta}` "
            f"completed10m_ratio=`{res.completed10m_positive_ratio:.2f}` "
            f"max_pending=`{res.max_pending}` max_in_progress=`{res.max_in_progress}` "
            f"max_stale=`{res.max_stale}` "
            f"distill_tail_ok=`{res.distill_tail_ok}` max_eligible_now=`{res.max_eligible_now}` "
            f"tail_breach_streak_max=`{res.tail_breach_streak_max}` "
            f"dynamic_alert_ok=`{res.dynamic_alert_ok}` max_dynamic_alert_count=`{res.max_dynamic_alert_count}` "
            f"error_rate_gate_ok=`{res.error_rate_gate_ok}` "
            f"max_failure_rate_10m_gate_pct=`{res.max_failure_rate_10m_gate_pct:.2f}`"
        )
    lines.extend(
        [
            "",
            "## Sustained Distillation Tail SLO",
            f"- ok: `{sustained_tail.ok}`",
            f"- reason: `{sustained_tail.reason}`",
            f"- sample_count: `{sustained_tail.sample_count}`",
            f"- min_samples_required: `{sustained_tail.min_samples_required}`",
            (
                "- max_consecutive_high_watermark_breach: "
                f"`{sustained_tail.max_consecutive_high_watermark_breach}` "
                f"(allowed `< {sustained_tail.max_allowed_consecutive_breach}`)"
            ),
            (
                "- above_target_ratio: "
                f"`{sustained_tail.above_target_ratio}` "
                f"(allowed `<= {sustained_tail.max_allowed_above_target_ratio}`)"
            ),
            f"- latest_eligible_now: `{sustained_tail.latest_eligible_now}`",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-hours", type=float, default=24.0)
    parser.add_argument("--interval-sec", type=int, default=300)
    parser.add_argument("--tag", type=str, default="runtime-gate")
    parser.add_argument("--min-completed-per-hour", type=int, default=3)
    parser.add_argument("--distill-target", type=int, default=8)
    parser.add_argument("--distill-high-watermark", type=int, default=12)
    parser.add_argument("--distill-consecutive-breach", type=int, default=2)
    parser.add_argument("--tail-slo-max-consecutive-breach", type=int, default=3)
    parser.add_argument("--tail-slo-max-above-target-ratio", type=float, default=0.35)
    parser.add_argument("--tail-slo-min-samples", type=int, default=12)
    args = parser.parse_args()

    AUDITS_DIR.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    stem = f"{started.strftime('%Y-%m-%d')}-{args.tag}"
    jsonl_path = AUDITS_DIR / f"{stem}.jsonl"
    summary_path = AUDITS_DIR / f"{stem}-summary.md"

    samples: List[dict] = []
    end_ts = time.time() + int(args.duration_hours * 3600)
    while time.time() < end_ts:
        ts = utc_now().isoformat()
        try:
            containers = get_container_statuses()
            task_metrics = get_task_metrics()
            distillation_metrics = get_distillation_metrics()
            dynamic_metrics = get_dynamic_alert_metrics(args.interval_sec)
            rollout_mode, enforce = get_contract_flags()
            containers_healthy = all(
                (status != "NOT RUNNING") and ("unhealthy" not in status.lower())
                for status in containers.values()
            )
            sample = {
                "ts_utc": ts,
                **task_metrics,
                **distillation_metrics,
                **dynamic_metrics,
                "contract_rollout_mode": rollout_mode,
                "contract_enforce": enforce,
                "containers": containers,
                "containers_healthy": containers_healthy,
            }
        except Exception as exc:
            sample = {"ts_utc": ts, "error": str(exc)}

        samples.append(sample)
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        write_summary(
            summary_path,
            started,
            samples,
            args.interval_sec,
            args.min_completed_per_hour,
            args.distill_target,
            args.distill_high_watermark,
            args.distill_consecutive_breach,
            args.tail_slo_max_consecutive_breach,
            args.tail_slo_max_above_target_ratio,
            args.tail_slo_min_samples,
        )
        time.sleep(max(5, args.interval_sec))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
