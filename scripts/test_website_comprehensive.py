#!/usr/bin/env python3
"""
Комплексный тест создания одностраничника с применением лучших практик
- Увеличенный timeout
- Детальное логирование
- Проверка всех этапов
"""

import requests
import json
import time
from pathlib import Path

url = "http://localhost:8010/run"

# Задача с четкими инструкциями
goal = """создай одностраничный HTML сайт webpage.html про пластиковые окна.

ТРЕБОВАНИЯ:
1. Используй инструмент create_file для создания файла
2. Современный дизайн с градиентами и анимациями
3. SEO оптимизация (meta теги, заголовки H1-H3)
4. Красивые CSS стили (flexbox, grid)
5. Адаптивная верстка для мобильных устройств
6. Секции: заголовок, преимущества, контакты, форма обратной связи
7. Используй семантические HTML5 теги
8. Добавь favicon и Open Graph мета-теги"""

print("🚀 КОМПЛЕКСНЫЙ ТЕСТ СОЗДАНИЯ ОДНОСТРАНИЧНИКА")
print("=" * 80)
print(f"📝 Задача: {goal[:150]}...")
print("=" * 80)
print()

start_time = time.time()

try:
    print("⏳ Отправляю запрос (timeout: 300s)...")
    response = requests.post(
        url,
        json={"goal": goal, "max_steps": 500},
        timeout=300  # Увеличили timeout
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
            metadata = knowledge.get('metadata', {})
            if metadata:
                print(f"📋 Метаданные: {json.dumps(metadata, indent=2, ensure_ascii=False)}")
            print()

        # Расширенный поиск файла
        print("🔍 Расширенный поиск созданного файла...")
        print("-" * 80)

        search_paths = [
            Path("webpage.html"),
            Path("index.html"),
            Path("/tmp/atra-workspace/webpage.html"),
            Path("/tmp/atra-workspace/index.html"),
            Path("./webpage.html"),
            Path("./index.html"),
        ]

        # Ищем все HTML файлы в текущей директории
        for html_file in Path(".").glob("*.html"):
            if html_file.is_file() and html_file.name not in ["index.html"]:  # Исключаем frontend/index.html
                search_paths.append(html_file)

        found = False
        for path in search_paths:
            if path.exists() and path.is_file():
                print(f"✅ НАЙДЕН ФАЙЛ: {path.resolve()}")
                print(f"   Размер: {path.stat().st_size} байт")
                print(f"   Модифицирован: {time.ctime(path.stat().st_mtime)}")

                try:
                    content = path.read_text(encoding='utf-8')
                    print(f"   Длина: {len(content)} символов")
                    print()

                    # Проверки содержимого
                    checks = {
                        "HTML структура": "<html" in content.lower() or "<!doctype" in content.lower(),
                        "Пластиковые окна": "пластиков" in content.lower() or "окн" in content.lower(),
                        "CSS стили": "css" in content.lower() or "<style" in content.lower() or "style=" in content.lower(),
                        "SEO мета-теги": "<meta" in content.lower(),
                        "Адаптивность": "viewport" in content.lower() or "media" in content.lower(),
                        "Семантические теги": any(tag in content.lower() for tag in ["<header", "<section", "<footer", "<nav", "<article"]),
                    }

                    print("📋 ПРОВЕРКА СОДЕРЖИМОГО:")
                    for check_name, passed in checks.items():
                        status = "✅" if passed else "❌"
                        print(f"   {status} {check_name}")
                    print()

                    print("📄 ПРЕВЬЮ ФАЙЛА (первые 2000 символов):")
                    print("-" * 80)
                    print(content[:2000])
                    if len(content) > 2000:
                        print(f"\n... (еще {len(content) - 2000} символов)")
                    print("-" * 80)

                    # Сохраняем копию
                    logs_dir = Path("logs")
                    logs_dir.mkdir(exist_ok=True)
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    copy_path = logs_dir / f"webpage_{timestamp}.html"
                    copy_path.write_text(content, encoding='utf-8')
                    print(f"\n💾 Копия сохранена: {copy_path}")

                    found = True
                    break
                except Exception as e:
                    print(f"   ⚠️ Ошибка чтения: {e}")

        if not found:
            print("⚠️ Файл не найден в локальной файловой системе")
            print()
            print("🔍 Проверка Docker контейнера...")
            import subprocess
            try:
                docker_result = subprocess.run(
                    ["docker", "exec", "victoria-agent", "find", "/app", "-name", "*.html", "-type", "f", "-mmin", "-5"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if docker_result.returncode == 0 and docker_result.stdout.strip():
                    print("✅ Найдены файлы в контейнере:")
                    for line in docker_result.stdout.strip().split('\n'):
                        if line and 'venv' not in line and 'site-packages' not in line:
                            print(f"   {line}")
                            # Пробуем скопировать
                            try:
                                copy_result = subprocess.run(
                                    ["docker", "cp", f"victoria-agent:{line}", "."],
                                    capture_output=True,
                                    text=True,
                                    timeout=10
                                )
                                if copy_result.returncode == 0:
                                    filename = Path(line).name
                                    print(f"   ✅ Скопирован как: {filename}")
                            except:
                                pass
                else:
                    print("   ⚠️ Файлы не найдены в контейнере")
            except Exception as e:
                print(f"   ⚠️ Ошибка проверки контейнера: {e}")

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
