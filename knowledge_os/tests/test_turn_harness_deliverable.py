import importlib.util
import subprocess
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "app" / "turn_harness" / "deliverable.py"
_spec = importlib.util.spec_from_file_location("turn_harness_deliverable", _PATH)
deliverable = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deliverable)


def test_diff_is_limited_to_written_path(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    target = tmp_path / "src" / "a.py"
    target.parent.mkdir()
    target.write_text("print(1)\n")
    other = tmp_path / "src" / "noise.py"
    other.write_text("print(2)\n")
    got = deliverable.build_deliverable(str(tmp_path), ["src/a.py"])
    assert got["presented"] == ["src/a.py"]
    assert "src/a.py" in got["workspace_diff"]
    assert "noise.py" not in got["workspace_diff"]


def test_missing_git_is_explicit(tmp_path):
    (tmp_path / "a.py").write_text("x\n")
    got = deliverable.build_deliverable(str(tmp_path), ["a.py"])
    assert got["presented"] == ["a.py"]
    assert got["workspace_diff"].startswith("git_diff_unavailable")
