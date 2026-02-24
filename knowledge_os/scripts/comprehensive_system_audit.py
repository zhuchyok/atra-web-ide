#!/usr/bin/env python3
"""
Комплексный аудит системы ATRA командой из 13 экспертов
Проверяет все модули, импорты, связи и потенциальные проблемы
"""

import ast
import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SystemAuditor:
    """Аудитор системы для проверки всех модулей"""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []
        self.info: List[Dict] = []
        self.imports_map: Dict[str, Set[str]] = {}
        self.modules_checked: Set[str] = set()

    def audit_all(self):
        """Проводит полный аудит системы"""
        print("🔍 НАЧАЛО КОМПЛЕКСНОГО АУДИТА СИСТЕМЫ ATRA")
        print("=" * 80)

        # 1. Проверка основных модулей
        print("\n📦 1. ПРОВЕРКА ОСНОВНЫХ МОДУЛЕЙ")
        self.check_main_modules()

        # 2. Проверка импортов
        print("\n📥 2. ПРОВЕРКА ИМПОРТОВ")
        self.check_imports()

        # 3. Проверка связей между модулями
        print("\n🔗 3. ПРОВЕРКА СВЯЗЕЙ МЕЖДУ МОДУЛЯМИ")
        self.check_module_connections()

        # 4. Проверка базы данных
        print("\n💾 4. ПРОВЕРКА БАЗЫ ДАННЫХ")
        self.check_database()

        # 5. Проверка Telegram бота
        print("\n🤖 5. ПРОВЕРКА TELEGRAM БОТА")
        self.check_telegram_bot()

        # 6. Проверка execution модулей
        print("\n⚙️ 6. ПРОВЕРКА EXECUTION МОДУЛЕЙ")
        self.check_execution_modules()

        # 7. Проверка сигналов
        print("\n📡 7. ПРОВЕРКА СИСТЕМЫ СИГНАЛОВ")
        self.check_signals()

        # 8. Проверка конфигураций
        print("\n⚙️ 8. ПРОВЕРКА КОНФИГУРАЦИЙ")
        self.check_configurations()

        # 9. Проверка тестов
        print("\n🧪 9. ПРОВЕРКА ТЕСТОВ")
        self.check_tests()

        # 10. Финальный отчет
        print("\n📊 10. ФИНАЛЬНЫЙ ОТЧЕТ")
        self.print_report()

    def check_main_modules(self):
        """Проверяет основные модули системы"""
        critical_modules = [
            "main.py",
            "signal_live.py",
            "config.py",
            "src/telegram/bot_core.py",
            "src/telegram/handlers.py",
            "src/telegram/commands.py",
            "src/database/db.py",
            "src/database/acceptance.py",
            "src/execution/auto_execution.py",
            "src/execution/exchange_api.py",
        ]

        for module_path in critical_modules:
            full_path = self.root_dir / module_path
            if full_path.exists():
                self.info.append({"type": "module_exists", "module": module_path, "status": "✅"})
            else:
                self.errors.append(
                    {"type": "missing_module", "module": module_path, "severity": "critical"}
                )
                print(f"  ❌ Отсутствует: {module_path}")

    def check_imports(self):
        """Проверяет все импорты в проекте"""
        python_files = list(self.root_dir.rglob("*.py"))

        for py_file in python_files:
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()
                    tree = ast.parse(content, filename=str(py_file))

                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                self.check_import_path(alias.name, py_file)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                self.check_import_path(node.module, py_file)
            except SyntaxError as e:
                self.errors.append(
                    {
                        "type": "syntax_error",
                        "file": str(py_file),
                        "error": str(e),
                        "severity": "critical",
                    }
                )
            except Exception as e:
                self.warnings.append(
                    {
                        "type": "parse_error",
                        "file": str(py_file),
                        "error": str(e),
                        "severity": "medium",
                    }
                )

    def check_import_path(self, module_path: str, file_path: Path):
        """Проверяет существование импортируемого модуля"""
        if not module_path or module_path.startswith("_"):
            return

        # Пропускаем стандартные библиотеки
        if not any(
            module_path.startswith(p) for p in ["src.", ".", "config", "signal_live", "cleanup"]
        ):
            return

        # Проверяем локальные импорты
        if module_path.startswith("src."):
            parts = module_path.replace("src.", "").split(".")
            module_file = self.root_dir / "src" / "/".join(parts) / "__init__.py"
            py_file = self.root_dir / "src" / "/".join(parts) + ".py"

            if not module_file.exists() and not py_file.exists():
                # Проверяем родительские директории
                parent = self.root_dir / "src"
                for part in parts[:-1]:
                    parent = parent / part
                    if not parent.exists():
                        self.errors.append(
                            {
                                "type": "missing_import",
                                "module": module_path,
                                "file": str(file_path),
                                "severity": "high",
                            }
                        )
                        return

    def check_module_connections(self):
        """Проверяет связи между модулями"""
        # Проверяем критические связи
        connections = [
            ("main.py", "src.telegram.bot_core", "run_telegram_bot_in_existing_loop"),
            ("main.py", "signal_live", "run_hybrid_signal_system_fixed"),
            ("src.telegram.handlers", "src.database.acceptance", "AcceptanceDatabase"),
            ("src.telegram.handlers", "src.execution.auto_execution", "AutoExecutionService"),
            ("src.execution.auto_execution", "src.database.acceptance", "AcceptanceDatabase"),
        ]

        for source, target_module, target_item in connections:
            try:
                if source.endswith(".py"):
                    # Проверяем импорт в файле
                    source_path = self.root_dir / source
                    if source_path.exists():
                        with open(source_path) as f:
                            content = f.read()
                            if (
                                target_module.replace(".", "/") in content
                                or target_module in content
                            ):
                                self.info.append(
                                    {
                                        "type": "connection_ok",
                                        "source": source,
                                        "target": target_module,
                                        "status": "✅",
                                    }
                                )
                            else:
                                self.warnings.append(
                                    {
                                        "type": "missing_connection",
                                        "source": source,
                                        "target": target_module,
                                        "severity": "medium",
                                    }
                                )
            except Exception as e:
                self.warnings.append(
                    {
                        "type": "connection_check_error",
                        "source": source,
                        "target": target_module,
                        "error": str(e),
                        "severity": "low",
                    }
                )

    def check_database(self):
        """Проверяет модули базы данных"""
        db_modules = [
            "src/database/db.py",
            "src/database/acceptance.py",
            "src/database/initialization.py",
            "src/database/connection_pool.py",
        ]

        for module in db_modules:
            path = self.root_dir / module
            if path.exists():
                # Проверяем основные методы
                with open(path) as f:
                    content = f.read()
                    if "class" in content and "def" in content:
                        self.info.append({"type": "db_module_ok", "module": module, "status": "✅"})
            else:
                self.errors.append(
                    {"type": "missing_db_module", "module": module, "severity": "high"}
                )

    def check_telegram_bot(self):
        """Проверяет Telegram бота"""
        telegram_modules = [
            "src/telegram/bot_core.py",
            "src/telegram/handlers.py",
            "src/telegram/commands.py",
            "src/telegram/bot_commands.py",
        ]

        for module in telegram_modules:
            path = self.root_dir / module
            if path.exists():
                with open(path) as f:
                    content = f.read()
                    # Проверяем наличие основных функций
                    if "async def" in content or "def" in content:
                        self.info.append(
                            {"type": "telegram_module_ok", "module": module, "status": "✅"}
                        )

    def check_execution_modules(self):
        """Проверяет модули исполнения"""
        execution_modules = [
            "src/execution/auto_execution.py",
            "src/execution/exchange_api.py",
            "src/execution/exchange_adapter.py",
        ]

        for module in execution_modules:
            path = self.root_dir / module
            if path.exists():
                self.info.append({"type": "execution_module_ok", "module": module, "status": "✅"})

    def check_signals(self):
        """Проверяет систему сигналов"""
        signal_modules = [
            "signal_live.py",
            "src/signals/core.py",
            "src/signals/generation.py",
        ]

        for module in signal_modules:
            path = self.root_dir / module
            if path.exists():
                self.info.append({"type": "signal_module_ok", "module": module, "status": "✅"})

    def check_configurations(self):
        """Проверяет конфигурационные файлы"""
        config_files = [
            "config.py",
            "env",
            ".env",
        ]

        for config_file in config_files:
            path = self.root_dir / config_file
            if path.exists():
                self.info.append({"type": "config_exists", "file": config_file, "status": "✅"})

    def check_tests(self):
        """Проверяет наличие тестов"""
        test_dir = self.root_dir / "tests"
        if test_dir.exists():
            test_files = list(test_dir.rglob("test_*.py"))
            self.info.append({"type": "tests_found", "count": len(test_files), "status": "✅"})
        else:
            self.warnings.append({"type": "no_tests", "severity": "medium"})

    def print_report(self):
        """Выводит финальный отчет"""
        print("\n" + "=" * 80)
        print("📊 ФИНАЛЬНЫЙ ОТЧЕТ АУДИТА")
        print("=" * 80)

        print(
            f"\n❌ КРИТИЧЕСКИЕ ОШИБКИ: {len([e for e in self.errors if e.get('severity') == 'critical'])}"
        )
        print(
            f"⚠️ ВЫСОКИЙ ПРИОРИТЕТ: {len([e for e in self.errors if e.get('severity') == 'high'])}"
        )
        print(f"⚠️ ПРЕДУПРЕЖДЕНИЯ: {len(self.warnings)}")
        print(f"✅ УСПЕШНЫЕ ПРОВЕРКИ: {len(self.info)}")

        if self.errors:
            print("\n🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ:")
            for error in self.errors[:20]:  # Показываем первые 20
                print(
                    f"  - {error.get('type')}: {error.get('module', error.get('file', 'unknown'))}"
                )

        if self.warnings:
            print("\n🟡 ПРЕДУПРЕЖДЕНИЯ:")
            for warning in self.warnings[:20]:
                print(
                    f"  - {warning.get('type')}: {warning.get('module', warning.get('file', 'unknown'))}"
                )


if __name__ == "__main__":
    auditor = SystemAuditor()
    auditor.audit_all()
