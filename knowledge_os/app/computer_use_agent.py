"""
Computer Use Agent - Anthropic Computer Use API pattern
Wraps BrowserOperator for use as Victoria tool.

Usage:
    from computer_use_agent import get_computer_use_agent

    agent = get_computer_use_agent()
    result = await agent.execute("Открой сайт и сделай скриншот")
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ComputerUseAgent:
    """
    Computer Use Agent - exposes BrowserOperator as LLM-usable tool.
    This follows Anthropic's Computer Use API pattern:
    - LLM generates actions
    - Agent executes in browser
    - Returns screenshot + observations
    """

    def __init__(self):
        self._browser_op = None
        self._initialized = False

    async def _ensure_init(self):
        if self._initialized:
            return
        try:
            from browser_operator import get_browser_operator

            self._browser_op = get_browser_operator()
            self._initialized = True
            logger.info("[ComputerUseAgent] Initialized")
        except ImportError as e:
            logger.warning(f"[ComputerUseAgent] BrowserOperator not available: {e}")
            self._initialized = True

    async def execute(
        self,
        goal: str,
        project_context: str = "general",
        max_steps: int = 10,
    ) -> Dict[str, Any]:
        """Execute a browser task."""
        await self._ensure_init()

        if self._browser_op is None:
            return {
                "status": "error",
                "message": "BrowserOperator not available",
                "output": "",
                "screenshot": None,
            }

        try:
            result = await self._browser_op.execute_task(goal, project_context)
            logger.info(f"[ComputerUseAgent] Task completed: {result.get('status')}")
            return result
        except Exception as e:
            logger.error(f"[ComputerUseAgent] Error: {e}")
            return {"status": "error", "message": str(e), "output": "", "screenshot": None}

    async def take_screenshot(self, url: str) -> Dict[str, Any]:
        """Take a screenshot of a URL."""
        return await self.execute(f"Go to {url} and take a screenshot")

    async def verify_ui(self, url: str, requirements: str) -> Dict[str, Any]:
        """Verify UI matches requirements."""
        return await self.execute(f"Go to {url} and verify: {requirements}. Report findings.")

    async def fill_form(self, url: str, form_data: Dict[str, str]) -> Dict[str, Any]:
        """Fill a form on a page."""
        fields = ", ".join(f"{k}={v}" for k, v in form_data.items())
        return await self.execute(f"Go to {url} and fill: {fields}")

    async def click_element(self, url: str, selector: str) -> Dict[str, Any]:
        """Click an element by selector."""
        return await self.execute(f"Go to {url} and click: {selector}")


_instance: Optional[ComputerUseAgent] = None


def get_computer_use_agent() -> ComputerUseAgent:
    global _instance
    if _instance is None:
        _instance = ComputerUseAgent()
    return _instance
