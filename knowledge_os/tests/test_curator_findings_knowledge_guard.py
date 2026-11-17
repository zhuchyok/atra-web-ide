"""Write-side guard: refusal / non-actionable curator findings must not enter knowledge_nodes."""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "curator_findings_to_knowledge.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("curator_findings_to_knowledge", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def test_refusal_cognitive_code_blocked(mod):
    text = (
        "[напиши одну строку кода] Когнитивный Код: не могу приступить — "
        "INSUFFICIENT_CONTEXT / UNVERIFIED"
    )
    assert mod.is_non_knowledge_finding(text) is True


def test_insufficient_context_alone_blocked(mod):
    assert (
        mod.is_non_knowledge_finding(
            "[goal] Status: INSUFFICIENT_CONTEXT — need path before coding"
        )
        is True
    )


def test_ne_mogu_pristupit_blocked(mod):
    assert (
        mod.is_non_knowledge_finding(
            "[тест] Согласно когнитивному кодексу, я не могу приступить без ТЗ"
        )
        is True
    )


def test_ok_chatter_not_actionable(mod):
    assert (
        mod.is_non_knowledge_finding(
            "[check file] ОК — pip install, os.system не найден в /app/x.py"
        )
        is True
    )


def test_queued_status_not_actionable(mod):
    assert (
        mod.is_non_knowledge_finding(
            "[check] ⏳ Task task_abc queued to worker"
        )
        is True
    )


def test_real_problem_kept(mod):
    text = (
        "[проверь apply_migrations.py] ПРОБЛЕМА: найдено «pip install» "
        "(строка 25): runtime install в логере"
    )
    assert mod.is_non_knowledge_finding(text) is False


def test_filter_actionable_problems_skips_refusals(mod):
    problems = [
        "[g] Когнитивный Код: не могу приступить — INSUFFICIENT_CONTEXT",
        "[g] ПРОБЛЕМА: hardcoded secret in line 10",
        "[g] ОК: nothing found",
    ]
    kept, skipped = mod.filter_actionable_problems(problems)
    assert skipped == 2
    assert len(kept) == 1
    assert "ПРОБЛЕМА" in kept[0]


@pytest.mark.asyncio
async def test_save_to_db_skips_refusal(mod, monkeypatch):
    monkeypatch.setattr(mod, "DATABASE_URL", "postgresql://unused")
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.close = AsyncMock()

    fake_asyncpg = MagicMock()
    fake_asyncpg.connect = AsyncMock(return_value=conn)

    with patch.dict("sys.modules", {"asyncpg": fake_asyncpg}):
        saved = await mod.save_to_db(
            [
                "[g] не могу приступить — INSUFFICIENT_CONTEXT",
                "[g] ПРОБЛЕМА: disk full on /var/log",
            ],
            "curator_test.json",
        )

    assert saved == 1
    assert conn.execute.await_count == 1
    args = conn.execute.await_args.args
    assert "ПРОБЛЕМА" in args[1]
    assert "не могу приступить" not in args[1]


def test_save_to_fallback_skips_refusal(mod, tmp_path, monkeypatch):
    fallback = tmp_path / "findings.jsonl"
    monkeypatch.setattr(mod, "FALLBACK_FILE", fallback)
    saved = mod.save_to_fallback(
        [
            "[g] Cognitive Code refusal / INSUFFICIENT_CONTEXT",
            "[g] ПРОБЛЕМА: redis UDS missing",
        ],
        "curator_test.json",
    )
    assert saved == 1
    lines = fallback.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "ПРОБЛЕМА" in lines[0]
    assert "INSUFFICIENT_CONTEXT" not in lines[0]
