#!/usr/bin/env python3
"""
Скрипт синхронизации данных команды через Git.

Синхронизирует:
- Базы знаний сотрудников (scripts/*_knowledge.md)
- Программы обучения (scripts/learning_programs/*_program.md)
- Правила (.cursorrules)
- Управление командой (observability/team_member_manager.py)
- Общие данные команды
"""

import os
import shutil
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

# Конфигурация синхронизации
SYNC_CONFIG = {
    "remote_repo": os.getenv("TEAM_DATA_REPO", "https://github.com/your-org/team-data.git"),
    "local_dir": os.getenv("TEAM_DATA_DIR", ".team_data"),
    "sync_files": [
        # Базы знаний
        "scripts/*_knowledge.md",
        # Программы обучения
        "scripts/learning_programs/*_program.md",
        # Правила
        ".cursorrules",
        # Управление командой
        "observability/team_member_manager.py",
        "observability/expert_selector.py",
        "observability/knowledge_base.py",
        "observability/retrospective.py",
        # Общие данные
        "observability/continuous_learning.py",
        "observability/best_practices_searcher.py",
    ],
    "exclude_patterns": [
        "__pycache__",
        "*.pyc",
        ".git",
        ".DS_Store",
    ],
}


class TeamDataSync:
    """Класс для синхронизации данных команды через Git."""

    def __init__(self, config: Dict = None):
        self.config = config or SYNC_CONFIG
        self.local_dir = Path(self.config["local_dir"])
        self.remote_repo = self.config["remote_repo"]
        self.project_root = Path(__file__).parent.parent

    def ensure_git_repo(self) -> bool:
        """Проверяет и инициализирует Git репозиторий для данных команды."""
        if not self.local_dir.exists():
            print(f"📁 Создание директории для данных команды: {self.local_dir}")
            self.local_dir.mkdir(parents=True, exist_ok=True)

        git_dir = self.local_dir / ".git"
        if not git_dir.exists():
            print(f"🔧 Инициализация Git репозитория...")
            try:
                subprocess.run(
                    ["git", "init"],
                    cwd=self.local_dir,
                    check=True,
                    capture_output=True,
                )
                # Настройка remote если указан
                if self.remote_repo:
                    subprocess.run(
                        ["git", "remote", "add", "origin", self.remote_repo],
                        cwd=self.local_dir,
                        check=True,
                        capture_output=True,
                    )
                print("✅ Git репозиторий инициализирован")
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ Ошибка инициализации Git: {e}")
                return False
        return True

    def collect_team_data(self) -> Dict[str, List[str]]:
        """Собирает все файлы данных команды."""
        files = {
            "knowledge_bases": [],
            "learning_programs": [],
            "rules": [],
            "management": [],
            "other": [],
        }

        # Базы знаний
        knowledge_dir = self.project_root / "scripts"
        if knowledge_dir.exists():
            for file in knowledge_dir.glob("*_knowledge.md"):
                files["knowledge_bases"].append(str(file.relative_to(self.project_root)))

        # Программы обучения
        learning_dir = self.project_root / "scripts" / "learning_programs"
        if learning_dir.exists():
            for file in learning_dir.glob("*_program.md"):
                files["learning_programs"].append(
                    str(file.relative_to(self.project_root))
                )

        # Правила
        rules_file = self.project_root / ".cursorrules"
        if rules_file.exists():
            files["rules"].append(".cursorrules")

        # Управление командой
        observability_dir = self.project_root / "observability"
        if observability_dir.exists():
            for file in observability_dir.glob("*.py"):
                if any(
                    pattern in file.name
                    for pattern in [
                        "team_member",
                        "expert_selector",
                        "knowledge_base",
                        "retrospective",
                        "continuous_learning",
                        "best_practices",
                    ]
                ):
                    files["management"].append(
                        str(file.relative_to(self.project_root))
                    )

        return files

    def sync_to_central(self, push: bool = False) -> bool:
        """Синхронизирует данные в центральный репозиторий."""
        if not self.ensure_git_repo():
            return False

        print("📦 Сбор данных команды...")
        files = self.collect_team_data()

        # Копирование файлов в центральный репозиторий
        for category, file_list in files.items():
            for file_path in file_list:
                src = self.project_root / file_path
                if src.exists():
                    # Сохраняем структуру директорий
                    dst = self.local_dir / file_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    print(f"  ✅ {file_path}")

        # Создание индекса файлов
        index_file = self.local_dir / "team_data_index.json"
        index_data = {
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "files": files,
            "project": str(self.project_root.name),
        }
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)

        # Git commit
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.local_dir,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"Sync team data from {self.project_root.name} - {datetime.now(timezone.utc).isoformat()}",
                ],
                cwd=self.local_dir,
                check=True,
                capture_output=True,
            )
            print("✅ Данные закоммичены в локальный репозиторий")

            if push and self.remote_repo:
                subprocess.run(
                    ["git", "push", "origin", "main"],
                    cwd=self.local_dir,
                    check=True,
                    capture_output=True,
                )
                print("✅ Данные отправлены в удаленный репозиторий")

            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка Git операций: {e}")
            return False

    def sync_from_central(self, pull: bool = True) -> bool:
        """Синхронизирует данные из центрального репозитория."""
        if not self.local_dir.exists():
            print(f"❌ Центральный репозиторий не найден: {self.local_dir}")
            return False

        if pull:
            try:
                subprocess.run(
                    ["git", "pull", "origin", "main"],
                    cwd=self.local_dir,
                    check=True,
                    capture_output=True,
                )
                print("✅ Данные обновлены из удаленного репозитория")
            except subprocess.CalledProcessError as e:
                print(f"⚠️ Не удалось обновить из удаленного репозитория: {e}")

        # Чтение индекса
        index_file = self.local_dir / "team_data_index.json"
        if not index_file.exists():
            print("❌ Индекс данных не найден")
            return False

        with open(index_file, "r", encoding="utf-8") as f:
            index_data = json.load(f)

        # Копирование файлов обратно в проект
        files = index_data.get("files", {})
        for category, file_list in files.items():
            for file_path in file_list:
                src = self.local_dir / file_path
                if src.exists():
                    dst = self.project_root / file_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    print(f"  ✅ {file_path}")

        print("✅ Данные синхронизированы в проект")
        return True

    def status(self) -> Dict:
        """Показывает статус синхронизации."""
        status = {
            "local_repo_exists": self.local_dir.exists(),
            "git_initialized": (self.local_dir / ".git").exists() if self.local_dir.exists() else False,
            "files_count": 0,
            "last_sync": None,
        }

        if self.local_dir.exists():
            index_file = self.local_dir / "team_data_index.json"
            if index_file.exists():
                with open(index_file, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                    status["last_sync"] = index_data.get("last_sync")
                    status["files_count"] = sum(
                        len(files) for files in index_data.get("files", {}).values()
                    )

        return status


def main():
    """Главная функция для CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Синхронизация данных команды через Git")
    parser.add_argument(
        "action",
        choices=["sync", "pull", "push", "status"],
        help="Действие: sync (в обе стороны), pull (из центра), push (в центр), status (статус)",
    )
    parser.add_argument(
        "--remote",
        help="URL удаленного репозитория (переопределяет TEAM_DATA_REPO)",
    )
    parser.add_argument(
        "--local-dir",
        help="Локальная директория для данных (переопределяет TEAM_DATA_DIR)",
    )

    args = parser.parse_args()

    config = SYNC_CONFIG.copy()
    if args.remote:
        config["remote_repo"] = args.remote
    if args.local_dir:
        config["local_dir"] = args.local_dir

    sync = TeamDataSync(config)

    if args.action == "status":
        status = sync.status()
        print("\n📊 Статус синхронизации:")
        print(f"  Локальный репозиторий: {'✅' if status['local_repo_exists'] else '❌'}")
        print(f"  Git инициализирован: {'✅' if status['git_initialized'] else '❌'}")
        print(f"  Файлов: {status['files_count']}")
        if status["last_sync"]:
            print(f"  Последняя синхронизация: {status['last_sync']}")
    elif args.action == "sync":
        print("🔄 Синхронизация данных команды...")
        sync.sync_to_central(push=False)
        sync.sync_from_central(pull=False)
    elif args.action == "pull":
        print("⬇️ Загрузка данных из центрального репозитория...")
        sync.sync_from_central(pull=True)
    elif args.action == "push":
        print("⬆️ Отправка данных в центральный репозиторий...")
        sync.sync_to_central(push=True)


if __name__ == "__main__":
    main()

