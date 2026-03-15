"""
[SINGULARITY 10.0+] Browser Operator.
Autonomous visual verification and UI testing using browser-use and Playwright.
"""

import asyncio
import base64
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Optional: browser-use imports
try:
    from browser_use import Agent, Browser, BrowserConfig, Controller
    from langchain_openai import ChatOpenAI

    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False
    logging.warning("⚠️ browser-use not installed. BrowserOperator will run in mock mode.")

logger = logging.getLogger(__name__)


def _make_browser_config(headless: bool, user_data_dir: Optional[str] = None) -> "BrowserConfig":
    """Build BrowserConfig, optionally with persistent profile (cookies/session survive restarts)."""
    kwargs: Dict[str, Any] = {
        "headless": headless,
        "disable_security": True,  # Allow local testing
    }
    if user_data_dir:
        kwargs["user_data_dir"] = user_data_dir
        # Для первого входа в Директ/любой кабинет нужен видимый браузер
        if headless:
            logger.info(
                "BROWSER_USER_DATA_DIR задан: при первом логине установи BROWSER_USE_HEADLESS=false"
            )
    if not BROWSER_USE_AVAILABLE:
        return None
    try:
        return BrowserConfig(**kwargs)
    except TypeError:
        # Старые версии browser-use без user_data_dir
        kwargs.pop("user_data_dir", None)
        logger.warning(
            "Текущая версия browser-use не поддерживает user_data_dir; сессия не сохранится"
        )
        return BrowserConfig(**kwargs)


class BrowserOperator:
    """
    Operates a browser autonomously to verify UI/UX and perform actions.
    Acts as the 'eyes and hands' for Victoria, executed by Veronica.

    Постоянный профиль: задай BROWSER_USER_DATA_DIR (путь к папке) — тогда куки/логин
    сохранятся между запусками. Для первого входа в Директ включи BROWSER_USE_HEADLESS=false.
    """

    def __init__(self):
        self.headless = os.getenv("BROWSER_USE_HEADLESS", "true").lower() == "true"
        user_data_dir = os.getenv("BROWSER_USER_DATA_DIR", "").strip() or None
        if user_data_dir and not os.path.isabs(user_data_dir):
            # Относительный путь — от корня knowledge_os или репо
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            user_data_dir = os.path.abspath(os.path.join(base, user_data_dir))
        if user_data_dir:
            os.makedirs(user_data_dir, exist_ok=True)
        self.browser_config = (
            _make_browser_config(self.headless, user_data_dir) if BROWSER_USE_AVAILABLE else None
        )
        self.controller = Controller() if BROWSER_USE_AVAILABLE else None

    async def execute_task(self, goal: str, project_context: str = "general") -> Dict[str, Any]:
        """
        Executes a browser task autonomously.
        """
        if not BROWSER_USE_AVAILABLE:
            return {
                "status": "error",
                "message": "browser-use library not installed",
                "output": "Mock output: Browser automation is not available.",
            }

        try:
            # Use local LLM via OpenAI-compatible API (Ollama/Victoria)
            # Note: browser-use works best with vision models.
            # We'll use Victoria's endpoint as the brain.
            llm_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

            # For now, we use a generic ChatOpenAI config pointing to our local brain
            llm = ChatOpenAI(
                model=os.getenv("VICTORIA_MODEL", "victoria-wisdom-v3.5"),
                base_url=f"{llm_url}/v1",
                api_key="not-needed",
            )

            browser = Browser(config=self.browser_config)
            agent = Agent(task=goal, llm=llm, browser=browser, controller=self.controller)

            logger.info(f"🌐 [BROWSER OPERATOR] Starting task: {goal}")
            history = await agent.run()

            # Extract results
            final_result = history.final_result()
            screenshots = history.screenshots()

            last_screenshot_b64 = None
            if screenshots:
                # Convert last screenshot to base64 for Victoria
                with open(screenshots[-1], "rb") as f:
                    last_screenshot_b64 = base64.b64encode(f.read()).decode("utf-8")

            return {
                "status": "success",
                "output": final_result,
                "screenshot": last_screenshot_b64,
                "steps_count": len(history.steps),
            }

        except Exception as e:
            logger.error(f"❌ [BROWSER OPERATOR] Task failed: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            # Ensure browser is closed if needed (Agent usually handles this)
            pass

    async def verify_ui(self, url: str, requirements: str) -> Dict[str, Any]:
        """
        Specific shortcut for UI verification.
        """
        goal = f"Go to {url} and verify if it matches these requirements: {requirements}. Provide a detailed report and a screenshot."
        return await self.execute_task(goal)


_instance = None


def get_browser_operator():
    global _instance
    if _instance is None:
        _instance = BrowserOperator()
    return _instance
