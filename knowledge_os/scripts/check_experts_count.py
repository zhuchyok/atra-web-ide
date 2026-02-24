#!/usr/bin/env python3
"""
[KNOWLEDGE OS] Скрипт проверки соответствия хардкодных списков экспертов реальным данным БД.

Этот скрипт:
1. Выполняет SQL запросы к БД:
   - SELECT COUNT(*) FROM experts
   - SELECT name FROM experts
   - SELECT name, role, department FROM experts
2. Сканирует кодовую базу на наличие захардкоженных списков экспертов
3. Сравнивает найденные имена с актуальными данными из таблицы experts
4. Валидирует FALLBACK_EXPERTS из expert_validator.py
5. Выводит детальный отчёт о расхождениях и рекомендации

Использование:
    python scripts/check_experts_count.py [--fix] [--verbose]

Флаги:
    --fix       Предложить автоматические исправления (требует подтверждения)
    --verbose   Подробный вывод (включая все SQL запросы)
    --dry-run   Только показать, что будет проверено (без подключения к БД)
    --sql-only  Только выполнить SQL запросы (без сканирования кода)

Перед выполнением скрипт запрашивает подтверждение у пользователя.
"""

import argparse
import asyncio
import getpass
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Определение корня проекта
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Добавляем путь к проекту для импорта
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "app"))

# Зависимости (asyncpg) устанавливаются на этапе setup, не в рантайме (12-Factor).
ASYNCPG_SETUP_HINT = "Установите зависимости: bash knowledge_os/scripts/setup_knowledge_os.sh"
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

# Попытка импорта expert_validator
try:
    from expert_validator import (
        COORDINATOR_NAMES,
        EXTENDED_FALLBACK_EXPERTS,
        FALLBACK_EXPERTS,
        ValidationResult,
        get_all_experts_info,
        get_db_expert_count,
        get_db_expert_names,
        validate_expert_names,
    )

    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False
    FALLBACK_EXPERTS = ["Дмитрий", "Мария", "Максим"]
    EXTENDED_FALLBACK_EXPERTS = FALLBACK_EXPERTS
    COORDINATOR_NAMES = {"Виктория"}

# Конфигурация подключения к БД
USER_NAME = getpass.getuser()
DEFAULT_DB_URL = (
    os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:5432/knowledge_os"
)

DB_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# Паттерны для поиска хардкодных списков экспертов
HARDCODED_PATTERNS = [
    # Списки в квадратных скобках: ["Дмитрий", "Мария", ...]
    r'\[\s*["\']([А-Яа-яЁё]+)["\'](?:\s*,\s*["\']([А-Яа-яЁё]+)["\'])+\s*\]',
    # Присваивание списка: experts = ["...", "..."]
    r"(?:experts?|team|directors?|war_room)\s*=\s*\[([^\]]+)\]",
    # Строки в промптах с перечислением имён
    r"-\s*([А-Яа-яЁё]+)\s*\([^)]+\)",
]

# Известные имена экспертов: из configs/experts/_known_names_generated.py (после sync_employees.py) или fallback
_known_names_path = PROJECT_ROOT.parent / "configs" / "experts" / "_known_names_generated.py"
if _known_names_path.exists():
    try:
        import importlib.util

        _spec = importlib.util.spec_from_file_location("_known_names", _known_names_path)
        if _spec and _spec.loader:
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            KNOWN_EXPERT_NAMES = getattr(_mod, "KNOWN_EXPERT_NAMES", set())
    except Exception:
        pass
if not KNOWN_EXPERT_NAMES:
    KNOWN_EXPERT_NAMES = {
        "Виктория",
        "Дмитрий",
        "Игорь",
        "Сергей",
        "Анна",
        "Максим",
        "Елена",
        "Алексей",
        "Павел",
        "Мария",
        "Роман",
        "Ольга",
        "Татьяна",
        "Екатерина",
        "Андрей",
        "София",
        "Никита",
        "Дарья",
        "Марина",
        "Юлия",
        "Артем",
        "Анастасия",
        "Яна",
        "Владимир",
        "Глеб",
        "Даниил",
        "Кирилл",
        "Михаил",
        "Александр",
        "Наталья",
        "Светлана",
        "Олег",
        "Вадим",
        "Полина",
        "Ксения",
        "Виталий",
        "Станислав",
        "Денис",
        "Евгений",
        "Илья",
        "Леонид",
        "Тимофей",
        "Валерия",
        "Ульяна",
        "Алла",
        "Борис",
        "Галина",
        "Зоя",
        "Лариса",
        "Инна",
        "Марк",
        "Филипп",
        "Георгий",
        "Василий",
        "Константин",
        "Ирина",
        "Людмила",
        "Вероника",
    }

