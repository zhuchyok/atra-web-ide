#!/usr/bin/env python3
"""Тест создания веб-страницы через Victoria"""
import requests
import json
import time

url = "http://localhost:8010/run"
goal = "создай HTML файл webpage.html с красивой веб-страницей: заголовок 'Привет от Victoria', параграф 'Это страница создана Victoria Enhanced', добавь CSS стили для красивого дизайна"

print("🚀 Отправляю задачу Victoria...")
print(f"📝 Задача: {goal}")
print()

try:
    response = requests.post(
        url,
        json={"goal": goal, "max_steps": 500},
        timeout=120
    )

    if response.status_code == 200:
        result = response.json()
        print("✅ Статус:", result.get("status", "N/A"))
        print()
        print("📊 Ответ Victoria:")
        print("=" * 60)
        print(result.get("output", "")[:1000])
        print("=" * 60)

        knowledge = result.get("knowledge", {})
        if knowledge:
            print(f"\n🎯 Метод: {knowledge.get('method', 'N/A')}")
            print(f"📁 Проект: {knowledge.get('project_context', 'N/A')}")
    else:
        print(f"❌ Ошибка HTTP {response.status_code}")
        print(response.text[:500])

except requests.exceptions.Timeout:
    print("⏱️ Таймаут - Victoria не ответила за 2 минуты")
except Exception as e:
    print(f"❌ Ошибка: {e}")
