#!/usr/bin/env python3
"""
Auto-switch runtime profile between balanced and night-peak modes.

Decision uses hysteresis to avoid mode flapping:
- switch ON when pressure is high;
- switch OFF only after sustained calm.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOGGLE_SCRIPT = ROOT / "scripts" / "toggle_night_peak_profile.sh"
STATE_FILE = ROOT / ".cache" / "night_peak_profile_state.json"
ENV_FILE = ROOT / ".env"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class Config:
    high_queue: int = _env_int("NIGHT_PEAK_HIGH_QUEUE", 4)
    low_queue: int = _env_int("NIGHT_PEAK_LOW_QUEUE", 0)
    high_overload_10m: int = _env_int("NIGHT_PEAK_HIGH_OVERLOAD_10M", 120)
    low_overload_10m: int = _env_int("NIGHT_PEAK_LOW_OVERLOAD_10M", 20)
    stale_threshold_min: int = _env_int("NIGHT_PEAK_STALE_THRESHOLD_MIN", 15)
    min_switch_interval_sec: int = _env_int("NIGHT_PEAK_MIN_SWITCH_INTERVAL_SEC", 1200)


def run_cmd(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:  # pragma: no cover
        return 1, "", str(exc)


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def current_mode_from_env() -> str:
    if not ENV_FILE.exists():
        return "off"
    mode = "off"
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("ORCHESTRATOR_BACKGROUND_MAX_DISPATCH_PER_CYCLE="):
            value = line.split("=", 1)[1].strip()
            mode = "on" if value == "0" else "off"
            break
    return mode


def psql_scalar(sql: str) -> int:
    code, out, err = run_cmd(
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
            "-c",
            sql,
        ],
        timeout=40,
    )
    if code != 0:
        raise RuntimeError(f"psql_failed:{err or out}")
    try:
        return int(out.strip())
    except ValueError as exc:
        raise RuntimeError(f"psql_parse_failed:{out}") from exc


def vector_overload_count(minutes: int = 10) -> int:
    code, out, err = run_cmd(
        [
            "docker",
            "logs",
            f"--since={minutes}m",
            "knowledge_vector_core",
        ],
        timeout=40,
    )
    if code != 0 and not out and err:
        raise RuntimeError(f"vector_logs_failed:{err}")

    count = 0
    for line in (out + "\n" + err).splitlines():
        lower = line.lower()
        if (
            " 503 " in line
            or '"status":503' in line
            or 'http/1.1" 503' in lower
            or "overload" in lower
            or "cooldown" in lower
        ):
            count += 1
    return count


def collect_metrics(cfg: Config) -> dict:
    pending = psql_scalar("SELECT COUNT(*) FROM tasks WHERE status='pending';")
    in_progress = psql_scalar("SELECT COUNT(*) FROM tasks WHERE status='in_progress';")
    queued = psql_scalar("SELECT COUNT(*) FROM tasks WHERE status='queued';")
    stale = psql_scalar(
        "SELECT COUNT(*) FROM tasks WHERE status='in_progress' "
        f"AND updated_at < NOW() - INTERVAL '{cfg.stale_threshold_min} minutes';"
    )
    overload_10m = vector_overload_count(minutes=10)

    return {
        "pending": pending,
        "in_progress": in_progress,
        "queued": queued,
        "active_queue": pending + in_progress + queued,
        "stale_in_progress": stale,
        "vector_overload_10m": overload_10m,
    }


def decide_mode(current_mode: str, metrics: dict, cfg: Config) -> tuple[str, str]:
    active_queue = metrics["active_queue"]
    stale = metrics["stale_in_progress"]
    overload = metrics["vector_overload_10m"]

    high_pressure = (
        active_queue >= cfg.high_queue
        or stale > 0
        or overload >= cfg.high_overload_10m
    )
    calm_window = (
        active_queue <= cfg.low_queue
        and stale == 0
        and overload <= cfg.low_overload_10m
    )

    if current_mode == "off" and high_pressure:
        reason = (
            f"pressure_high(queue={active_queue},stale={stale},"
            f"overload_10m={overload})"
        )
        return "on", reason
    if current_mode == "on" and calm_window:
        reason = (
            f"pressure_calm(queue={active_queue},stale={stale},"
            f"overload_10m={overload})"
        )
        return "off", reason
    return current_mode, "hold"


def apply_mode(target_mode: str) -> None:
    if not TOGGLE_SCRIPT.exists():
        raise RuntimeError(f"toggle_script_missing:{TOGGLE_SCRIPT}")
    code, out, err = run_cmd(["bash", str(TOGGLE_SCRIPT), target_mode, "--apply"], timeout=240)
    if code != 0:
        raise RuntimeError(f"toggle_failed:{err or out}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-switch night peak profile")
    parser.add_argument("--dry-run", action="store_true", help="Compute only; do not switch")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    cfg = Config()
    state = load_state()
    now = int(time.time())

    try:
        current_mode = current_mode_from_env()
        metrics = collect_metrics(cfg)
        desired_mode, decision_reason = decide_mode(current_mode, metrics, cfg)
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False) if args.json else f"❌ {payload['error']}")
        return 1

    last_switch_ts = int(state.get("last_switch_ts", 0) or 0)
    seconds_since_switch = now - last_switch_ts if last_switch_ts else 10**9
    blocked_by_dwell = (
        desired_mode != current_mode
        and seconds_since_switch < cfg.min_switch_interval_sec
    )

    action = "none"
    if desired_mode != current_mode and not blocked_by_dwell and not args.dry_run:
        apply_mode(desired_mode)
        action = f"switched_to_{desired_mode}"
        state.update(
            {
                "last_switch_ts": now,
                "last_mode": desired_mode,
                "last_reason": decision_reason,
            }
        )
        save_state(state)
    elif desired_mode != current_mode and blocked_by_dwell:
        action = "hold_min_interval"
    elif desired_mode != current_mode and args.dry_run:
        action = f"would_switch_to_{desired_mode}"

    payload = {
        "ok": True,
        "current_mode": current_mode,
        "desired_mode": desired_mode,
        "action": action,
        "decision_reason": decision_reason,
        "seconds_since_last_switch": seconds_since_switch,
        "min_switch_interval_sec": cfg.min_switch_interval_sec,
        "metrics": metrics,
        "thresholds": {
            "high_queue": cfg.high_queue,
            "low_queue": cfg.low_queue,
            "high_overload_10m": cfg.high_overload_10m,
            "low_overload_10m": cfg.low_overload_10m,
            "stale_threshold_min": cfg.stale_threshold_min,
        },
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(
            "AUTO PROFILE:"
            f" current={current_mode}"
            f" desired={desired_mode}"
            f" action={action}"
            f" reason={decision_reason}"
            f" queue={metrics['active_queue']}"
            f" stale={metrics['stale_in_progress']}"
            f" overload10m={metrics['vector_overload_10m']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
