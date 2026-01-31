#!/usr/bin/env python3
"""
Скрипт для автоматического обновления импортов после реорганизации архитектуры
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

# Маппинг старых импортов на новые
IMPORT_MAPPING = {
    # Execution
    'order_manager': 'src.execution.order_manager',
    'exchange_adapter': 'src.execution.exchange_adapter',
    'exchange_api': 'src.execution.exchange_api',
    'exchange_base': 'src.execution.exchange_base',
    'improved_position_manager': 'src.execution.position_manager',
    'auto_execution': 'src.execution.auto_execution',
    
    # Risk
    'risk_manager': 'src.risk.risk_manager',
    'correlation_risk_manager': 'src.risk.correlation_risk',
    'capital_management': 'src.risk.capital_management',
    'position_tracker': 'src.risk.position_tracker',
    'risk_monitor': 'src.risk.monitor',
    
    # Database
    'db': 'src.database.db',
    'db_connection_pool': 'src.database.connection_pool',
    'database_initialization': 'src.database.initialization',
    
    # Adapters
    'adaptive_cache': 'src.adapters.cache',
    'adaptive_signal_system': 'src.adapters.signal',
    'adaptive_parameter_controller': 'src.adapters.parameters',
    'adaptive_position_sizer': 'src.adapters.position_sizer',
    
    # Monitoring
    'prometheus_metrics': 'src.monitoring.prometheus',
    'alert_system': 'src.monitoring.alerts',
    'monitoring_system': 'src.monitoring.system',
}

def update_imports_in_file(file_path: Path) -> Tuple[bool, List[str]]:
    """Обновляет импорты в файле"""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        changes = []
        
        # Обновляем простые импорты: import module_name
        for old_name, new_name in IMPORT_MAPPING.items():
            # Паттерн: import module_name
            pattern1 = rf'^import\s+{old_name}\b'
            if re.search(pattern1, content, re.MULTILINE):
                content = re.sub(pattern1, f'import {new_name}', content, flags=re.MULTILINE)
                changes.append(f'import {old_name} → import {new_name}')
            
            # Паттерн: from module_name import ...
            pattern2 = rf'^from\s+{old_name}\s+import'
            if re.search(pattern2, content, re.MULTILINE):
                content = re.sub(pattern2, f'from {new_name} import', content, flags=re.MULTILINE)
                changes.append(f'from {old_name} import → from {new_name} import')
        
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True, changes
        return False, []
    except Exception as e:
        print(f"❌ Ошибка в {file_path}: {e}")
        return False, []

def main():
    """Основная функция"""
    root = Path('.')
    updated_files = []
    skipped_files = []
    
    # Исключаем директории
    exclude_dirs = {'.git', 'venv', '__pycache__', '.pytest_cache', 'htmlcov', 
                    'src/execution', 'src/risk', 'src/database', 'src/adapters', 
                    'src/monitoring', 'archive', 'backups'}
    
    # Ищем все Python файлы
    for py_file in root.rglob('*.py'):
        # Пропускаем исключенные директории
        if any(excluded in str(py_file) for excluded in exclude_dirs):
            continue
        
        # Пропускаем сам скрипт
        if py_file.name == 'update_imports.py':
            continue
        
        updated, changes = update_imports_in_file(py_file)
        if updated:
            updated_files.append((py_file, changes))
        elif changes:
            skipped_files.append((py_file, changes))
    
    # Выводим результаты
    print(f"📊 РЕЗУЛЬТАТЫ ОБНОВЛЕНИЯ ИМПОРТОВ:\n")
    print(f"✅ Обновлено файлов: {len(updated_files)}")
    print(f"⚠️  Пропущено файлов: {len(skipped_files)}\n")
    
    if updated_files:
        print("📝 ОБНОВЛЕННЫЕ ФАЙЛЫ:")
        for file_path, changes in updated_files[:20]:  # Показываем первые 20
            print(f"\n  {file_path}")
            for change in changes:
                print(f"    • {change}")
        
        if len(updated_files) > 20:
            print(f"\n  ... и еще {len(updated_files) - 20} файлов")

if __name__ == '__main__':
    main()

