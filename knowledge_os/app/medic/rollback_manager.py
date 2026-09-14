"""
Rollback Manager — автоматический откат исправлений.

Отслеживает все изменения файлов и позволяет:
1. Сохранить snapshot перед изменением
2. Откатить одно изменение
3. Откатить все изменения за период
4. Автоматический откат если исправление сломало тесты
"""

import asyncio
import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Rollback storage
ROLLBACK_DIR = Path(os.getenv("ROLLBACK_DIR", "/tmp/victoria-rollback"))

# Max rollback history
MAX_ROLLBACK_HISTORY = int(os.getenv("MAX_ROLLBACK_HISTORY", "100"))


class RollbackEntry:
    """Запись об изменении для возможности отката."""

    def __init__(
        self,
        change_id: str,
        file_path: str,
        old_content: str,
        new_content: str,
        reason: str,
        timestamp: str,
    ):
        self.change_id = change_id
        self.file_path = file_path
        self.old_content = old_content
        self.new_content = new_content
        self.reason = reason
        self.timestamp = timestamp
        self.rolled_back = False
        self.rolled_back_at: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "change_id": self.change_id,
            "file_path": self.file_path,
            "old_content": self.old_content[:1000],  # Truncate for storage
            "new_content": self.new_content[:1000],
            "reason": self.reason,
            "timestamp": self.timestamp,
            "rolled_back": self.rolled_back,
            "rolled_back_at": self.rolled_back_at,
        }


class RollbackManager:
    """
    Менеджер отката изменений.

    Workflow:
    1. before_change() — сохранить состояние перед изменением
    2. after_change() — записать изменение
    3. rollback() — откатить изменение
    4. rollback_all() — откатить все изменения за период
    """

    def __init__(self):
        self.changes: List[RollbackEntry] = []
        self._initialized = False

    async def initialize(self):
        """Инициализация."""
        if self._initialized:
            return

        try:
            ROLLBACK_DIR.mkdir(parents=True, exist_ok=True)
            self._initialized = True
            logger.info(f"✅ [ROLLBACK] Инициализирован: {ROLLBACK_DIR}")
        except Exception as e:
            logger.error(f"❌ [ROLLBACK] Ошибка инициализации: {e}")

    async def before_change(self, file_path: str) -> str:
        """
        Сохранить состояние файла перед изменением.
        Возвращает change_id для отката.
        """
        if not self._initialized:
            await self.initialize()

        change_id = f"change_{int(time.time())}_{os.getpid()}"

        try:
            src = Path(file_path)
            if src.exists():
                with open(src, "r") as f:
                    old_content = f.read()
            else:
                old_content = ""

            # Сохраняем в ROLLBACK_DIR
            rollback_file = ROLLBACK_DIR / f"{change_id}.json"
            rollback_data = {
                "change_id": change_id,
                "file_path": file_path,
                "old_content": old_content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            with open(rollback_file, "w") as f:
                json.dump(rollback_data, f)

            logger.debug(f"📸 [ROLLBACK] Snapshot: {file_path} → {change_id}")
            return change_id

        except Exception as e:
            logger.error(f"❌ [ROLLBACK] Ошибка snapshot: {e}")
            return ""

    async def after_change(
        self,
        change_id: str,
        file_path: str,
        new_content: str,
        reason: str = "",
    ):
        """Записать изменение после применения."""
        try:
            entry = RollbackEntry(
                change_id=change_id,
                file_path=file_path,
                old_content="",  # Уже сохранена в before_change
                new_content=new_content,
                reason=reason,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            self.changes.append(entry)

            # Обновляем файл отката
            rollback_file = ROLLBACK_DIR / f"{change_id}.json"
            if rollback_file.exists():
                with open(rollback_file) as f:
                    data = json.load(f)
                data["new_content"] = new_content[:1000]
                data["reason"] = reason
                with open(rollback_file, "w") as f:
                    json.dump(data, f)

            logger.info(f"📝 [ROLLBACK] Изменение записано: {change_id} | {file_path}")

        except Exception as e:
            logger.error(f"❌ [ROLLBACK] Ошибка записи: {e}")

    async def rollback(self, change_id: str) -> bool:
        """Откатить конкретное изменение."""
        try:
            rollback_file = ROLLBACK_DIR / f"{change_id}.json"
            if not rollback_file.exists():
                logger.error(f"❌ [ROLLBACK] Файл отката не найден: {change_id}")
                return False

            with open(rollback_file) as f:
                data = json.load(f)

            file_path = data["file_path"]
            old_content = data["old_content"]

            # Восстанавливаем файл
            dst = Path(file_path)
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "w") as f:
                f.write(old_content)

            # Помечаем как откаченное
            data["rolled_back"] = True
            data["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
            with open(rollback_file, "w") as f:
                json.dump(data, f)

            # Обновляем в памяти
            for entry in self.changes:
                if entry.change_id == change_id:
                    entry.rolled_back = True
                    entry.rolled_back_at = data["rolled_back_at"]
                    break

            logger.info(f"↩️ [ROLLBACK] Откат выполнен: {file_path}")
            return True

        except Exception as e:
            logger.error(f"❌ [ROLLBACK] Ошибка отката: {e}")
            return False

    async def rollback_all(self, since_minutes: int = 60) -> int:
        """Откатить все изменения за последние N минут."""
        if not self._initialized:
            return 0

        try:
            cutoff = time.time() - (since_minutes * 60)
            rolled_back = 0

            for entry in self.changes:
                if entry.rolled_back:
                    continue

                # Проверяем timestamp
                try:
                    entry_time = datetime.fromisoformat(entry.timestamp).timestamp()
                    if entry_time > cutoff:
                        success = await self.rollback(entry.change_id)
                        if success:
                            rolled_back += 1
                except:
                    continue

            logger.info(f"↩️ [ROLLBACK] Откатано {rolled_back} изменений за {since_minutes} мин")
            return rolled_back

        except Exception as e:
            logger.error(f"❌ [ROLLBACK] Ошибка массового отката: {e}")
            return 0

    async def get_history(self, limit: int = 50) -> List[Dict]:
        """Получить историю изменений."""
        history = []
        for entry in reversed(self.changes[-limit:]):
            history.append(entry.to_dict())
        return history

    async def get_stats(self) -> Dict:
        """Получить статистику."""
        total = len(self.changes)
        rolled_back = sum(1 for c in self.changes if c.rolled_back)
        return {
            "total_changes": total,
            "rolled_back": rolled_back,
            "active": total - rolled_back,
        }

    async def cleanup(self, older_than_hours: int = 24):
        """Очистить старые записи отката."""
        try:
            cutoff = time.time() - (older_than_hours * 3600)
            cleaned = 0

            for rollback_file in ROLLBACK_DIR.glob("change_*.json"):
                try:
                    with open(rollback_file) as f:
                        data = json.load(f)
                    file_time = datetime.fromisoformat(data["timestamp"]).timestamp()
                    if file_time < cutoff:
                        rollback_file.unlink()
                        cleaned += 1
                except:
                    continue

            logger.info(f"🧹 [ROLLBACK] Очищено {cleaned} старых записей")
            return cleaned

        except Exception as e:
            logger.error(f"❌ [ROLLBACK] Ошибка очистки: {e}")
            return 0


# Singleton
_rollback_manager: Optional[RollbackManager] = None


def get_rollback_manager() -> RollbackManager:
    """Получить singleton RollbackManager."""
    global _rollback_manager
    if _rollback_manager is None:
        _rollback_manager = RollbackManager()
    return _rollback_manager
