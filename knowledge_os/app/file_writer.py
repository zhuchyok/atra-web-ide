"""
SafeFileWriter — безопасная запись файлов с бэкапами.
Интеграция с ReActAgent (create_file, write_file).
"""
import hashlib
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.code_validator import CodeValidator

logger = logging.getLogger(__name__)


def _default_workspace_root() -> Path:
    """Корень workspace: env или /app в Docker, иначе cwd."""
    root = os.getenv("WORKSPACE_ROOT")
    if root:
        return Path(root).resolve()
    if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() == "true":
        return Path("/app").resolve()
    return Path.cwd()


class SafeFileWriter:
    """Безопасная запись файлов с бэкапами и проверкой путей."""

    # Системные пути, запись в которые запрещена

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root or str(_default_workspace_root())).resolve()
        self.backup_dir = self.workspace_root / ".agent_backups"
        self.backup_enabled = os.getenv("AGENT_BACKUP_ENABLED", "true").lower() in ("true", "1", "yes")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("SafeFileWriter: workspace=%s, backup_enabled=%s", self.workspace_root, self.backup_enabled)

    def write_file(
        self,
        filepath: str,
        content: str,
        overwrite: bool = True,
    ) -> Dict[str, Any]:
        """Безопасная запись файла."""
        try:
            target_path = self._resolve_path(filepath)

            if not self._is_within_workspace(target_path):
                return {"error": f"Путь вне workspace: {target_path}"}

            if self._is_blocked_path(target_path):
                return {"error": f"Запись в этот путь запрещена: {target_path}"}

            if target_path.exists() and not overwrite:
                return {"error": "Файл существует. Используйте overwrite=True"}

            # [SINGULARITY 14.3] Pre-flight Validation
            if CodeValidator.is_python_file(filepath):
                validation = CodeValidator.validate_python(content, filename=filepath)
                if not validation.get("success"):
                    error_msg = f"ОШИБКА ВАЛИДАЦИИ КОДА: {validation.get('error')}"
                    if validation.get("line"):
                        error_msg += f" (строка {validation.get('line')})"
                    logger.error(f"SafeFileWriter: {error_msg} в {filepath}")
                    return {
                        "error": error_msg,
                        "validation_failed": True,
                        "type": validation.get("type"),
                        "line": validation.get("line")
                    }

            backup_info = None
            if target_path.exists() and self.backup_enabled:
                backup_info = self._create_backup(target_path)

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")

            try:
                rel_path = target_path.relative_to(self.workspace_root)
            except ValueError:
                rel_path = target_path

            return {
                "success": True,
                "path": str(target_path),
                "relative_path": str(rel_path),
                "size": len(content),
                "backup": backup_info,
                "message": f"Файл записан: {rel_path} ({len(content)} символов)",
            }
        except Exception as e:
            logger.exception("SafeFileWriter: ошибка записи %s", filepath)
            return {"error": str(e)}

    def _resolve_path(self, filepath: str) -> Path:
        """Нормализация пути относительно workspace."""
        path = Path(filepath)
        if path.is_absolute():
            try:
                return (self.workspace_root / path.relative_to(self.workspace_root)).resolve()
            except ValueError:
                return path.resolve()
        return (self.workspace_root / path).resolve()

    def _is_within_workspace(self, path: Path) -> bool:
        """Проверка, что путь внутри workspace."""
        try:
            path.resolve().relative_to(self.workspace_root)
            return True
        except ValueError:
            return False

    def _is_blocked_path(self, path: Path) -> bool:
        """Проверка на запрещённые пути."""
        path_str = str(path)
        blocked = ["/etc/", "/root/", "/var/", "/bin/", "/sbin/", "/usr/bin/"]
        return any(path_str.startswith(p) for p in blocked)

    def _create_backup(self, filepath: Path) -> Dict[str, Any]:
        """Создание бэкапа с timestamp и хэшем."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            content_hash = hashlib.md5(filepath.read_bytes()).hexdigest()[:8]
            backup_name = f"{filepath.name}.{timestamp}.{content_hash}.bak"
            backup_path = self.backup_dir / backup_name
            shutil.copy2(filepath, backup_path)
            logger.info("Бэкап создан: %s", backup_path)
            return {
                "path": str(backup_path),
                "original": str(filepath),
                "timestamp": timestamp,
                "hash": content_hash,
            }
        except Exception as e:
            logger.warning("Не удалось создать бэкап %s: %s", filepath, e)
            return {}
