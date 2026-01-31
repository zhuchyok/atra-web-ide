"""
Батчинг запросов эмбеддингов к Ollama (Фаза 3, день 3–4).
Группирует запросы и выполняет параллельные вызовы.
"""
import asyncio
import logging
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class EmbeddingBatchProcessor:
    """Процессор для батчинга запросов эмбеддингов к Ollama."""

    def __init__(
        self,
        ollama_url: str,
        ollama_model: str,
        batch_size: int = 10,
        batch_timeout_ms: int = 50,
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self.queue: asyncio.Queue = asyncio.Queue()
        self.processing = False
        self.results_cache: Dict[str, List[float]] = {}

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Получение эмбеддинга с батчингом."""
        if not text or len(text.strip()) < 2:
            return None
        cache_key = text.strip().lower()
        if cache_key in self.results_cache:
            return self.results_cache[cache_key]
        future: asyncio.Future = asyncio.Future()
        await self.queue.put((text, future))
        if not self.processing:
            asyncio.create_task(self._process_batches())
        try:
            return await asyncio.wait_for(future, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Embedding batch timeout for: %s...", text[:50])
            return None

    async def _process_batches(self) -> None:
        """Обработка батчей из очереди."""
        self.processing = True
        try:
            while not self.queue.empty():
                batch: List[str] = []
                futures: List[asyncio.Future] = []
                timeout_sec = self.batch_timeout_ms / 1000.0
                loop = asyncio.get_running_loop()
                deadline = loop.time() + timeout_sec
                while len(batch) < self.batch_size:
                    try:
                        wait = max(0.01, deadline - loop.time())
                        text, future = await asyncio.wait_for(
                            self.queue.get(), timeout=min(wait, timeout_sec)
                        )
                        batch.append(text)
                        futures.append(future)
                    except asyncio.TimeoutError:
                        break
                if not batch:
                    continue
                try:
                    embeddings = await self._call_ollama_batch(batch)
                    for i, (f, emb) in enumerate(zip(futures, embeddings)):
                        if not f.done():
                            f.set_result(emb)
                        if emb is not None and i < len(batch):
                            self.results_cache[batch[i].strip().lower()] = emb
                    logger.debug("Processed embedding batch of %s items", len(batch))
                except Exception as e:
                    logger.error("Error processing batch: %s", e)
                    for f in futures:
                        if not f.done():
                            f.set_exception(e)
        finally:
            self.processing = False

    async def _call_ollama_batch(
        self, texts: List[str]
    ) -> List[Optional[List[float]]]:
        """Параллельные запросы к Ollama (Ollama не поддерживает один батч)."""
        tasks = [self._call_ollama_single(t) for t in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: List[Optional[List[float]]] = []
        for r in results:
            if isinstance(r, Exception):
                logger.debug("Ollama single error: %s", r)
                out.append(None)
            else:
                out.append(r)
        return out

    async def _call_ollama_single(self, text: str) -> Optional[List[float]]:
        """Одиночный запрос к Ollama."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={"model": self.ollama_model, "prompt": text[:8000]},
                )
                if r.status_code == 200:
                    return r.json().get("embedding")
                logger.warning("Ollama embeddings %s: %s", r.status_code, r.text[:200])
                return None
        except Exception as e:
            logger.warning("Ollama embedding error: %s", e)
            return None

    def clear_cache(self) -> None:
        """Очистка кэша результатов."""
        self.results_cache.clear()

    async def stats(self) -> Dict:
        """Статистика процессора."""
        return {
            "queue_size": self.queue.qsize(),
            "processing": self.processing,
            "cache_size": len(self.results_cache),
            "batch_size": self.batch_size,
            "batch_timeout_ms": self.batch_timeout_ms,
        }
