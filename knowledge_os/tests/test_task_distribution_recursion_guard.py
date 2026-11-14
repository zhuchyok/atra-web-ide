import pytest

import app.task_distribution_system_complete as tds_mod
from app.task_distribution_system_complete import TaskDistributionSystem, _is_task_parser_wrapper_text


def test_wrapper_text_detector_flags_parser_prompt():
    text = "Проанализируй следующий промпт Veronica и извлеки все задачи: ..."
    assert _is_task_parser_wrapper_text(text) is True


@pytest.mark.asyncio
async def test_parse_veronica_prompt_rejects_wrapper_text():
    system = TaskDistributionSystem("postgresql://unused")
    tasks = await system._parse_veronica_prompt(
        "Проанализируй следующий промпт Veronica и извлеки все задачи:\nfoo",
        {"departments": [{"name": "General"}]},
    )
    assert tasks == []


@pytest.mark.asyncio
async def test_parse_veronica_prompt_no_json_does_not_fallback_to_prompt(monkeypatch):
    system = TaskDistributionSystem("postgresql://unused")

    class DummyVictoria:
        async def solve(self, _prompt, method="extended_thinking"):
            return {"result": "no structured tasks here"}

    monkeypatch.setattr(tds_mod, "_get_victoria_enhanced_singleton", lambda: DummyVictoria())
    monkeypatch.setenv("OLLAMA_HANDS_URL", "http://127.0.0.1:9")

    tasks = await system._parse_veronica_prompt(
        "Сделай обычную задачу без parser-wrapper текста",
        {"departments": [{"name": "General"}]},
    )
    assert tasks == []