# Файлы для исключения из сканирования
EXCLUDE_PATTERNS = [
    "**/venv/**",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/node_modules/**",
    "**/check_experts_count.py",  # Сам этот скрипт
    "**/seed_experts.sql",  # Seed файлы - это источник правды
]


class ExpertChecker:
    """Проверяет соответствие хардкодных списков экспертов данным в БД."""

    def __init__(self, db_url: str = DB_URL, verbose: bool = False):
        self.db_url = db_url
        self.verbose = verbose
        self.db_experts: Set[str] = set()
        self.db_experts_info: List[Dict] = []
        self.hardcoded_findings: List[Dict] = []
        self.sql_results: Dict[str, any] = {}

    async def run_sql_count(self) -> int:
        """
        Выполняет SELECT COUNT(*) FROM experts.

        Returns:
            Количество экспертов или -1 при ошибке
        """
        if not ASYNCPG_AVAILABLE:
            return -1

        try:
            conn = await asyncpg.connect(self.db_url)
            result = await conn.fetchval("SELECT COUNT(*) FROM experts")
            await conn.close()
            self.sql_results["count"] = result

            if self.verbose:
                print(f"\n🔢 SELECT COUNT(*) FROM experts: {result}")

            return result or 0
        except Exception as e:
            print(f"❌ Ошибка SQL COUNT: {e}")
            return -1

    async def run_sql_names(self) -> List[str]:
        """
        Выполняет SELECT name FROM experts.

        Returns:
            Список имён экспертов
        """
        if not ASYNCPG_AVAILABLE:
            return []

        try:
            conn = await asyncpg.connect(self.db_url)
            rows = await conn.fetch("SELECT name FROM experts ORDER BY name")
            await conn.close()
            names = [row["name"] for row in rows]
            self.sql_results["names"] = names

            if self.verbose:
                print(f"\n📋 SELECT name FROM experts ({len(names)} записей):")
                for name in names:
                    print(f"   - {name}")

            return names
        except Exception as e:
            print(f"❌ Ошибка SQL names: {e}")
            return []

    async def run_sql_full_info(self) -> List[Dict]:
        """
        Выполняет SELECT name, role, department FROM experts.

        Returns:
            Список словарей с полной информацией об экспертах
        """
        if not ASYNCPG_AVAILABLE:
            return []

        try:
            conn = await asyncpg.connect(self.db_url)
            rows = await conn.fetch("SELECT name, role, department FROM experts ORDER BY name")
            await conn.close()

            info = [dict(row) for row in rows]
            self.sql_results["full_info"] = info
            self.db_experts_info = info

            if self.verbose:
                print(f"\n📊 SELECT name, role, department FROM experts ({len(info)} записей):")
                for row in info:
                    dept = row["department"] or "N/A"
                    print(f"   - {row['name']} | {row['role']} | {dept}")

            return info
        except Exception as e:
            print(f"❌ Ошибка SQL full_info: {e}")
            return []

    async def get_db_experts(self) -> Set[str]:
        """Получает актуальный список экспертов из БД (включая автономно нанятых)."""
        if not ASYNCPG_AVAILABLE:
            print("❌ asyncpg не установлен.", ASYNCPG_SETUP_HINT)
            return set()

        try:
            conn = await asyncpg.connect(self.db_url)
            rows = await conn.fetch(
                "SELECT name, role, department, metadata FROM experts ORDER BY name"
            )
            await conn.close()

            self.db_experts = {row["name"] for row in rows}
            self.db_experts_info = [
                {k: v for k, v in dict(row).items() if k != "metadata"} for row in rows
            ]
            # Автономно нанятые — валидны, даже если не в KNOWN/хардкодах
            self.autonomous_names = {
                row["name"]
                for row in rows
                if (row.get("metadata") or {}).get("is_autonomous") in (True, "true")
            }
            if self.verbose:
                print(
                    f"\n📊 Эксперты в БД ({len(self.db_experts)}), автономных: {len(self.autonomous_names)}"
                )
                for row in rows:
                    dept = row["department"] or "N/A"
                    aut = " [автономный]" if row["name"] in self.autonomous_names else ""
                    print(f"   - {row['name']} ({row['role']}, {dept}){aut}")

            return self.db_experts
        except Exception as e:
            print(f"❌ Ошибка подключения к БД: {e}")
            self.db_experts = set()
            self.autonomous_names = set()
            return set()

    async def validate_fallback_experts(self) -> Optional[ValidationResult]:
        """
        Валидирует FALLBACK_EXPERTS из expert_validator.py.

        Returns:
            ValidationResult или None если validator недоступен
        """
        if not VALIDATOR_AVAILABLE:
            print("⚠️ expert_validator не импортирован, пропускаем валидацию fallback")
            return None

        validation = await validate_expert_names(FALLBACK_EXPERTS, emit_warning=False)

        print(f"\n🔍 Валидация FALLBACK_EXPERTS ({len(FALLBACK_EXPERTS)}):")
        print(f"   Статус: {validation}")

        if validation.missing_names:
            print(f"   ❌ Отсутствуют в БД: {validation.missing_names}")

        if not validation.is_valid and validation.db_expert_count > len(FALLBACK_EXPERTS):
            print(f"   ⚠️ В БД больше экспертов ({validation.db_expert_count}), чем в fallback")

        return validation

    def scan_file(self, file_path: Path) -> List[Dict]:
        """Сканирует файл на наличие хардкодных списков экспертов."""
        findings = []

        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            for line_num, line in enumerate(lines, 1):
                # Ищем русские имена в контексте списков
                found_names = set()

                # Поиск имён в квадратных скобках
                bracket_match = re.findall(r"\[([^\]]+)\]", line)
                for match in bracket_match:
                    names = re.findall(r'["\']([А-Яа-яЁё]+)["\']', match)
                    for name in names:
                        if name in KNOWN_EXPERT_NAMES:
                            found_names.add(name)

                # Поиск имён в строках формата "- Имя (роль)"
                dash_names = re.findall(r"-\s*([А-Яа-яЁё]+)\s*\(", line)
                for name in dash_names:
                    if name in KNOWN_EXPERT_NAMES:
                        found_names.add(name)

                if found_names and len(found_names) >= 2:  # Минимум 2 имени для "списка"
                    findings.append(
                        {
                            "file": str(file_path.relative_to(PROJECT_ROOT)),
                            "line": line_num,
                            "content": line.strip()[:100],
                            "names": found_names,
                        }
                    )

        except Exception as e:
            if self.verbose:
                print(f"⚠️ Не удалось прочитать {file_path}: {e}")

        return findings

    def scan_codebase(self) -> List[Dict]:
        """Сканирует всю кодовую базу на наличие хардкодных списков."""
        print("🔍 Сканирование кодовой базы...")

        all_findings = []

        # Сканируем Python файлы
        for py_file in PROJECT_ROOT.rglob("*.py"):
            # Проверяем исключения
            skip = False
            for pattern in EXCLUDE_PATTERNS:
                if (
                    py_file.match(pattern)
                    or "venv" in str(py_file)
                    or "__pycache__" in str(py_file)
                ):
                    skip = True
                    break

            if skip:
                continue

            findings = self.scan_file(py_file)
            all_findings.extend(findings)

        self.hardcoded_findings = all_findings
        return all_findings

    def analyze_discrepancies(self) -> Tuple[Set[str], Set[str]]:
        """
        Анализирует расхождения между хардкодными списками и БД.
        Автономно нанятые (metadata->>'is_autonomous'='true') — валидны, не флаговать.

        Returns:
            (missing_in_db, missing_in_code): Имена, отсутствующие в БД и в коде
        """
        hardcoded_names = set()
        for finding in self.hardcoded_findings:
            hardcoded_names.update(finding["names"])

        autonomous = getattr(self, "autonomous_names", set())
        missing_in_db = hardcoded_names - self.db_experts
        missing_in_code = (
            self.db_experts - hardcoded_names - {"Виктория"} - autonomous
        )  # Виктория и автономные — исключения

        return missing_in_db, missing_in_code

    def generate_report(self) -> str:
        """Генерирует отчёт о проверке."""
        missing_in_db, missing_in_code = self.analyze_discrepancies()

        report = []
        report.append("=" * 60)
        report.append("📋 ОТЧЁТ О ПРОВЕРКЕ ХАРДКОДНЫХ СПИСКОВ ЭКСПЕРТОВ")
        report.append("=" * 60)
        report.append("")

        # Статистика
        report.append(f"📊 Всего экспертов в БД: {len(self.db_experts)}")
        report.append(f"📍 Найдено мест с хардкодами: {len(self.hardcoded_findings)}")
        report.append("")

        # Найденные хардкоды
        if self.hardcoded_findings:
            report.append("🔴 НАЙДЕННЫЕ ХАРДКОДНЫЕ СПИСКИ:")
            report.append("-" * 40)
            for finding in self.hardcoded_findings:
                report.append(f"  📁 {finding['file']}:{finding['line']}")
                report.append(f"     Имена: {', '.join(sorted(finding['names']))}")
                report.append(f"     Код: {finding['content'][:80]}...")
                report.append("")

        # Расхождения
        if missing_in_db:
            report.append("⚠️ ИМЕНА В КОДЕ, ОТСУТСТВУЮЩИЕ В БД:")
            for name in sorted(missing_in_db):
                report.append(f"   - {name}")
            report.append("")

        if missing_in_code and len(missing_in_code) > 5:
            report.append("ℹ️ ЭКСПЕРТЫ В БД, НЕ УПОМЯНУТЫЕ В ХАРДКОДАХ:")
            report.append("   (это может быть нормально, если используется динамическая загрузка)")
            for name in sorted(list(missing_in_code)[:10]):
                report.append(f"   - {name}")
            if len(missing_in_code) > 10:
                report.append(f"   ... и ещё {len(missing_in_code) - 10}")
            report.append("")

        # Рекомендации
        report.append("💡 РЕКОМЕНДАЦИИ:")
        report.append("-" * 40)

        if self.hardcoded_findings:
            report.append("1. Замените хардкодные списки на динамические запросы к БД:")
            report.append("   experts = await get_available_experts()")
            report.append("")
            report.append("2. Если динамическая загрузка невозможна, добавьте комментарий:")
            report.append(
                "   # TODO: Список может быть неполным. Проверьте через check_experts_count.py"
            )
            report.append("")

        if missing_in_db:
            report.append("3. Добавьте отсутствующих экспертов в БД или удалите из кода:")
            for name in sorted(missing_in_db):
                report.append(f"   INSERT INTO experts (name, role) VALUES ('{name}', 'TBD');")
            report.append("")

        # Итог
        report.append("=" * 60)
        if not self.hardcoded_findings and not missing_in_db:
            report.append("✅ ПРОВЕРКА ПРОЙДЕНА: Нет критических расхождений")
        elif missing_in_db:
            report.append("❌ ПРОВЕРКА НЕ ПРОЙДЕНА: Обнаружены расхождения с БД")
        else:
            report.append("⚠️ ВНИМАНИЕ: Найдены хардкодные списки, рекомендуется рефакторинг")
        report.append("=" * 60)

        return "\n".join(report)


