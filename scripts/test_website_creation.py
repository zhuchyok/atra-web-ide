#!/usr/bin/env python3
"""
Тест создания одностраничника через Victoria
Проверяет создание HTML файла и показывает результат
"""

import requests
import json
import time
import os
from pathlib import Path

url = "http://localhost:8010/run"
goal = "создай одностраничный HTML сайт webpage.html про пластиковые окна: современный дизайн, SEO оптимизация, красивые стили CSS, адаптивная верстка"

print("🚀 ЗАПУСК ТЕСТА СОЗДАНИЯ ОДНОСТРАНИЧНИКА")
print("=" * 80)
print(f"📝 Задача: {goal}")
print("=" * 80)
print()

start_time = time.time()

try:
    response = requests.post(
        url,
        json={"goal": goal, "max_steps": 500},
        timeout=180
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
        print(output[:2000])
        if len(output) > 2000:
            print(f"\n... (еще {len(output) - 2000} символов)")
        print("=" * 80)
        print()
        
        if knowledge:
            print("🎯 Метод:", knowledge.get('method', 'N/A'))
            print("📁 Проект:", knowledge.get('project_context', 'N/A'))
            print()
        
        # Ищем созданный файл
        print("🔍 Поиск созданного файла...")
        print("-" * 80)
        
        # Проверяем возможные места
        possible_locations = [
            "webpage.html",
            "index.html",
            "/tmp/atra-workspace/webpage.html",
            "/tmp/atra-workspace/index.html",
            "./webpage.html",
            "./index.html"
        ]
        
        found_files = []
        for location in possible_locations:
            path = Path(location)
            if path.exists() and path.is_file():
                found_files.append(str(path.resolve()))
                print(f"✅ Найден: {path.resolve()}")
                print(f"   Размер: {path.stat().st_size} байт")
                
                # Показываем содержимое
                try:
                    content = path.read_text(encoding='utf-8')
                    print(f"   Длина: {len(content)} символов")
                    print()
                    print("📄 СОДЕРЖИМОЕ ФАЙЛА:")
                    print("-" * 80)
                    print(content[:1000])
                    if len(content) > 1000:
                        print(f"\n... (еще {len(content) - 1000} символов)")
                    print("-" * 80)
                    
                    # Сохраняем копию в logs
                    logs_dir = Path("logs")
                    logs_dir.mkdir(exist_ok=True)
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    copy_path = logs_dir / f"webpage_{timestamp}.html"
                    copy_path.write_text(content, encoding='utf-8')
                    print(f"\n💾 Копия сохранена: {copy_path}")
                except Exception as e:
                    print(f"   ⚠️ Ошибка чтения: {e}")
        
        if not found_files:
            print("⚠️ Файл не найден в стандартных местах")
            print("   Возможно файл создан в Docker контейнере")
            print("   Проверьте: docker exec victoria-agent find /app -name '*.html' -type f")
        
        # Проверяем Docker контейнер
        print()
        print("🐳 Проверка Docker контейнера...")
        import subprocess
        try:
            docker_result = subprocess.run(
                ["docker", "exec", "victoria-agent", "find", "/app", "-name", "*.html", "-type", "f", "-newer", "/app/knowledge_os/app/victoria_enhanced.py"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if docker_result.returncode == 0 and docker_result.stdout.strip():
                print("✅ Найдены файлы в контейнере:")
                for line in docker_result.stdout.strip().split('\n'):
                    if line and 'venv' not in line and 'site-packages' not in line:
                        print(f"   {line}")
        except Exception as e:
            print(f"   ⚠️ Не удалось проверить контейнер: {e}")
        
    else:
        print(f"❌ Ошибка HTTP {response.status_code}")
        print(response.text[:500])
        
except requests.exceptions.Timeout:
    print("⏱️ Таймаут - Victoria не ответила за 3 минуты")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("🏁 ТЕСТ ЗАВЕРШЕН")
print("=" * 80)
