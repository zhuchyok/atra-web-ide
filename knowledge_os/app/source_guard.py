#!/usr/bin/env python3
"""Source Guard — защита системного кода от записи автономными агентами.

[v149.5] Инцидент: LLM-ответ был записан как содержимое ai_core.py (строка 1 —
русский текст) → SyntaxError у всех свежих импортов, упал утренний отчёт.
Причина: execution_phase._execute_file_write и SystemTools.write_file писали
в любые пути без проверок.

Правила (KISS, fail-closed):
1. Системные пути (knowledge_os/app, src/agents, backend/app и др.) — запись запрещена.
   Исключение: env ATRA_ALLOW_SOURCE_WRITE=true (ручная разработка).
2. Любой .py — синтаксис-гейт: content обязан компилироваться.
3. Перезапись существующего файла контентом <30% исходного размера — запрещена
   (классический «файл заменён однострочником-мусором»).
4. Отказ логируется и уходит в ntfy (best effort) — видно, кто и что пытался.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Префиксы (встречаются в нормализованном абсолютном пути после корня репо)
PROTECTED_SOURCE_PREFIXES = (
    "knowledge_os/app/",
    "src/agents/",
    "backend/app/",
    "src/api/",
    "src/core/",
    "src/middleware/",
    "knowledge_os/scripts/",
)

_ENV_OVERRIDE = "ATRA_ALLOW_SOURCE_WRITE"


def _notify_refuse(reason: str, path: str, content_head: str) -> None:
    head = (content_head or "")[:120].replace("\n", " ")
    logger.error("🛡️ [SOURCE_GUARD] ОТКАЗ (%s): %s | content head: %r", reason, path, head)
    try:
        import requests

        ntfy = os.getenv("NTFY_URL", "https://ntfy.sh/atra_victoria_curator")
        requests.post(
            ntfy,
            data=(
                "🛡️ SOURCE_GUARD: запись отклонена\n\n"
                f"Причина: {reason}\nФайл: {path}\nКонтент: {head}..."
            ).encode("utf-8")[:3500],
            headers={"Title": "Source Guard: отказ записи", "Tags": "shield,rotating_light"},
            timeout=5,
        )
    except Exception:  # noqa: BLE001 — алерт не должен ломать основной поток
        pass


def guard_file_write(file_path: str, content: str, *, overwrite_check: bool = True) -> tuple[bool, str]:
    """Проверка перед записей файла. Возвращает (allowed, reason).

    file_path — РЕЗОЛВНУТЫЙ абсолютный или относительный путь (уже без ..).
    content — то, что собираются записать.
    """
    if not file_path or content is None:
        return False, "empty path/content"

    normalized = os.path.normpath(str(file_path)).replace(os.sep, "/").lstrip("/")
    if os.path.isabs(str(file_path)):
        normalized = os.path.normpath(str(file_path)).replace(os.sep, "/")

    # 1. Системные пути — запрещены (проверяем вхождение, т.к. корень репо в разных
    #    контейнерах разный: /workspace/atra-web-ide, /app, /workspace ...)
    allow_override = os.getenv(_ENV_OVERRIDE, "").lower() in ("true", "1", "yes")
    for prefix in PROTECTED_SOURCE_PREFIXES:
        if f"/{prefix}" in f"/{normalized}" and not allow_override:
            _notify_refuse(f"protected source path ({prefix})", normalized, content)
            return False, f"protected source path: {prefix}"

    # 2. Синтаксис-гейт для Python
    if normalized.endswith(".py"):
        try:
            compile(content, normalized, "exec")
        except SyntaxError as e:
            _notify_refuse(f"python syntax error (line {e.lineno})", normalized, content)
            return False, f"python syntax error: {e}"

    # 3. Перезапись усечением
    if overwrite_check and os.path.exists(str(file_path)):
        try:
            old_size = os.path.getsize(str(file_path))
            if old_size > 2000 and len(content) < old_size * 0.3:
                _notify_refuse(
                    f"truncation overwrite ({len(content)} chars vs {old_size})",
                    normalized,
                    content,
                )
                return False, "truncation overwrite refused"
        except OSError:
            pass

    return True, "ok"
