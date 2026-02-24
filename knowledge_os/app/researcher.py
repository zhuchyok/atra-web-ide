import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import asyncpg
import httpx

logger = logging.getLogger(__name__)

# DuckDuckGo search with fallback
try:
    from duckduckgo_search import DDGS

    DDGS_AVAILABLE = True
except ImportError:
    DDGS = None
    DDGS_AVAILABLE = False
    logger.warning("duckduckgo-search не установлен. Установите: pip install duckduckgo-search")


async def get_pool():
    return await asyncpg.create_pool(
        os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os"),
        min_size=1,
        max_size=5,
    )


async def process_with_local_model(
    prompt: str, node_url: str = "http://localhost:11434", model: str = "phi3.5:3.8b"
) -> str:
    """Обработка запроса локальной моделью (без токенов)"""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{node_url}/api/generate", json={"model": model, "prompt": prompt, "stream": False}
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
    except Exception as e:
        logger.error(f"Ошибка локальной модели: {e}")
    return ""


async def perform_research():
    """Автономное веб-исследование для экспертов с обработкой локальными моделями (без токенов)"""
    print("🌐 Starting Autonomous Web Research (без токенов)...")

    if not DDGS_AVAILABLE:
        print("⚠️ duckduckgo-search не установлен. Установите: pip install duckduckgo-search")
        return

    pool = await get_pool()

    # Определяем доступные узлы для локальных моделей (Mac Studio)
    local_nodes = [
        {"url": os.getenv("MAC_LLM_URL", "http://localhost:11434"), "name": "Mac Studio (Ollama)"}
    ]

    # Выбираем первый доступный узел
    available_node = None
    for node in local_nodes:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{node['url']}/api/tags")
                if response.status_code == 200:
                    available_node = node
                    print(f"✅ Используем локальную модель на {node['name']} (0 токенов)")
                    break
        except:
            continue

    if not available_node:
        print("⚠️ Нет доступных локальных моделей, сохраняем результаты без обработки")

    async with pool.acquire() as conn:
        # Получаем экспертов, которым нужно обновить знания
        experts = await conn.fetch(
            "SELECT id, name, department, role FROM experts ORDER BY RANDOM() LIMIT 3"
        )

        for expert in experts:
            query = f"latest trends and best practices 2025 in {expert['role']} for {expert['department']}"
            print(f"🔍 Expert {expert['name']} researching: {query}")

            try:
                # Шаг 1: Веб-поиск (без токенов)
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=3))

                if not results:
                    print(f"⚠️ No results found for {expert['name']}")
                    continue

                # Шаг 2: Обработка локальной моделью (без токенов)
                if available_node:
                    # Собираем результаты веб-поиска
                    web_content = "\n\n".join(
                        [
                            f"Title: {res['title']}\nURL: {res['href']}\nContent: {res['body']}"
                            for res in results
                        ]
                    )

                    # Промпт для локальной модели
                    analysis_prompt = f"""
                    Ты - эксперт {expert["name"]} в области {expert["role"]} для {expert["department"]}.
                    Проанализируй следующие результаты веб-поиска и создай краткое резюме ключевых инсайтов.

                    РЕЗУЛЬТАТЫ ВЕБ-ПОИСКА:
                    {web_content}

                    Создай структурированное резюме с ключевыми выводами для эксперта.
                    """

                    print("🤖 Обработка результатов локальной моделью (0 токенов)...")
                    analyzed_content = await process_with_local_model(
                        analysis_prompt, node_url=available_node["url"], model="phi3.5:3.8b"
                    )

                    if analyzed_content:
                        content = (
                            f"📚 АНАЛИЗ ВЕБ-ИССЛЕДОВАНИЯ (обработано локальной моделью, 0 токенов):\n\n{analyzed_content}\n\n📎 ИСТОЧНИКИ:\n"
                            + "\n".join([f"- {res['title']}: {res['href']}" for res in results])
                        )
                        print(
                            f"✅ Результаты обработаны локальной моделью ({len(analyzed_content)} символов)"
                        )
                    else:
                        # Fallback: просто сохраняем результаты без обработки
                        content = "\n\n".join(
                            [
                                f"Source: {res['href']}\nTitle: {res['title']}\nSnippet: {res['body']}"
                                for res in results
                            ]
                        )
                else:
                    # Без локальной модели: просто сохраняем результаты
                    content = "\n\n".join(
                        [
                            f"Source: {res['href']}\nTitle: {res['title']}\nSnippet: {res['body']}"
                            for res in results
                        ]
                    )

                # Сохранение в БД
                domain_id = await conn.fetchval(
                    "SELECT id FROM domains WHERE name = $1", expert["department"]
                )
                if not domain_id:
                    domain_id = await conn.fetchval(
                        "INSERT INTO domains (name) VALUES ($1) RETURNING id", expert["department"]
                    )

                # Помечаем как внешнее знание, обработанное локальной моделью
                metadata = {
                    "source": "web_research",
                    "processed_by": "local_model" if available_node else "raw",
                    "node": available_node["name"] if available_node else None,
                    "tokens_used": 0,  # Локальная модель = 0 токенов
                    "expert_id": str(expert["id"]),
                    "expert_name": expert["name"],
                    "urls": [res["href"] for res in results],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                embedding = None
                try:
                    from semantic_cache import get_embedding

                    embedding = await get_embedding(content[:8000])
                except Exception:
                    pass
                if embedding is not None:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                        VALUES ($1, $2, 0.85, $3, FALSE, $4::vector)
                    """,
                        domain_id,
                        content,
                        json.dumps(metadata),
                        str(embedding),
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                        VALUES ($1, $2, 0.85, $3, FALSE)
                    """,
                        domain_id,
                        content,
                        json.dumps(metadata),
                    )

                print(
                    f"✅ Research for {expert['name']} completed. {len(results)} insights added (0 токенов использовано!)"
                )

            except Exception as e:
                print(f"❌ Research error for {expert['name']}: {e}")
                import traceback

                traceback.print_exc()

    await pool.close()


if __name__ == "__main__":
    asyncio.run(perform_research())
