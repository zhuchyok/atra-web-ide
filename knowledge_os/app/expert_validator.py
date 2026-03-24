#!/usr/bin/env python3
"""
[KNOWLEDGE OS] Expert Validator Module.

Централизованная валидация списков экспертов.
Этот модуль обеспечивает:
1. Единый источник fallback-списков экспертов
2. Валидацию хардкодных списков через запросы к БД
3. Предупреждения при использовании статических данных

Использование:
    from expert_validator import (
        get_validated_fallback_experts,
        validate_expert_names,
        ExpertValidationWarning
    )

    # Получить fallback-список с валидацией
    experts = await get_validated_fallback_experts()

    # Валидировать конкретные имена
    valid, missing = await validate_expert_names(['Дмитрий', 'Мария'])

При невозможности подключения к БД используется fallback с предупреждением.
"""

import getpass
import logging
import os
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

# Third-party imports with fallback
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

logger = logging.getLogger(__name__)

# =============================================================================
# КОНФИГУРАЦИЯ ПОДКЛЮЧЕНИЯ К БД
# =============================================================================
USER_NAME = getpass.getuser()
DEFAULT_DB_URL = (
    os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:6432/knowledge_os"
)

DB_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)


# =============================================================================
# FALLBACK КОНФИГУРАЦИЯ
# ВАЖНО: Эти списки могут быть неполными!
# Для актуальных данных используйте get_validated_fallback_experts()
# Проверка: python scripts/check_experts_count.py --verbose
# =============================================================================

# Основные эксперты для fallback (минимальный набор)
FALLBACK_EXPERTS: List[str] = [
    "Дмитрий",  # Engineer
    "Мария",  # Analyst
    "Максим",  # Developer
]

# Расширенный fallback (для war-room и критических задач)
EXTENDED_FALLBACK_EXPERTS: List[str] = [
    "Дмитрий",
    "Мария",
    "Максим",
    "Сергей",
    "Елена",
]

# Координаторы (не включаются в обычные fallback-списки)
COORDINATOR_NAMES: Set[str] = {"Виктория"}


# =============================================================================
# CUSTOM WARNINGS
# =============================================================================


class ExpertValidationWarning(UserWarning):
    """Предупреждение о потенциальной неполноте списка экспертов."""

    pass


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class ValidationResult:
    """Результат валидации списка экспертов."""

    is_valid: bool
    valid_names: List[str]
    missing_names: List[str]
    db_expert_count: int
    hardcoded_count: int
    warning_message: Optional[str] = None
    validation_time: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        status = "✅ VALID" if self.is_valid else "⚠️ INCOMPLETE"
        return (
            f"{status} | DB: {self.db_expert_count} | "
            f"Checked: {self.hardcoded_count} | "
            f"Missing: {len(self.missing_names)}"
        )


@dataclass
class ExpertInfo:
    """Информация об эксперте из БД."""

    name: str
    role: str
    department: Optional[str] = None

    def __str__(self) -> str:
        dept = self.department or "General"
        return f"{self.name} ({self.role}, {dept})"


# =============================================================================
# ОСНОВНЫЕ ФУНКЦИИ ВАЛИДАЦИИ
# =============================================================================


async def get_db_expert_count() -> int:
    """
    Выполняет SELECT COUNT(*) FROM experts.

    Returns:
        Количество экспертов в БД или -1 при ошибке
    """
    if not ASYNCPG_AVAILABLE:
        logger.debug("ℹ️ asyncpg недоступен, невозможно получить COUNT(*) (используем fallback)")
        return -1

    try:
        conn = await asyncpg.connect(DB_URL)
        result = await conn.fetchval("SELECT COUNT(*) FROM experts")
        await conn.close()
        return result or 0
    except Exception as exc:
        logger.error("Ошибка SELECT COUNT(*) FROM experts: %s", exc)
        return -1


