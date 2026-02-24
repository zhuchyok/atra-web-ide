#!/usr/bin/env python3
"""
Тест создания одностраничника через Victoria с принудительным использованием ReAct
"""

import requests
import json
import time
from pathlib import Path

url = "http://localhost:8010/run"

# Задача с явным указанием действий, чтобы Victoria использовала ReAct
goal = """создай одностраничный HTML сайт webpage.html про пластиковые окна.
Требования:
1. Используй инструмент create_file для создания файла
2. Современный дизайн с градиентами
3. SEO оптимизация (meta теги, заголовки)
4. Красивые CSS стили
5. Адаптивная верстка для мобильных
6. Секции: заголовок, преимущества, контакты"""

print("🚀 ТЕСТ СОЗДАНИЯ ОДНОСТРАНИЧНИКА (ReAct)")
print("=" * 80)
print(f"📝 Задача: {goal[:100]}...")
print("=" * 80)
print()

start_time = time.time()

try:
    response = requests.post(
        url,
        json={"goal": goal, "max_steps": 500},
        timeout=300
    )

    duration = time.time() - start_time

    if response.status_code == 200:
        result = response.json()
        status = result.get("status", "N/A")
        output = result.get("output", "")
        knowledge = result.get("knowledge", {})

        print(f"✅ Статус: {status}")
        print(f"⏱️ Время выполнения: {duration:.2f}с")
        print()

        print("📊 Ответ Victoria:")
        print("=" * 80)
        print(output)
        print("=" * 80)
        print()

        if knowledge:
            method = knowledge.get('method', 'N/A')
            print(f"🎯 Метод: {method}")
            print(f"📁 Проект: {knowledge.get('project_context', 'N/A')}")

            if method != "react":
                print(f"⚠️ ВНИМАНИЕ: Использован метод '{method}' вместо 'react'")
                print("   ReAct метод лучше подходит для задач с созданием файлов")
            else:
                print("✅ Использован ReAct метод - должен создать файл")
            print()

        # Ищем созданный файл
        print("🔍 Поиск созданного файла...")
        print("-" * 80)

        search_paths = [
            Path("webpage.html"),
            Path("index.html"),
            Path("/tmp/atra-workspace/webpage.html"),
            Path("/tmp/atra-workspace/index.html"),
        ]

        # Также проверяем текущую директорию
        for html_file in Path(".").glob("*.html"):
            if html_file.is_file():
                search_paths.append(html_file)

        found = False
        for path in search_paths:
            if path.exists() and path.is_file():
                print(f"✅ НАЙДЕН ФАЙЛ: {path.resolve()}")
                print(f"   Размер: {path.stat().st_size} байт")

                try:
                    content = path.read_text(encoding='utf-8')
                    print(f"   Длина: {len(content)} символов")
                    print()
                    print("📄 ПРЕВЬЮ ФАЙЛА (первые 1500 символов):")
                    print("-" * 80)
                    print(content[:1500])
                    if len(content) > 1500:
                        print(f"\n... (еще {len(content) - 1500} символов)")
                    print("-" * 80)

                    # Сохраняем копию
                    logs_dir = Path("logs")
                    logs_dir.mkdir(exist_ok=True)
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    copy_path = logs_dir / f"webpage_{timestamp}.html"
                    copy_path.write_text(content, encoding='utf-8')
                    print(f"\n💾 Копия сохранена: {copy_path}")

                    # Проверяем содержимое
                    if "<html" in content.lower() or "<!doctype" in content.lower():
                        print("✅ Файл содержит валидный HTML")
                    if "пластиков" in content.lower() or "окн" in content.lower():
                        print("✅ Файл содержит контент про пластиковые окна")
                    if "css" in content.lower() or "<style" in content.lower():
                        print("✅ Файл содержит CSS стили")

                    found = True
                    break
                except Exception as e:
                    print(f"   ⚠️ Ошибка чтения: {e}")

        if not found:
            print("⚠️ Файл не найден в локальной файловой системе")
            print("   Возможные причины:")
            print("   1. Файл создан в Docker контейнере")
            print("   2. Файл создан в другой директории")
            print("   3. Задача не была выполнена полностью")
            print()
            print("   Проверьте Docker:")
            print("   docker exec victoria-agent find /app -name '*.html' -type f -mmin -2")

    else:
        print(f"❌ Ошибка HTTP {response.status_code}")
        print(response.text[:500])

except requests.exceptions.Timeout:
    print("⏱️ Таймаут - Victoria не ответила за 5 минут")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("🏁 ТЕСТ ЗАВЕРШЕН")
print("=" * 80)
