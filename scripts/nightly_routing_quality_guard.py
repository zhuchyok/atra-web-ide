#!/usr/bin/env python3
"""
Nightly routing quality guard.

Flow:
1) Build fresh routing quality snapshot.
2) Evaluate action (rollout/canary_only/rollback) by thresholds.
3) Dry-run by default; apply to Redis only with --apply.
4) Write JSON + markdown artifacts to docs/audits.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDITS = ROOT / "docs" / "audits"


@dataclass
class GuardThresholds:
    min_events: int = 100
    target_win_rate: float = 0.90
    min_win_rate_rollback: float = 0.80
    target_regret_rate: float = 0.15
    max_regret_rate_rollback: float = 0.25
    # Local on-device LLM profile: stable p95 is in hundreds of seconds.
    max_p95_ms: float = 450000.0
    max_p95_ms_rollback: float = 600000.0


def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, text=True, capture_output=True, check=True, cwd=str(ROOT))
    return p.stdout.strip()


def load_routing_snapshot(count: int, window_hours: float) -> dict[str, Any]:
    include_synthetic = os.getenv("ROUTING_GUARD_INCLUDE_SYNTHETIC", "0").lower() in ("1", "true", "yes")
    exclude_prefixes = os.getenv("ROUTING_EXCLUDE_REASON_PREFIXES", "quality_seed_")
    exclude_routes = os.getenv("ROUTING_EXCLUDE_ROUTES", "cloud")
    cmd = [
        "python3",
        "scripts/aggregate_routing_quality.py",
        "--count",
        str(count),
        "--window-hours",
        str(window_hours),
        "--print-json",
    ]
    if include_synthetic:
        cmd.append("--include-synthetic")
    else:
        cmd.extend(["--exclude-reason-prefixes", exclude_prefixes, "--exclude-routes", exclude_routes])
    out = run(cmd)
    return json.loads(out.splitlines()[-1])


def evaluate_action(metrics: dict[str, Any], th: GuardThresholds) -> dict[str, Any]:
    events = int(metrics.get("events_total_window", 0) or 0)
    win = float(metrics.get("routing_win_rate", 0.0) or 0.0)
    regret = float(metrics.get("decision_regret_rate", 0.0) or 0.0)
    p95 = float(metrics.get("latency_p95_ms", 0.0) or 0.0)

    if events < th.min_events:
        return {
            "action": "canary_only",
            "reason": f"insufficient_events:{events}<{th.min_events}",
            "hard_fail": False,
        }
    hard_fail = (
        win < th.min_win_rate_rollback
        or regret > th.max_regret_rate_rollback
        or p95 > th.max_p95_ms_rollback
    )
    if hard_fail:
        return {
            "action": "rollback",
            "reason": (
                f"hard_fail(win={win:.4f},regret={regret:.4f},p95={p95:.2f})"
            ),
            "hard_fail": True,
        }

    soft_fail = win < th.target_win_rate or regret > th.target_regret_rate or p95 > th.max_p95_ms
    if soft_fail:
        return {
            "action": "canary_only",
            "reason": f"soft_fail(win={win:.4f},regret={regret:.4f},p95={p95:.2f})",
            "hard_fail": False,
        }
    return {"action": "rollout", "reason": "ok", "hard_fail": False}


def apply_action(action: str, reason: str) -> dict[str, Any]:
    # Map action to existing contract flags.
    if action == "rollout":
        cmds = [
            ["SET", "system:contract_rollout_mode", "enforce"],
            ["SET", "system:contract_enforce", "1"],
        ]
    else:
        cmds = [
            ["SET", "system:contract_rollout_mode", "shadow"],
            ["SET", "system:contract_enforce", "0"],
        ]
    # persist reason and timestamp for auditability
    now = datetime.now(timezone.utc).isoformat()
    cmds.extend(
        [
            ["SET", "system:routing_guard:last_action", action],
            ["SET", "system:routing_guard:last_reason", reason],
            ["SET", "system:routing_guard:last_ts_utc", now],
        ]
    )

    executed = []
    for cmd in cmds:
        run(["docker", "exec", "knowledge_os_redis", "redis-cli", "-s", "/data/redis.sock", *cmd])
        executed.append(" ".join(cmd))
    return {"applied": True, "commands": executed}


def publish_decision_telemetry(metrics: dict[str, Any], action: str, reason: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    commands = [
        ["SET", "system:routing_guard:last_action", action],
        ["SET", "system:routing_guard:last_reason", reason],
        ["SET", "system:routing_guard:last_ts_utc", now],
        ["SET", "system:routing_guard:last_events_total_window", str(int(metrics.get("events_total_window", 0) or 0))],
        ["SET", "system:routing_guard:last_win_rate", str(float(metrics.get("routing_win_rate", 0.0) or 0.0))],
        ["SET", "system:routing_guard:last_regret_rate", str(float(metrics.get("decision_regret_rate", 0.0) or 0.0))],
        ["SET", "system:routing_guard:last_latency_p95_ms", str(float(metrics.get("latency_p95_ms", 0.0) or 0.0))],
    ]
    for cmd in commands:
        run(["docker", "exec", "knowledge_os_redis", "redis-cli", "-s", "/data/redis.sock", *cmd])


def to_markdown(report: dict[str, Any]) -> str:
    m = report["routing_metrics"]
    d = report["decision"]
    lines = [
        "# Nightly Routing Guard",
        "",
        f"- ts_utc: `{report['ts_utc']}`",
        f"- mode: `{report['mode']}`",
        f"- action: `{d['action']}`",
        f"- reason: `{d['reason']}`",
        "",
        "## Metrics",
        f"- events_total_window: `{m.get('events_total_window')}`",
        f"- routing_win_rate: `{m.get('routing_win_rate')}`",
        f"- decision_regret_rate: `{m.get('decision_regret_rate')}`",
        f"- latency_p95_ms: `{m.get('latency_p95_ms')}`",
        "",
        "## Thresholds",
    ]
    for k, v in report["thresholds"].items():
        lines.append(f"- {k}: `{v}`")
    if report.get("apply_result"):
        lines.extend(["", "## Apply Result"])
        lines.append(f"- applied: `{report['apply_result'].get('applied', False)}`")
        for c in report["apply_result"].get("commands", []):
            lines.append(f"- `{c}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=1000)
    p.add_argument("--window-hours", type=float, default=24.0)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--min-events", type=int, default=100)
    p.add_argument("--target-win-rate", type=float, default=0.90)
    p.add_argument("--min-win-rate-rollback", type=float, default=0.80)
    p.add_argument("--target-regret-rate", type=float, default=0.15)
    p.add_argument("--max-regret-rate-rollback", type=float, default=0.25)
    p.add_argument("--max-p95-ms", type=float, default=450000.0)
    p.add_argument("--max-p95-ms-rollback", type=float, default=600000.0)
    args = p.parse_args()

    th = GuardThresholds(
        min_events=args.min_events,
        target_win_rate=args.target_win_rate,
        min_win_rate_rollback=args.min_win_rate_rollback,
        target_regret_rate=args.target_regret_rate,
        max_regret_rate_rollback=args.max_regret_rate_rollback,
        max_p95_ms=args.max_p95_ms,
        max_p95_ms_rollback=args.max_p95_ms_rollback,
    )
    metrics = load_routing_snapshot(args.count, args.window_hours)
    decision = evaluate_action(metrics, th)

    report = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry-run",
        "routing_metrics": metrics,
        "decision": decision,
        "thresholds": th.__dict__,
        "apply_result": None,
    }
    publish_decision_telemetry(metrics, decision["action"], decision["reason"])
    if args.apply:
        report["apply_result"] = apply_action(decision["action"], decision["reason"])

    AUDITS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json_path = AUDITS / f"{stamp}-nightly-routing-guard.json"
    md_path = AUDITS / f"{stamp}-nightly-routing-guard.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

