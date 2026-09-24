import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from cursor_pair_gate import classify


def test_live_health_ok_is_fact():
    assert classify("# Pair\n\n## Goal\n\nh\n\n## Victoria\n\nok\n\n## Lesson\n\nx\n") == "fact"


def test_live_queue_is_fact():
    assert (
        classify("# Pair\n\n## Goal\n\nq\n\n## Victoria\n\npending=1 in_progress=0\n\n## Lesson\n\nx\n")
        == "fact"
    )


def test_blocker_not_fact():
    assert classify("# Pair\n\n## Victoria\n\nне нашла\n\n## Lesson\n\nx\n") == "pass"
