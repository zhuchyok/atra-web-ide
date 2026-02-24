"""
Централизованное управление путями проекта
Основано на лучших практиках Python (PEP 420, PEP 517/518, PEP 484)

Этот модуль обеспечивает:
- Автоматическое определение корня проекта
- Дедупликацию путей в sys.path
- Кроссплатформенность (Windows/Unix)
- Кэширование для производительности
- Проверку существования путей
- Типизацию для лучшей поддержки IDE
"""

from pathlib import Path
import sys
import os
from typing import List, Optional, Set
from functools import lru_cache

# Кэшируем корень проекта
_PROJECT_ROOT: Optional[Path] = None
_KNOWLEDGE_OS_ROOT: Optional[Path] = None
_KNOWLEDGE_OS_APP: Optional[Path] = None
_SCRIPTS_ROOT: Optional[Path] = None

def _find_project_root(start_path: Optional[Path] = None) -> Path:
    """
    Найти корень проекта по маркерам (.git, pyproject.toml, setup.py)

    Args:
        start_path: Начальный путь для поиска (по умолчанию - текущий файл)

    Returns:
        Path к корню проекта

    Raises:
        RuntimeError: Если корень проекта не найден
    """
    if start_path is None:
        start_path = Path(__file__).resolve()

    current = start_path.parent if start_path.is_file() else start_path

    # Маркеры корня проекта
    markers = ['.git', 'pyproject.toml', 'setup.py', 'PLAN.md']

    for parent in [current] + list(current.parents):
        if any((parent / marker).exists() for marker in markers):
            return parent

    # Fallback: используем директорию на 2 уровня выше от scripts/utils
    fallback = start_path.parent.parent.parent if 'scripts' in str(start_path) else start_path.parent
    return fallback.resolve()

def get_project_root() -> Path:
    """Получить корень проекта (кэшированный)"""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = _find_project_root()
    return _PROJECT_ROOT

def get_knowledge_os_root() -> Path:
    """Получить корень knowledge_os"""
    global _KNOWLEDGE_OS_ROOT
    if _KNOWLEDGE_OS_ROOT is None:
        _KNOWLEDGE_OS_ROOT = get_project_root() / "knowledge_os"
    return _KNOWLEDGE_OS_ROOT

def get_knowledge_os_app() -> Path:
    """Получить knowledge_os/app"""
    global _KNOWLEDGE_OS_APP
    if _KNOWLEDGE_OS_APP is None:
        _KNOWLEDGE_OS_APP = get_knowledge_os_root() / "app"
    return _KNOWLEDGE_OS_APP

def get_scripts_root() -> Path:
    """Получить корень scripts (кэшированный)"""
    global _SCRIPTS_ROOT
    if _SCRIPTS_ROOT is None:
        _SCRIPTS_ROOT = get_project_root() / "scripts"
    return _SCRIPTS_ROOT


def get_backend_root() -> Path:
    """Получить корень backend"""
    return get_project_root() / "backend"


def get_frontend_root() -> Path:
    """Получить корень frontend"""
    return get_project_root() / "frontend"


def get_src_root() -> Path:
    """Получить корень src"""
    return get_project_root() / "src"

