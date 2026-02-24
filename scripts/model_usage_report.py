#!/usr/bin/env python3
"""
Генерация отчета об использовании моделей всеми компонентами системы
"""
import os
import re
import json
from typing import Dict, List, Set
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent

def scan_python_files() -> Dict[str, List[str]]:
    """Сканирование всех Python файлов на использование моделей"""
    model_usage = defaultdict(list)

    # Паттерны для поиска моделей
    patterns = [
        r'model["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'MODEL["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'model_name["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'"model":\s*["\']([^"\']+)["\']',
        r"'model':\s*['\"]([^'\"]+)['\"]",
    ]

    # Исключаем некоторые директории
    exclude_dirs = {'node_modules', '.git', '__pycache__', '.venv', 'venv', '.pytest_cache'}

    for py_file in PROJECT_ROOT.rglob('*.py'):
        # Пропускаем исключенные директории
        if any(excluded in str(py_file) for excluded in exclude_dirs):
            continue

        try:
            content = py_file.read_text(encoding='utf-8', errors='ignore')

            # Ищем все упоминания моделей
            found_models = set()
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Фильтруем только реальные названия моделей (содержат : или -)
                    if ':' in match or '-' in match or match.endswith('b') or 'model' not in match.lower():
                        found_models.add(match)

            if found_models:
                relative_path = str(py_file.relative_to(PROJECT_ROOT))
                for model in found_models:
                    model_usage[model].append(relative_path)
        except Exception as e:
            pass

    return dict(model_usage)

def scan_config_files() -> Dict[str, List[str]]:
    """Сканирование конфигурационных файлов"""
    model_usage = defaultdict(list)

    config_patterns = ['.yaml', '.yml', '.json', '.env', 'docker-compose.yml']

    for config_file in PROJECT_ROOT.rglob('*'):
        if any(config_file.suffix == ext for ext in config_patterns) or config_file.name in ['docker-compose.yml', '.env']:
            if any(excluded in str(config_file) for excluded in {'.git', 'node_modules', '__pycache__'}):
                continue

            try:
                content = config_file.read_text(encoding='utf-8', errors='ignore')

                # Ищем модели в конфигах
                patterns = [
                    r'MODEL["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                    r'model["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                    r'["\']([^"\']+:[0-9]+b?)["\']',  # model:size
                ]

                found_models = set()
                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if ':' in match or match.endswith('b') or ('model' not in match.lower() and len(match) > 3):
                            found_models.add(match)

                if found_models:
                    relative_path = str(config_file.relative_to(PROJECT_ROOT))
                    for model in found_models:
                        model_usage[model].append(relative_path)
            except:
                pass

    return dict(model_usage)

def get_available_models() -> Dict:
    """Получение списка доступных моделей из последнего сканирования"""
    scan_file = '/tmp/available_models.json'
    if os.path.exists(scan_file):
        try:
            with open(scan_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"mlx_models": [], "ollama_models": [], "all_models": []}

def generate_report():
    """Генерация итогового отчета"""
    print("🔍 Сканирование использования моделей...")

    # Сканируем файлы
    python_usage = scan_python_files()
    config_usage = scan_config_files()

    # Объединяем
    all_usage = defaultdict(list)
    for model, files in python_usage.items():
        all_usage[model].extend(files)
    for model, files in config_usage.items():
        all_usage[model].extend(files)

    # Получаем доступные модели
    available = get_available_models()
    mlx_models = set(available.get('mlx_models', []))
    ollama_models = set(available.get('ollama_models', []))
    all_available = mlx_models | ollama_models

    # Группируем по компонентам
    components = {
        'Victoria Agent': [],
        'Veronica Agent': [],
        'Orchestrator': [],
        'AI Core': [],
        'Local Router': [],
        'Smart Worker': [],
        'Other': []
    }

    for model, files in all_usage.items():
        for file in files:
            if 'victoria' in file.lower():
                components['Victoria Agent'].append((model, file))
            elif 'veronica' in file.lower():
                components['Veronica Agent'].append((model, file))
            elif 'orchestrator' in file.lower():
                components['Orchestrator'].append((model, file))
            elif 'ai_core' in file.lower():
                components['AI Core'].append((model, file))
            elif 'local_router' in file.lower():
                components['Local Router'].append((model, file))
            elif 'smart_worker' in file.lower():
                components['Smart Worker'].append((model, file))
            else:
                components['Other'].append((model, file))

    # Выводим отчет
    print("\n" + "="*80)
    print("📊 ИТОГОВАЯ ТАБЛИЦА ИСПОЛЬЗОВАНИЯ МОДЕЛЕЙ")
    print("="*80)

    print("\n✅ ДОСТУПНЫЕ МОДЕЛИ:")
    print(f"   MLX ({len(mlx_models)}): {', '.join(sorted(mlx_models))}")
    print(f"   Ollama ({len(ollama_models)}): {', '.join(sorted(ollama_models))}")

    print("\n📋 ИСПОЛЬЗОВАНИЕ ПО КОМПОНЕНТАМ:")
    for component, usages in components.items():
        if usages:
            models_used = set([m for m, _ in usages])
            print(f"\n{component}:")
            for model in sorted(models_used):
                status = "✅" if model in all_available else "❌ НЕ НАЙДЕНА"
                files = [f for m, f in usages if m == model]
                print(f"   • {model} {status}")
                if len(files) <= 3:
                    for file in files[:3]:
                        print(f"     └─ {file}")
                else:
                    for file in files[:2]:
                        print(f"     └─ {file}")
                    print(f"     └─ ... и еще {len(files) - 2} файлов")

    # Проверяем несуществующие модели
    print("\n⚠️ НЕСУЩЕСТВУЮЩИЕ МОДЕЛИ (используются, но не найдены):")
    missing_models = set()
    for model in all_usage.keys():
        if model not in all_available and len(model) > 3:
            missing_models.add(model)

    if missing_models:
        for model in sorted(missing_models):
            files = all_usage[model]
            print(f"   • {model} (используется в {len(files)} файлах)")
            for file in files[:3]:
                print(f"     └─ {file}")
    else:
        print("   ✅ Все используемые модели найдены!")

    # Сохраняем отчет
    report = {
        "timestamp": datetime.now().isoformat(),
        "available_models": {
            "mlx": list(mlx_models),
            "ollama": list(ollama_models),
            "all": list(all_available)
        },
        "usage_by_component": {
            k: list(set([m for m, _ in v])) for k, v in components.items() if v
        },
        "missing_models": list(missing_models),
        "detailed_usage": dict(all_usage)
    }

    report_file = '/tmp/model_usage_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Подробный отчет сохранен в: {report_file}")

if __name__ == '__main__':
    from datetime import datetime
    generate_report()
