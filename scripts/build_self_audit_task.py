#!/usr/bin/env python3
"""Собрать задачу самоаудита с РЕАЛЬНЫМ материалом: выдержки ответов Виктории
за последние сутки из кураторских отчётов.

Раньше самоаудит был бесполезен: Виктория stateless, своих прошлых ответов
не видит — и честно отказывалась выдумывать примеры (находка от 2026-11-10).
Теперь куратор подкладывает ей её собственные ответы.

Использование: python3 scripts/build_self_audit_task.py > /tmp/self_audit_task.txt
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "docs" / "curator_reports"
TEMPLATE = ROOT / "scripts" / "curator_self_audit_tasks.txt"


def main() -> None:
    base = TEMPLATE.read_text(encoding="utf-8")
    cutoff = datetime.now() - timedelta(hours=30)
    excerpts = []
    # только отчёты вида curator_YYYY-MM-DD_HH-MM-SS.json (не curator_full_*)
    import re

    pat = re.compile(r"^curator_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})$")
    dated = []
    for f in REPORTS.glob("curator_*.json"):
        m = pat.match(f.stem)
        if not m:
            continue
        try:
            ts = datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H-%M-%S")
        except ValueError:
            continue
        dated.append((ts, f))
    for ts, f in sorted(dated, reverse=True):
        if ts < cutoff:
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for r in d.get("results", []):
            goal, out = r.get("goal", ""), str(r.get("output_preview", ""))
            if "самоаудит" in goal.lower() or "интроспек" in goal.lower() or len(out) < 20:
                continue
            excerpts.append(f"ЗАДАЧА: {goal[:150]}\nТВОЙ ОТВЕТ: {out[:600]}")
        if len(excerpts) >= 8:
            break
    material = "\n\n".join(excerpts[:8]) or "(материала за сутки нет — проанализируй свои общие паттерны и честно скажи, что данных не хватает)"
    print(base)
    print(
        "\n\n=== МАТЕРИАЛ: твои реальные ответы за последние сутки ===\n"
        "Анализируй ИХ (не выдумывай примеры). Для каждого: честный ли отказ при незнании, "
        "нет ли выдуманных фактов под уверенной формой, шаблонность.\n\n" + material
    )


if __name__ == "__main__":
    main()
