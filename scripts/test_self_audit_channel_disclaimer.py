#!/usr/bin/env python3
"""String check: self-audit channel disclaimer present (brain-direct ≠ #65)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKERS = (
    "мозг напрямую",
    "БЕЗ file tools",
    "#65",
    "помей",  # «не/НЕ помей» — канал ≠ #65
)


def _has_all(text: str, label: str) -> None:
    low = text.lower()
    for m in MARKERS:
        assert m.lower() in low, f"missing in {label}: {m}"


def test_send_self_audit_system_disclaimer() -> None:
    text = (ROOT / "scripts" / "send_self_audit_chat.py").read_text(encoding="utf-8")
    _has_all(text, "send_self_audit_chat.py")


def test_build_task_preamble_disclaimer() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from build_self_audit_task import build_task_text  # noqa: PLC0415

    _has_all(build_task_text(), "build_task_text()")


def test_template_disclaimer() -> None:
    text = (ROOT / "scripts" / "curator_self_audit_tasks.txt").read_text(encoding="utf-8")
    _has_all(text, "curator_self_audit_tasks.txt")


if __name__ == "__main__":
    test_send_self_audit_system_disclaimer()
    test_build_task_preamble_disclaimer()
    test_template_disclaimer()
    print("OK: self-audit channel disclaimer present")
