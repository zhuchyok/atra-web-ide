#!/usr/bin/env python3
"""
Быстрый тест создания сайта с проверкой MLX API Server
"""

import asyncio
import sys
import os
from pathlib import Path
import httpx

# Настройка путей проекта (лучшие практики)
# Используем централизованную утилиту для управления путями
try:
    # Пробуем использовать утилиту, если доступна
    from scripts.utils.path_setup import setup_project_paths
    setup_project_paths()
except ImportError:
    # Fallback: настройка путей вручную (для обратной совместимости)
    project_root = Path(__file__).parent.parent.resolve()
    knowledge_os_root = project_root / "knowledge_os"
    knowledge_os_app = knowledge_os_root / "app"

    paths_to_add = [
        str(project_root),
        str(knowledge_os_root),
        str(knowledge_os_app),
    ]

    # Добавляем в sys.path только если еще нет (дедупликация)
    for path_str in paths_to_add:
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    # Обновляем PYTHONPATH с использованием os.pathsep для кроссплатформенности
    existing_pythonpath = os.environ.get('PYTHONPATH', '')
    existing_paths = existing_pythonpath.split(os.pathsep) if existing_pythonpath else []
    new_paths = [p for p in paths_to_add if p not in existing_paths]
    if new_paths:
        os.environ['PYTHONPATH'] = os.pathsep.join(new_paths + existing_paths)

async def check_mlx_server():
    """Проверить доступность MLX API Server"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:11435/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m.get('name') for m in models]
                print(f"✅ MLX API Server доступен")
                print(f"   Доступно моделей: {len(models)}")
                print(f"   Нужные модели:")
                print(f"     - qwen2.5-coder:32b: {'✅' if 'qwen2.5-coder:32b' in model_names else '❌'}")
                print(f"     - phi3.5:3.8b: {'✅' if 'phi3.5:3.8b' in model_names else '❌'}")
                return True
            else:
                print(f"❌ MLX API Server отвечает с кодом {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ MLX API Server недоступен: {e}")
        print(f"   Запустите: python3 knowledge_os/app/mlx_api_server.py")
        return False

async def run_test():
    """Запустить тест создания сайта"""
    print("\n" + "=" * 80)
    print("🚀 ЗАПУСК ТЕСТА СОЗДАНИЯ САЙТА")
    print("=" * 80 + "\n")

    # Проверяем сервер
    if not await check_mlx_server():
        print("\n⚠️ Продолжаем тест, но результаты могут быть неполными")

    # Импортируем и запускаем тест
    from scripts.test_task_distribution_trace import test_task_distribution

    print("\n📝 Задача: напишут одностраничный сайт по пластиковым окнам современный и наполнят его сео\n")

    result = await test_task_distribution()

    if result and result.get('result'):
        result_text = result.get('result', '')
        print("\n" + "=" * 80)
        print("✅ РЕЗУЛЬТАТ ПОЛУЧЕН")
        print("=" * 80)
        print(f"Длина: {len(result_text)} символов")
        print(f"Метод: {result.get('method', 'N/A')}")
        print(f"Назначений: {result.get('assignments_count', 0)}")
        print(f"Выполнено: {result.get('completed_count', 0)}")

        # Сохраняем результат
        from datetime import datetime
        result_file = Path(__file__).parent.parent / "logs" / f"website_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(result_text)
        print(f"\n💾 Результат сохранен в: {result_file}")

        # Если HTML, сохраняем как HTML
        if '<html' in result_text.lower() or '<!doctype' in result_text.lower():
            html_file = Path(__file__).parent.parent / "logs" / f"website_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(result_text)
            print(f"🌐 HTML сохранен в: {html_file}")

        print("\n📄 ПРЕВЬЮ РЕЗУЛЬТАТА:")
        print("-" * 80)
        print(result_text[:1000])
        if len(result_text) > 1000:
            print(f"\n... (еще {len(result_text) - 1000} символов)")
        print("-" * 80)
    else:
        print("\n❌ Результат не получен")

    return result

if __name__ == "__main__":
    asyncio.run(run_test())
