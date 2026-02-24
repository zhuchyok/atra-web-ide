#!/usr/bin/env python3
"""Тест делегирования задач через Victoria"""
import requests
import json

url = "http://localhost:8010/run"

# Тест 1: Задача для Veronica (создание файла)
print("🧪 Тест 1: Задача для Veronica (создание файла)")
goal1 = "создай файл test_delegation.txt с текстом это тест делегирования"
print(f"📝 Задача: {goal1}")
print()

try:
    response = requests.post(
        url,
        json={"goal": goal1, "max_steps": 500},
        timeout=60
    )

    if response.status_code == 200:
        result = response.json()
        print("✅ Статус:", result.get("status", "N/A"))
        print("📊 Ответ:")
        print(result.get("output", "")[:400])
        print()
        knowledge = result.get("knowledge", {})
        if knowledge:
            print(f"🎯 Метод: {knowledge.get('method', 'N/A')}")
            if "delegated_to" in knowledge:
                print(f"👤 Делегировано: {knowledge.get('delegated_to')}")
        print()
    else:
        print(f"❌ Ошибка HTTP {response.status_code}")
        print(response.text[:500])
except Exception as e:
    print(f"❌ Ошибка: {e}")

print("=" * 60)
print()

# Тест 2: Задача для Victoria (планирование)
print("🧪 Тест 2: Задача для Victoria (планирование)")
goal2 = "спланируй архитектуру новой системы"
print(f"📝 Задача: {goal2}")
print()

try:
    response = requests.post(
        url,
        json={"goal": goal2, "max_steps": 500},
        timeout=60
    )

    if response.status_code == 200:
        result = response.json()
        print("✅ Статус:", result.get("status", "N/A"))
        print("📊 Ответ:")
        print(result.get("output", "")[:400])
        print()
        knowledge = result.get("knowledge", {})
        if knowledge:
            print(f"🎯 Метод: {knowledge.get('method', 'N/A')}")
            if "delegated_to" in knowledge:
                print(f"👤 Делегировано: {knowledge.get('delegated_to')}")
        print()
    else:
        print(f"❌ Ошибка HTTP {response.status_code}")
except Exception as e:
    print(f"❌ Ошибка: {e}")
