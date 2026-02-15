"""
Тесты expert_services: список имён экспертов и текст услуг для промптов.
Без БД работают за счёт employees.json (configs/experts). Связь с docs/TESTING_FULL_SYSTEM.md.
Запуск: из knowledge_os: python3 -m pytest tests/test_expert_services.py -v
"""
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Чтобы employees.json нашёлся из atra-web-ide
_project_root = os.path.dirname(_root) if os.path.basename(_root) == "knowledge_os" else _root
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pytest


def test_get_all_expert_names_returns_list():
    """get_all_expert_names возвращает список (из employees.json и/или БД)."""
    from app.expert_services import get_all_expert_names

    names = get_all_expert_names()
    assert isinstance(names, list)
    # Если есть employees.json в проекте — будут имена
    if names:
        assert all(isinstance(n, str) for n in names)


def test_get_all_expert_names_max_count():
    """max_count ограничивает длину списка."""
    from app.expert_services import get_all_expert_names

    names = get_all_expert_names(max_count=3)
    assert isinstance(names, list)
    assert len(names) <= 3


def test_get_expert_services_text_returns_string():
    """get_expert_services_text возвращает строку для вставки в промпт."""
    from app.expert_services import get_expert_services_text

    text = get_expert_services_text(max_entries=5)
    assert isinstance(text, str)


def test_list_experts_by_role_returns_list():
    """list_experts_by_role возвращает список dict с name/role."""
    from app.expert_services import list_experts_by_role

    experts = list_experts_by_role("backend")
    assert isinstance(experts, list)
    for e in experts:
        assert isinstance(e, dict)
        assert "name" in e or "role" in e
