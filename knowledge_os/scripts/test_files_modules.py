#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка файлов и модулей
"""

import sys
import os
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.test_utils import (
    TestResult, TestStatus, check_file_exists, check_module_import,
    check_class_exists, check_function_exists, measure_time, get_file_path
)
from scripts.test_config import REQUIRED_FILES, REQUIRED_MODULES, PROJECT_ROOT


@measure_time
def test_required_files_exist() -> TestResult:
    """Проверяет существование всех требуемых файлов"""
    missing_files = []
    existing_files = []
    
    all_files = []
    for category_files in REQUIRED_FILES.values():
        all_files.extend(category_files)
    
    # Убираем дубликаты
    unique_files = list(set(all_files))
    
    for file_path in unique_files:
        full_path = get_file_path(file_path)
        if check_file_exists(full_path):
            existing_files.append(file_path)
        else:
            missing_files.append(file_path)
    
    if missing_files:
        return TestResult(
            name="Проверка файлов",
            status=TestStatus.FAIL,
            message=f"Отсутствуют {len(missing_files)} файлов из {len(unique_files)}",
            details={
                "missing": missing_files,
                "existing": existing_files,
                "total_required": len(unique_files),
                "total_existing": len(existing_files)
            },
            recommendations=[
                f"Проверьте наличие файлов: {', '.join(missing_files[:5])}",
                "Убедитесь, что проект полностью склонирован",
                "Проверьте структуру директорий"
            ]
        )
    
    return TestResult(
        name="Проверка файлов",
        status=TestStatus.PASS,
        message=f"Все {len(unique_files)} требуемых файлов существуют",
        details={
            "files_checked": len(unique_files),
            "categories": list(REQUIRED_FILES.keys())
        }
    )


@measure_time
def test_signal_system_files() -> TestResult:
    """Проверяет файлы сигнальной системы"""
    files = REQUIRED_FILES.get("signal_system", [])
    missing = []
    existing = []
    
    for file_path in files:
        full_path = get_file_path(file_path)
        if check_file_exists(full_path):
            existing.append(file_path)
        else:
            missing.append(file_path)
    
    if missing:
        return TestResult(
            name="Файлы сигнальной системы",
            status=TestStatus.FAIL,
            message=f"Отсутствуют файлы: {len(missing)}",
            details={"missing": missing, "existing": existing},
            recommendations=[
                "Проверьте наличие модулей фильтров в src/filters/",
                "Убедитесь, что signal_live.py существует",
                "Проверьте структуру директорий src/"
            ]
        )
    
    return TestResult(
        name="Файлы сигнальной системы",
        status=TestStatus.PASS,
        message=f"Все {len(existing)} файлов сигнальной системы найдены",
        details={"files": existing}
    )


@measure_time
def test_order_execution_files() -> TestResult:
    """Проверяет файлы исполнения ордеров"""
    files = REQUIRED_FILES.get("order_execution", [])
    missing = []
    existing = []
    
    for file_path in files:
        full_path = get_file_path(file_path)
        if check_file_exists(full_path):
            existing.append(file_path)
        else:
            missing.append(file_path)
    
    if missing:
        return TestResult(
            name="Файлы исполнения ордеров",
            status=TestStatus.FAIL,
            message=f"Отсутствуют файлы: {len(missing)}",
            details={"missing": missing, "existing": existing},
            recommendations=[
                "Проверьте наличие exchange_adapter.py",
                "Убедитесь, что модули исполнения ордеров существуют"
            ]
        )
    
    return TestResult(
        name="Файлы исполнения ордеров",
        status=TestStatus.PASS,
        message=f"Все {len(existing)} файлов исполнения ордеров найдены",
        details={"files": existing}
    )


@measure_time
def test_modules_importable() -> TestResult:
    """Проверяет возможность импорта модулей"""
    all_modules = []
    for category_modules in REQUIRED_MODULES.values():
        all_modules.extend(category_modules)
    
    # Убираем дубликаты
    unique_modules = list(set(all_modules))
    
    import_errors = []
    successful_imports = []
    
    for module_info in unique_modules:
        if isinstance(module_info, tuple):
            module_name, class_name = module_info
        else:
            module_name = module_info
            class_name = None
        
        # Преобразуем путь к модулю (src/filters/... -> src.filters....)
        if "/" in module_name:
            module_name = module_name.replace("/", ".")
        if module_name.endswith(".py"):
            module_name = module_name[:-3]
        
        success, error = check_module_import(module_name)
        if success:
            # Если указан класс, проверяем его существование
            if class_name:
                class_success, class_error = check_class_exists(module_name, class_name)
                if class_success:
                    successful_imports.append(f"{module_name}.{class_name}")
                else:
                    import_errors.append(f"{module_name}.{class_name}: {class_error}")
            else:
                # Модуль без класса - просто проверяем импорт
                successful_imports.append(module_name)
        else:
            import_errors.append(f"{module_name}: {error}")
    
    if import_errors:
        # Показываем все ошибки для диагностики
        return TestResult(
            name="Импорт модулей",
            status=TestStatus.FAIL,
            message=f"Ошибки импорта: {len(import_errors)} из {len(unique_modules)}",
            details={
                "errors": import_errors,  # Все ошибки для диагностики
                "successful": successful_imports,
                "total": len(unique_modules),
                "success_rate": f"{(len(successful_imports)/len(unique_modules)*100):.1f}%"
            },
            recommendations=[
                "Проверьте установку зависимостей: pip install -r requirements.txt",
                "Убедитесь, что все модули находятся в правильных директориях",
                "Проверьте наличие __init__.py в пакетах",
                f"Детали ошибок: {', '.join(import_errors[:5])}"
            ]
        )
    
    return TestResult(
        name="Импорт модулей",
        status=TestStatus.PASS,
        message=f"Все {len(unique_modules)} модулей успешно импортированы",
        details={"modules": successful_imports}
    )


@measure_time
def test_filter_modules() -> TestResult:
    """Проверяет модули фильтров"""
    filter_modules = REQUIRED_MODULES.get("signal_system", [])
    filter_modules = [m for m in filter_modules if "filters" in str(m[0])]
    
    errors = []
    successful = []
    
    for module_info in filter_modules:
        if isinstance(module_info, tuple):
            module_name, class_name = module_info
        else:
            module_name = module_info
            class_name = None
        
        # Преобразуем путь
        if "/" in module_name:
            module_name = module_name.replace("/", ".")
        if module_name.endswith(".py"):
            module_name = module_name[:-3]
        
        success, error = check_module_import(module_name)
        if success:
            if class_name:
                class_success, class_error = check_class_exists(module_name, class_name)
                if class_success:
                    successful.append(f"{module_name}.{class_name}")
                else:
                    errors.append(f"{module_name}.{class_name}: {class_error}")
            else:
                successful.append(module_name)
        else:
            errors.append(f"{module_name}: {error}")
    
    if errors:
        return TestResult(
            name="Модули фильтров",
            status=TestStatus.FAIL,
            message=f"Проблемы с {len(errors)} модулями фильтров",
            details={
                "errors": errors,  # Все ошибки
                "successful": successful,
                "total_filters": len(filter_modules),
                "success_rate": f"{(len(successful)/len(filter_modules)*100):.1f}%" if filter_modules else "0%"
            },
            recommendations=[
                "Проверьте наличие всех файлов фильтров в src/filters/",
                "Убедитесь, что классы фильтров правильно определены",
                f"Детали ошибок: {', '.join(errors[:3])}"
            ]
        )
    
    return TestResult(
        name="Модули фильтров",
        status=TestStatus.PASS,
        message=f"Все {len(successful)} модулей фильтров работают",
        details={"modules": successful}
    )


@measure_time
def test_directory_structure() -> TestResult:
    """Проверяет структуру директорий"""
    required_dirs = [
        "src",
        "src/filters",
        "src/strategies",
        "src/analysis",
        "scripts",
        "logs"
    ]
    
    missing_dirs = []
    existing_dirs = []
    
    for dir_path in required_dirs:
        full_path = get_file_path(dir_path)
        if os.path.isdir(full_path):
            existing_dirs.append(dir_path)
        else:
            missing_dirs.append(dir_path)
    
    if missing_dirs:
        return TestResult(
            name="Структура директорий",
            status=TestStatus.WARNING,
            message=f"Отсутствуют директории: {len(missing_dirs)}",
            details={"missing": missing_dirs, "existing": existing_dirs},
            recommendations=[
                "Создайте недостающие директории",
                "Проверьте структуру проекта"
            ]
        )
    
    return TestResult(
        name="Структура директорий",
        status=TestStatus.PASS,
        message=f"Все {len(existing_dirs)} требуемых директорий существуют",
        details={"directories": existing_dirs}
    )


def run_all_file_tests() -> list:
    """Запускает все тесты файлов и модулей"""
    tests = [
        test_required_files_exist,
        test_signal_system_files,
        test_order_execution_files,
        test_modules_importable,
        test_filter_modules,
        test_directory_structure
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
            print(result)
        except Exception as e:
            results.append(TestResult(
                name=test_func.__name__,
                status=TestStatus.FAIL,
                message=f"Исключение при выполнении: {str(e)}"
            ))
    
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("ПРОВЕРКА ФАЙЛОВ И МОДУЛЕЙ")
    print("=" * 60)
    
    results = run_all_file_tests()
    
    from scripts.test_utils import print_test_summary
    print_test_summary(results)

