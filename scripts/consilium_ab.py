#!/usr/bin/env python3
"""A/B «одиночная Виктория vs консилиум» на eval-наборе (план 2026-09-22, Фаза 3.2).

Для каждого вопроса из configs/evals/consilium_v1.jsonl:
  A — POST /run (async) на Victoria 8010 — одиночный ответ.
  B — POST /api/expert-dialogue/start (mode=debate) на backend 8080 — консилиум.
Судья — victoria-wisdom-24k через MLX 11435 (/api/chat): rubric-оценка 0-10 обоим
ответам (correctness, grounding, completeness) + победитель.

Результат: configs/evals/results/battle_<TS>.json
Запуск: python3 scripts/consilium_ab.py --limit 4 [--category security]
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VICTORIA = os.getenv("VICTORIA_URL", "http://localhost:8010")
DIALOGUE = os.getenv("EXPERT_DIALOGUE_URL", "http://localhost:8080")
MLX = os.getenv("MLX_BASE_URL", "http://localhost:11435")
JUDGE_MODEL = os.getenv("VICTORIA_WISDOM_MODEL", "victoria-wisdom-24k")
POLL_TIMEOUT = float(os.getenv("AB_POLL_TIMEOUT", "180"))


def _post_json(url, payload, timeout=30):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get_json(url, timeout=15):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def solo_answer(goal: str) -> str:
    """Одиночная Виктория через /run async + poll."""
    resp = _post_json(f"{VICTORIA}/run?async_mode=true", {"goal": goal})
    if resp.get("status") == "success" and resp.get("output"):
        return resp["output"]  # fast-path
    task_id = resp.get("task_id")
    if not task_id:
        return f"[ERROR] no task_id: {json.dumps(resp)[:120]}"
    deadline = time.monotonic() + POLL_TIMEOUT
    while time.monotonic() < deadline:
        try:
            rec = _get_json(f"{VICTORIA}/run/status/{task_id}")
            if rec.get("status") in ("completed", "failed"):
                return rec.get("output") or f"[{rec.get('status')}] empty"
        except Exception:
            pass
        time.sleep(3)
    return "[ERROR] timeout"


def consilium_answer(goal: str) -> str:
    """Консилиум (debate) через expert-dialogue. Контракт: POST /start {topic, mode}."""
    try:
        resp = _post_json(
            f"{DIALOGUE}/api/expert-dialogue/start",
            {"topic": goal, "mode": "debate"},
            timeout=300,
        )
    except Exception as e:
        return f"[ERROR] dialogue: {e}"
    parts = resp.get("opinions") or []
    synth = resp.get("synthesis") or resp.get("result") or ""
    if not synth and parts:
        synth = "\n".join(f"— {p.get('expert','?')}: {p.get('opinion','')}" for p in parts)
    if resp.get("fallback_used") or resp.get("lightweight_used"):
        note = " [degraded]"
    else:
        note = ""
    engine = resp.get("engine_used", "?")
    return f"[{engine}{note}] {synth}".strip()


def judge(goal: str, answer_a: str, answer_b: str) -> dict:
    """Rubric-оценка судьёй на MLX. Возвращает {'a':x,'b':y,'winner':'A'|'B'|'tie','reason':...}."""
    prompt = (
        "Ты — строгий судья ответов ИИ-ассистента. Оцени два ответа на один вопрос по шкале 0-10 "
        "по трём критериям: корректность, опора на факты (без выдумок), полнота.\n\n"
        f"ВОПРОС: {goal}\n\n"
        f"ОТВЕТ A (одиночный):\n{answer_a[:2500]}\n\n"
        f"ОТВЕТ B (консилиум):\n{answer_b[:2500]}\n\n"
        "Ответь ТОЛЬКО в формате JSON без пояснений:\n"
        '{"a": <0-10>, "b": <0-10>, "winner": "A"|"B"|"tie", "reason": "<одна фраза>"}'
    )
    try:
        resp = _post_json(
            f"{MLX}/api/chat",
            {"model": JUDGE_MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False},
            timeout=120,
        )
        raw = resp.get("message", {}).get("content", "")
        # Убрать think-артефакты и найти валидный JSON-объект (не всегда первый "{").
        raw = raw.replace("<think>", "").replace("</think>", "")
        verdict = None
        for i in (raw.find("{"), raw.rfind("{")):
            for start in ([i] if i >= 0 else []):
                end = raw.rfind("}") + 1
                if end > start:
                    try:
                        verdict = json.loads(raw[start:end])
                        break
                    except json.JSONDecodeError:
                        continue
            if verdict:
                break
        if verdict is None:
            return {"a": 0.0, "b": 0.0, "winner": "error", "reason": f"judge parse: {raw[:80]}"}
        return {
            "a": float(verdict.get("a", 0)),
            "b": float(verdict.get("b", 0)),
            "winner": verdict.get("winner", "tie"),
            "reason": verdict.get("reason", ""),
        }
    except Exception as e:
        return {"a": 0.0, "b": 0.0, "winner": "error", "reason": str(e)[:120]}
    return {"a": 0.0, "b": 0.0, "winner": "error", "reason": "judge parse failed"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=os.path.join(ROOT, "configs/evals/consilium_v1.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--category", default="")
    args = ap.parse_args()

    items = [json.loads(l) for l in open(args.file, encoding="utf-8") if l.strip()]
    if args.category:
        items = [i for i in items if i["category"] == args.category]
    if args.limit:
        items = items[: args.limit]
    if not items:
        print("Нет вопросов для прогона.")
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(ROOT, "configs/evals/results", f"battle_{ts}.json")
    results, wins = [], {"A": 0, "B": 0, "tie": 0, "error": 0}
    for n, item in enumerate(items, 1):
        print(f"[{n}/{len(items)}] {item['id']}: {item['goal'][:60]}", flush=True)
        a = solo_answer(item["goal"])
        b = consilium_answer(item["goal"])
        verdict = judge(item["goal"], a, b)
        wins[verdict["winner"]] = wins.get(verdict["winner"], 0) + 1
        results.append({**item, "solo": a[:1500], "consilium": b[:1500], "verdict": verdict})
        print(
            f"    A={verdict['a']:.0f} B={verdict['b']:.0f} → {verdict['winner']} ({verdict['reason'][:60]})",
            flush=True,
        )

    out = {"timestamp": ts, "wins": wins, "results": results}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    total = sum(v for k, v in wins.items() if k != "error")
    print(f"\n🏆 Итог: A(соло)={wins['A']} B(консилиум)={wins['B']} tie={wins['tie']} error={wins['error']} из {total}")
    print(f"Отчёт: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
