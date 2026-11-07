"""Docker Engine multiplex frames for /containers/{id}/logs."""

import struct


def multiplex_docker_logs(payload: bytes, stream: int = 1) -> bytes:
    """8-byte header + payload. Plain UTF-8 makes docker-py raise unrecognized stream: 50."""
    if not isinstance(payload, bytes):
        payload = str(payload).encode("utf-8", errors="replace")
    return struct.pack(">BxxxI", stream, len(payload)) + payload
