#!/usr/bin/env python3
"""Порог ученичества: сколько пар с фактом, пора ли поднимать рой."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "docs" / "curator_reports"
NEED = 3
FACT_MARKERS = (
    "health",
    "docker",
    "knowledge_nodes",
    "проверил",
    "прочитала",
    "localhost:",
    "ok —",
    "status",
    "curl",
    "8010",
    "8011",
    "3005",
    "8501",
    "pending=",
    "in_progress=",
)
BLOCKER_ONLY = ("n/a", "не проверяла", "блокер", "нет канала", "не нашла", "не нашёл")


def _section(text: str, header: str) -> str:
    low = text.lower()
    key = header.lower()
    if key not in low:
        return ""
    rest = low.split(key, 1)[1]
    for nxt in ("## lesson", "## goal", "## victoria"):
        if nxt != key and nxt in rest:
            rest = rest.split(nxt, 1)[0]
    return rest.strip()


def classify(text: str) -> str:
    vic = _section(text, "## victoria")
    if not vic:
        return "pass"
    if any(m in vic for m in BLOCKER_ONLY):
        return "pass"
    live = vic.strip()
    if live == "ok" or live.startswith("ok —"):
        return "fact"
    if any(m in vic for m in FACT_MARKERS):
        return "fact"
    return "pass"


def main() -> int:
    pairs = sorted(REPORTS.glob("pair_*.md"))
    facts = [p for p in pairs if classify(p.read_text(encoding="utf-8")) == "fact"]
    print(f"pairs={len(pairs)} fact_pairs={len(facts)} need={NEED}")
    if len(facts) >= NEED:
        print("GATE=swarm_ready")
        print(
            "Сделай без спроса: журналы экспертов + cursor-method в промпт роя "
            "+ тот же запрет «готово без доказательства»."
        )
        return 0
    print("GATE=wait")
    print(f"Ещё {NEED - len(facts)} пар(ы), где Виктория сама достала факт.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