async def get_db_expert_names() -> List[str]:
    """
    Выполняет SELECT name FROM experts.

    Returns:
        Список имён экспертов из БД или пустой список при ошибке
    """
    if not ASYNCPG_AVAILABLE:
        logger.debug(
            "ℹ️ asyncpg недоступен, невозможно получить имена экспертов (используем fallback)"
        )
        return []

    try:
        conn = await asyncpg.connect(DB_URL)
        rows = await conn.fetch("SELECT name FROM experts ORDER BY name")
        await conn.close()
        return [row["name"] for row in rows]
    except Exception as exc:
        logger.error("Ошибка SELECT name FROM experts: %s", exc)
        return []


async def get_all_experts_info() -> List[ExpertInfo]:
    """
    Получает полную информацию об экспертах из БД.

    Returns:
        Список ExpertInfo объектов
    """
    if not ASYNCPG_AVAILABLE:
        return []

    try:
        conn = await asyncpg.connect(DB_URL)
        rows = await conn.fetch("SELECT name, role, department FROM experts ORDER BY name")
        await conn.close()
        return [
            ExpertInfo(name=row["name"], role=row["role"], department=row["department"])
            for row in rows
        ]
    except Exception as exc:
        logger.error("Ошибка получения информации об экспертах: %s", exc)
        return []


async def validate_expert_names(names: List[str], emit_warning: bool = True) -> ValidationResult:
    """
    Валидирует список имён экспертов против БД.

    Args:
        names: Список имён для проверки
        emit_warning: Генерировать ли предупреждение при расхождениях

    Returns:
        ValidationResult с деталями проверки
    """
    db_names = await get_db_expert_names()
    db_count = len(db_names)

    if db_count == 0:
        # БД недоступна или пуста
        warning_msg = (
            "⚠️ ВНИМАНИЕ: Невозможно валидировать список экспертов - "
            "БД недоступна или пуста. Используется хардкод-список, "
            "который может быть неполным!"
        )
        if emit_warning:
            logger.warning(warning_msg)
            warnings.warn(warning_msg, ExpertValidationWarning)

        return ValidationResult(
            is_valid=False,
            valid_names=names,
            missing_names=[],
            db_expert_count=0,
            hardcoded_count=len(names),
            warning_message=warning_msg,
        )

    db_names_set = set(db_names)
    names_set = set(names)

    valid_names = [n for n in names if n in db_names_set]
    missing_names = list(names_set - db_names_set)

    # Проверяем, есть ли эксперты в БД, которых нет в списке
    extra_in_db = db_names_set - names_set - COORDINATOR_NAMES

    warning_msg = None
    is_valid = len(missing_names) == 0

    if missing_names:
        warning_msg = (
            f"⚠️ Эксперты отсутствуют в БД: {missing_names}. "
            "Проверьте актуальность списка через check_experts_count.py"
        )
    elif len(extra_in_db) > len(names):
        warning_msg = (
            f"⚠️ В БД больше экспертов ({db_count}), чем в хардкод-списке ({len(names)}). "
            f"Возможно неполное покрытие. Рекомендуется использовать динамическую загрузку."
        )
        is_valid = False

    if warning_msg and emit_warning:
        logger.warning(warning_msg)
        warnings.warn(warning_msg, ExpertValidationWarning)

    return ValidationResult(
        is_valid=is_valid,
        valid_names=valid_names,
        missing_names=missing_names,
        db_expert_count=db_count,
        hardcoded_count=len(names),
        warning_message=warning_msg,
    )


