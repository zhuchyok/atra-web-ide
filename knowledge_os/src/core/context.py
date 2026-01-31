import requests
from typing import Dict

try:
    from src.utils.cache_utils import cache_with_ttl
except ImportError:
    try:
        from cache_utils import cache_with_ttl
    except ImportError:
        def cache_with_ttl(*args, **kwargs):
            def decorator(func):
                return func
            return decorator


@cache_with_ttl(ttl_seconds=1800)
def get_fgi_value() -> int:
    """FGI (0-100) с кэшированием ~30 минут от alternative.me."""
    try:
        url = "https://api.alternative.me/fng/"
        params = {"limit": 1, "format": "json"}
        session = requests.Session()
        session.headers.update(
            {"User-Agent": "Mozilla/5.0 (compatible; ATRA/1.0)"}
        )
        resp = session.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            val = int(data.get("data", [{}])[0].get("value", 0))
            return max(0, min(val, 100))
        return -1
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return -1


def get_fgi_label(value: int) -> str:
    if value < 0:
        return "—"
    if value <= 25:
        return "Страх"
    if value <= 45:
        return "Умеренный страх"
    if value < 55:
        return "Нейтрально"
    if value < 75:
        return "Умеренная жадность"
    return "Жадность"


async def get_market_sentiment(
    symbol: str,
    get_anomaly_data_with_fallback,
    db,
    ttl_seconds: int = 900,
) -> Dict:
    """Сводный сентимент: FGI + аномалии (+ опционально новости).

    Требует передачи функции `get_anomaly_data_with_fallback` и инстанса `db` для кэша.
    """
    try:
        cache_key = f"sentiment:{symbol}"
        cached = db.cache_get("market_sentiment", cache_key)
        if cached is not None:
            return cached

        fgi_val = get_fgi_value()
        fgi_norm = None
        if isinstance(fgi_val, int) and 0 <= fgi_val <= 100:
            fgi_norm = (fgi_val - 50) / 50.0

        data = await get_anomaly_data_with_fallback(symbol, ttl_seconds=ttl_seconds)
        score = 0.0
        source = data.get("source", "none") if isinstance(data, dict) else "none"
        if isinstance(data, dict):
            v24 = float(data.get("volume_24h", 0) or 0)
            mc = float(data.get("market_cap", 0) or 0)
            if v24 > 0 and mc > 0:
                ratio = min(1.0, (v24 / mc) * 2.0)
                score += (ratio - 0.5)

        if fgi_norm is not None:
            score = (0.6 * score) + (0.4 * fgi_norm)

        score = max(-1.0, min(1.0, score))
        label = (
            "Сильный позитив"
            if score > 0.5
            else (
                "Умеренный позитив"
                if score > 0.1
                else (
                    "Нейтрально"
                    if score > -0.1
                    else ("Умеренно негативно" if score > -0.5 else "Сильный негатив")
                )
            )
        )
        result = {
            "score": score,
            "label": label,
            "fgi": fgi_val if isinstance(fgi_val, int) else None,
            "source": source,
        }
        db.cache_set("market_sentiment", cache_key, result, ttl_seconds)
        return result
    except (ValueError, TypeError, KeyError):
        return {"score": 0.0, "label": "Нейтрально", "fgi": None, "source": "error"}


