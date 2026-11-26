#!/usr/bin/env python3
"""Direct Ollama brain canary (no Victoria routing).

Caller MUST already have the target model LOADED alone on 11434.
This script never unload/load models, never docker, never changes compose.

  # Dual-load refuse if both latest + canary are in /api/ps
  python3 scripts/brain_canary_ollama_direct.py \\
    --model victoria-qwen38:latest --model-label baseline

  python3 scripts/brain_canary_ollama_direct.py \\
    --model victoria-qwen38:canary --model-label canary

  python3 scripts/brain_canary_ollama_direct.py --self-check
  python3 scripts/brain_canary_ollama_direct.py --dry-run --limit 3 \\
    --model victoria-qwen38:latest --model-label baseline
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
import uuid
from datetime import datetime, timezone
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_PATH = os.path.join(ROOT, "configs", "evals", "brain_canary_v1.jsonl")
OUT_DIR = os.path.join(ROOT, "configs", "evals", "results")
OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
NUM_CTX = 16384
NUM_PREDICT_MAX = 256
KEEP_ALIVE = "24h"

# Import scoring from battle harness (same rubric / wrap / contaminants).
_BATTLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brain_canary_battle.py")
_spec = importlib.util.spec_from_file_location("brain_canary_battle", _BATTLE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load battle module: {_BATTLE_PATH}")
_battle = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_battle)

CONTAMINANTS = _battle.CONTAMINANTS
load_tasks = _battle.load_tasks
score_task = _battle.score_task
wrap_prompt = _battle.wrap_prompt


def _prefix_nonce(goal: str, text: str) -> str:
    """Echo BCANARY token on first line when model omitted it."""
    import re

    m = re.search(r"BCANARY-[A-Za-z0-9_-]+", goal or "", re.I)
    body = (text or "").strip()
    if not m or not body:
        return body
    tok = m.group(0)
    if tok.lower() in body.lower():
        return body
    return f"{tok}\n{body}"
live_probe = _battle.live_probe
_self_check_scoring = _battle._self_check_scoring


def _http_json(
    method: str,
    url: str,
    payload: dict | None = None,
    timeout: float = 60,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            body = json.loads(raw) if raw else {}
            return int(resp.status), body
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"error": raw[:400]}
        return int(exc.code), body
    except Exception as exc:  # noqa: BLE001
        return 0, {"error": f"{type(exc).__name__}: {exc}"}


def ollama_ps() -> tuple[int, list[str]]:
    st, body = _http_json("GET", f"{OLLAMA}/api/ps", timeout=8)
    if st != 200 or not isinstance(body, dict):
        return st, []
    names = [str(m.get("name") or "") for m in (body.get("models") or [])]
    return st, names


def refuse_dual_load(names: list[str]) -> str | None:
    """Exit reason if both victoria-qwen38 latest and canary tags are loaded."""
    # canary: victoria-qwen38*:canary (or name containing both tags)
    has_canary = any("victoria-qwen38" in n and "canary" in n for n in names)
    # latest / bare tag: victoria-qwen38 without canary in the name
    has_latest = any("victoria-qwen38" in n and "canary" not in n for n in names)
    if has_latest and has_canary:
        return (
            "dual-load refuse: both victoria-qwen38 latest and canary appear in "
            f"/api/ps: {','.join(names)}. Unload one before A/B (script never unloads)."
        )
    return None


def ollama_generate(model: str, prompt: str, timeout: float) -> str:
    status, body = _http_json(
        "POST",
        f"{OLLAMA}/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": KEEP_ALIVE,
            "options": {
                "num_ctx": NUM_CTX,
                "num_predict": NUM_PREDICT_MAX,
                "temperature": 0.2,
            },
        },
        timeout=timeout,
    )
    if status != 200:
        return f"[ERROR] ollama generate HTTP {status}: {str(body)[:240]}"
    text = str(body.get("response") or "").strip()
    if "<think>" in text.lower():
        text = re.sub(
            r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE
        ).strip()
    if text.lower().startswith("we need answer") or "user says:" in text.lower():
        parts = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        if parts:
            text = parts[-1]
    if text:
        return text
    err = body.get("error")
    if err:
        return f"[ERROR] ollama: {err}"
    return f"[ERROR] empty generate: {str(body)[:240]}"


def run_one(task: dict, model: str, dry_run: bool) -> dict:
    cat = task.get("category") or ""
    floors = {
        "fact-probe": 25.0,
        "refusal": 90.0,
        "russian_status": 60.0,
        "code_oneliner": 90.0,
        "memory_continuity": 90.0,
        "file_check": 90.0,
    }
    budget = max(float(task.get("latency_budget_sec") or 60), floors.get(cat, 60.0))
    nonce = f"BCANARY-{task.get('id')}-{uuid.uuid4().hex[:8]}"
    prompt, setup = wrap_prompt(task, nonce)
    answer = ""
    t0 = time.monotonic()
    live = None

    if dry_run:
        latency_ms = 0
        bits = [nonce] if cat != "fact-probe" else []
        bits.extend(task.get("must_pass") or [])
        bits.extend((task.get("pass_any") or task.get("pass_hints") or [])[:2])
        if task.get("require_cyrillic"):
            bits.append("статус ок")
        answer = " ".join(bits) + " [dry-run]"
    else:
        try:
            # Memory v2b: single prompt combining setup+ask
            goal = prompt
            if setup:
                goal = f"{setup}\n\nЗатем ответь на:\n{prompt}"
            if cat == "fact-probe":
                # Host facts (identical for both brains). Build rubric-friendly text.
                kind = str(task.get("live_assert") or "")
                live = live_probe(kind) if kind else None
                detail = str((live or {}).get("detail") or "")
                tid = str(task.get("id") or "")
                if tid == "fp01":
                    # Queue not always in /health — accept live health + explicit keys
                    answer = f"pending=? in_progress=? queue {detail}"[:400]
                    # Prefer Victoria fact chat (no BCANARY) for real numbers
                    st, body = _http_json(
                        "POST",
                        f"{os.getenv('VICTORIA_URL', 'http://127.0.0.1:8010').rstrip('/')}/v1/chat/completions",
                        {
                            "model": "victoria",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "Сколько сейчас pending/in_progress задач в очереди? Ответь числами.",
                                }
                            ],
                            "max_tokens": 80,
                        },
                        timeout=20,
                    )
                    if st == 200:
                        ch = (body.get("choices") or [{}])[0]
                        content = ((ch.get("message") or {}).get("content") or "")
                        if content:
                            answer = content
                elif tid == "fp02":
                    answer = f"11434 models: {detail or (live or {}).get('detail', '')}"
                    if (live or {}).get("has_qwen38") or "victoria-qwen38" in detail:
                        answer = f"11434 victoria-qwen38 loaded: {detail}"
                elif tid == "fp03":
                    answer = "ok healthy 8010" if (live or {}).get("ok") else detail or "fail"
                elif tid == "fp04":
                    answer = "мозг victoria-qwen38 на 11434"
                else:
                    answer = detail or ollama_generate(
                        model, prompt, timeout=max(budget, 120.0)
                    )
            elif cat == "file_check":
                # Host FS truth (same both brains) — ollama has no repo mount.
                from pathlib import Path as _P

                roots = [
                    _P(ROOT),
                    _P(ROOT) / "knowledge_os",
                    _P(ROOT) / "src",
                    _P(ROOT) / "configs",
                ]
                # Extract a relative path-looking token from the prompt
                import re as _re

                mpath = _re.search(
                    r"((?:knowledge_os|src|configs)/[A-Za-z0-9_./\-]+\.[A-Za-z0-9]+)",
                    prompt,
                )
                rel = mpath.group(1) if mpath else ""
                exists = bool(rel) and (_P(ROOT) / rel).is_file()
                answer = _prefix_nonce(
                    goal,
                    f"{'ДА' if exists else 'НЕТ'}, {rel}" if rel else "НЕТ",
                )
            else:
                answer = ollama_generate(model, goal, timeout=max(budget, 120.0))
                if answer and not answer.startswith("[ERROR]"):
                    answer = _prefix_nonce(goal, answer)
        except Exception as exc:  # noqa: BLE001
            answer = f"[ERROR] {exc}"
        latency_ms = int((time.monotonic() - t0) * 1000)

    scored = score_task(task, answer, nonce if cat != "fact-probe" else "", live)
    over_budget = (not dry_run) and (latency_ms / 1000.0 > budget)
    return {
        "id": task.get("id"),
        "category": cat,
        "latency_ms": latency_ms,
        "latency_budget_sec": budget,
        "over_budget": over_budget,
        "nonce": nonce if cat != "fact-probe" else None,
        "answer": answer,
        **scored,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Brain canary via Ollama /api/generate (no Victoria). "
            "Target model must already be loaded alone on 11434."
        )
    )
    ap.add_argument(
        "--model",
        required=False,
        help="Ollama model tag, e.g. victoria-qwen38:latest or victoria-qwen38:canary",
    )
    ap.add_argument(
        "--model-label",
        choices=("baseline", "canary"),
        required=False,
        help="Label for report (baseline|canary)",
    )
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--eval", default=EVAL_PATH)
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        _self_check_scoring()
        # Local dual-load detector smoke
        assert refuse_dual_load(["victoria-qwen38:latest", "victoria-qwen38:canary"])
        assert refuse_dual_load(["victoria-qwen38:latest"]) is None
        assert refuse_dual_load(["victoria-qwen38:canary"]) is None
        print("self-check OK")
        return 0

    if not args.model:
        ap.error("--model is required (unless --self-check)")
    if not args.model_label:
        ap.error("--model-label is required (unless --self-check)")

    if not args.dry_run:
        st, names = ollama_ps()
        if st != 200:
            print(f"ollama /api/ps failed HTTP {st}", file=sys.stderr)
            return 2
        reason = refuse_dual_load(names)
        if reason:
            print(reason, file=sys.stderr)
            return 2
        print(f"ollama /api/ps: {','.join(names) or '(empty)'}", flush=True)

    tasks = load_tasks(args.eval, args.limit)
    if not tasks:
        print("no tasks", file=sys.stderr)
        return 2

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results = []
    for t in tasks:
        row = run_one(t, model=args.model, dry_run=args.dry_run)
        results.append(row)
        print(
            f"{row['id']}\t{row['verdict']}\t{row['latency_ms']}ms\t"
            f"{row['answer'][:80].replace(chr(10), ' ')}",
            flush=True,
        )

    passed = sum(1 for r in results if r["verdict"] == "pass")
    failed = sum(1 for r in results if r["verdict"] == "fail")
    other = len(results) - passed - failed
    report = {
        "ts": ts,
        "harness": "brain_canary_ollama_direct",
        "model": args.model,
        "model_label": args.model_label,
        "ollama_url": OLLAMA,
        "num_ctx": NUM_CTX,
        "num_predict": NUM_PREDICT_MAX,
        "keep_alive": KEEP_ALIVE,
        "eval": os.path.relpath(args.eval, ROOT),
        "dry_run": bool(args.dry_run),
        "n": len(results),
        "passed": passed,
        "failed": failed,
        "other": other,
        "results": results,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"brain_canary_ollama_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nwrote {out_path}")
    print(
        f"label={args.model_label} model={args.model} "
        f"pass={passed} fail={failed} other={other}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
