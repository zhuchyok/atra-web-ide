"""Hub run_smart_agent_async prepends CURSOR_METHOD_PROMPT once."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_run_smart_agent_async_prepends_cursor_method_once():
    from app import ai_core
    from app.cursor_method import CURSOR_METHOD_PROMPT

    mock_impl = AsyncMock(return_value="ok")
    with patch.dict("os.environ", {"USE_AI_PIPELINE_V2": "false"}, clear=False):
        with patch.object(ai_core, "run_smart_agent_async_impl", mock_impl):
            await ai_core.run_smart_agent_async("plain task")
            first = mock_impl.await_args.args[0]
            assert first.startswith(CURSOR_METHOD_PROMPT)
            assert first.count("МЕТОД CURSOR") == 1
            assert first.endswith("plain task")

            mock_impl.reset_mock()
            already = f"{CURSOR_METHOD_PROMPT}already prefixed"
            await ai_core.run_smart_agent_async(already)
            second = mock_impl.await_args.args[0]
            assert second == already
            assert second.count("МЕТОД CURSOR") == 1
