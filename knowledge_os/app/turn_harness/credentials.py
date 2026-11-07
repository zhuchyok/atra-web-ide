"""В конфиге и в логе — имя переменной. Значение читается на операцию."""

from __future__ import annotations

import os


def resolve(ref: str):
    value = os.environ.get(ref, "")
    if not str(value).strip():
        return None
    return str(value)


def describe(ref: str) -> dict:
    return {
        "ref": ref,
        "configured": resolve(ref) is not None,
        "source": "env",
    }
