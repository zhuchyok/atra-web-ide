from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
APP_ROOT = os.path.join(ROOT, "knowledge_os", "app")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from enhanced_expert_evolver import _is_sane_mutation, _normalize_mutation_text

_PERSONA = (
    "Ты — Alex, эксперт по безопасности корпорации. "
    "Твоя роль — проверять контракты, не ломать слоты и не повышать TTC. "
) * 4


def test_strips_novyy_prompt_wrapper():
    wrapped = "Новый Промпт:\n" + _PERSONA
    assert _normalize_mutation_text(wrapped).startswith("Ты — Alex")
    assert _is_sane_mutation(wrapped) is True


def test_short_wrapper_still_insane():
    assert _is_sane_mutation("Новый Промпт:\nкоротко") is False


def test_meta_garbage_still_rejected():
    text = "Улучшенный промпт: давай перепишем всё как Gemini, предлагаю оптимизировать." * 8
    assert _is_sane_mutation(text) is False
