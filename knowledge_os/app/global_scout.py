"""
[KNOWLEDGE OS] Global Scout Engine.
Integration with external APIs to validate knowledge relevance.
Part of the ATRA Singularity framework.
"""

import asyncio
import getpass
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# Third-party imports with fallback
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None
    AIOHTTP_AVAILABLE = False

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

# Local project imports with fallback
try:
    from ai_core import run_smart_agent_async
except ImportError:
    async def run_smart_agent_async(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_async."""
        return None

try:
    from semantic_cache import SemanticAICache
except ImportError:
    class SemanticAICache:
        """Fallback for SemanticAICache."""
        async def save_to_cache(self, *args, **kwargs): pass

logger = logging.getLogger(__name__)

USER_NAME = getpass.getuser()
# Priority: 1. env var, 2. local user (Mac), 3. fallback to admin (Server)
if USER_NAME == 'zhuchyok':
    DEFAULT_DB_URL = f'postgresql://{USER_NAME}@localhost:5432/knowledge_os'
else:
    DEFAULT_DB_URL = 'postgresql://admin:secret@localhost:5432/knowledge_os'

DB_URL = os.getenv('DATABASE_URL', DEFAULT_DB_URL)

# API Keys (можно добавить в .env)
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
STACK_OVERFLOW_KEY = os.getenv('STACK_OVERFLOW_KEY', '')


@dataclass
class ExternalValidation:
    """Результат валидации знания из внешних источников"""
    source: str  # 'github', 'stackoverflow', 'arxiv', 'hackernews'
    relevance_score: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0
    evidence: str  # Ссылка или текст доказательства
    timestamp: datetime
    metadata: Dict[str, Any]


class GitHubScout:
    """Интеграция с GitHub API для проверки best practices"""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token or GITHUB_TOKEN
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    async def search_repositories(self, query: str, limit: int = 5) -> List[Dict]:
        """Поиск репозиториев по запросу"""
        if not AIOHTTP_AVAILABLE:
            return []

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/search/repositories"
                params = {
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": limit
                }
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("items", [])

                    logger.warning("GitHub API error: %d", response.status)
                    return []
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("GitHub search error: %s", exc)
            return []

    async def validate_knowledge(self, knowledge_content: str, domain: str) -> ExternalValidation:
        """Валидация знания через GitHub"""
        # Извлекаем ключевые слова из знания
        keywords = self._extract_keywords(knowledge_content, domain)
        query = " ".join(keywords[:3])  # Первые 3 ключевых слова

        repositories = await self.search_repositories(query, limit=5)

        if not repositories:
            return ExternalValidation(
                source="github",
                relevance_score=0.0,
                confidence=0.0,
                evidence="No repositories found",
                timestamp=datetime.now(),
                metadata={}
            )

        # Вычисляем релевантность на основе популярности репозиториев
        total_stars = sum(r.get("stargazers_count", 0) for r in repositories)
        avg_stars = total_stars / len(repositories) if repositories else 0

        # Нормализуем score (0-1)
        relevance_score = min(1.0, avg_stars / 10000.0)  # 10k stars = 1.0

        return ExternalValidation(
            source="github",
            relevance_score=relevance_score,
            confidence=0.8 if repositories else 0.0,
            evidence=f"Found {len(repositories)} repositories, avg {avg_stars:.0f} stars",
            timestamp=datetime.now(),
            metadata={
                "repositories": [
                    {
                        "name": r.get("full_name"),
                        "stars": r.get("stargazers_count"),
                        "url": r.get("html_url")
                    }
                    for r in repositories[:3]
                ]
            }
        )

    def _extract_keywords(self, content: str, domain: str) -> List[str]:
        """Извлечение ключевых слов из контента"""
        # Простая экстракция (можно улучшить с NLP)
        words = content.lower().split()
        # Фильтруем стоп-слова
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were",
            "be", "been", "to", "of", "and", "or"
        }
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        # Добавляем домен
        if domain:
            keywords.insert(0, domain.lower())
        return keywords[:10]


class StackOverflowScout:
    """Интеграция с Stack Overflow API для проверки решений"""

    BASE_URL = "https://api.stackexchange.com/2.3"

    def __init__(self, key: Optional[str] = None):
        self.key = key or STACK_OVERFLOW_KEY

    async def search_questions(self, query: str, limit: int = 5) -> List[Dict]:
        """Поиск вопросов на Stack Overflow"""
        if not AIOHTTP_AVAILABLE:
            return []

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/search/advanced"
                params = {
                    "q": query,
                    "order": "desc",
                    "sort": "votes",
                    "site": "stackoverflow",
                    "pagesize": limit
                }
                if self.key:
                    params["key"] = self.key

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("items", [])

                    logger.warning("Stack Overflow API error: %d", response.status)
                    return []
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Stack Overflow search error: %s", exc)
            return []

    async def validate_knowledge(self, knowledge_content: str, domain: str) -> ExternalValidation:
        """Валидация знания через Stack Overflow"""
        keywords = self._extract_keywords(knowledge_content, domain)
        query = " ".join(keywords[:3])

        questions = await self.search_questions(query, limit=5)

        if not questions:
            return ExternalValidation(
                source="stackoverflow",
                relevance_score=0.0,
                confidence=0.0,
                evidence="No questions found",
                timestamp=datetime.now(),
                metadata={}
            )

        # Вычисляем релевантность на основе голосов
        total_votes = sum(q.get("score", 0) for q in questions)
        avg_votes = total_votes / len(questions) if questions else 0

        # Нормализуем score (0-1)
        relevance_score = min(1.0, avg_votes / 100.0)  # 100 votes = 1.0

        return ExternalValidation(
            source="stackoverflow",
            relevance_score=relevance_score,
            confidence=0.7 if questions else 0.0,
            evidence=f"Found {len(questions)} questions, avg {avg_votes:.1f} votes",
            timestamp=datetime.now(),
            metadata={
                "questions": [
                    {
                        "title": q.get("title"),
                        "votes": q.get("score"),
                        "answers": q.get("answer_count", 0),
                        "url": q.get("link")
                    }
                    for q in questions[:3]
                ]
            }
        )

    def _extract_keywords(self, content: str, domain: str) -> List[str]:
        """Извлечение ключевых слов"""
        words = content.lower().split()
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were",
            "be", "been", "to", "of", "and", "or"
        }
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        if domain:
            keywords.insert(0, domain.lower())
        return keywords[:10]


class ArxivScout:
    """Интеграция с arXiv API для проверки научных публикаций"""

    BASE_URL = "http://export.arxiv.org/api/query"

    async def search_papers(self, query: str, limit: int = 5) -> List[Dict]:
        """Поиск статей на arXiv"""
        if not AIOHTTP_AVAILABLE:
            return []

        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": limit,
                    "sortBy": "relevance",
                    "sortOrder": "descending"
                }
                async with session.get(self.BASE_URL, params=params) as response:
                    if response.status == 200:
                        text = await response.text()
                        # Простой парсинг XML (можно улучшить)
                        # В реальности нужен XML парсер
                        return self._parse_arxiv_response(text)

                    logger.warning("arXiv API error: %d", response.status)
                    return []
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("arXiv search error: %s", exc)
            return []

    def _parse_arxiv_response(self, _xml_text: str) -> List[Dict]:
        """Простой парсинг ответа arXiv (упрощенный)"""
        # В реальности нужен XML парсер (xml.etree.ElementTree)
        # Здесь возвращаем пустой список для упрощения
        return []

    async def validate_knowledge(self, knowledge_content: str, domain: str) -> ExternalValidation:
        """Валидация знания через arXiv"""
        keywords = self._extract_keywords(knowledge_content, domain)
        query = " ".join(keywords[:3])

        papers = await self.search_papers(query, limit=5)

        return ExternalValidation(
            source="arxiv",
            relevance_score=0.5 if papers else 0.0,
            confidence=0.6 if papers else 0.0,
            evidence=f"Found {len(papers)} papers" if papers else "No papers found",
            timestamp=datetime.now(),
            metadata={"papers": papers}
        )

    def _extract_keywords(self, content: str, domain: str) -> List[str]:
        """Извлечение ключевых слов"""
        words = content.lower().split()
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were",
            "be", "been", "to", "of", "and", "or"
        }
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        if domain:
            keywords.insert(0, domain.lower())
        return keywords[:10]


class GlobalScout:
    """Главный класс для интеграции со всеми внешними API"""

    def __init__(self):
        self.github = GitHubScout()
        self.stackoverflow = StackOverflowScout()
        self.arxiv = ArxivScout()

    async def validate_knowledge_node(
        self,
        knowledge_id: int,
        content: str,
        domain: str
    ) -> Dict[str, Any]:
        """Валидация узла знания через все внешние источники"""
        logger.info("🔍 Validating knowledge node %d via external APIs...", knowledge_id)

        # Параллельная валидация через все источники
        validations = await asyncio.gather(
            self.github.validate_knowledge(content, domain),
            self.stackoverflow.validate_knowledge(content, domain),
            self.arxiv.validate_knowledge(content, domain),
            return_exceptions=True
        )

        # Обработка результатов
        results = []
        for validation in validations:
            if isinstance(validation, Exception):
                logger.error("Validation error: %s", validation)
                continue
            results.append({
                "source": validation.source,
                "relevance_score": validation.relevance_score,
                "confidence": validation.confidence,
                "evidence": validation.evidence,
                "timestamp": validation.timestamp.isoformat(),
                "metadata": validation.metadata
            })

        # Вычисляем общий score
        if results:
            avg_relevance = sum(r["relevance_score"] for r in results) / len(results)
            avg_confidence = sum(r["confidence"] for r in results) / len(results)
        else:
            avg_relevance = 0.0
            avg_confidence = 0.0

        return {
            "knowledge_id": str(knowledge_id),
            "overall_relevance": avg_relevance,
            "overall_confidence": avg_confidence,
            "validations": results,
            "validated_at": datetime.now().isoformat()
        }

    async def update_knowledge_validation(self, conn, knowledge_id: int, validation_result: Dict):
        """Обновление узла знания с результатами валидации"""
        if not ASYNCPG_AVAILABLE:
            return

        try:
            # Получаем текущие metadata
            current_metadata = await conn.fetchval(
                "SELECT metadata FROM knowledge_nodes WHERE id = $1",
                knowledge_id
            )

            if current_metadata is None:
                current_metadata = {}
            elif isinstance(current_metadata, str):
                current_metadata = json.loads(current_metadata)

            # Добавляем результаты валидации
            current_metadata["external_validation"] = validation_result
            current_metadata["last_validated"] = datetime.now().isoformat()

            # Обновляем в БД
            await conn.execute(
                "UPDATE knowledge_nodes SET metadata = $1 WHERE id = $2",
                json.dumps(current_metadata),
                knowledge_id
            )

            logger.info("✅ Updated validation for knowledge node %d", knowledge_id)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error updating validation: %s", exc)


class PredictiveSynthesisScout:
    """Proactive knowledge synthesis based on emerging trends (Singularity v3.0)."""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.cache = SemanticAICache()

    async def run_predictive_cycle(self):
        """Monitor trends and pre-cache potential user queries."""
        if not ASYNCPG_AVAILABLE:
            return

        logger.info("🔭 Predictive Scout: Monitoring future trends...")

        # 1. Fetch recent knowledge gaps or news-like nodes
        conn = await asyncpg.connect(self.db_url)
        nodes = await conn.fetch("""
            SELECT content, d.name as domain
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.created_at > NOW() - INTERVAL '24 hours'
            ORDER BY RANDOM() LIMIT 3
        """)
        await conn.close()

        if not nodes:
            return

        for node in nodes:
            # 2. Synthesize a "Future Question"
            prompt = (
                "ВЫ - ГЛОБАЛЬНЫЙ СКРАУТ ATRA. "
                f"НА ОСНОВЕ НОВОГО ЗНАНИЯ: \"{node['content']}\" (Домен: {node['domain']})\n\n"
                "ЗАДАЧА: Предскажите 1 вопрос, который Владелец может задать в ближайшем будущем "
                "в связи с этим трендом. Дайте идеальный экспертный ответ.\n\n"
                "ВЕРНИТЕ JSON:\n"
                "{\n"
                "    \"predicted_query\": \"Вопрос...\",\n"
                "    \"expert_response\": \"Ответ...\"\n"
                "}"
            )

            response = await run_smart_agent_async(
                prompt,
                expert_name="Виктория",
                category="predictive_scout"
            )

            if not response:
                continue

            try:
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0]

                data = json.loads(response)

                # 3. Pre-cache the result
                await self.cache.save_to_cache(
                    data['predicted_query'],
                    data['expert_response'],
                    "Виктория"
                )
                logger.info("✨ Pre-cached future query: %s", data['predicted_query'])

            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Predictive synthesis error: %s", exc)


async def run_global_scout_cycle():
    """Основной цикл Global Scout для валидации знаний и пре-кэширования"""
    if not ASYNCPG_AVAILABLE:
        logger.error("❌ asyncpg is not installed. Global Scout aborted.")
        return

    logger.info("🌐 Global Scout: Starting validation cycle...")

    conn = await asyncpg.connect(DB_URL)
    scout = GlobalScout()
    predictive = PredictiveSynthesisScout()

    try:
        # Run predictive pre-caching
        await predictive.run_predictive_cycle()

        # (Existing validation code...)
        # (те, которые еще не валидировались или валидировались давно)
        knowledge_nodes = await conn.fetch("""
            SELECT k.id, k.content, d.name as domain
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.metadata->>'last_validated' IS NULL
               OR (k.metadata->>'last_validated')::timestamp < NOW() - INTERVAL '30 days'
            ORDER BY k.created_at DESC
            LIMIT 10
        """)

        if not knowledge_nodes:
            logger.info("No knowledge nodes to validate")
            return

        logger.info("Found %d knowledge nodes to validate", len(knowledge_nodes))

        # Валидируем каждое знание
        for node in knowledge_nodes:
            try:
                validation_result = await scout.validate_knowledge_node(
                    node["id"],
                    node["content"],
                    node["domain"]
                )

                # Обновляем в БД
                await scout.update_knowledge_validation(conn, node["id"], validation_result)

                # Небольшая задержка между запросами (rate limiting)
                await asyncio.sleep(1)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Error validating node %d: %s", node['id'], exc)

        logger.info("✅ Global Scout cycle completed")

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Global Scout error: %s", exc)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_global_scout_cycle())
