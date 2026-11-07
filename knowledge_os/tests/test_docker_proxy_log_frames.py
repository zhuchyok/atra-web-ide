"""docker-proxy /logs must be Docker multiplex frames, not plain text."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRAMES = ROOT / "infrastructure" / "docker" / "docker-proxy" / "log_frames.py"
PROXY = ROOT / "infrastructure" / "docker" / "docker-proxy" / "main.py"


def _load_frames():
    spec = importlib.util.spec_from_file_location("docker_proxy_log_frames", FRAMES)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_multiplex_header_is_stdout_frame():
    mod = _load_frames()
    payload = b"2026-11-07 hello"
    frame = mod.multiplex_docker_logs(payload)
    assert frame[0] == 1
    assert int.from_bytes(frame[4:8], "big") == len(payload)
    assert frame[8:] == payload
    assert frame[0] != ord("2")


def test_logs_handler_does_not_return_plain_text():
    text = PROXY.read_text(encoding="utf-8")
    chunk = text.split('and "/logs" in full_path', 1)[1].split("elif")[0]
    assert "multiplex_docker_logs" in chunk
    assert 'media_type="text/plain"' not in chunk
    assert "COPY main.py log_frames.py" in (
        ROOT / "infrastructure" / "docker" / "docker-proxy" / "Dockerfile"
    ).read_text(encoding="utf-8")
