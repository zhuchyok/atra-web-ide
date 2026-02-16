"""
[SINGULARITY 10.0+] Browser Operator.
Autonomous visual verification and UI testing using browser-use and Playwright.
"""

import os
import logging
import asyncio
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

# Optional: browser-use imports
try:
    from browser_use import Agent, Browser, BrowserConfig, Controller
    from langchain_openai import ChatOpenAI
    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False
    logging.warning("⚠️ browser-use not installed. BrowserOperator will run in mock mode.")

logger = logging.getLogger(__name__)

class BrowserOperator:
    """
    Operates a browser autonomously to verify UI/UX and perform actions.
    Acts as the 'eyes and hands' for Victoria, executed by Veronica.
    """
    
    def __init__(self):
        self.headless = os.getenv("BROWSER_USE_HEADLESS", "true").lower() == "true"
        self.browser_config = BrowserConfig(
            headless=self.headless,
            disable_security=True,  # Allow local testing
        )
        self.controller = Controller()
        
    async def execute_task(self, goal: str, project_context: str = "general") -> Dict[str, Any]:
        """
        Executes a browser task autonomously.
        """
        if not BROWSER_USE_AVAILABLE:
            return {
                "status": "error",
                "message": "browser-use library not installed",
                "output": "Mock output: Browser automation is not available."
            }
            
        try:
            # Use local LLM via OpenAI-compatible API (Ollama/Victoria)
            # Note: browser-use works best with vision models.
            # We'll use Victoria's endpoint as the brain.
            llm_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
            
            # For now, we use a generic ChatOpenAI config pointing to our local brain
            llm = ChatOpenAI(
                model=os.getenv("VICTORIA_MODEL", "qwen2.5-coder:32b"),
                base_url=f"{llm_url}/v1",
                api_key="not-needed"
            )
            
            browser = Browser(config=self.browser_config)
            agent = Agent(
                task=goal,
                llm=llm,
                browser=browser,
                controller=self.controller
            )
            
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
                "steps_count": len(history.steps)
            }
            
        except Exception as e:
            logger.error(f"❌ [BROWSER OPERATOR] Task failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
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
