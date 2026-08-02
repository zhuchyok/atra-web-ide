"""v135: victoria-wisdom MLX-primary routing helpers (repo-root executor)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_KOS = _ROOT / "knowledge_os"


def _import_root_executor_helpers():
    """Prefer repo-root src/ over knowledge_os/src stub package."""
    root_s = str(_ROOT)
    kos_s = str(_KOS)
    # Drop shadow path entries (cwd/knowledge_os often precedes root).
    cleaned = []
    for p in sys.path:
        try:
            rp = str(Path(p).resolve())
        except Exception:
            rp = p
        if rp == kos_s or rp.endswith("/knowledge_os"):
            continue
        cleaned.append(p)
    sys.path[:] = [root_s] + [p for p in cleaned if p != root_s]
    for key in list(sys.modules):
        if key == "src" or key.startswith("src."):
            del sys.modules[key]
    from src.agents.core.executor import (  # noqa: WPS433
        _is_victoria_wisdom,
        _normalize_model_for_backend,
        _wisdom_mlx_primary_enabled,
    )

    return _is_victoria_wisdom, _normalize_model_for_backend, _wisdom_mlx_primary_enabled


def test_normalize_strips_latest_for_mlx():
    _, normalize, _ = _import_root_executor_helpers()
    mlx = "http://host.docker.internal:11435"
    ollama = "http://host.docker.internal:11434"
    assert normalize("victoria-wisdom-v3.5:latest", mlx, mlx) == "victoria-wisdom-v3.5"
    assert normalize("victoria-wisdom-v3.5:latest", ollama, mlx) == "victoria-wisdom-v3.5:latest"
    assert normalize("phi3.5:3.8b", mlx, mlx) == "phi3.5:3.8b"


def test_is_victoria_wisdom():
    is_wisdom, _, _ = _import_root_executor_helpers()
    assert is_wisdom("victoria-wisdom-v3.5:latest")
    assert is_wisdom("victoria-wisdom-v3.5")
    assert not is_wisdom("phi3.5:3.8b")
    assert not is_wisdom("")


def test_wisdom_mlx_primary_default_on(monkeypatch):
    _, _, enabled = _import_root_executor_helpers()
    monkeypatch.delenv("VICTORIA_WISDOM_MLX_PRIMARY", raising=False)
    assert enabled() is True
    monkeypatch.setenv("VICTORIA_WISDOM_MLX_PRIMARY", "false")
    assert enabled() is False
