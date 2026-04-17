"""
Google Grounding - Real-time information via Google Search API

Usage:
    from google_grounder import GoogleGrounder

    grounder = GoogleGrounder()
    results = await grounder.ground("When was Python 3.12 released?")
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")


class GoogleGrounder:
    """
    Google Custom Search API for real-time grounding.
    Falls back to scraping if API key not available.
    """

    def __init__(self, max_results: int = 5):
        self.max_results = max_results
        self.api_key = GOOGLE_API_KEY
        self.cse_id = GOOGLE_CSE_ID

    async def ground(self, query: str) -> List[Dict[str, Any]]:
        """Search Google for real-time information."""
        if not self.api_key:
            return await self._fallback_scrape(query)
        return await self._api_search(query)

    async def _api_search(self, query: str) -> List[Dict[str, Any]]:
        import httpx

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": self.max_results,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"[GoogleGrounder] API error: {resp.status_code}")
                    return await self._fallback_scrape(query)

                data = resp.json()
                results = []
                for item in data.get("items", [])[: self.max_results]:
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "url": item.get("link", ""),
                            "snippet": item.get("snippet", ""),
                            "source": "google",
                        }
                    )
                return results
        except Exception as e:
            logger.warning(f"[GoogleGrounder] Error: {e}")
            return await self._fallback_scrape(query)

    async def _fallback_scrape(self, query: str) -> List[Dict[str, Any]]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=self.max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "source": "duckduckgo",
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"[GoogleGrounder] Fallback failed: {e}")
            return []


async def ground_query(query: str) -> List[Dict[str, Any]]:
    """Convenience function."""
    grounder = GoogleGrounder()
    return await grounder.ground(query)


_instance: Optional[GoogleGrounder] = None


def get_google_grounder() -> GoogleGrounder:
    global _instance
    if _instance is None:
        _instance = GoogleGrounder()
    return _instance
