#!/usr/bin/env python3
"""
Detect new Python crash reports for MLX coalitions and notify.

Monitors:
  ~/Library/Logs/DiagnosticReports/Python-*.ips

Filters:
  coalitionName starts with "com.atra.mlx-"

Outputs:
  - per-incident JSON reports in Application Support
  - detector log
  - macOS notification (osascript)
  - optional ntfy push if ATRA_CRASH_NTFY_URL is configured
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DIAG_DIR = Path.home() / "Library" / "Logs" / "DiagnosticReports"
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "Atra" / "python-crash-detector"
STATE_FILE = APP_SUPPORT_DIR / "state.json"
REPORTS_DIR = APP_SUPPORT_DIR / "reports"
LOG_FILE = Path.home() / "Library" / "Logs" / "atra-python-crash-detector.log"

COALITION_PREFIX = os.getenv("ATRA_CRASH_COALITION_PREFIX", "com.atra.mlx-")
NTFY_URL = os.getenv("ATRA_CRASH_NTFY_URL", "").strip()


def log_line(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def read_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_state(state: dict[str, Any]) -> None:
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_ips(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            first_line = f.readline().strip()
            if not first_line:
                return None
            meta = json.loads(first_line)
            body = json.loads(f.read())
    except Exception as exc:
        log_line(f"parse_failed path={path} error={exc}")
        return None
    return {"meta": meta, "body": body}


def extract_trigger_stack(body: dict[str, Any], max_frames: int = 15) -> list[str]:
    threads = body.get("threads", [])
    triggered = None
    for t in threads:
        if t.get("triggered"):
            triggered = t
            break
    if triggered is None and isinstance(body.get("faultingThread"), int):
        idx = body.get("faultingThread")
        if 0 <= idx < len(threads):
            triggered = threads[idx]
    if not triggered:
        return []

    lines: list[str] = []
    for frame in triggered.get("frames", [])[:max_frames]:
        symbol = frame.get("symbol", "?")
        image_index = frame.get("imageIndex", "?")
        location = frame.get("symbolLocation", 0)
        lines.append(f"{symbol} (+{location}) [image:{image_index}]")
    return lines


def notify_macos(title: str, subtitle: str, message: str) -> None:
    script = (
        'display notification "{}" with title "{}" subtitle "{}"'
        .format(message.replace('"', "'"), title.replace('"', "'"), subtitle.replace('"', "'"))
    )
    try:
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True, timeout=5)
    except Exception as exc:
        log_line(f"notification_failed error={exc}")


def notify_ntfy(title: str, message: str) -> None:
    if not NTFY_URL:
        return
    data = message.encode("utf-8")
    req = urllib.request.Request(NTFY_URL, data=data, method="POST")
    req.add_header("Title", title)
    req.add_header("Content-Type", "text/plain; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except urllib.error.URLError as exc:
        log_line(f"ntfy_failed error={exc}")


def write_report(payload: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    incident = payload.get("incident_id", "unknown")
    out_path = REPORTS_DIR / f"python_crash_{ts}_{incident}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = REPORTS_DIR / "latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def detect_new_events(force_latest: bool = False) -> int:
    state = read_state()
    now_ts = time.time()
    files = sorted(Path(p) for p in glob.glob(str(DIAG_DIR / "Python-*.ips")))

    if not state:
        # Bootstrap without noisy alerts on historical incidents.
        known = {}
        for p in files:
            known[p.name] = int(p.stat().st_mtime)
        write_state(
            {
                "initialized_at": datetime.now(timezone.utc).isoformat(),
                "last_scan_ts": int(now_ts),
                "known_files": known,
                "seen_incidents": [],
            }
        )
        log_line(f"bootstrapped files={len(files)}")
        return 0

    known_files = dict(state.get("known_files", {}))
    seen_incidents = set(state.get("seen_incidents", []))
    new_hits = 0

    candidates: list[Path] = []
    if force_latest and files:
        candidates = [files[-1]]
    else:
        for p in files:
            mtime = int(p.stat().st_mtime)
            if known_files.get(p.name, 0) < mtime:
                candidates.append(p)

    for path in candidates:
        parsed = parse_ips(path)
        known_files[path.name] = int(path.stat().st_mtime)
        if not parsed:
            continue
        meta = parsed["meta"]
        body = parsed["body"]
        coalition = str(body.get("coalitionName", ""))
        incident = str(meta.get("incident_id", body.get("incident", "")))
        if incident and incident in seen_incidents:
            continue
        if not coalition.startswith(COALITION_PREFIX):
            continue

        stack = extract_trigger_stack(body)
        exception = body.get("exception", {})
        payload = {
            "detected_at_utc": datetime.now(timezone.utc).isoformat(),
            "report_file": str(path),
            "incident_id": incident,
            "timestamp": meta.get("timestamp"),
            "coalitionName": coalition,
            "procName": body.get("procName"),
            "pid": body.get("pid"),
            "exception": exception,
            "termination": body.get("termination", {}),
            "trigger_stack": stack,
        }
        report_path = write_report(payload)

        signal = exception.get("signal", "unknown")
        subtitle = f"{coalition} | signal={signal}"
        message = f"Python crash detected. report={report_path.name}"
        notify_macos("ATRA MLX Crash", subtitle, message)
        notify_ntfy("ATRA MLX Crash", f"{subtitle}\n{message}")
        log_line(f"crash_detected incident={incident} coalition={coalition} signal={signal}")

        if incident:
            seen_incidents.add(incident)
        new_hits += 1

    state["last_scan_ts"] = int(now_ts)
    state["known_files"] = known_files
    state["seen_incidents"] = sorted(seen_incidents)
    write_state(state)
    return new_hits


def main() -> int:
    parser = argparse.ArgumentParser(description="ATRA Python crash detector for MLX coalitions")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit")
    parser.add_argument("--force-latest-alert", action="store_true", help="Force scan latest report for validation")
    args = parser.parse_args()

    hits = detect_new_events(force_latest=args.force_latest_alert)
    log_line(f"scan_done hits={hits}")
    if args.once:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
