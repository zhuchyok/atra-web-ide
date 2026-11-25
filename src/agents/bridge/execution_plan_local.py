"""Local workspace-scoped execution of Victoria execution_plan steps.

Mutate/run require approve_writes=True. No MCP dependency.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)

_GIT_TOKEN_RE = re.compile(r"\bgit\b", re.IGNORECASE)
_INTERPRETER_BASES = frozenset({"python", "python3", "bash", "sh", "zsh"})

ALLOWED_COMMANDS: Set[str] = {
    "pytest",
    "python",
    "python3",
    "pip",
    "pip3",
    "npm",
    "node",
    "cargo",
    "go",
    "make",
    "cmake",
    "ruff",
    "mypy",
    "tsc",
    "eslint",
    "pylint",
    # git mutate/read via dedicated tools + ATRA_ALLOW_GIT_*; not shell here
    "ls",
    "cat",
    "find",
    "grep",
    "curl",
}


def validate_command(command: str, allowed: Set[str] | None = None) -> str:
    if not command:
        raise ValueError("Empty command not allowed")
    allow = allowed or ALLOWED_COMMANDS
    parts = command.strip().split()
    base_cmd = parts[0] if parts else ""
    if base_cmd not in allow:
        raise ValueError(f"Command '{base_cmd}' not allowed. Use: {', '.join(sorted(allow))}")
    for pattern in ("&&", "||", ";", "|", ">", ">>", "<", "$(", "`", "\\", "2>", "0>", "1>"):
        if pattern in command:
            raise ValueError(f"Dangerous pattern '{pattern}' not allowed in commands")
    # approve_writes ≠ ATRA_ALLOW_GIT_MUTATE: block python/bash smuggling `git …`
    if base_cmd in _INTERPRETER_BASES and _GIT_TOKEN_RE.search(command):
        if os.getenv("ATRA_ALLOW_GIT_MUTATE", "").lower() not in ("true", "1", "yes"):
            raise ValueError(
                "git via interpreter blocked (ATRA_ALLOW_GIT_MUTATE not set). "
                "Use dedicated git tools after human approve."
            )
    return command


def resolve_workspace_path(workspace_path: str, rel_or_abs: str) -> Path:
    root = Path(workspace_path).expanduser().resolve()
    raw = (rel_or_abs or "").strip()
    if not raw:
        raise ValueError("Empty path")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace: {resolved}") from exc
    return resolved


def execute_plan_local(
    execution_plan: List[Dict[str, Any]],
    workspace_path: str,
    *,
    approve_writes: bool = False,
    max_read_chars: int = 8000,
) -> List[str]:
    """Run plan steps on local FS. Mutate/run require approve_writes=True."""
    results: List[str] = []
    root = Path(workspace_path).expanduser().resolve()
    for i, step in enumerate(execution_plan, 1):
        action = step.get("action")
        description = step.get("description", "")
        try:
            if action == "read_file":
                path = resolve_workspace_path(workspace_path, step.get("path", ""))
                if not path.is_file():
                    results.append(f"❌ Шаг {i}: read_file — нет файла {path}")
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                snippet = text[:max_read_chars]
                truncated = len(text) > max_read_chars
                results.append(
                    f"✅ Шаг {i}: read_file {path} ({len(text)} chars)"
                    f"{' truncated' if truncated else ''}\n"
                    f"{snippet}{'…' if truncated else ''}"
                )
            elif action == "edit":
                path = resolve_workspace_path(workspace_path, step.get("path", ""))
                content = step.get("content")
                old_s = step.get("old_string")
                new_s = step.get("new_string")
                preview = (
                    f"old_string={str(old_s)[:120]!r}→new_string={str(new_s)[:120]!r}"
                    if old_s is not None and new_s is not None
                    else f"rewrite_chars={len(content or '')}"
                )
                if not approve_writes:
                    results.append(
                        f"⏸ Шаг {i}: edit needs_approve path={path} ({preview}). "
                        "Повторите victoria_execute_plan(..., approve_writes=True)."
                    )
                    continue
                if old_s is not None and new_s is not None:
                    if not path.is_file():
                        results.append(f"❌ Шаг {i}: edit — нет файла {path}")
                        continue
                    cur = path.read_text(encoding="utf-8", errors="replace")
                    if old_s not in cur:
                        results.append(f"❌ Шаг {i}: edit — old_string не найден в {path}")
                        continue
                    path.write_text(cur.replace(old_s, new_s, 1), encoding="utf-8")
                    results.append(f"✅ Шаг {i}: edit StrReplace {path}")
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content if content is not None else "", encoding="utf-8")
                    results.append(f"✅ Шаг {i}: edit write {path}")
            elif action == "run":
                command = validate_command(step.get("command", ""))
                if not approve_writes:
                    results.append(
                        f"⏸ Шаг {i}: run needs_approve command={command!r}. "
                        "Повторите с approve_writes=True."
                    )
                    continue
                completed = subprocess.run(
                    command.split(),
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                out = (completed.stdout or "")[:2000]
                err = (completed.stderr or "")[:1000]
                results.append(
                    f"{'✅' if completed.returncode == 0 else '❌'} Шаг {i}: run "
                    f"rc={completed.returncode}\n{out}{err}"
                )
            else:
                results.append(f"⚠️ Шаг {i}: неизвестное действие {action} ({description})")
        except Exception as e:
            logger.exception("Ошибка на шаге %s", i)
            results.append(f"❌ Шаг {i}: {action} — {e}")
    return results
