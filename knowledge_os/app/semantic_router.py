import asyncio
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("semantic_router")
_REDIS_MANAGER_SINGLETON = None


def _get_redis_manager_singleton():
    global _REDIS_MANAGER_SINGLETON
    if _REDIS_MANAGER_SINGLETON is not None:
        return _REDIS_MANAGER_SINGLETON
    try:
        from app.redis_manager import RedisManager

        _REDIS_MANAGER_SINGLETON = RedisManager()
    except ImportError:
        logger.debug("RedisManager not available for SemanticRouter cache")
        _REDIS_MANAGER_SINGLETON = None
    return _REDIS_MANAGER_SINGLETON


class SemanticRouter:
    """
    Семантический роутер для мгновенной классификации запросов.
    Использует эмбеддинги для определения типа задачи (Fast Track, Reasoning, Coding).
    """

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold
        self.is_docker = (
            os.path.exists("/.dockerenv")
            or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
        )
        self.ollama_base = os.getenv("OLLAMA_BASE_URL") or (
            "http://host.docker.internal:11434" if self.is_docker else "http://localhost:11434"
        )
        self.embed_url = f"{self.ollama_base.rstrip('/')}/api/embeddings"
        self.embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

        # [SINGULARITY 24.0] Redis Cache for Embeddings
        self.redis_manager = _get_redis_manager_singleton()

        # Эталонные фразы для категорий (будут заменены на эмбеддинги при первом вызове)
        self.categories = {
            "fast_track": [
                "привет",
                "здравствуй",
                "как дела",
                "кто ты",
                "что ты умеешь",
                "спасибо",
                "пока",
                "тест",
                "ping",
                "hi",
                "hello",
            ],
            "info_query": [
                "помощь",
                "help",
                "инструкция",
                "как пользоваться",
                "навыки",
                "способности",
            ],
            "vip_query": ["иван", "ceo", "стратег", "совет директоров", "стратегическое решение"],
        }
        self.category_embeddings: Dict[str, List[List[float]]] = {}

    async def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Получить эмбеддинг через Ollama (с кэшированием в Redis)"""
        cache_key = f"emb:{self.embed_model}:{text.strip().lower()}"
        if self.redis_manager:
            cached = await self.redis_manager.get_cache(cache_key)
            if cached:
                return cached

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.embed_url,
                    json={"model": self.embed_model, "prompt": text, "keep_alive": 0},
                )
                if response.status_code == 200:
                    emb = response.json().get("embedding")
                    if emb and self.redis_manager:
                        # Кэшируем на 7 дней (эмбеддинги статичны для модели)
                        await self.redis_manager.set_cache(cache_key, emb, ttl=604800)
                    return emb
        except Exception as e:
            logger.error(f"Embedding error: {e}")
        return None

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Расчет косинусного сходства"""
        import math

        dot_product = sum(a * b for a, b in zip(v1, v2))
        magnitude1 = math.sqrt(sum(a * a for a in v1))
        magnitude2 = math.sqrt(sum(b * b for b in v2))
        if not magnitude1 or not magnitude2:
            return 0.0
        return dot_product / (magnitude1 * magnitude2)

    async def warmup(self):
        """Прогрев: вычисление эмбеддингов для эталонных фраз"""
        logger.info("🚀 Warming up Semantic Router...")
        for cat, phrases in self.categories.items():
            embeddings = []
            for phrase in phrases:
                emb = await self._get_embedding(phrase)
                if emb:
                    embeddings.append(emb)
            self.category_embeddings[cat] = embeddings
        logger.info(
            f"✅ Semantic Router warmed up. Categories: {list(self.category_embeddings.keys())}"
        )

    async def route(self, query: str) -> Optional[str]:
        """Определить категорию запроса и подгрузить релевантные навыки (Predictive Prefetching)"""
        if not self.category_embeddings:
            await self.warmup()

        query_emb = await self._get_embedding(query)
        if not query_emb:
            return None

        best_score = 0.0
        best_category = None

        for cat, embeddings in self.category_embeddings.items():
            for emb in embeddings:
                score = self._cosine_similarity(query_emb, emb)
                if score > best_score:
                    best_score = score
                    best_category = cat

        if best_score >= self.threshold:
            logger.info(f"🎯 Routed to {best_category} (score: {best_score:.2f})")

            # [SINGULARITY 24.0] Predictive Context Prefetching
            # Если мы определили категорию, можем заранее подгрузить релевантные SOP
            try:
                from app.skill_registry import get_skill_registry

                registry = get_skill_registry()
                # Ищем навыки по категории роутера
                related_skills = [
                    s for s in registry.get_all_skills() if s.category == best_category
                ]
                if related_skills:
                    logger.info(
                        f"🔮 [PREFETCH] Found {len(related_skills)} related skills for {best_category}"
                    )
                    # Сохраняем в кэш Redis для быстрого доступа в ai_core
                    if self.redis_manager:
                        prefetch_data = "\n".join(
                            [
                                f"### SOP: {s.name}\n{s.instructions[:1000]}"
                                for s in related_skills[:2]
                            ]
                        )
                        await self.redis_manager.set_cache(
                            f"prefetch:{hashlib.md5(query.encode()).hexdigest()}",
                            prefetch_data,
                            ttl=300,
                        )
            except Exception as pe:
                logger.debug(f"Predictive prefetch failed: {pe}")

            return best_category

        return None


# Глобальный экземпляр
_router = None


def get_semantic_router():
    global _router
    if _router is None:
        _router = SemanticRouter()
    return _router


if __name__ == "__main__":

    async def test():
        router = get_semantic_router()
        await router.warmup()
        res = await router.route("хай, виктория")
        print(f"Result for 'хай, виктория': {res}")
        res = await router.route("что ты умеешь делать?")
        print(f"Result for 'что ты умеешь делать?': {res}")

    asyncio.run(test())
