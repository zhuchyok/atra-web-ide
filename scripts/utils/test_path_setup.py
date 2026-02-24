#!/usr/bin/env python3
"""
Тесты для path_setup.py
Проверка корректности работы управления путями
"""

import sys
import os
from pathlib import Path

# Настраиваем пути перед импортом
_project_root = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(_project_root))

from scripts.utils.path_setup import (
    setup_project_paths,
    get_project_root,
    get_knowledge_os_root,
    get_knowledge_os_app,
    get_scripts_root,
    get_all_project_paths,
    verify_paths,
    reset_paths,
)

def test_get_project_root():
    """Тест получения корня проекта"""
    root = get_project_root()
    assert root.exists(), f"Корень проекта не существует: {root}"
    assert (root / "PLAN.md").exists() or (root / ".git").exists(), "Не найден маркер корня проекта"
    print(f"✅ get_project_root: {root}")

def test_get_paths():
    """Тест получения всех путей"""
    paths = get_all_project_paths()
    assert "project_root" in paths
    assert "knowledge_os_root" in paths
    assert "knowledge_os_app" in paths
    assert "scripts_root" in paths
    print(f"✅ get_all_project_paths: {len(paths)} путей")

def test_setup_paths():
    """Тест настройки путей"""
    initial_path_count = len(sys.path)
    added = setup_project_paths(verbose=False)
    assert len(added) > 0, "Не добавлено ни одного пути"
    assert len(sys.path) >= initial_path_count + len(added), "Пути не добавлены в sys.path"
    print(f"✅ setup_project_paths: добавлено {len(added)} путей")

def test_verify_paths():
    """Тест проверки путей"""
    verification = verify_paths()
    assert isinstance(verification, dict), "verify_paths должна возвращать словарь"
    # Проверяем что основные пути существуют
    assert verification.get("project_root", False), "Корень проекта должен существовать"
    print(f"✅ verify_paths: {sum(verification.values())}/{len(verification)} путей существуют")

def test_deduplication():
    """Тест дедупликации путей"""
    initial_path_count = len(sys.path)
    # Пытаемся добавить пути дважды
    added1 = setup_project_paths(verbose=False)
    added2 = setup_project_paths(verbose=False)
    # Второй раз не должно быть добавлено новых путей
    assert len(added2) == 0, "Дедупликация не работает"
    print(f"✅ Дедупликация работает: второй вызов не добавил путей")

def test_reset():
    """Тест сброса кэша"""
    root1 = get_project_root()
    reset_paths()
    root2 = get_project_root()
    # После сброса должен быть пересчитан, но результат должен быть тот же
    assert root1 == root2, "После reset_paths корень должен быть тот же"
    print(f"✅ reset_paths работает")

if __name__ == "__main__":
    print("🧪 ТЕСТИРОВАНИЕ path_setup.py")
    print("=" * 60)

    try:
        test_get_project_root()
        test_get_paths()
        test_setup_paths()
        test_verify_paths()
        test_deduplication()
        test_reset()

        print("=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    except AssertionError as e:
        print(f"❌ ОШИБКА: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
