#!/usr/bin/env python3
"""
[KNOWLEDGE OS] Quick Expert Validation Script
Быстрая проверка соответствия хардкодов экспертов данным в БД.

Использование:
    python scripts/quick_validate_experts.py

Для полной проверки:
    python scripts/check_experts_count.py --verbose
"""

import asyncio
import getpass
import os
import sys
from datetime import datetime
from typing import Dict, List, Set, Tuple

# Определение корня проекта
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'app'))

try:
    import asyncpg
except ImportError:
    print("❌ asyncpg не установлен. Установите: pip install asyncpg")
    sys.exit(1)

# Конфигурация БД
USER_NAME = getpass.getuser()
if USER_NAME == 'zhuchyok':
    DEFAULT_DB_URL = f'postgresql://{USER_NAME}@localhost:5432/knowledge_os'
else:
    DEFAULT_DB_URL = 'postgresql://admin:secret@localhost:5432/knowledge_os'

DB_URL = os.getenv('DATABASE_URL', DEFAULT_DB_URL)


# =============================================================================
# ИЗВЕСТНЫЕ ХАРДКОДЫ (для сравнения)
# =============================================================================

# Из telegram_gateway.py и telegram_simple.py
TELEGRAM_HARDCODED = {'Виктория', 'Владимир'}
TELEGRAM_SIMPLE_HARDCODED = {'Виктория', 'Владимир', 'Дмитрий', 'Мария'}

# Из expert_validator.py
FALLBACK_EXPERTS = {'Дмитрий', 'Мария', 'Максим'}
EXTENDED_FALLBACK = {'Дмитрий', 'Мария', 'Максим', 'Сергей', 'Елена'}
COORDINATORS = {'Виктория'}

# Из distillation_engine.py
DISTILLATION_HARDCODED = {'Виктория', 'Дмитрий', 'Мария'}


async def get_db_experts() -> Tuple[int, List[Dict]]:
    """Получает список экспертов из БД."""
    try:
        conn = await asyncpg.connect(DB_URL)
        count = await conn.fetchval("SELECT COUNT(*) FROM experts")
        rows = await conn.fetch(
            "SELECT name, role, department FROM experts ORDER BY name"
        )
        await conn.close()
        return count, [dict(r) for r in rows]
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return -1, []


def compare_sets(
    hardcoded: Set[str], 
    db_names: Set[str], 
    label: str
) -> Tuple[Set[str], Set[str]]:
    """Сравнивает хардкод с данными БД."""
    missing_in_db = hardcoded - db_names
    missing_in_code = db_names - hardcoded - COORDINATORS
    
    return missing_in_db, missing_in_code


async def main():
    print("=" * 70)
    print("🔍 БЫСТРАЯ ВАЛИДАЦИЯ ХАРДКОДОВ ЭКСПЕРТОВ")
    print(f"   Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Получаем данные из БД
    count, experts = await get_db_experts()
    
    if count < 0:
        print("\n❌ Не удалось подключиться к БД. Проверьте DATABASE_URL.")
        return 1
    
    db_names = {e['name'] for e in experts}
    
    print(f"\n📊 ДАННЫЕ ИЗ БД:")
    print(f"   Всего экспертов: {count}")
    print(f"   Имена: {', '.join(sorted(db_names))}")
    
    # Проверяем каждый хардкод
    checks = [
        (TELEGRAM_HARDCODED, "telegram_gateway.py (строки 293-296)"),
        (TELEGRAM_SIMPLE_HARDCODED, "telegram_simple.py (строки 187-200)"),
        (FALLBACK_EXPERTS, "expert_validator.py FALLBACK_EXPERTS"),
        (EXTENDED_FALLBACK, "expert_validator.py EXTENDED_FALLBACK"),
        (DISTILLATION_HARDCODED, "distillation_engine.py (строка 64)"),
    ]
    
    all_ok = True
    
    print("\n" + "=" * 70)
    print("📋 РЕЗУЛЬТАТЫ ПРОВЕРКИ:")
    print("=" * 70)
    
    for hardcoded, label in checks:
        missing_in_db, missing_in_code = compare_sets(hardcoded, db_names, label)
        
        if missing_in_db:
            print(f"\n❌ {label}")
            print(f"   Хардкод: {hardcoded}")
            print(f"   ⚠️ ОТСУТСТВУЮТ В БД: {missing_in_db}")
            all_ok = False
        elif len(missing_in_code) > len(hardcoded):
            print(f"\n⚠️ {label}")
            print(f"   Хардкод: {hardcoded}")
            print(f"   ℹ️ Не охвачено ({len(missing_in_code)}): {sorted(missing_in_code)[:5]}...")
        else:
            print(f"\n✅ {label}")
            print(f"   Хардкод: {hardcoded} — все присутствуют в БД")
    
    # Итоговый статус
    print("\n" + "=" * 70)
    if all_ok:
        print("✅ ВАЛИДАЦИЯ ПРОЙДЕНА: Все хардкодные имена существуют в БД")
    else:
        print("❌ ВАЛИДАЦИЯ НЕ ПРОЙДЕНА: Обнаружены расхождения!")
        print("   Рекомендация: Проверьте отчёт и обновите код или БД")
    print("=" * 70)
    
    # Рекомендации
    all_hardcoded = (
        TELEGRAM_HARDCODED | TELEGRAM_SIMPLE_HARDCODED | 
        FALLBACK_EXPERTS | EXTENDED_FALLBACK | DISTILLATION_HARDCODED
    )
    
    not_in_any_hardcode = db_names - all_hardcoded - COORDINATORS
    
    if not_in_any_hardcode:
        print(f"\n💡 ЭКСПЕРТЫ В БД, НЕ ОХВАЧЕННЫЕ ХАРДКОДАМИ:")
        for name in sorted(not_in_any_hardcode):
            exp = next((e for e in experts if e['name'] == name), {})
            role = exp.get('role', '?')
            dept = exp.get('department', '?')
            print(f"   - {name} ({role}, {dept})")
        print("\n   ℹ️ Это может быть нормально, если используется динамическая загрузка.")
        print("   Но telegram_gateway НЕ поддержит обращение к этим экспертам!")
    
    # Сохраняем краткий отчёт
    report_path = os.path.join(SCRIPT_DIR, 'reports', 'quick_validation.txt')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"Quick Validation Report - {datetime.now()}\n")
        f.write(f"DB Experts Count: {count}\n")
        f.write(f"DB Expert Names: {', '.join(sorted(db_names))}\n")
        f.write(f"Status: {'PASS' if all_ok else 'FAIL'}\n")
        if not_in_any_hardcode:
            f.write(f"Not in hardcodes: {', '.join(sorted(not_in_any_hardcode))}\n")
    
    print(f"\n📄 Краткий отчёт: {report_path}")
    
    return 0 if all_ok else 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