def setup_project_paths(
    paths: Optional[List[Path]] = None,
    add_to_pythonpath: bool = True,
    check_exists: bool = True,
    verbose: bool = False
) -> List[str]:
    """
    Настроить пути проекта в sys.path и PYTHONPATH

    Args:
        paths: Список путей для добавления (по умолчанию - стандартные пути проекта)
        add_to_pythonpath: Добавить пути в PYTHONPATH для дочерних процессов
        check_exists: Проверять существование путей
        verbose: Выводить информацию о добавленных путях

    Returns:
        Список добавленных путей (строки)

    Examples:
        >>> from scripts.utils.path_setup import setup_project_paths
        >>> added = setup_project_paths(verbose=True)
        >>> print(f"Добавлено путей: {len(added)}")
    """
    if paths is None:
        paths = [
            get_project_root(),
            get_knowledge_os_root(),
            get_knowledge_os_app(),
            get_scripts_root(),
        ]

    added_paths: List[str] = []
    skipped_paths: List[str] = []

    # Нормализуем все пути заранее для дедупликации
    normalized_paths: Set[str] = set()

    for path in paths:
        try:
            # Нормализуем путь
            resolved_path = path.resolve()
            path_str = str(resolved_path)

            # Дедупликация на уровне нормализованных путей
            if path_str in normalized_paths:
                if verbose:
                    print(f"⏭️  Пропущен (дубликат): {resolved_path}")
                continue
            normalized_paths.add(path_str)

            # Проверяем существование
            if check_exists and not resolved_path.exists():
                import warnings
                warnings.warn(f"Путь не существует: {resolved_path}", UserWarning)
                skipped_paths.append(path_str)
                if verbose:
                    print(f"⚠️  Пропущен (не существует): {resolved_path}")
                continue

            # Добавляем в sys.path только если еще нет
            if path_str not in sys.path:
                sys.path.insert(0, path_str)
                added_paths.append(path_str)
                if verbose:
                    print(f"✅ Добавлен: {resolved_path}")
            else:
                if verbose:
                    print(f"⏭️  Уже в sys.path: {resolved_path}")
        except (OSError, ValueError) as e:
            import warnings
            warnings.warn(f"Ошибка обработки пути {path}: {e}", UserWarning)
            skipped_paths.append(str(path))

    # Обновляем PYTHONPATH для дочерних процессов
    if add_to_pythonpath and added_paths:
        existing_pythonpath = os.environ.get('PYTHONPATH', '')
        existing_paths = existing_pythonpath.split(os.pathsep) if existing_pythonpath else []

        # Нормализуем существующие пути для сравнения
        existing_normalized = {str(Path(p).resolve()) for p in existing_paths if p}

        # Добавляем только новые пути
        new_paths = [p for p in added_paths if p not in existing_normalized]
        if new_paths:
            all_paths = new_paths + existing_paths
            os.environ['PYTHONPATH'] = os.pathsep.join(all_paths)
            if verbose:
                print(f"📝 Обновлен PYTHONPATH: добавлено {len(new_paths)} путей")

    if verbose and skipped_paths:
        print(f"⚠️  Пропущено путей: {len(skipped_paths)}")

    return added_paths

def reset_paths():
    """Сбросить кэш путей (для тестирования)"""
    global _PROJECT_ROOT, _KNOWLEDGE_OS_ROOT, _KNOWLEDGE_OS_APP, _SCRIPTS_ROOT
    _PROJECT_ROOT = None
    _KNOWLEDGE_OS_ROOT = None
    _KNOWLEDGE_OS_APP = None
    _SCRIPTS_ROOT = None


def get_all_project_paths() -> dict[str, Path]:
    """
    Получить все основные пути проекта

    Returns:
        Словарь с ключами: project_root, knowledge_os_root, knowledge_os_app,
        scripts_root, backend_root, frontend_root, src_root
    """
    return {
        "project_root": get_project_root(),
        "knowledge_os_root": get_knowledge_os_root(),
        "knowledge_os_app": get_knowledge_os_app(),
        "scripts_root": get_scripts_root(),
        "backend_root": get_backend_root(),
        "frontend_root": get_frontend_root(),
        "src_root": get_src_root(),
    }


def verify_paths() -> dict[str, bool]:
    """
    Проверить существование всех основных путей проекта

    Returns:
        Словарь с результатами проверки для каждого пути
    """
    paths = get_all_project_paths()
    return {key: path.exists() for key, path in paths.items()}

# Автоматическая настройка при импорте (опционально)
# Раскомментируйте, если хотите автоматическую настройку:
# setup_project_paths()
