"""
ApprovalManager — проверка необходимости подтверждения для критичных действий.
Фаза 2 (упрощённая): при AGENT_APPROVAL_REQUIRED=true — отказ в записи в критичные файлы.
Полный flow (pause/resume, UI) — отдельная итерация.
"""
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Критичные файлы/паттерны — требуют подтверждения при AGENT_APPROVAL_REQUIRED=true
CRITICAL_FILE_PATTERNS = (
    "package.json",
    "package-lock.json",
    ".env",
    ".env.",
    "docker-compose",
    "Dockerfile",
    "nginx",
    "requirements.txt",
    "pyproject.toml",
    "config/",
    "database/",
)


def _normalize_path(filepath: str) -> str:
    """Нормализация пути для проверки."""
    return str(Path(filepath).name) if filepath else ""


def requires_approval_for_write(filepath: str) -> Tuple[bool, str]:
    """
    Проверяет, требуется ли подтверждение для записи в файл.
    Returns:
        (True, "причина") если нужен approval
        (False, "") если можно писать без подтверждения
    """
    if not filepath:
        return False, ""
    fp = filepath.replace("\\", "/").lower()
    name = Path(filepath).name.lower()
    for pattern in CRITICAL_FILE_PATTERNS:
        pat = pattern.lower()
        if pat.endswith("/"):
            if pat in fp or fp.startswith(pat.rstrip("/")):
                return True, f"запись в {pattern.rstrip('/')}/"
        elif pat in name or pat in fp:
            return True, f"запись в критичный файл {name}"
    return False, ""


def is_approval_required() -> bool:
    """Включена ли проверка approval (из env)."""
    return os.getenv("AGENT_APPROVAL_REQUIRED", "false").lower() in ("true", "1", "yes")
