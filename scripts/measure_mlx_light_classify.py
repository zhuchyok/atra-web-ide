#!/usr/bin/env python3
"""
Замер лёгкой MLX-классификации в Victoria (гипотеза 1, docs/MLX_STRATEGY_LIGHT_AND_VITALITY.md).

Использование:
  1. Включите в Victoria: VICTORIA_MLX_LIGHT_CLASSIFY=true (docker-compose или .env), перезапустите victoria-agent.
  2. Запустите замер:
     VICTORIA_URL=http://localhost:8010 python3 scripts/measure_mlx_light_classify.py
  3. Посмотрите вывод: число запросов, время на запрос, итог.
  4. По логам Victoria посчитайте срабатывания:
     docker logs victoria-agent 2>&1 | grep MLX_LIGHT_CLASSIFY

  Разбор логов (если передать их на stdin):
     docker logs victoria-agent 2>&1 | tail -500 | python3 scripts/measure_mlx_light_classify.py --parse-logs
"""
import argparse
import json
import os
import re
import sys
import time

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")

# Запросы 5–25 слов, без явных ключевых слов — обычно дают category=general
TEST_PROMPTS = [
    "Как лучше организовать код в этом проекте?",
    "Можешь подсказать что проверить перед деплоем?",
    "Есть ли у нас тесты на этот модуль?",
    "Что обычно делают в таких случаях в индустрии?",
    "С чего начать рефакторинг этого участка?",
    "Какие риски если мы поменяем эту настройку?",
    "Подходит ли такой подход для нашей команды?",
    "Что посмотреть в первую очередь в логах?",
    "Как часто стоит запускать эти проверки?",
    "Есть ли альтернатива этому решению?",
    "На что обратить внимание при код-ревью?",
    "Какой порядок действий ты рекомендуешь?",
    "Что может пойти не так при обновлении?",
    "Какие документы стоит обновить после изменений?",
    "Как связаны между собой эти компоненты?",
]


def run_one(url: str, goal: str, timeout: int = 90):
    payload = {"goal": goal, "max_steps": 50, "project_context": "atra-web-ide"}
    t0 = time.perf_counter()
    try:
        r = requests.post(f"{url}/run", json=payload, params={"async_mode": "false"}, timeout=timeout)
        elapsed = time.perf_counter() - t0
        if r.status_code == 200:
            return r.json(), elapsed
        return {"status": "error", "error": r.status_code}, elapsed
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {"status": "error", "error": str(e)}, elapsed


def parse_log_line(line: str):
    # [MLX_LIGHT_CLASSIFY] general -> coding goal_len=7 duration_ms=1234
    m = re.search(r"\[MLX_LIGHT_CLASSIFY\] general -> (\w+) goal_len=(\d+) duration_ms=([\d.]+)", line)
    if m:
        return {"new_category": m.group(1), "goal_len": int(m.group(2)), "duration_ms": float(m.group(3))}
    m = re.search(r"\[MLX_LIGHT_CLASSIFY\] no_change_or_error duration_ms=([\d.]+)", line)
    if m:
        return {"new_category": None, "duration_ms": float(m.group(1))}
    return None


def main():
    ap = argparse.ArgumentParser(description="Замер MLX light classify: запросы к Victoria и/или разбор логов")
    ap.add_argument("--parse-logs", action="store_true", help="Читать stdin, парсить строки [MLX_LIGHT_CLASSIFY], вывести сводку")
    ap.add_argument("--url", default=VICTORIA_URL, help="URL Victoria (default: VICTORIA_URL или http://localhost:8010)")
    ap.add_argument("--count", type=int, default=0, help="Сколько промптов отправить (0 = все)")
    args = ap.parse_args()

    if args.parse_logs:
        # Режим разбора логов
        lines = sys.stdin.readlines()
        records = []
        for line in lines:
            r = parse_log_line(line)
            if r:
                records.append(r)
        if not records:
            print("Строк [MLX_LIGHT_CLASSIFY] не найдено.")
            return
        changed = [r for r in records if r.get("new_category")]
        durations = [r["duration_ms"] for r in records if "duration_ms" in r]
        print("=== Замер MLX_LIGHT_CLASSIFY (из логов) ===")
        print(f"Всего вызовов: {len(records)}")
        print(f"Смена категории (general -> X): {len(changed)}")
        if changed:
            from collections import Counter
            cats = Counter(r["new_category"] for r in changed)
            for c, n in cats.most_common():
                print(f"  -> {c}: {n}")
        if durations:
            print(f"duration_ms: min={min(durations):.0f} max={max(durations):.0f} avg={sum(durations)/len(durations):.0f}")
        return

    # Режим отправки запросов
    if args.count > 0:
        prompts = TEST_PROMPTS[: args.count]
    else:
        prompts = TEST_PROMPTS

    url = args.url.rstrip("/")
    try:
        r = requests.get(f"{url}/health", timeout=5)
        if r.status_code != 200:
            print(f"Victoria не отвечает: {url}/health -> {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Victoria недоступна: {url} — {e}")
        sys.exit(1)

    print("=== Замер MLX light classify ===")
    print(f"Victoria: {url}")
    print(f"Запросов: {len(prompts)} (убедитесь, что VICTORIA_MLX_LIGHT_CLASSIFY=true)")
    print()

    total_sec = 0.0
    ok = 0
    for i, goal in enumerate(prompts, 1):
        resp, elapsed = run_one(url, goal)
        total_sec += elapsed
        # Victoria TaskResponse: status + output; считать успехом и ответ с полем output при 200
        status = resp.get("status", "?")
        has_output = "output" in resp
        if status == "success" or (status != "error" and has_output):
            ok += 1
        print(f"[{i}/{len(prompts)}] {elapsed:.1f}s — {goal[:50]}...")
    print()
    print(f"Итого: {ok}/{len(prompts)} успешных, суммарно {total_sec:.1f} с, в среднем {total_sec / len(prompts):.1f} с на запрос")
    print()
    print("Срабатывания классификации в логах Victoria:")
    print("  docker logs victoria-agent 2>&1 | grep MLX_LIGHT_CLASSIFY")
    print("Разбор логов:")
    print("  docker logs victoria-agent 2>&1 | tail -500 | python3 scripts/measure_mlx_light_classify.py --parse-logs")


if __name__ == "__main__":
    main()
