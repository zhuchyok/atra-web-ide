"""
П.6 PRINCIPLE_EXPERTS_FIRST: единая точка веб-поиска для воркера и экспертов.

Порядок провайдеров задаётся конфигом WEB_SEARCH_PROVIDERS (по умолчанию duckduckgo,ollama).
При ошибке/таймауте — ретраи с экспоненциальной задержкой, затем следующий провайдер.
Таймауты на провайдера: WEB_SEARCH_TIMEOUT_DUCKDUCKGO, WEB_SEARCH_TIMEOUT_OLLAMA (сек).
"""
import hashlib
import logging
import os
import time
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# П.1 пушка: кэш результатов по хешу запроса (TTL 1–6 ч)
_WEB_SEARCH_CACHE: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
WEB_SEARCH_CACHE_TTL_SEC = int(os.getenv("WEB_SEARCH_CACHE_TTL_SEC", "3600"))  # 1 ч по умолчанию
WEB_SEARCH_CACHE_MAX_SIZE = int(os.getenv("WEB_SEARCH_CACHE_MAX_SIZE", "500"))

OLLAMA_WEB_SEARCH_URL = "https://ollama.com/api/web_search"

# Конфиг: порядок провайдеров (через запятую), таймауты в секундах, макс ретраев на провайдера
WEB_SEARCH_PROVIDERS = (os.getenv("WEB_SEARCH_PROVIDERS") or "duckduckgo,ollama").strip().lower().split(",")
WEB_SEARCH_TIMEOUT_DUCKDUCKGO = float(os.getenv("WEB_SEARCH_TIMEOUT_DUCKDUCKGO", "10"))
WEB_SEARCH_TIMEOUT_OLLAMA = float(os.getenv("WEB_SEARCH_TIMEOUT_OLLAMA", "15"))
WEB_SEARCH_MAX_RETRIES = int(os.getenv("WEB_SEARCH_MAX_RETRIES", "2"))


def _search_duckduckgo(query: str, max_results: int, timeout: float) -> List[Dict[str, Any]]:
    """Один вызов DuckDuckGo. При ошибке пробрасывает исключение."""
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    out = []
    for r in results:
        out.append({
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", ""),
            "source": "duckduckgo",
        })
    return out


def _search_ollama(query: str, max_results: int, timeout: float) -> List[Dict[str, Any]]:
    """Один вызов Ollama web_search. При ошибке или пустом ответе возвращает []."""
    api_key = os.getenv("OLLAMA_API_KEY")
    if not api_key:
        return []
    import httpx
    n = min(max_results, 10)
    with httpx.Client(timeout=timeout) as client:
        r = client.post(
            OLLAMA_WEB_SEARCH_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"query": query[:500], "max_results": n},
        )
    if r.status_code != 200:
        logger.debug("[WEB_SEARCH] Ollama web_search: %s %s", r.status_code, (r.text or "")[:200])
        return []
    data = r.json()
    out = []
    for item in (data if isinstance(data, list) else data.get("results", data.get("data", [])))[:n]:
        if isinstance(item, dict):
            out.append({
                "title": item.get("title", item.get("name", "")),
                "url": item.get("url", item.get("link", "")),
                "snippet": item.get("snippet", item.get("body", item.get("content", ""))),
                "source": "ollama_web_search",
            })
    return out


def _cache_key(query: str, max_results: int) -> str:
    return hashlib.sha256(f"{query.strip().lower()}:{max_results}".encode()).hexdigest()


def web_search_sync(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Синхронный веб-поиск по конфигу провайдеров (WEB_SEARCH_PROVIDERS).
    Результаты кэшируются по хешу запроса (TTL WEB_SEARCH_CACHE_TTL_SEC).
    Ретраи с экспоненциальной задержкой (1s, 2s), затем следующий провайдер.
    Возвращает список dict с ключами: title, url, snippet, source.
    В логах пишется использованный источник (used_source).
    """
    key = _cache_key(query, max_results)
    now = time.time()
    if key in _WEB_SEARCH_CACHE:
        cached, ts = _WEB_SEARCH_CACHE[key]
        if now - ts < WEB_SEARCH_CACHE_TTL_SEC:
            logger.debug("[WEB_SEARCH] cache hit key=%s", key[:12])
            return cached
        del _WEB_SEARCH_CACHE[key]
    # Ограничение размера кэша (LRU-подобное: удаляем самые старые)
    if len(_WEB_SEARCH_CACHE) >= WEB_SEARCH_CACHE_MAX_SIZE:
        oldest = min(_WEB_SEARCH_CACHE.items(), key=lambda x: x[1][1])
        del _WEB_SEARCH_CACHE[oldest[0]]

    for provider in WEB_SEARCH_PROVIDERS:
        provider = provider.strip()
        if not provider:
            continue
        timeout = WEB_SEARCH_TIMEOUT_DUCKDUCKGO if provider == "duckduckgo" else WEB_SEARCH_TIMEOUT_OLLAMA
        for attempt in range(WEB_SEARCH_MAX_RETRIES):
            try:
                if provider == "duckduckgo":
                    out = _search_duckduckgo(query, max_results, timeout)
                elif provider == "ollama":
                    out = _search_ollama(query, max_results, timeout)
                else:
                    logger.debug("[WEB_SEARCH] Unknown provider: %s", provider)
                    break
                if out:
                    used = out[0].get("source", provider)
                    logger.info("[WEB_SEARCH] used_source=%s results=%d", used, len(out))
                    _WEB_SEARCH_CACHE[key] = (out, now)
                    return out
                if provider == "ollama":
                    break  # пустой ответ — не ретраим
            except Exception as e:
                delay = (2 ** attempt) if attempt < WEB_SEARCH_MAX_RETRIES - 1 else 0
                logger.debug("[WEB_SEARCH] %s attempt %s failed: %s; delay=%.1fs", provider, attempt + 1, e, delay)
                if delay > 0:
                    time.sleep(delay)
        # перед следующим провайдером короткая пауза
        time.sleep(0.5)
    return []
