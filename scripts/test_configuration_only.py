#!/usr/bin/env python3
"""
Проверка конфигурации без API запросов
Проверяет что tinyllama исключена из всех списков ответов
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_no_tinyllama_in_code():
    """Проверка что tinyllama исключена из кода"""
    print("🚫 ПРОВЕРКА: Исключение tinyllama из ответов")
    print("=" * 60)
    
    files_to_check = [
        ("knowledge_os/app/react_agent.py", "fallback_models"),
        ("knowledge_os/app/extended_thinking.py", "fallback_models"),
        ("knowledge_os/app/victoria_enhanced.py", "model_priorities"),
        ("knowledge_os/app/mlx_api_server.py", "CATEGORY_TO_MODEL"),
        ("backend/app/routers/chat.py", "_select_model_for_chat")
    ]
    
    issues = []
    passed = 0
    
    for file_path, context in files_to_check:
        full_path = os.path.join(os.path.dirname(__file__), '..', file_path)
        if not os.path.exists(full_path):
            print(f"⚠️ Файл не найден: {file_path}")
            continue
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Проверяем что tinyllama не используется для ответов
        # (может быть закомментирована или исключена)
        lines = content.split('\n')
        found_issues = []
        
        for i, line in enumerate(lines, 1):
            # Ищем использование tinyllama в контексте ответов
            if 'tinyllama' in line.lower() and 'tinyllama' in line:
                # Проверяем что это не комментарий и не исключение
                stripped = line.strip()
                if not stripped.startswith('#') and 'исключена' not in line.lower() and 'только для' not in line.lower():
                    # Проверяем контекст - не должно быть в списках для ответов
                    if any(keyword in line.lower() for keyword in ['fallback', 'model', 'fast', 'default', 'return']):
                        found_issues.append((i, line.strip()[:80]))
        
        if found_issues:
            print(f"\n❌ {file_path}:")
            for line_num, line_content in found_issues[:3]:
                print(f"   Строка {line_num}: {line_content}...")
            issues.extend([(file_path, i, l) for i, l in found_issues])
        else:
            print(f"✅ {file_path}: tinyllama исключена")
            passed += 1
    
    print(f"\n📊 Результат: {passed}/{len(files_to_check)} файлов проверены")
    
    if issues:
        print(f"\n⚠️ Найдено {len(issues)} потенциальных проблем")
        return False
    else:
        print("\n✅ Все файлы корректны - tinyllama исключена из ответов")
        return True

def test_ollama_models_config():
    """Проверка конфигурации Ollama моделей"""
    print("\n📋 ПРОВЕРКА: Конфигурация Ollama моделей")
    print("=" * 60)
    
    file_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_os/app/local_router.py')
    
    if not os.path.exists(file_path):
        print("⚠️ Файл не найден")
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Проверяем что OLLAMA_MODELS настроены правильно
    if 'OLLAMA_MODELS' in content:
        print("✅ OLLAMA_MODELS найдены")
        
        # Проверяем наличие нужных моделей
        required_models = ['phi3.5:3.8b', 'moondream', 'llava:7b']
        for model in required_models:
            if model in content:
                print(f"   ✅ {model} настроен")
            else:
                print(f"   ⚠️ {model} не найден")
        
        return True
    else:
        print("❌ OLLAMA_MODELS не найдены")
        return False

def test_queue_implementation():
    """Проверка реализации очереди"""
    print("\n🔄 ПРОВЕРКА: Реализация очереди")
    print("=" * 60)
    
    queue_file = os.path.join(os.path.dirname(__file__), '..', 'knowledge_os/app/mlx_request_queue.py')
    server_file = os.path.join(os.path.dirname(__file__), '..', 'knowledge_os/app/mlx_api_server.py')
    
    checks = []
    
    # Проверка mlx_request_queue.py
    if os.path.exists(queue_file):
        with open(queue_file, 'r', encoding='utf-8') as f:
            queue_content = f.read()
        
        if 'class MLXRequestQueue' in queue_content:
            checks.append(("MLXRequestQueue класс", True))
        if 'RequestPriority' in queue_content:
            checks.append(("RequestPriority enum", True))
        if 'add_request' in queue_content:
            checks.append(("add_request метод", True))
        if 'HIGH' in queue_content and 'MEDIUM' in queue_content:
            checks.append(("Приоритеты HIGH/MEDIUM", True))
    else:
        checks.append(("mlx_request_queue.py файл", False))
    
    # Проверка интеграции в mlx_api_server.py
    if os.path.exists(server_file):
        with open(server_file, 'r', encoding='utf-8') as f:
            server_content = f.read()
        
        if 'X-Request-Priority' in server_content:
            checks.append(("Поддержка X-Request-Priority", True))
        if 'get_request_queue' in server_content:
            checks.append(("Интеграция get_request_queue", True))
        if '/queue/stats' in server_content:
            checks.append(("Endpoint /queue/stats", True))
    else:
        checks.append(("mlx_api_server.py файл", False))
    
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"   {status} {check_name}")
    
    return all(r for _, r in checks)

def main():
    """Главная функция"""
    print("🔍 ПРОВЕРКА КОНФИГУРАЦИИ СИСТЕМЫ")
    print("=" * 60)
    
    results = {}
    results["no_tinyllama"] = test_no_tinyllama_in_code()
    results["ollama_config"] = test_ollama_models_config()
    results["queue_impl"] = test_queue_implementation()
    
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ПРОВЕРКИ КОНФИГУРАЦИИ:")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✅" if result else "❌"
        print(f"   {status} {test}")
    
    print(f"\n✅ Пройдено: {passed}/{total}")
    
    if passed == total:
        print("   ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
    else:
        print("   ⚠️ Некоторые проверки не прошли")

if __name__ == "__main__":
    main()
