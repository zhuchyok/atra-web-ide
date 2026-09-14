"""
Sandbox — изолированное тестирование исправлений перед деплоем.

Позволяет Victoria:
1. Создать snapshot текущего состояния
2. Применить исправление в sandbox
3. Протестировать
4. Если все ок → применить в продакшн
5. Если нет → откатить
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Sandbox directory
SANDBOX_DIR = Path(os.getenv("SANDBOX_DIR", "/tmp/victoria-sandbox"))

# Max sandbox size
MAX_SANDBOX_SIZE_MB = int(os.getenv("MAX_SANDBOX_SIZE_MB", "500"))


class Sandbox:
    """
    Изолированная среда для тестирования исправлений.

    Workflow:
    1. snapshot() — создать снимок текущего состояния
    2. apply_fix() — применить исправление в sandbox
    3. test() — запустить тесты
    4. deploy() — применить в продакшн если тесты прошли
    5. rollback() — откатить если что-то пошло не так
    """

    def __init__(self):
        self.sandbox_id: Optional[str] = None
        self.sandbox_path: Optional[Path] = None
        self.snapshot_path: Optional[Path] = None
        self._initialized = False

    async def initialize(self):
        """Инициализация sandbox директории."""
        if self._initialized:
            return

        try:
            SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
            self._initialized = True
            logger.info(f"✅ [SANDBOX] Инициализирована: {SANDBOX_DIR}")
        except Exception as e:
            logger.error(f"❌ [SANDBOX] Ошибка инициализации: {e}")

    async def snapshot(self, files: List[str]) -> str:
        """
        Создать snapshot указанных файлов.
        Возвращает sandbox_id для дальнейших операций.
        """
        if not self._initialized:
            await self.initialize()

        self.sandbox_id = f"sandbox_{int(time.time())}_{os.getpid()}"
        self.sandbox_path = SANDBOX_DIR / self.sandbox_id
        self.sandbox_path.mkdir(parents=True, exist_ok=True)

        self.snapshot_path = self.sandbox_path / "snapshot"
        self.snapshot_path.mkdir(parents=True, exist_ok=True)

        snapshot_manifest = {
            "sandbox_id": self.sandbox_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": {},
        }

        for file_path in files:
            src = Path(file_path)
            if src.exists():
                # Создаем структуру директорий
                rel_path = src.relative_to(src.anchor) if src.is_absolute() else src
                dst = self.snapshot_path / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)

                # Копируем файл
                shutil.copy2(src, dst)
                snapshot_manifest["files"][str(file_path)] = {
                    "size": src.stat().st_size,
                    "mtime": src.stat().st_mtime,
                }
                logger.debug(f"📸 [SANDBOX] Snapshot: {file_path}")

        # Сохраняем манифест
        manifest_path = self.sandbox_path / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(snapshot_manifest, f, indent=2)

        logger.info(
            f"📸 [SANDBOX] Snapshot создан: {self.sandbox_id} | "
            f"Файлов: {len(files)}"
        )
        return self.sandbox_id

    async def apply_fix(self, file_path: str, new_content: str) -> bool:
        """
        Применить исправление в sandbox.
        """
        if not self.sandbox_path:
            logger.error("❌ [SANDBOX] Snapshot не создан")
            return False

        try:
            src = Path(file_path)
            rel_path = src.relative_to(src.anchor) if src.is_absolute() else src
            dst = self.sandbox_path / "snapshot" / rel_path

            # Создаем директорию если нужно
            dst.parent.mkdir(parents=True, exist_ok=True)

            # Записываем исправление
            with open(dst, "w") as f:
                f.write(new_content)

            logger.info(f"🔧 [SANDBOX] Fix применен: {file_path}")
            return True

        except Exception as e:
            logger.error(f"❌ [SANDBOX] Ошибка применения fix: {e}")
            return False

    async def test(self, test_command: Optional[str] = None) -> Dict:
        """
        Протестировать исправление в sandbox.
        """
        if not self.sandbox_path:
            return {"success": False, "error": "Snapshot не создан"}

        results = {
            "success": True,
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "errors": [],
        }

        snapshot_dir = self.sandbox_path / "snapshot"

        # 1. Проверяем синтаксис Python файлов
        python_files = list(snapshot_dir.rglob("*.py"))
        for py_file in python_files:
            results["tests_run"] += 1
            try:
                result = subprocess.run(
                    ["python3", "-m", "py_compile", str(py_file)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    results["tests_passed"] += 1
                else:
                    results["tests_failed"] += 1
                    results["errors"].append({
                        "file": str(py_file),
                        "error": result.stderr[:500],
                    })
                    results["success"] = False
            except subprocess.TimeoutExpired:
                results["tests_failed"] += 1
                results["errors"].append({
                    "file": str(py_file),
                    "error": "Compilation timeout",
                })
                results["success"] = False
            except Exception as e:
                results["tests_failed"] += 1
                results["errors"].append({
                    "file": str(py_file),
                    "error": str(e)[:500],
                })
                results["success"] = False

        # 2. Запускаем кастомные тесты если указаны
        if test_command:
            results["tests_run"] += 1
            try:
                result = subprocess.run(
                    test_command,
                    shell=True,
                    cwd=str(snapshot_dir),
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    results["tests_passed"] += 1
                else:
                    results["tests_failed"] += 1
                    results["errors"].append({
                        "test": test_command,
                        "error": result.stderr[:500],
                    })
                    results["success"] = False
            except subprocess.TimeoutExpired:
                results["tests_failed"] += 1
                results["errors"].append({
                    "test": test_command,
                    "error": "Test timeout",
                })
                results["success"] = False
            except Exception as e:
                results["tests_failed"] += 1
                results["errors"].append({
                    "test": test_command,
                    "error": str(e)[:500],
                })
                results["success"] = False

        logger.info(
            f"{'✅' if results['success'] else '❌'} [SANDBOX] Тестирование: "
            f"{results['tests_passed']}/{results['tests_run']} passed"
        )
        return results

    async def deploy(self) -> bool:
        """
        Применить исправление из sandbox в продакшн.
        """
        if not self.sandbox_path or not self.snapshot_path:
            logger.error("❌ [SANDBOX] Snapshot не создан")
            return False

        try:
            manifest_path = self.sandbox_path / "manifest.json"
            with open(manifest_path) as f:
                manifest = json.load(f)

            deployed_count = 0
            for file_path in manifest["files"]:
                src = self.snapshot_path / Path(file_path).relative_to(
                    Path(file_path).anchor
                )
                dst = Path(file_path)

                if src.exists():
                    # Копируем в продакшн
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    deployed_count += 1
                    logger.info(f"🚀 [SANDBOX] Deployed: {file_path}")

            logger.info(
                f"✅ [SANDBOX] Deploy завершен: {deployed_count} файлов"
            )
            return True

        except Exception as e:
            logger.error(f"❌ [SANDBOX] Ошибка deploy: {e}")
            return False

    async def rollback(self) -> bool:
        """
        Откатить изменения из sandbox.
        Восстанавливает оригинальные файлы из snapshot.
        """
        if not self.sandbox_path or not self.snapshot_path:
            logger.error("❌ [SANDBOX] Snapshot не создан")
            return False

        try:
            manifest_path = self.sandbox_path / "manifest.json"
            with open(manifest_path) as f:
                manifest = json.load(f)

            restored_count = 0
            for file_path, info in manifest["files"].items():
                dst = Path(file_path)
                if dst.exists():
                    # Восстанавливаем из snapshot
                    src = self.snapshot_path / Path(file_path).relative_to(
                        Path(file_path).anchor
                    )
                    if src.exists():
                        shutil.copy2(src, dst)
                        restored_count += 1
                        logger.info(f"↩️ [SANDBOX] Restored: {file_path}")

            logger.info(
                f"✅ [SANDBOX] Rollback завершен: {restored_count} файлов"
            )
            return True

        except Exception as e:
            logger.error(f"❌ [SANDBOX] Ошибка rollback: {e}")
            return False

    async def cleanup(self):
        """Очистить sandbox."""
        if self.sandbox_path and self.sandbox_path.exists():
            shutil.rmtree(self.sandbox_path)
            logger.info(f"🧹 [SANDBOX] Очищен: {self.sandbox_id}")
            self.sandbox_id = None
            self.sandbox_path = None
            self.snapshot_path = None

    async def get_status(self) -> Dict:
        """Получить статус sandbox."""
        if not self.sandbox_path:
            return {"active": False}

        manifest_path = self.sandbox_path / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
            return {
                "active": True,
                "sandbox_id": self.sandbox_id,
                "files": len(manifest.get("files", {})),
                "created_at": manifest.get("created_at"),
            }

        return {"active": True, "sandbox_id": self.sandbox_id}


# Singleton
_sandbox: Optional[Sandbox] = None


def get_sandbox() -> Sandbox:
    """Получить singleton Sandbox."""
    global _sandbox
    if _sandbox is None:
        _sandbox = Sandbox()
    return _sandbox
