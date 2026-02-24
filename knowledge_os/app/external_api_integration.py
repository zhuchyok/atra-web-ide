"""
External API Integration
Интеграция с внешними API (GitHub, Stack Overflow, документация)
Singularity 8.0: New Capabilities
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class ExternalAPIIntegration:
    """
    Интеграция с внешними API для дополнения ответов.
    Поддерживает GitHub, Stack Overflow, документацию библиотек.
    """

    def __init__(self):
        """Инициализация интеграции с внешними API"""
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.stackoverflow_key = os.getenv("STACKOVERFLOW_KEY")
        self.cache: Dict[str, Any] = {}  # Простой in-memory кэш

    async def search_github_code(
        self, query: str, language: str = "python", limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Ищет код на GitHub.

        Args:
            query: Поисковый запрос
            language: Язык программирования
            limit: Максимальное количество результатов

        Returns:
            Список результатов поиска
        """
        cache_key = f"github_{query}_{language}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            url = "https://api.github.com/search/code"
            params = {"q": f"{query} language:{language}", "per_page": limit}
            headers = {}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])

                    results = []
                    for item in items[:limit]:
                        results.append(
                            {
                                "repository": item.get("repository", {}).get("full_name", ""),
                                "path": item.get("path", ""),
                                "url": item.get("html_url", ""),
                                "snippet": item.get("text_matches", [{}])[0].get("fragment", "")[
                                    :200
                                ],
                            }
                        )

                    self.cache[cache_key] = results
                    return results
                else:
                    logger.warning(f"⚠️ [EXTERNAL API] GitHub API error: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"❌ [EXTERNAL API] Ошибка поиска на GitHub: {e}")
            return []

    async def search_stackoverflow(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Ищет решения на Stack Overflow.

        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов

        Returns:
            Список результатов поиска
        """
        cache_key = f"stackoverflow_{query}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            url = "https://api.stackexchange.com/2.3/search/advanced"
            params = {
                "q": query,
                "site": "stackoverflow",
                "pagesize": limit,
                "sort": "relevance",
                "order": "desc",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])

                    results = []
                    for item in items[:limit]:
                        results.append(
                            {
                                "title": item.get("title", ""),
                                "link": item.get("link", ""),
                                "score": item.get("score", 0),
                                "answer_count": item.get("answer_count", 0),
                                "excerpt": item.get("excerpt", "")[:200],
                            }
                        )

                    self.cache[cache_key] = results
                    return results
                else:
                    logger.warning(
                        f"⚠️ [EXTERNAL API] Stack Overflow API error: {response.status_code}"
                    )
                    return []
        except Exception as e:
            logger.error(f"❌ [EXTERNAL API] Ошибка поиска на Stack Overflow: {e}")
            return []

    async def get_library_documentation(self, library_name: str, query: str) -> Optional[str]:
        """
        Получает документацию библиотеки (упрощенная версия).

        Args:
            library_name: Имя библиотеки
            query: Поисковый запрос

        Returns:
            Релевантная документация или None
        """
        # Упрощенная версия - можно расширить через парсинг официальной документации
        # Пока возвращаем None
        logger.debug(f"📚 [EXTERNAL API] Запрос документации для {library_name}: {query}")
        return None

    async def enhance_response_with_external_data(self, query: str, current_response: str) -> str:
        """
        Дополняет ответ внешними данными.

        Args:
            query: Исходный запрос
            current_response: Текущий ответ

        Returns:
            Дополненный ответ
        """
        enhanced_parts = [current_response]

        # Определяем, нужны ли внешние данные
        query_lower = query.lower()

        # Если запрос о коде, ищем на GitHub
        if any(kw in query_lower for kw in ["код", "пример", "реализация", "github"]):
            github_results = await self.search_github_code(query, limit=2)
            if github_results:
                enhanced_parts.append("\n\n📚 **Релевантные примеры с GitHub:**")
                for result in github_results:
                    enhanced_parts.append(
                        f"- [{result['repository']}/{result['path']}]({result['url']})"
                    )
                    if result.get("snippet"):
                        enhanced_parts.append(f"  ```\n{result['snippet']}\n```")

        # Если запрос о проблеме/ошибке, ищем на Stack Overflow
        if any(
            kw in query_lower for kw in ["ошибка", "проблема", "как исправить", "stackoverflow"]
        ):
            so_results = await self.search_stackoverflow(query, limit=2)
            if so_results:
                enhanced_parts.append("\n\n💡 **Релевантные решения на Stack Overflow:**")
                for result in so_results:
                    enhanced_parts.append(
                        f"- [{result['title']}]({result['link']}) (score: {result['score']}, answers: {result['answer_count']})"
                    )
                    if result.get("excerpt"):
                        enhanced_parts.append(f"  {result['excerpt']}")

        return "\n".join(enhanced_parts)


# Singleton instance
_external_api_instance: Optional[ExternalAPIIntegration] = None


def get_external_api_integration() -> ExternalAPIIntegration:
    """Получить singleton экземпляр интеграции с внешними API"""
    global _external_api_instance
    if _external_api_instance is None:
        _external_api_instance = ExternalAPIIntegration()
    return _external_api_instance
