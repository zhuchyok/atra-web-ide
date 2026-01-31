#!/usr/bin/env python3
"""
Полный тест цепочки: твоя задача → Victoria → Veronica → модель → ответ → обратно.
Выводит все шаги: кому передаётся, как решается, через какую модель, ответ Veronica.

Запуск:
  cd knowledge_os && python3 scripts/test_full_chain_veronica.py
  VICTORIA_URL=... VERONICA_URL=... python3 scripts/test_full_chain_veronica.py
  GOAL="Привет" python3 scripts/test_full_chain_veronica.py   # быстрый тест без Veronica
  DEMO=1 python3 scripts/test_full_chain_veronica.py          # только пример вывода шагов (без запросов)
  POLL_MINUTES=8 python3 scripts/test_full_chain_veronica.py   # ждать до 8 мин (для поиска)
"""

import os
import sys
import json

try:
    import requests
except ImportError:
    print("Установите: pip install requests")
    sys.exit(2)

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
VERONICA_URL = os.getenv("VERONICA_URL", "http://localhost:8011")
# Переопредели задачу: GOAL="Привет" — быстрый тест без Veronica; иначе — задача для Veronica (поиск)
GOAL = os.getenv("GOAL", "Найди в интернете кратко: что такое LLM (одним абзацем).")
POLL_MINUTES = int(os.getenv("POLL_MINUTES", "6"))  # макс. минут ожидания (исследование может занять 5+ мин)


def sep():
    print("-" * 60)


def step(num, text):
    print(f"\n  [{num}] {text}")


def run_demo():
    """Вывести пример всех шагов без запросов к серверам."""
    print("\n" + "=" * 60)
    print("  ПРИМЕР ВЫВОДА ПОЛНОГО ТЕСТА (DEMO, без запросов)")
    print("=" * 60)
    print(f"\n  Твоя задача: «{GOAL}»")
    step(1, f"Запрос отправлен → Victoria ({VICTORIA_URL}/run)")
    sep()
    step(2, "Victoria приняла решение:")
    print("      method      = delegation")
    print("      delegated_to= Veronica")
    print("      task_id     = <uuid>")
    sep()
    step(3, "Цепочка выполнения:")
    print("      Ты → Victoria (:8010) → Veronica (:8011) → выполнение → обратно в Victoria → тебе")
    sep()
    step(4, "Шаги координации (кто что делал):")
    print("      • Задача отправлена Veronica")
    print("      • Задача выполнена Veronica")
    sep()
    step(5, "Через какую модель/способ:")
    print("      Victoria (общий метод): delegation")
    print("      Veronica (метод/модель на её стороне): react / simple")
    sep()
    step(6, "Ответ Вероники (итог, переданный через Victoria):")
    print("      LLM (Large Language Model) — большая языковая модель, нейросеть для генерации текста.")
    sep()
    step(7, "Обратно по цепочке:")
    print("      Veronica → Victoria → тебе (status=success)")
    sep()
    print("\n  Конец демо. Запусти без DEMO=1 для реального теста.")
    return 0


