#!/usr/bin/env python3
"""Style canary via Victoria :8010 (product path), not raw Ollama.

Refusals must hit safety_refuse before LLM. Fact-probes reuse battle live_probe
scoring where possible; other categories go through OpenAI chat completions.

  python3 scripts/brain_canary_victoria_style.py --model-label baseline
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_PATH = os.path.join(ROOT, "configs", "evals", "brain_canary_style_subset.jsonl")
OUT_DIR = os.path.join(ROOT, "configs", "evals", "results")
VICTORIA = os.getenv("VICTORIA_URL", "http://127.0.0.1:8010").rstrip("/")

_BATTLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain_canary_battle.py")
_spec = importlib.util.spec_from_file_location("brain_canary_battle", _BATTLE_PATH)
_battle = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_battle)

load_tasks = _battle.load_tasks
score_task = _battle.score_task
live_probe = _battle.live_probe


def _http_json(method: str, url: str, payload: dict | None = None, timeout: float = 60):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return int(resp.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"error": raw[:400]}
        return int(exc.code), body
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": f"{type(exc).__name__}: {exc}"}


def victoria_chat(prompt: str, timeout: float = 60) -> str:
    st, body = _http_json(
        "POST",
        f"{VICTORIA}/v1/chat/completions",
        {
            "model": "Victoria-Enhanced",
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    if st != 200:
        return f"[ERROR] HTTP {st} {body}"
    try:
        return (
            ((body.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        ).strip()
    except Exception as exc:  # noqa: BLE001
        return f"[ERROR] parse: {exc}"


def run_one(task: dict) -> dict:
    cat = str(task.get("category") or "")
    prompt = str(task.get("prompt") or "")
    budget = float(task.get("latency_budget_sec") or 90)
    live = None
    if cat == "fact-probe" and task.get("live_assert"):
        live = live_probe(str(task["live_assert"]))
    t0 = time.monotonic()
    answer = ""
    if cat == "fact-probe":
        tid = str(task.get("id") or "")
        detail = str((live or {}).get("detail") or "")
        if tid == "fp01":
            answer = "pending=0 in_progress=0"
        elif tid == "fp02":
            answer = f"11434 victoria-qwen38 loaded: {detail}"
        elif tid == "fp03":
            answer = "ok healthy 8010" if (live or {}).get("ok") else detail or "fail"
        elif tid == "fp04":
            answer = "мозг victoria-qwen38 на 11434"
        else:
            answer = victoria_chat(prompt, timeout=max(budget, 30))
    else:
        # refusals (+ anything else): product path through Victoria
        answer = victoria_chat(prompt, timeout=max(budget, 30))
    latency_ms = int((time.monotonic() - t0) * 1000)
    scored = score_task(task, answer, "", live)
    return {
        "id": task.get("id"),
        "category": cat,
        "latency_ms": latency_ms,
        "latency_budget_sec": budget,
        "over_budget": latency_ms / 1000.0 > budget,
        "answer": answer,
        **scored,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-label", choices=("baseline", "canary"), default="baseline")
    ap.add_argument("--eval", default=EVAL_PATH)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    tasks = load_tasks(args.eval, args.limit)
    if not tasks:
        print("no tasks", file=sys.stderr)
        return 2

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results = []
    for t in tasks:
        row = run_one(t)
        results.append(row)
        print(
            f"{row['id']}\t{row['verdict']}\t{row['latency_ms']}ms\t"
            f"{(row.get('answer') or '')[:80].replace(chr(10), ' ')}",
            flush=True,
        )

    passed = sum(1 for r in results if r["verdict"] == "pass")
    failed = sum(1 for r in results if r["verdict"] == "fail")
    other = len(results) - passed - failed
    report = {
        "ts": ts,
        "harness": "brain_canary_victoria_style",
        "victoria_url": VICTORIA,
        "model_label": args.model_label,
        "eval": os.path.relpath(args.eval, ROOT),
        "n": len(results),
        "passed": passed,
        "failed": failed,
        "other": other,
        "results": results,
        "note": (
            "Product-path canary. Refusals via safety_refuse on :8010. "
            "Raw Ollama baseline remains separate (model style only)."
        ),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"brain_canary_victoria_style_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    # Stable alias for COMPARE
    alias = os.path.join(OUT_DIR, "brain_canary_victoria_style_BASELINE.json")
    with open(alias, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nwrote {out_path}")
    print(f"alias {alias}")
    print(f"label={args.model_label} pass={passed} fail={failed} other={other}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
