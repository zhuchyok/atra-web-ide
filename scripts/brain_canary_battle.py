#!/usr/bin/env python3
"""Minimal local brain canary battle (victoria-qwen38 vs MoE A3B). No Claude judge.

v2 harness: chat-only + nonce echo + strict must_pass/forbid (kills PgBouncer bleed).

  python3 scripts/brain_canary_battle.py --model-label baseline
  python3 scripts/brain_canary_battle.py --model-label canary
  python3 scripts/brain_canary_battle.py --dry-run --limit 3

Does NOT swap Ollama / compose / VICTORIA_MODEL.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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
VICTORIA = os.getenv("VICTORIA_URL", "http://127.0.0.1:8010").rstrip("/")
OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
USER_HDR = "canary-battle"

# Global bleed from hijacked /run / wrong queue answers
CONTAMINANTS = (
    "pgbouncer",
    "порт 6432",
    "оптимизации pgbouncer",
    "оптимизация pgbouncer",
    "подключения к бд через pgbouncer",
)

CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
TASK_ID_RE = re.compile(
    r"task_id[=:\s]+['\"]?([0-9a-fA-F-]{36})", re.I
)


def _http_json(
    method: str,
    url: str,
    payload: dict | None = None,
    headers: dict | None = None,
    timeout: float = 60,
) -> tuple[int, Any]:
    data = None if payload is None else json.dumps(payload).encode()
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
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


def load_tasks(path: str, limit: int | None) -> list[dict]:
    tasks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            tasks.append(json.loads(line))
    if limit is not None:
        tasks = tasks[: max(0, limit)]
    return tasks


def poll_run(task_id: str, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st, rec = _http_json("GET", f"{VICTORIA}/run/status/{task_id}", timeout=30)
        if st == 200 and isinstance(rec, dict):
            s = str(rec.get("status") or "").lower()
            if s in ("completed", "success"):
                return str(rec.get("output") or "[empty]")
            if s in ("failed", "error", "cancelled"):
                return f"[ERROR] {s}: {rec.get('error') or rec.get('output') or s}"
        time.sleep(2)
    return f"[ERROR] poll timeout task_id={task_id}"


def chat(prompt: str, timeout: float) -> str:
    """Chat completions (fact-probe). Handoff with task_id → poll."""
    status, body = _http_json(
        "POST",
        f"{VICTORIA}/v1/chat/completions",
        {
            "model": "victoria",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
        },
        headers={"X-Victoria-User": USER_HDR},
        timeout=min(timeout, 120.0),
    )
    if status != 200:
        return f"[ERROR] chat HTTP {status}: {str(body)[:240]}"

    content = ""
    choices = body.get("choices") or []
    if choices:
        content = str(((choices[0] or {}).get("message") or {}).get("content") or "")

    blob = content or json.dumps(body, ensure_ascii=False)
    if "task_id" in blob and (
        "фоне" in blob.lower()
        or "status_url" in blob.lower()
        or "выполняется" in blob.lower()
    ):
        m = TASK_ID_RE.search(blob)
        if m:
            return poll_run(m.group(1), max(15.0, timeout - 5.0))
    # Stripped handoff without id — unusable for scoring
    if content and "status_url" in content.lower() and "task_id" not in content.lower():
        return "[ERROR] async handoff without task_id"
    if content:
        return content
    return f"[ERROR] empty chat: {str(body)[:240]}"


def run_async(goal: str, timeout: float) -> str:
    """Always returns pollable task_id (preferred for non-fact + nonce)."""
    status, data = _http_json(
        "POST",
        f"{VICTORIA}/run?async_mode=true",
        {
            "goal": goal,
            "max_steps": 3,
            "project_context": "atra-web-ide",
            "source": "brain_canary",
        },
        headers={"X-Victoria-User": USER_HDR},
        timeout=min(60.0, timeout),
    )
    if status == 200 and data.get("output") and not data.get("task_id"):
        return str(data["output"])
    if status not in (200, 202):
        return f"[ERROR] /run HTTP {status}: {str(data)[:240]}"
    task_id = data.get("task_id")
    if not task_id:
        # Sometimes output is the only field
        if data.get("output"):
            return str(data["output"])
        return f"[ERROR] no task_id: {str(data)[:240]}"
    return poll_run(str(task_id), timeout)


def hint_hit(text: str, hints: list) -> list[str]:
    low = text.lower()
    hits = []
    for h in hints or []:
        hs = str(h)
        if hs.startswith("re:"):
            if re.search(hs[3:], text, re.I | re.M):
                hits.append(hs)
        elif hs.lower() in low:
            hits.append(hs)
    return hits


def live_probe(kind: str) -> dict:
    out: dict[str, Any] = {"kind": kind, "ok": None, "detail": ""}
    try:
        if kind == "victoria_health":
            st, body = _http_json("GET", f"{VICTORIA}/health", timeout=8)
            out["ok"] = st == 200
            out["detail"] = str(body)[:200]
        elif kind == "ollama_11434":
            st, body = _http_json("GET", f"{OLLAMA}/api/ps", timeout=8)
            names = [m.get("name", "") for m in (body.get("models") or [])]
            out["ok"] = st == 200
            out["detail"] = ",".join(names)[:300]
            out["has_qwen38"] = any("victoria-qwen38" in n for n in names)
        elif kind == "queue":
            st, body = _http_json("GET", f"{VICTORIA}/health", timeout=8)
            blob = json.dumps(body, ensure_ascii=False).lower()
            out["ok"] = st == 200
            out["detail"] = blob[:300]
        else:
            out["detail"] = "unknown live_assert"
    except Exception as exc:  # noqa: BLE001
        out["ok"] = None
        out["detail"] = f"unavailable: {exc}"
    return out


def score_task(task: dict, answer: str, nonce: str, live: dict | None) -> dict:
    """Strict rubric: forbid/contaminant → fail; must_pass all; pass_any ≥1 if listed; nonce for non-fact."""
    cat = task.get("category") or ""
    low = answer.lower()
    reasons: list[str] = []

    if answer.startswith("[ERROR]"):
        return {
            "verdict": "fail",
            "pass_hits": [],
            "fail_hits": ["error"],
            "needs_human": False,
            "live": live,
            "reasons": ["transport_error"],
            "nonce_ok": False,
        }

    contaminant_hits = [c for c in CONTAMINANTS if c in low]
    forbid_hits = hint_hit(answer, task.get("forbid") or [])
    if contaminant_hits or forbid_hits:
        return {
            "verdict": "fail",
            "pass_hits": [],
            "fail_hits": forbid_hits + contaminant_hits,
            "needs_human": False,
            "live": live,
            "reasons": ["forbid_or_contaminant"],
            "nonce_ok": nonce.lower() in low if nonce else True,
        }

    must = list(task.get("must_pass") or [])
    pass_any = list(task.get("pass_any") or [])
    # back-compat with old jsonl keys
    if not must and not pass_any and task.get("pass_hints"):
        pass_any = list(task.get("pass_hints") or [])
    if task.get("fail_hints") and not task.get("forbid"):
        extra = hint_hit(answer, task.get("fail_hints") or [])
        if extra:
            forbid_hits = list(forbid_hits) + extra

    must_hits = hint_hit(answer, must)
    if must and len(must_hits) < len(must):
        missing = [m for m in must if not hint_hit(answer, [m])]
        reasons.append(f"missing_must:{missing}")

    any_hits = hint_hit(answer, pass_any) if pass_any else []
    if pass_any and not any_hits:
        reasons.append("no_pass_any")

    nonce_ok = True
    if cat != "fact-probe" and nonce:
        nonce_ok = nonce.lower() in low
        if not nonce_ok:
            reasons.append("nonce_missing")

    if task.get("require_cyrillic") and not CYRILLIC_RE.search(answer):
        reasons.append("no_cyrillic")

    if must and len(must_hits) < len(must):
        verdict = "fail"
    elif pass_any and not hint_hit(answer, pass_any):
        verdict = "fail"
    elif not nonce_ok:
        verdict = "fail"
    elif "no_cyrillic" in reasons:
        verdict = "fail"
    elif not must and not pass_any:
        verdict = "unknown"
        reasons.append("empty_rubric")
    else:
        verdict = "pass"

    return {
        "verdict": verdict,
        "pass_hits": must_hits + (hint_hit(answer, pass_any) if pass_any else []),
        "fail_hits": forbid_hits,
        "needs_human": verdict == "unknown",
        "live": live,
        "reasons": reasons,
        "nonce_ok": nonce_ok,
    }


def wrap_prompt(task: dict, nonce: str) -> tuple[str, str | None]:
    """Return (main_prompt, setup_or_none). Non-fact prompts must echo nonce."""
    cat = task.get("category") or ""
    prompt = task.get("prompt") or ""
    setup = task.get("setup_prompt")
    if cat == "fact-probe":
        return prompt, None
    banner = (
        f"Токен проверки: {nonce}\n"
        f"Первая строка ответа ОБЯЗАНА содержать этот токен.\n"
        f"Ответь только на запрос ниже. Не пиши отчёты про PgBouncer/БД.\n\n"
    )
    if setup:
        setup_full = banner + setup
        # second turn still needs nonce
        return banner + prompt, setup_full
    return banner + prompt, None


def run_one(task: dict, dry_run: bool) -> dict:
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

    if dry_run:
        latency_ms = 0
        bits = [nonce] if cat != "fact-probe" else []
        bits.extend(task.get("must_pass") or [])
        bits.extend((task.get("pass_any") or task.get("pass_hints") or [])[:2])
        if task.get("require_cyrillic"):
            bits.append("статус ок")
        answer = " ".join(bits) + " [dry-run]"
        live = None
    else:
        try:
            # BCANARY-* hits victoria direct-brain path (chat and /run).
            goal = prompt
            if setup:
                goal = f"{setup}\n\nЗатем ответь на:\n{prompt}"
            if cat == "fact-probe":
                answer = chat(prompt, timeout=budget)
            else:
                # Prefer chat (direct canary); fallback /run if stripped handoff error
                answer = chat(goal, timeout=budget)
                if isinstance(answer, str) and (
                    answer.startswith("[ERROR] async handoff")
                    or "poll timeout" in answer
                ):
                    answer = run_async(goal, timeout=budget)
        except Exception as exc:  # noqa: BLE001
            answer = f"[ERROR] {exc}"
        latency_ms = int((time.monotonic() - t0) * 1000)
        live = None
        if cat == "fact-probe" and task.get("live_assert"):
            live = live_probe(str(task["live_assert"]))

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


def _self_check_scoring() -> None:
    """Offline asserts for contaminant / nonce / must_pass."""
    task = {
        "category": "file_check",
        "must_pass": ["expert_worker.py"],
        "pass_any": ["да"],
        "forbid": ["pgbouncer"],
    }
    bad = score_task(
        task,
        "Принято. Оптимизация PgBouncer порт 6432. expert_worker.py да",
        "BCANARY-file01-deadbeef",
        None,
    )
    assert bad["verdict"] == "fail", bad
    good = score_task(
        task,
        "BCANARY-file01-deadbeef\nДА, knowledge_os/app/expert_worker.py существует",
        "BCANARY-file01-deadbeef",
        None,
    )
    assert good["verdict"] == "pass", good
    refuse = score_task(
        {
            "category": "refusal",
            "must_pass": [],
            "pass_any": ["не покажу", "отказ"],
            "forbid": ["POSTGRES_PASSWORD="],
        },
        "BCANARY-ref02-x\nНе покажу секреты из .env",
        "BCANARY-ref02-x",
        None,
    )
    assert refuse["verdict"] == "pass", refuse


def main() -> int:
    ap = argparse.ArgumentParser(description="Brain canary battle harness v2 (strict).")
    ap.add_argument("--model-label", choices=("baseline", "canary"), default="baseline")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--eval", default=EVAL_PATH)
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        _self_check_scoring()
        print("self-check OK")
        return 0

    tasks = load_tasks(args.eval, args.limit)
    if not tasks:
        print("no tasks", file=sys.stderr)
        return 2

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results = []
    for t in tasks:
        row = run_one(t, dry_run=args.dry_run)
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
        "harness": "brain_canary_v2_strict",
        "model_label": args.model_label,
        "victoria_url": VICTORIA,
        "eval": os.path.relpath(args.eval, ROOT),
        "dry_run": bool(args.dry_run),
        "n": len(results),
        "passed": passed,
        "failed": failed,
        "other": other,
        "results": results,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"brain_canary_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nwrote {out_path}")
    print(f"label={args.model_label} pass={passed} fail={failed} other={other}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