async def get_validated_fallback_experts(
    extended: bool = False, emit_warning: bool = True
) -> Tuple[List[str], ValidationResult]:
    """
    Получает fallback-список экспертов с валидацией.

    ВАЖНО: Всегда предпочитайте динамическую загрузку из БД!
    Эта функция для случаев, когда БД недоступна.

    Args:
        extended: Использовать расширенный fallback-список
        emit_warning: Генерировать предупреждение

    Returns:
        Tuple[список_экспертов, результат_валидации]
    """
    fallback = EXTENDED_FALLBACK_EXPERTS if extended else FALLBACK_EXPERTS

    # Пытаемся получить актуальные данные из БД
    db_names = await get_db_expert_names()

    if db_names:
        # БД доступна - используем данные из неё
        # Фильтруем координаторов
        experts = [n for n in db_names if n not in COORDINATOR_NAMES]

        # Проверяем fallback на актуальность
        validation = await validate_expert_names(fallback, emit_warning=False)

        if emit_warning and not validation.is_valid:
            msg = (
                f"ℹ️ Fallback-список ({len(fallback)}) отличается от БД ({len(db_names)}). "
                "Рекомендуется обновить FALLBACK_EXPERTS в expert_validator.py"
            )
            logger.info(msg)

        return experts, validation

    # БД недоступна - используем fallback с предупреждением
    if emit_warning:
        msg = (
            "⚠️ БД недоступна! Используется хардкод-список экспертов. "
            "Список может быть неполным или устаревшим. "
            "Проверьте через: python scripts/check_experts_count.py"
        )
        logger.warning(msg)
        warnings.warn(msg, ExpertValidationWarning)

    validation = ValidationResult(
        is_valid=False,
        valid_names=fallback,
        missing_names=[],
        db_expert_count=0,
        hardcoded_count=len(fallback),
        warning_message="БД недоступна, используется fallback",
    )

    return fallback.copy(), validation


# =============================================================================
# УТИЛИТЫ
# =============================================================================


async def print_expert_comparison():
    """
    Выводит сравнение хардкод-списков с данными БД.
    Полезно для диагностики.
    """
    print("=" * 60)
    print("📊 СРАВНЕНИЕ ХАРДКОД-СПИСКОВ ЭКСПЕРТОВ С БД")
    print("=" * 60)

    # 1. SELECT COUNT(*)
    count = await get_db_expert_count()
    print(f"\n🗄️ SELECT COUNT(*) FROM experts: {count}")

    # 2. SELECT name
    names = await get_db_expert_names()
    print(f"\n📋 SELECT name FROM experts ({len(names)} записей):")
    for name in names:
        fallback_marker = " [в FALLBACK]" if name in FALLBACK_EXPERTS else ""
        extended_marker = " [в EXTENDED]" if name in EXTENDED_FALLBACK_EXPERTS else ""
        print(f"   - {name}{fallback_marker}{extended_marker}")

    # 3. Валидация основного fallback
    print(f"\n🔍 Валидация FALLBACK_EXPERTS ({len(FALLBACK_EXPERTS)}):")
    validation = await validate_expert_names(FALLBACK_EXPERTS, emit_warning=False)
    print(f"   Статус: {validation}")
    if validation.missing_names:
        print(f"   ❌ Отсутствуют в БД: {validation.missing_names}")

    # 4. Расхождения
    db_set = set(names) - COORDINATOR_NAMES
    fallback_set = set(FALLBACK_EXPERTS)

    only_in_db = db_set - fallback_set
    only_in_fallback = fallback_set - db_set

    if only_in_db:
        print(f"\n⚠️ Эксперты в БД, но НЕ в fallback ({len(only_in_db)}):")
        for name in sorted(only_in_db):
            print(f"   - {name}")

    if only_in_fallback:
        print(f"\n❌ Эксперты в fallback, но НЕ в БД ({len(only_in_fallback)}):")
        for name in sorted(only_in_fallback):
            print(f"   - {name}")

    print("\n" + "=" * 60)
    if not only_in_fallback and len(only_in_db) == 0:
        print("✅ Хардкод-списки соответствуют БД")
    elif only_in_fallback:
        print("❌ ОШИБКА: В fallback есть несуществующие эксперты!")
    else:
        print("⚠️ ВНИМАНИЕ: Хардкод-списки неполные (есть эксперты только в БД)")
    print("=" * 60)


# =============================================================================
# CLI ИНТЕРФЕЙС
# =============================================================================

if __name__ == "__main__":
    import asyncio

    asyncio.run(print_expert_comparison())
