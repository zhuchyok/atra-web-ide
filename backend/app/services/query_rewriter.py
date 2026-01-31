"""
Фаза 4, неделя 1: переписывание запросов для улучшения поиска в RAG.

Пример: «как настроить?» → «инструкция по настройке», «что такое X» → «определение X».
Опционально: LLM для переписывания; по умолчанию — эвристики и синонимы.
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


# Простые шаблоны: паттерн запроса → как переписать для поиска (ключевые слова)
# В replacement \1 — первая группа (для re.sub).
QUERY_REWRITE_PATTERNS = [
    (r"как\s+(настроить|сделать|запустить|установить)", r"инструкция настройка запуск установка"),
    (r"что\s+такое\s+(.+)", r"определение \1"),
    (r"какой\s+(.+)", r"\1 описание"),
    (r"почему\s+(.+)", r"причина \1 объяснение"),
    (r"где\s+(.+)", r"расположение \1 путь"),
    (r"зачем\s+(.+)", r"цель \1 назначение"),
    (r"сколько\s+(.+)", r"\1 число количество метрика"),
]


class QueryRewriter:
    """
    Переписывание запроса для улучшения поиска в RAG.
    Сохраняет исходный запрос для ответа; возвращает вариант, оптимизированный для поиска.
    """

    def __init__(self, use_llm: bool = False, llm_url: Optional[str] = None):
        self.use_llm = use_llm
        self.llm_url = llm_url

    async def rewrite_for_rag(
        self,
        query: str,
        history: Optional[List[dict]] = None,
        max_length: int = 200,
    ) -> str:
        """
        Переписывание запроса для лучшего поиска по БЗ.
        history: предыдущие сообщения диалога (опционально, для контекста).
        Возвращает строку, подходящую для эмбеддинга/поиска.
        """
        if not query or not query.strip():
            return query
        q = query.strip()
        if self.use_llm and self.llm_url:
            rewritten = await self._rewrite_with_llm(q, history)
            if rewritten:
                return rewritten[:max_length]
        return self._rewrite_heuristic(q)[:max_length]

    def _rewrite_heuristic(self, query: str) -> str:
        """Эвристическое переписывание по шаблонам и ключевым словам."""
        q_lower = query.lower()
        for pattern, replacement in QUERY_REWRITE_PATTERNS:
            m = re.search(pattern, q_lower, re.IGNORECASE)
            if m:
                try:
                    repl = re.sub(pattern, replacement, q_lower, count=1, flags=re.IGNORECASE)
                    if repl and repl != q_lower:
                        return (repl + " " + q_lower).strip()[:300]
                except re.error:
                    pass
        return query

    async def _rewrite_with_llm(
        self, query: str, history: Optional[List[dict]] = None
    ) -> Optional[str]:
        """Переписывание через LLM (один запрос к Ollama/API)."""
        try:
            import httpx
            prompt = (
                "Перепиши следующий поисковый запрос пользователя в одно короткое предложение "
                "из ключевых слов для семантического поиска по базе знаний. "
                "Сохрани суть. Ответь только переписанным запросом, без пояснений.\n\nЗапрос: "
            ) + query
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.post(
                    f"{self.llm_url.rstrip('/')}/api/generate",
                    json={"model": "llama2", "prompt": prompt, "stream": False},
                )
                if r.status_code != 200:
                    return None
                data = r.json()
                text = (data.get("response") or "").strip()
                return text or None
        except Exception as e:
            logger.debug("Query rewrite LLM failed: %s", e)
            return None