async def main():
    parser = argparse.ArgumentParser(
        description="Проверка соответствия хардкодных списков экспертов данным в БД"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    parser.add_argument(
        "--dry-run", action="store_true", help="Только показать, что будет проверено"
    )
    parser.add_argument("--fix", action="store_true", help="Предложить автоматические исправления")
    parser.add_argument("--no-confirm", action="store_true", help="Не запрашивать подтверждение")
    parser.add_argument(
        "--sql-only",
        action="store_true",
        help="Только выполнить SQL запросы (без сканирования кода)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🔍 ПРОВЕРКА ХАРДКОДНЫХ СПИСКОВ ЭКСПЕРТОВ")
    print(f"   Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"📁 Корень проекта: {PROJECT_ROOT}")
    print(f"🗄️  База данных: {DB_URL.split('@')[1] if '@' in DB_URL else DB_URL}")
    print(f"📦 expert_validator: {'✅ доступен' if VALIDATOR_AVAILABLE else '❌ не импортирован'}")
    print("")

    if args.dry_run:
        print("🔄 Режим dry-run: только сканирование кода")
        checker = ExpertChecker(verbose=args.verbose)
        findings = checker.scan_codebase()
        print(f"\n📍 Найдено {len(findings)} мест с потенциальными хардкодами")
        for f in findings[:10]:
            print(f"   - {f['file']}:{f['line']}: {', '.join(f['names'])}")
        return

    # Запрос подтверждения
    if not args.no_confirm:
        print("⚠️  Этот скрипт выполнит:")
        print("   1. SQL запросы к БД:")
        print("      - SELECT COUNT(*) FROM experts")
        print("      - SELECT name FROM experts")
        print("      - SELECT name, role, department FROM experts")
        if not args.sql_only:
            print("   2. Сканирование всех .py файлов в проекте")
            print("   3. Валидация FALLBACK_EXPERTS из expert_validator.py")
            print("   4. Генерация отчёта о расхождениях")
        print("")
        confirm = input("Продолжить? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes", "д", "да"):
            print("❌ Отменено пользователем")
            return

    print("")

    # Создаём checker и выполняем проверку
    checker = ExpertChecker(db_url=DB_URL, verbose=args.verbose)

    # =========================================================================
    # ВЫПОЛНЕНИЕ SQL ЗАПРОСОВ
    # =========================================================================
    print("=" * 60)
    print("📊 ВЫПОЛНЕНИЕ SQL ЗАПРОСОВ")
    print("=" * 60)

    # 1. SELECT COUNT(*)
    count = await checker.run_sql_count()
    if count >= 0:
        print(f"\n✅ SELECT COUNT(*) FROM experts: {count}")
    else:
        print("\n❌ Не удалось выполнить SELECT COUNT(*)")

    # 2. SELECT name
    names = await checker.run_sql_names()
    if names:
        print(f"\n✅ SELECT name FROM experts: {len(names)} записей")
        if args.verbose:
            for name in names:
                fallback_mark = " ⭐" if name in FALLBACK_EXPERTS else ""
                print(f"      - {name}{fallback_mark}")
    else:
        print("\n❌ Не удалось выполнить SELECT name")

    # 3. SELECT full info
    info = await checker.run_sql_full_info()
    if info:
        print(f"\n✅ SELECT name, role, department FROM experts: {len(info)} записей")
        if args.verbose:
            for row in info:
                dept = row["department"] or "N/A"
                print(f"      - {row['name']} | {row['role']} | {dept}")

    # Если только SQL - выходим
    if args.sql_only:
        print("\n" + "=" * 60)
        print("✅ SQL запросы выполнены")
        print("=" * 60)
        return

    # =========================================================================
    # ВАЛИДАЦИЯ FALLBACK
    # =========================================================================
    print("\n" + "=" * 60)
    print("🔍 ВАЛИДАЦИЯ FALLBACK СПИСКОВ")
    print("=" * 60)

    validation = await checker.validate_fallback_experts()

    # Также валидируем extended fallback
    if VALIDATOR_AVAILABLE:
        ext_validation = await validate_expert_names(EXTENDED_FALLBACK_EXPERTS, emit_warning=False)
        print(f"\n🔍 Валидация EXTENDED_FALLBACK_EXPERTS ({len(EXTENDED_FALLBACK_EXPERTS)}):")
        print(f"   Статус: {ext_validation}")

    # =========================================================================
    # СКАНИРОВАНИЕ КОДА
    # =========================================================================
    print("\n" + "=" * 60)
    print("📂 СКАНИРОВАНИЕ КОДОВОЙ БАЗЫ")
    print("=" * 60)

    # Сканируем код
    checker.scan_codebase()

    # Генерируем и выводим отчёт
    report = checker.generate_report()
    print(report)

    # =========================================================================
    # СОХРАНЕНИЕ ОТЧЁТА
    # =========================================================================
    report_path = PROJECT_ROOT / "scripts" / "reports" / "experts_check_report.txt"
    report_path.parent.mkdir(exist_ok=True)

    # Добавляем timestamp и SQL результаты в отчёт
    full_report = f"""Дата проверки: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
БД: {DB_URL.split("@")[1] if "@" in DB_URL else DB_URL}

SQL РЕЗУЛЬТАТЫ:
  SELECT COUNT(*) FROM experts: {checker.sql_results.get("count", "N/A")}
  SELECT name FROM experts: {len(checker.sql_results.get("names", []))} записей

FALLBACK ВАЛИДАЦИЯ:
  FALLBACK_EXPERTS: {FALLBACK_EXPERTS}
  Валиден: {validation.is_valid if validation else "N/A"}

{report}
"""

    report_path.write_text(full_report, encoding="utf-8")
    print(f"\n📄 Отчёт сохранён: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
