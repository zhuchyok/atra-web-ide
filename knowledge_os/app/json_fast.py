"""
Быстрый JSON для горячих путей (мировая практика: orjson там, где часто сериализуют/парсят).

Единая точка: при наличии orjson используем его, иначе stdlib json.
Установка: orjson в requirements.txt (не в рантайме — 12-Factor).
"""
from __future__ import annotations

from typing import Any, Optional

try:
    import orjson
    _HAS_ORJSON = True
except ImportError:
    _HAS_ORJSON = False
    import json as _stdlib_json


def loads(data: Optional[bytes | str]) -> Optional[Any]:
    """
    Парсинг JSON из bytes или str. Возвращает dict/list или None при пустом/невалидном вводе.
    Не передавайте None из кэша — проверяйте «if cached_data» до вызова (edge case: пустая строка).
    """
    if data is None or data == b"" or data == "":
        return None
    if _HAS_ORJSON:
        if isinstance(data, str):
            data = data.encode("utf-8")
        try:
            return orjson.loads(data)
        except orjson.JSONDecodeError:
            return None
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    try:
        return _stdlib_json.loads(data)
    except (TypeError, ValueError):
        return None


def dumps(obj: Any, *, indent: bool = False) -> str:
    """
    Сериализация в JSON (drop-in замена json.dumps). Возвращает str.
    Рекомендуется передавать только типы, сериализуемые orjson (dict, list, str, int, float, bool);
    datetime — использовать default=str в вызывающем коде при необходимости.
    """
    if _HAS_ORJSON:
        opt = orjson.OPT_APPEND_NEWLINE
        if indent:
            opt |= orjson.OPT_INDENT_2
        return orjson.dumps(obj, option=opt).decode("utf-8")
    if indent:
        return _stdlib_json.dumps(obj, ensure_ascii=False, indent=2)
    return _stdlib_json.dumps(obj, ensure_ascii=False)
