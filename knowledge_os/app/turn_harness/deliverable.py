"""Сдача хода: какие файлы записаны и их git diff --stat."""

from __future__ import annotations

import subprocess


def build_deliverable(workspace: str, paths: list) -> dict:
    clean = []
    for raw in paths:
        rel = str(raw).replace("\\", "/").lstrip("/")
        if rel and ".." not in rel.split("/"):
            clean.append(rel)
    if not clean:
        return {"presented": [], "workspace_diff": ""}
    try:
        proc = subprocess.run(
            ["git", "diff", "--stat", "--", *clean],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"presented": clean, "workspace_diff": f"git_diff_unavailable: {e}"}
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "git failed").strip()
        return {"presented": clean, "workspace_diff": "git_diff_unavailable: " + err[:300]}
    stat = proc.stdout.strip()
    if not stat:
        proc2 = subprocess.run(
            ["git", "status", "--short", "--", *clean],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        stat = proc2.stdout.strip() or "(нет diff: файл совпадает с индексом или не под git)"
    return {"presented": clean, "workspace_diff": stat}
