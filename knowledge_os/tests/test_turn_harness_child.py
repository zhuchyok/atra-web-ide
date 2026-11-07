import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "app" / "turn_harness" / "child.py"
_spec = importlib.util.spec_from_file_location("turn_harness_child", _PATH)
child = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(child)


def test_depth_over_3_is_a_violation():
    ok, why = child.inspect_child({"depth": 4, "permission_mode": "plan"}, "read_file")
    assert ok is False and "depth" in why


def test_plan_cannot_write():
    ok, why = child.inspect_child({"depth": 1, "permission_mode": "plan"}, "write_file")
    assert ok is False and "plan" in why


def test_dont_ask_only_listed_tools():
    meta = {"depth": 1, "permission_mode": "dont_ask", "allowed_tools": ["read_file"]}
    assert child.inspect_child(meta, "read_file")[0] is True
    assert child.inspect_child(meta, "git_push")[0] is False


def test_output_schema_is_required_keys():
    meta = {"output_schema": ["file_path", "status"]}
    assert child.check_output(meta, {"file_path": "a.py", "status": "ok"})[0] is True
    ok, why = child.check_output(meta, {"file_path": "a.py"})
    assert ok is False and "status" in why


def test_string_contract_name_is_not_a_key_list():
    assert child.result_violation({"output_schema": "expert_response_v1"}, "просто текст") == ""


def test_json_result_satisfies_required_keys():
    raw = '{"file_path": "a.py", "status": "ok"}'
    assert child.result_violation({"output_schema": ["file_path", "status"]}, raw) == ""
    assert child.result_violation({"output_schema": ["file_path", "status"]}, "не json") == (
        "result is not an object"
    )


def test_ordinary_task_without_child_fields_is_allowed():
    assert child.inspect_child({}, "write_file") == (True, "")
    assert child.inspect_child({"source": "nightly"}, "git_push")[0] is True
