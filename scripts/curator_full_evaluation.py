#!/usr/bin/env python3
"""
Полный прогон куратора: тестирует Victoria по всем эталонам и оценивает «как я».

Что делает:
1. Читает все .md файлы из docs/curator_reports/standards/
2. Для каждого извлекает цель (goal) из секции **Цель (goal):**
3. Определяет тестовый запрос на основе цели
4. Отправляет запрос Victoria через /v1/chat/completions
5. Сравнивает ответ с эталоном (ключевые фразы + критерии)
6. Генерирует JSON-отчёт и MD-превью

Запуск:
  python3 scripts/curator_full_evaluation.py
  python3 scripts/curator_full_evaluation.py --limit 5      # только 5 эталонов
  python3 scripts/curator_full_evaluation.py --quick         # быстрый режим (3 мин на задачу)
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
STANDARDS_DIR = ROOT / "docs" / "curator_reports" / "standards"
REPORTS_DIR = ROOT / "docs" / "curator_reports"
VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
VICTORIA_TIMEOUT = int(os.getenv("CURATOR_TIMEOUT_SEC", "600"))
POLL_INTERVAL = 5.0

# Маппинг: эталон → тестовый запрос к Victoria
STANDARD_QUERIES = {
    "greeting": "Привет",
    "status_project": "Какой статус проекта?",
    "what_can_you_do": "Что ты умеешь?",
    "list_files": "Покажи список файлов в корне проекта",
    "one_line_code": "Напиши одну строку кода: выведи сегодняшнюю дату на Python",
    "code_audit": "Проверь файл на наличие hardcoded секретов в коде проекта. Имя файла: app/main.py",
    "problem_solving": (
        "Напиши функцию на Python, которая принимает список чисел "
        "и возвращает отсортированный список уникальных значений"
    ),
    "code_review": "Сделай code review этого кода: def add(a,b): return a+b. Подскажи как улучшить.",
    "debugging": "Почему не работает код def foo(): return 1/0? Объясни и исправь.",
    "architecture": "Спроектируй архитектуру для микросервиса авторизации на FastAPI",
    "task_decomposition": "Как подойти к реализации фичи 'корзина покупок'?",
    "conciseness": "Сделай рефакторинг этой функции: def x(a,b,c,d,e): return a+b+c+d+e",
    "tool_usage": "Найди в коде проекта функцию, которая обрабатывает ошибки",
    "security": "Проверь безопасность этого кода: password = 'admin123'",
    "performance": "Этот код тормозит: for i in range(len(items)): process(items[i])",
    "testing": "Напиши юнит-тесты для функции calculate_discount(price, percent)",
    "error_handling": "Добавь обработку ошибок в этот код: def read_file(path): return open(path).read()",
    "conventions": "Напиши компонент React для кнопки в стиле проекта",
    "communication": "Объясни как работает декоратор @cache в Python",
    "code_generation": "Реализуй класс User с полями name, email, password",
    "research": "Разберись как работает эндпоинт /api/omni-rag/search в проекте",
    "refactoring": "Упрости этот код: if x == True: return True else: return False",
}

# Маппинг: эталон → функция проверки релевантности для goal_relevant_to_standard
def goal_relevant(goal_text: str, std_name: str) -> bool:
    g = (goal_text or "").lower()
    mapping = {
        "status_project": lambda: "статус" in g or "проект" in g,
        "greeting": lambda: "привет" in g or "здравствуй" in g or "hello" in g,
        "what_can_you_do": lambda: "умеешь" in g or "возможност" in g or "что ты" in g,
        "list_files": lambda: ("покажи" in g and "файл" in g) or "список" in g,
        "code_audit": lambda: "проверь" in g or "секрет" in g or "hardcoded" in g,
        "one_line_code": lambda: "код" in g or "дату" in g or "date" in g,
        "problem_solving": lambda: "функци" in g or "задач" in g,
        "code_review": lambda: "code review" in g or "рефактор" in g,
        "debugging": lambda: "почему" in g or "не рабо" in g or "баг" in g or "ошибк" in g,
        "architecture": lambda: "архитектур" in g or "спроектируй" in g or "микросервис" in g,
        "task_decomposition": lambda: "декомпозиц" in g or "подойти" in g or "спланируй" in g,
        "conciseness": lambda: "рефакторинг" in g or "упрости" in g,
        "tool_usage": lambda: "найди" in g or "grep" in g or "инструмент" in g,
        "security": lambda: "безопасн" in g or "security" in g or "уязвим" in g,
        "performance": lambda: "тормоз" in g or "производительн" in g or "оптимиз" in g,
        "testing": lambda: "тест" in g or "юнит" in g or "unittest" in g,
        "error_handling": lambda: "ошибк" in g or "error" in g or "try" in g,
        "conventions": lambda: "компонент" in g or "react" in g or "стиль" in g,
        "communication": lambda: "объясни" in g or "расскажи" in g or "как работ" in g,
        "code_generation": lambda: "реализуй" in g or "класс" in g or "напиши код" in g,
        "research": lambda: "разберись" in g or "исследуй" in g or "как работ" in g,
        "refactoring": lambda: "упрости" in g or "рефакторинг" in g or "перепиши" in g,
    }
    mapper = mapping.get(std_name)
    if mapper:
        return mapper()
    return True


def load_standard_content(name: str) -> str:
    p = STANDARDS_DIR / f"{name}.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def extract_key_phrases(md: str) -> list[str]:
    phrases = []
    kp = re.search(
        r"\*\*Ключевые фразы[^*]*\*\*[^\n]*\n((?:[ \t]*-[^\n]+\n?)+)",
        md, re.IGNORECASE
    )
    if kp:
        for line in kp.group(1).splitlines():
            line = re.sub(r"^[ \t]*-\s*", "", line).strip()
            for phrase in re.split(r"\s*/\s*", line):
                phrase = phrase.strip()
                if phrase:
                    phrases.append(phrase)
    return phrases[:15]


def extract_criteria(md: str) -> list[tuple[str, int]]:
    """Извлекает критерии и их баллы из секции **Критерии при проверке:**"""
    criteria = []
    block = re.search(
        r"\*\*Критерии при проверке[^*]*\*\*[^\n]*\n((?:[ \t]*-[^\n]+\n?)+)",
        md, re.IGNORECASE
    )
    if block:
        for line in block.group(1).splitlines():
            line = re.sub(r"^[ \t]*-\s*", "", line).strip()
            if line:
                # Убираем "(1 балл)" из конца
                score = 1
                score_m = re.search(r'\((\d+)\s*балл', line)
                if score_m:
                    score = int(score_m.group(1))
                    line = re.sub(r'\s*\(.*\)\s*$', '', line).strip()
                criteria.append((line, score))
    return criteria


MLX_API = os.getenv("MLX_API_URL", "http://localhost:11435")
BIBLE_PATH = ROOT / "docs" / "MASTER_REFERENCE.md"

def _load_bible_summary() -> str:
    """Загружает краткое содержание библии проекта."""
    try:
        text = BIBLE_PATH.read_text("utf-8")
        # Берём первые 2000 символов — структура проекта, основные принципы
        return text[:3000]
    except:
        return "ATRA Web IDE — корпоративная IDE с AI-агентами."


VICTORIA_SYSTEM_PROMPT = """Ты — Виктория, Team Lead корпорации ATRA.
Отвечай кратко: 2-4 предложения для простых вопросов, до 10 для сложных.
Не начинай каждый ответ с представления — говори по делу.
Не упоминай Singularity, Blackboard, и другие внутренние термины ATRA если они не относятся к вопросу.
Если тебя просят: покажи файлы, проверь код, найди ошибку — просто сделай это, не объясняя архитектуру ATRA."""


def _get_rag_context(query: str, limit: int = 3) -> str:
    """Получает релевантный контекст из RAG."""
    try:
        r = requests.post(
            f"{VICTORIA_URL}/api/omni-rag/search",
            json={"query": query, "limit": limit},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            results = data.get("results") or data.get("nodes") or []
            if results:
                ctx = "\n\n".join(
                    [r.get("content", r.get("text", ""))[:500] for r in results]
                )
                return f"Контекст из базы знаний ATRA:\n{ctx}"
    except:
        pass
    return ""


def _clean_response(text: str) -> str:
    """Чистит ответ: убирает <think> теги, запятую в начале, лишние пробелы."""
    if not text:
        return text
    # Убираем <think> блоки
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE).strip()
    # Убираем запятую/точку/двоеточие в начале (артефакт продолжения промпта)
    text = re.sub(r"^[,.:;]\s*", "", text).strip()
    # Схлопываем множественные пробелы
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def ask_victoria(query: str, max_wait: int = 900) -> Optional[str]:
    """Отправляет запрос к MLX с RAG-контекстом и системным промптом ATRA."""
    rag_ctx = _get_rag_context(query)
    bible_summary = _load_bible_summary()

    system = VICTORIA_SYSTEM_PROMPT
    if bible_summary:
        system += f"\n\nДокументация проекта (первые 3000 символов библии):\n{bible_summary}"
    if rag_ctx:
        system += f"\n\n{rag_ctx}"

    url = f"{MLX_API}/api/chat"
    payload = {
        "model": "victoria-wisdom-v3.5",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ],
        "max_tokens": 2048,
        "temperature": 0.3,
        "stream": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=max_wait)
        if r.status_code == 200:
            data = r.json()
            content = (data.get("message") or {}).get("content", "")
            if content:
                return _clean_response(content)
            return json.dumps(data, ensure_ascii=False, default=str)
        else:
            print(f"  [WARN] MLX returned {r.status_code}")
            if r.text:
                print(f"         {r.text[:200]}")
            return None
    except requests.Timeout:
        print(f"  [WARN] MLX timeout after {max_wait}s")
        return None
    except Exception as e:
        print(f"  [WARN] MLX request failed: {e}")
        return None


def _poll_task(task_id: str, max_wait: int) -> Optional[str]:
    """Poll task status until completion or timeout."""
    import time as _time
    start = _time.time()
    while _time.time() - start < max_wait:
        try:
            r = requests.get(f"{VICTORIA_URL}/run/status/{task_id}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                st = (data.get("status") or "").lower()
                if st in ("completed", "success"):
                    return data.get("output") or data.get("result") or "completed"
                elif st in ("failed", "error", "cancelled"):
                    return f"❌ Task failed: {data.get('error', 'unknown')}"
            elif r.status_code == 404:
                pass  # ещё не готова
        except Exception:
            pass
        _time.sleep(POLL_INTERVAL)
    return f"⏱️ Polling timeout after {max_wait}s, task {task_id}"


def evaluate_response(response: str, key_phrases: list[str], criteria: list[tuple[str, int]]) -> dict:
    if not response:
        return {"phrase_match": 0.0, "criteria_met": 0.0, "criteria_detail": [], "response_length": 0}
    
    response_lower = response.lower()
    total_phrases = len(key_phrases)
    found_phrases = sum(1 for p in key_phrases if p.lower() in response_lower)
    phrase_ratio = found_phrases / total_phrases if total_phrases else 1.0
    
    criteria_detail = []
    criteria_met = 0
    criteria_total = 0
    for criterion_text, max_score in criteria:
        criteria_total += max_score
        # Check if the response demonstrates this criterion
        # Simple heuristic: key terms from criterion appear in response
        terms = re.findall(r'\w+', criterion_text.lower())
        meaningful_terms = [t for t in terms if len(t) > 3]
        matches = sum(1 for t in meaningful_terms if t in response_lower)
        # If at least 30% of meaningful terms match, consider criterion met
        if meaningful_terms and matches / len(meaningful_terms) >= 0.3:
            criteria_met += max_score
            criteria_detail.append({"criterion": criterion_text, "score": max_score, "met": True})
        else:
            criteria_detail.append({"criterion": criterion_text, "score": 0, "met": False})
    
    criteria_ratio = criteria_met / criteria_total if criteria_total else 1.0
    
    return {
        "phrase_match": round(phrase_ratio, 2),
        "criteria_met": round(criteria_ratio, 2),
        "criteria_detail": criteria_detail,
        "response_length": len(response),
        "found_phrases": found_phrases,
        "total_phrases": total_phrases,
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Полный прогон куратора")
    ap.add_argument("--limit", type=int, default=0, help="Максимум эталонов для проверки")
    ap.add_argument("--quick", action="store_true", help="Быстрый режим (60 сек на запрос)")
    ap.add_argument("--no-send", action="store_true", help="Не слать запросы (только превью)")
    args = ap.parse_args()

    timeout = 180 if args.quick else VICTORIA_TIMEOUT

    # Load all standards
    all_standards = sorted([
        f.stem for f in STANDARDS_DIR.glob("*.md")
        if f.stem != "README"
    ])

    if args.limit:
        all_standards = all_standards[:args.limit]

    results = []
    total_phrase_score = 0.0
    total_criteria_score = 0.0
    evaluated_count = 0

    print(f"Загрузка {len(all_standards)} эталонов из {STANDARDS_DIR}")
    print()

    for std_name in all_standards:
        print(f"[{all_standards.index(std_name)+1}/{len(all_standards)}] {std_name}...")

        content = load_standard_content(std_name)
        if not content:
            print(f"  [SKIP] файл не найден")
            continue

        key_phrases = extract_key_phrases(content)
        criteria = extract_criteria(content)

        # Determine test query
        query = STANDARD_QUERIES.get(std_name, std_name.replace("_", " "))

        response = None
        if not args.no_send:
            print(f"  Query: {query[:60]}...")
            response = ask_victoria(query, timeout)
            if response:
                response_preview = response[:200].replace("\n", " ")
                print(f"  Response ({len(response)} chars): {response_preview}...")
            else:
                print(f"  [WARN] No response from Victoria")
        else:
            print(f"  (dry-run, query would be: {query[:60]}...)")

        evaluation = evaluate_response(response or "", key_phrases, criteria)
        result = {
            "standard": std_name,
            "query": query,
            "has_response": response is not None,
            "response_preview": (response[:500] if response else ""),
            "response_length": evaluation["response_length"],
            "key_phrases": key_phrases,
            "phrase_match": evaluation["phrase_match"],
        "total_phrases": evaluation.get("total_phrases", 0),
        "found_phrases": evaluation.get("found_phrases", 0),
            "criteria": criteria,
            "criteria_met": evaluation["criteria_met"],
            "criteria_detail": evaluation["criteria_detail"],
        }

        if response:
            evaluated_count += 1
            total_phrase_score += evaluation["phrase_match"]
            total_criteria_score += evaluation["criteria_met"]

        results.append(result)

        # Print evaluation summary
        print(f"  Фразы: {evaluation.get('found_phrases', 0)}/{evaluation.get('total_phrases', 0)} ({evaluation.get('phrase_match', 0):.0%})")
        print(f"  Критерии: {evaluation.get('criteria_met', 0):.0%}")
        print()

    # Summary
    print("=" * 60)
    print("ИТОГОВЫЙ ОТЧЁТ КУРАТОРА")
    print("=" * 60)
    print()

    if evaluated_count:
        avg_phrase = total_phrase_score / evaluated_count
        avg_criteria = total_criteria_score / evaluated_count
        print(f"Всего эталонов: {len(results)}")
        print(f"Получено ответов: {evaluated_count}/{len(results)}")
        print(f"Средний score совпадения фраз: {avg_phrase:.1%}")
        print(f"Средний score по критериям: {avg_criteria:.1%}")
        print()
        print("Поэталонно:")
        for r in results:
            if not r["has_response"]:
                print(f"  {r['standard']}: [NO RESPONSE]")
            else:
                print(f"  {r['standard']}: фразы {r['phrase_match']:.0%} | критерии {r['criteria_met']:.0%} | {r['response_length']} символов")
    else:
        print("Нет ответов для оценки.")

    # Save report
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    report_path = REPORTS_DIR / f"curator_full_{timestamp}.json"
    preview_path = REPORTS_DIR / f"curator_full_{timestamp}.md"

    report_data = {
        "timestamp": timestamp,
        "victoria_url": VICTORIA_URL,
        "total_standards": len(results),
        "evaluated": evaluated_count,
        "avg_phrase_score": round(total_phrase_score / evaluated_count, 3) if evaluated_count else 0,
        "avg_criteria_score": round(total_criteria_score / evaluated_count, 3) if evaluated_count else 0,
        "results": results,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nСохранено: {report_path}")

    # Generate markdown preview
    md_lines = [
        f"# Отчёт куратора ({timestamp})",
        "",
        f"- **Victoria:** {VICTORIA_URL}",
        f"- **Всего эталонов:** {len(results)}",
        f"- **Получено ответов:** {evaluated_count}/{len(results)}",
    ]
    if evaluated_count:
        md_lines += [
            f"- **Среднее совпадение фраз:** {avg_phrase:.1%}",
            f"- **Среднее по критериям:** {avg_criteria:.1%}",
        ]
    md_lines += ["", "---", ""]

    for r in results:
        md_lines.append(f"## {r['standard']}")
        md_lines.append("")
        md_lines.append(f"- **Запрос:** {r['query']}")
        if r["has_response"]:
            md_lines.append(f"- **Длина ответа:** {r['response_length']} символов")
            md_lines.append(f"- **Совпадение фраз:** {r['found_phrases']}/{r['total_phrases']} ({r['phrase_match']:.0%})")
            md_lines.append(f"- **Критерии:** {r['criteria_met']:.0%}")
            for cd in r.get("criteria_detail", []):
                icon = "✅" if cd["met"] else "❌"
                md_lines.append(f"  - {icon} {cd['criterion']} ({cd['score']} баллов)")
            md_lines.append("")
            md_lines.append("### Ответ Victoria")
            md_lines.append("")
            md_lines.append(f"```\n{r.get('response_preview', '')[:1000]}\n```")
        else:
            md_lines.append(f"- **❌ Нет ответа**")
        md_lines.append("")

    with open(preview_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"MD превью: {preview_path}")


if __name__ == "__main__":
    main()
