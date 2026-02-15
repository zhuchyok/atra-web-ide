#!/usr/bin/env python3
"""
Сравнение ответов из кураторского отчёта с эталоном (скоринг «как я»).
Использование:
  python3 scripts/curator_compare_to_standard.py --report docs/curator_reports/curator_2026-02-08_23-16-02.json
  python3 scripts/curator_compare_to_standard.py --report docs/curator_reports/curator_*.json --standard what_can_you_do
  python3 scripts/curator_compare_to_standard.py --report docs/curator_reports/curator_*.json --standard-file docs/curator_reports/standards/greeting.md
  python3 scripts/curator_compare_to_standard.py --report ... --standard status_project --write-findings
Вывод: по каждой задаче — статус, длина ответа, совпадение ключевых фраз эталона с выводом (если эталон задан).
План «умнее быстрее» §4.1: при --write-findings при падении скоринга (совпадений < порога) дописывается пометка в FINDINGS_YYYY-MM-DD.md.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STANDARDS_DIR = ROOT / "docs" / "curator_reports" / "standards"
FINDINGS_DIR = ROOT / "docs" / "curator_reports"
SCORE_THRESHOLD = 0.5  # ниже — пишем в FINDINGS «требуется дообучение RAG / правка эталона»


def load_report(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_standard_content(name: str) -> str:
    """Загрузить содержимое эталона по имени (без .md) или по пути."""
    p = STANDARDS_DIR / f"{name}.md" if not name.endswith(".md") else STANDARDS_DIR / name
    if not p.exists():
        p = ROOT / name
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def extract_key_phrases(md: str, max_chars: int = 400) -> list[str]:
    """Из markdown эталона вытащить фразы для проверки: слова из заголовков и из блока эталонного ответа."""
    key_phrases = []
    # Слова, которые часто должны быть в ответе Victoria
    for word in ("Виктория", "Team Lead", "Atra", "чат", "эксперт", "планы", "файл", "Veronica",
                 "Привет", "помочь", "статус", "дашборд", "список", "ls", "datetime", "date.today",
                 "STDOUT", "total"):
        if word.lower() in md.lower():
            key_phrases.append(word)
    # Первый абзац после "Эталонный ответ" или "**Эталонный ответ**"
    m = re.search(r"\*\*Эталонный ответ\*\*[:\s]*\n(.*?)(?=\n\n|\n\*\*|\Z)", md, re.DOTALL | re.IGNORECASE)
    if m:
        block = m.group(1).strip()[:max_chars]
        # Несколько коротких фраз из блока (первые слова предложений)
        for part in re.split(r"[.\n]", block):
            part = part.strip()
            if 10 <= len(part) <= 80:
                key_phrases.append(part)
    return key_phrases[:15]  # не более 15 фраз


def main():
    ap = argparse.ArgumentParser(description="Сравнить отчёт куратора с эталоном")
    ap.add_argument("--report", required=True, help="Путь к curator_*.json")
    ap.add_argument("--standard", default="", help="Имя эталона (например what_can_you_do) или пусто — без сравнения")
    ap.add_argument("--standard-file", default="", help="Путь к .md эталона (альтернатива --standard)")
    ap.add_argument("--write-findings", action="store_true", help="При падении скоринга дописать пометку в FINDINGS_YYYY-MM-DD.md")
    ap.add_argument("--threshold", type=float, default=SCORE_THRESHOLD, help="Порог доли совпадений (0..1), ниже — пишем в FINDINGS (по умолч. 0.5)")
    args = ap.parse_args()

    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    if not report_path.exists():
        print(f"Файл не найден: {report_path}", file=sys.stderr)
        return 1

    data = load_report(report_path)
    results = data.get("results") or []
    if not results:
        print("В отчёте нет results.")
        return 0

    standard_text = ""
    if args.standard_file:
        p = Path(args.standard_file)
        if not p.is_absolute():
            p = ROOT / p
        if p.exists():
            standard_text = p.read_text(encoding="utf-8")
    elif args.standard:
        standard_text = load_standard_content(args.standard)

    key_phrases = extract_key_phrases(standard_text) if standard_text else []

    print(f"Отчёт: {report_path.name}")
    print(f"Задач: {len(results)}")
    if key_phrases:
        print(f"Эталон: ключевых фраз для проверки: {len(key_phrases)}")
    print()

    standard_name = args.standard or (Path(args.standard_file).stem if args.standard_file else "")
    findings_lines = []

    def goal_relevant_to_standard(goal_text: str, std: str) -> bool:
        """Задача релевантна эталону — иначе не пишем FINDINGS (привет не сравниваем со status_project)."""
        g = (goal_text or "").lower()
        if std == "status_project":
            return "статус" in g or "проект" in g or "дашборд" in g
        if std == "greeting":
            return "привет" in g or "здравствуй" in g or "hello" in g or "hi" in g
        if std == "what_can_you_do":
            return "умеешь" in g or "умею" in g or "возможност" in g or "что ты" in g
        if std == "list_files":
            return "файл" in g or "список" in g or "list" in g or "ls" in g or "покажи" in g
        if std == "one_line_code":
            return "код" in g or "выведи" in g or "datetime" in g or "date.today" in g
        return True  # неизвестный эталон — пишем по порогу

    for i, rec in enumerate(results, 1):
        goal = (rec.get("goal") or "")[:60]
        goal_full = (rec.get("goal") or "")
        status = rec.get("status", "?")
        out = rec.get("output_preview") or rec.get("output") or ""
        out_len = len(out)
        line = f"  [{i}] {goal}... → {status}, ответ {out_len} символов"
        print(line)
        if key_phrases and out:
            found = sum(1 for p in key_phrases if p.lower() in out.lower())
            total = len(key_phrases)
            ratio = found / total if total else 1.0
            print(f"       Совпадений с эталоном: {found}/{total} ключевых фраз")
            if args.write_findings and standard_name and total and ratio < args.threshold and goal_relevant_to_standard(goal_full, standard_name):
                findings_lines.append(
                    f"- **Требуется дообучение RAG / правка эталона:** эталон `{standard_name}`, отчёт `{report_path.name}`, "
                    f"задача «{goal}...», совпадений {found}/{total}. Проверить эталон в standards/ и при необходимости curator_add_standard_to_knowledge."
                )
        elif key_phrases and not out:
            print("       (нет текста ответа для сравнения)")
            if args.write_findings and standard_name and goal_relevant_to_standard(goal_full, standard_name):
                findings_lines.append(
                    f"- **Требуется дообучение RAG / правка эталона:** эталон `{standard_name}`, отчёт `{report_path.name}`, "
                    f"задача «{goal}...», нет текста ответа. Проверить эталон и цепочку Victoria."
                )

    if args.write_findings and findings_lines:
        FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
        date_suffix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        findings_path = FINDINGS_DIR / f"FINDINGS_{date_suffix}.md"
        header = f"\n\n## Сравнение с эталоном ({report_path.name}, {date_suffix})\n\n"
        with open(findings_path, "a", encoding="utf-8") as f:
            f.write(header + "\n".join(findings_lines) + "\n")
        print(f"\nВ FINDINGS записано: {findings_path} ({len(findings_lines)} записей)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
