"""Explicit victoria-qwen38 must not drop Ollama just because MLX picked wisdom."""

from pathlib import Path

SRC = (Path(__file__).resolve().parents[2] / "knowledge_os" / "app" / "local_router.py").read_text(
    encoding="utf-8"
)


def test_auto_wisdom_route_requires_empty_model():
    chunk = SRC.split("mlx_choice = self._select_model", 1)[1].split("if preferred_source:", 1)[0]
    assert "auto_wisdom_route" in chunk
    assert "(not model) and self._is_wisdom_model(mlx_choice)" in chunk
    assert "or self._is_wisdom_model(mlx_choice)" not in chunk.replace(
        "auto_wisdom_route = (not model) and self._is_wisdom_model(mlx_choice)", ""
    )
