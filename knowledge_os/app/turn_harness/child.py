"""Ребёнок не шире родителя. Хост задаёт режим, модель его не меняет."""

from __future__ import annotations

import json
import os

MAX_DEPTH = 3
_PLAN_FORBIDDEN = {"write_file", "run_terminal_cmd", "ssh_run", "git_push"}
_EDIT_FORBIDDEN = {"git_push", "ssh_run"}


def ceiling_mode() -> str:
    mode = os.getenv("CHILD_CEILING", "off").strip().lower()
    if mode in {"log", "enforce"}:
        return mode
    return "off"


def inspect_child(metadata: dict, tool_name: str) -> tuple:
    if "permission_mode" not in metadata and "parent_task_id" not in metadata:
        return True, ""
    depth = int(metadata.get("depth") or 0)
    if depth > MAX_DEPTH:
        return False, f"depth {depth} > {MAX_DEPTH}"
    mode = str(metadata.get("permission_mode") or "plan")
    if mode == "plan" and tool_name in _PLAN_FORBIDDEN:
        return False, f"plan forbids {tool_name}"
    if mode == "accept_edits" and tool_name in _EDIT_FORBIDDEN:
        return False, f"accept_edits forbids {tool_name}"
    if mode == "dont_ask":
        allowed = set(metadata.get("allowed_tools") or [])
        if tool_name not in allowed:
            return False, f"dont_ask forbids {tool_name}"
    return True, ""


def _required_keys(metadata: dict) -> list:
    if not isinstance(metadata, dict):
        return []
    schema = metadata.get("output_schema")
    if not isinstance(schema, list):
        return []
    return [str(key) for key in schema]


def result_violation(metadata: dict, result) -> str:
    if not _required_keys(metadata):
        return ""
    parsed = result
    if isinstance(result, str):
        text = result.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = result
    ok, why = check_output(metadata, parsed)
    return "" if ok else why


def check_output(metadata: dict, result) -> tuple:
    required = _required_keys(metadata)
    if not required:
        return True, ""
    if not isinstance(result, dict):
        return False, "result is not an object"
    missing = [key for key in required if key not in result]
    if missing:
        return False, "missing " + ",".join(missing)
    return True, ""
