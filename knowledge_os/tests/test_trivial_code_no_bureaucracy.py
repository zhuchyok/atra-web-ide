"""#66: trivial self-contained code → immediate code, no Cognitive Code / ТЗ refuse."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
VICTORIA_SERVER = ROOT / "src" / "agents" / "bridge" / "victoria_server.py"

TRIVIAL = "напиши одну строку кода на Python: вывод текущей даты"
HEAVY = "напиши модуль knowledge_os/app/foo.py с классом Foo и pytest"


def _load_helpers():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    # Markers + code_write + trivial helpers (stop before JSON envelope parsers).
    markers_start = text.index("_CODE_WRITE_GOAL_MARKERS = (")
    end = text.index("\ndef _parse_json_object_loose(")
    ns: dict = {"Optional": Optional, "re": __import__("re")}
    exec(compile(text[markers_start:end], str(VICTORIA_SERVER), "exec"), ns)
    return (
        ns["_is_trivial_self_contained_code_goal"],
        ns["_try_trivial_code_reply"],
        ns["_is_code_write_goal"],
    )


def test_trivial_one_liner_detected():
    trivial, reply, code_write = _load_helpers()
    assert code_write(TRIVIAL)
    assert trivial(TRIVIAL)
    assert reply(TRIVIAL) == "print(datetime.date.today())"


def test_heavy_code_not_trivial():
    trivial, reply, _ = _load_helpers()
    assert not trivial(HEAVY)
    assert reply(HEAVY) is None
    assert not trivial("исправь IndentationError в src/agents/bridge/victoria_server.py")


def test_explicit_concrete_excludes_trivial():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    fn = text[
        text.index("def _is_explicit_concrete_goal(") : text.index(
            "\ndef _override_need_clarification_strategy("
        )
    ]
    assert "_is_trivial_self_contained_code_goal(goal)" in fn
    assert "return False" in fn


def test_code_write_override_skips_trivial():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "not _is_trivial_self_contained_code_goal(goal)" in text
    assert text.count("code_write_goal_override") >= 1


def test_run_and_chat_wire_trivial_reply():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    assert "_try_trivial_code_reply(goal)" in text
    assert "[VICTORIA_CODE] /run trivial one-liner" in text
    assert "[VICTORIA_CODE] chat trivial one-liner" in text
    assert "trivial_self_contained_code" in text


def test_omni_rag_skips_trivial_and_code_write():
    text = VICTORIA_SERVER.read_text(encoding="utf-8")
    block = text[text.index("_skip_omni_rag") : text.index("_skip_omni_rag") + 500]
    assert "_is_trivial_self_contained_code_goal" in block
    assert "_is_code_write_goal" in block
