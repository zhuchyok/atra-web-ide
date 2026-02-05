"""
Unit tests for json_fast and http_client (оптимизации: быстрый JSON, общий HTTP-клиент).

Покрытие граничных случаев по рекомендациям QA (edge cases, regression).
Backend: type hints, контракт loads/dumps, resilience.
"""

import pytest

# --- json_fast ---


def test_json_fast_loads_valid_str():
    """Валидный JSON строка."""
    from knowledge_os.app.json_fast import loads
    assert loads('{"a": 1}') == {"a": 1}
    assert loads('[1,2,3]') == [1, 2, 3]


def test_json_fast_loads_valid_bytes():
    """Валидный JSON bytes."""
    from knowledge_os.app.json_fast import loads
    assert loads(b'{"a": 1}') == {"a": 1}


def test_json_fast_loads_empty_and_none():
    """Граничные случаи: пустая строка и None (не падать, вернуть None)."""
    from knowledge_os.app.json_fast import loads
    assert loads(None) is None
    assert loads("") is None
    assert loads(b"") is None


def test_json_fast_loads_invalid_returns_none():
    """Невалидный JSON — возврат None (resilience)."""
    from knowledge_os.app.json_fast import loads
    assert loads("not json") is None
    assert loads("{") is None


def test_json_fast_dumps_roundtrip():
    """dumps → loads roundtrip."""
    from knowledge_os.app.json_fast import loads, dumps
    obj = {"result_text": "hello", "node_ids": [1, 2, 3]}
    s = dumps(obj)
    assert isinstance(s, str)
    back = loads(s)
    assert back == obj


def test_json_fast_dumps_indent():
    """dumps с indent возвращает строку с переносами."""
    from knowledge_os.app.json_fast import dumps
    s = dumps({"a": 1}, indent=True)
    assert isinstance(s, str)
    assert "\n" in s


# --- http_client (async) ---


@pytest.mark.asyncio
async def test_http_client_get_returns_client():
    """get_http_client возвращает клиент (один на процесс)."""
    from knowledge_os.app.http_client import get_http_client
    client = await get_http_client()
    assert client is not None
    assert hasattr(client, "post")


@pytest.mark.asyncio
async def test_http_client_close_idempotent():
    """close_http_client можно вызывать дважды (idempotent)."""
    from knowledge_os.app.http_client import close_http_client, get_http_client
    await close_http_client()
    await close_http_client()
    # После close следующий get создаёт новый клиент
    client = await get_http_client()
    assert client is not None