def run():
    if os.getenv("DEMO", "").strip() == "1":
        return run_demo()

    print("\n" + "=" * 60)
    print("  ПОЛНЫЙ ТЕСТ ЦЕПОЧКИ: Твоя задача → Victoria → Veronica → ответ")
    print("=" * 60)
    print(f"\n  Твоя задача: «{GOAL}»")

    # --- Шаг 1: Запрос к Victoria (async: 202 + опрос статуса, чтобы не рвать по таймауту) ---
    step(1, f"Запрос отправлен → Victoria ({VICTORIA_URL}/run)")
    sep()
    try:
        r = requests.post(
            f"{VICTORIA_URL}/run",
            json={"goal": GOAL, "project_context": "atra-web-ide", "chat_history": []},
            params={"async_mode": "true"},
            timeout=15,
        )
    except Exception as e:
        print(f"  Ошибка запроса к Victoria: {e}")
        return 1
    print(f"  HTTP {r.status_code}")

    if r.status_code == 202:
        task_id = r.json().get("task_id")
        status_url = f"{VICTORIA_URL}/run/status/{task_id}"
        print(f"  Задача принята, task_id={task_id}. Ожидание выполнения (опрос каждые 5 с, макс. {POLL_MINUTES} мин)...")
        import time
        for _ in range(POLL_MINUTES * 12):
            time.sleep(5)
            sr = requests.get(status_url, timeout=10)
            if sr.status_code != 200:
                print(f"  Ошибка статуса: HTTP {sr.status_code}")
                return 1
            rec = sr.json()
            st = rec.get("status")
            if st == "completed":
                data = {"status": rec.get("status"), "output": rec.get("output"), "knowledge": rec.get("knowledge")}
                break
            if st == "failed":
                print(f"  Задача завершилась с ошибкой: {rec.get('error', 'unknown')}")
                return 1
            print(f"  ... статус: {st}")
        else:
            print(f"  Таймаут ожидания ({POLL_MINUTES} мин)")
            return 1
    elif r.status_code == 200:
        data = r.json()
    else:
        print(f"  Тело: {r.text[:500]}")
        return 1
    status = data.get("status", "")
    output = (data.get("output") or "").strip()
    knowledge = data.get("knowledge") or {}
    method = knowledge.get("method", "?")
    delegated_to = knowledge.get("delegated_to")
    task_id = knowledge.get("task_id")
    metadata = knowledge.get("metadata") or {}
    coordination_steps = metadata.get("coordination_steps") or []
    veronica_method = metadata.get("method", "?")  # метод/модель на стороне Veronica

    # --- Шаг 2: Решение Victoria ---
    step(2, "Victoria приняла решение:")
    print(f"      method      = {method}")
    print(f"      delegated_to= {delegated_to}")
    print(f"      task_id     = {task_id}")
    sep()

    # --- Шаг 3: Цепочка (кому передано) ---
    step(3, "Цепочка выполнения:")
    if delegated_to:
        print(f"      Ты → Victoria (:8010) → {delegated_to} (:8011) → выполнение → обратно в Victoria → тебе")
    else:
        print(f"      Ты → Victoria (:8010) → выполнение самой Victoria (без делегирования) → тебе")
    sep()

    # --- Шаг 4: Шаги координации ---
    if coordination_steps:
        step(4, "Шаги координации (кто что делал):")
        for s in coordination_steps:
            print(f"      • {s}")
    else:
        step(4, "Шаги координации: (не переданы в ответе)")
    sep()

    # --- Шаг 5: Через какую модель/способ ---
    step(5, "Через какую модель/способ:")
    print(f"      Victoria (общий метод): {method}")
    if delegated_to:
        print(f"      {delegated_to} (метод/модель на её стороне): {veronica_method}")
    sep()

    # --- Шаг 6: Ответ Veronica (из общего output) ---
    step(6, "Ответ Вероники (итог, переданный через Victoria):")
    if delegated_to and "Результат:" in output:
        veronica_part = output.split("Результат:", 1)[-1].strip()
        print(veronica_part[:2000] if len(veronica_part) > 2000 else veronica_part)
    else:
        print(output[:2000] if len(output) > 2000 else output)
    sep()

    # --- Шаг 7: Обратно ---
    step(7, "Обратно по цепочке:")
    print(f"      {delegated_to or 'Victoria'} → Victoria → тебе (status={status})")
    sep()

    # --- Дополнительно: прямой запрос к Veronica (чтобы увидеть её ответ и модель) ---
    print("\n  [Дополнительно] Прямой запрос к Veronica (та же задача) — ответ и модель:")
    sep()
    try:
        rv = requests.post(
            f"{VERONICA_URL}/run",
            json={"goal": GOAL},
            params={"async_mode": "false"},
            timeout=90,
        )
        if rv.status_code == 200:
            vdata = rv.json()
            v_out = (vdata.get("output") or "").strip()
            v_knowledge = vdata.get("knowledge") or {}
            v_method = v_knowledge.get("method", "?")
            print(f"      Veronica method (прямой ответ): {v_method}")
            print(f"      Veronica output (первые 800 символов):")
            print("      " + (v_out[:800].replace("\n", "\n      ") if v_out else "(пусто)"))
        else:
            print(f"      Veronica HTTP {rv.status_code}: {rv.text[:300]}")
    except Exception as e:
        print(f"      Ошибка прямого запроса к Veronica: {e}")
    sep()

    print("\n  Конец теста.")
    return 0 if status == "success" else 1


if __name__ == "__main__":
    sys.exit(run())
