"""Wave-4: train_victoria_wisdom.sh must refuse qwen2.5-3b / non-qwen38 bases."""

from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2] / "knowledge_os" / "scripts" / "train_victoria_wisdom.sh"
)


def test_train_script_blocks_wrong_family():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "qwen2.5-3b" in text
    assert "Refusing wrong-family base" in text
    assert "victoria-qwen38" in text
    assert "exit 2" in text
