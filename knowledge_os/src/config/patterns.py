"""
Конфигурация путей к файлам паттернов
Единый файл для управления всеми путями к паттернам в системе
"""

import os
from pathlib import Path

# Базовый путь к проекту
# Исправлено: идем на 2 уровня вверх от src/config/patterns.py до корня проекта
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()

# Основные пути к файлам паттернов
PATTERNS_CONFIG = {
    # Основной файл с паттернами ИИ
    "main_patterns_file": PROJECT_ROOT / "ai_learning_data" / "trading_patterns.json",
    
    # Backup файлы
    "backup_patterns_file": PROJECT_ROOT / "ai_learning_data" / "trading_patterns_backup.json",
    
    # Объединенный файл
    "merged_patterns_file": PROJECT_ROOT / "ai_learning_data" / "trading_patterns_merged.json",
    
    # Временные файлы
    "temp_patterns_file": PROJECT_ROOT / "ai_learning_data" / "trading_patterns_temp.json",
    
    # Логи и метрики
    "learning_metrics_file": PROJECT_ROOT / "ai_learning_data" / "learning_metrics.json",
    "optimized_parameters_file": PROJECT_ROOT / "ai_learning_data" / "optimized_parameters.json",
    "learning_model_file": PROJECT_ROOT / "ai_learning_data" / "learning_model.pkl",
}

# Настройки системы паттернов
PATTERNS_SETTINGS = {
    "max_patterns": 50000,  # Максимальное количество паттернов
    "cleanup_interval_hours": 24,  # Интервал очистки в часах
    "backup_before_cleanup": True,  # Создавать backup перед очисткой
    "auto_cleanup_enabled": True,  # Автоматическая очистка включена
}

def get_patterns_file_path(file_type="main"):
    """
    Получить путь к файлу паттернов по типу
    
    Args:
        file_type (str): Тип файла ('main', 'backup', 'merged', 'temp')
    
    Returns:
        str: Путь к файлу
    """
    if file_type == "main":
        return str(PATTERNS_CONFIG["main_patterns_file"])
    elif file_type == "backup":
        return str(PATTERNS_CONFIG["backup_patterns_file"])
    elif file_type == "merged":
        return str(PATTERNS_CONFIG["merged_patterns_file"])
    elif file_type == "temp":
        return str(PATTERNS_CONFIG["temp_patterns_file"])
    else:
        raise ValueError(f"Неизвестный тип файла: {file_type}")

def get_learning_metrics_path():
    """Получить путь к файлу метрик обучения"""
    return str(PATTERNS_CONFIG["learning_metrics_file"])

def get_optimized_parameters_path():
    """Получить путь к файлу оптимизированных параметров"""
    return str(PATTERNS_CONFIG["optimized_parameters_file"])

def get_learning_model_path():
    """Получить путь к файлу модели обучения"""
    return str(PATTERNS_CONFIG["learning_model_file"])

def ensure_patterns_directory():
    """Создать директорию для паттернов если не существует"""
    patterns_dir = PROJECT_ROOT / "ai_learning_data"
    patterns_dir.mkdir(exist_ok=True)
    return str(patterns_dir)

def get_patterns_count():
    """Получить количество паттернов в основном файле"""
    import json
    patterns_file = get_patterns_file_path("main")
    
    if not os.path.exists(patterns_file):
        return 0
    
    try:
        with open(patterns_file, 'r', encoding='utf-8') as f:
            patterns = json.load(f)
        return len(patterns) if isinstance(patterns, list) else 0
    except Exception:
        return 0

def get_patterns_file_size():
    """Получить размер файла паттернов в байтах"""
    patterns_file = get_patterns_file_path("main")
    
    if not os.path.exists(patterns_file):
        return 0
    
    return os.path.getsize(patterns_file)

# Экспорт основных функций
__all__ = [
    'get_patterns_file_path',
    'get_learning_metrics_path', 
    'get_optimized_parameters_path',
    'get_learning_model_path',
    'ensure_patterns_directory',
    'get_patterns_count',
    'get_patterns_file_size',
    'PATTERNS_SETTINGS'
]
