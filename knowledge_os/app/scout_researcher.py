#!/usr/bin/env python3
"""
🕵️ МОДУЛЬ КОНКУРЕНТНОЙ РАЗВЕДКИ (ГЛЕБ)
Автоматизированный поиск и сбор данных о конкурентах на рынке.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import List

import asyncpg  # type: ignore # pylint: disable=import-error
import httpx
from duckduckgo_search import DDGS  # type: ignore # pylint: disable=import-error

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
VECTOR_CORE_URL = os.getenv("VECTOR_CORE_URL", "http://knowledge_vector_core:8001")


async def get_embedding(text: str) -> List[float]:
    """Получает векторное представление текста через VectorCore."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{VECTOR_CORE_URL}/encode", json={"text": text}, timeout=30.0
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.error("VectorCore error: %s", e)
            return [0.0] * 768  # nomic-embed-text; knowledge_nodes.embedding vector(768)


async def get_pool():
    """Создает пул соединений с базой данных PostgreSQL."""
    return await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)


async def perform_scout_research(business_name: str, locations: str):
    """Выполняет поиск данных по конкурентам и сохраняет их в базу знаний."""
    logger.info(
        "🕵️ Глеб (Разведчик): Начинаю сбор данных по конкурентам для '%s' в %s...",
        business_name,
        locations,
    )
    pool = await get_pool()

    queries = [
        f"список компаний по установке пластиковых окон в {locations} 2025",
        f"пластиковые окна {locations} справочник организаций полный список",
        "все фирмы по окнам ПВХ в Чувашии",
        f"рейтинг компаний пластиковых окон {locations} отзывы 2024",
        "производители окон ПВХ в Чувашии адреса телефоны",
        f"остекление балконов и лоджий {locations} список компаний",
        "дилеры оконных профилей Rehau Veka KBE в Чувашии",
        f"Яндекс Карты пластиковые окна {locations} список",
        f"2ГИС оконные фирмы {locations} все организации",
        f"Пульс Цен {locations} окна ПВХ список поставщиков",
    ]

    # Добавляем конкретных конкурентов, если они переданы через аргументы
    if len(sys.argv) > 3:
        extra_competitors = sys.argv[3].split(",")
        for comp in extra_competitors:
            queries.append(f"компания {comp.strip()} {locations} окна отзывы")

    if not pool:
        logger.error("❌ Не удалось создать пул соединений с БД")
        return

    async with pool.acquire() as conn:
        expert = await conn.fetchrow("SELECT id, name FROM experts WHERE name = 'Глеб'")
        if not expert:
            logger.error("❌ Эксперт Глеб не найден в базе данных.")
            await pool.close()
            return

        domain_id = await conn.fetchval(
            "SELECT id FROM domains WHERE name = 'Competitive Intelligence'"
        )
        if not domain_id:
            domain_id = await conn.fetchval(
                "INSERT INTO domains (name) VALUES ('Competitive Intelligence') RETURNING id"
            )

        total_insights = 0
        for query in queries:
            logger.info("🔍 Поиск: %s", query)
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=10))

                for res in results:
                    content = (
                        f"Конкурентная разведка: {res['title']}\n"
                        f"Источник: {res['href']}\n"
                        f"Описание: {res['body']}"
                    )
                    embedding = await get_embedding(content)

                    metadata = {
                        "source": "scout_research",
                        "query": query,
                        "expert_id": str(expert["id"]),
                        "expert_name": expert["name"],
                        "url": res["href"],
                        "business_target": business_name,
                        "location": locations,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, embedding, confidence_score, metadata, is_verified)
                        VALUES ($1, $2, $3, 0.90, $4, FALSE)
                    """,
                        domain_id,
                        content,
                        str(embedding),
                        json.dumps(metadata),
                    )
                    total_insights += 1

            except Exception as e:
                logger.error("❌ Ошибка поиска '%s': %s", query, e)

        # Создаем задачу для Глеба: Проанализировать собранные данные
        victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
        task_desc = (
            f"Глеб, я собрала {total_insights} записей о рынке в {locations}. "
            f"Проведи анализ конкурентов и подготовь SWOT для '{business_name}'."
        )

        await conn.execute(
            """
            INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
            VALUES ($1, $2, 'pending', $3, $4, $5)
        """,
            f"🕵️ Анализ конкурентов: {business_name}",
            task_desc,
            expert["id"],
            victoria_id,
            json.dumps({"source": "scout_orchestrator", "business": business_name}),
        )

        logger.info(
            "✅ Глеб завершил сбор данных. Добавлено %d зацепок. Задача создана.", total_insights
        )

    await pool.close()


if __name__ == "__main__":
    business = sys.argv[1] if len(sys.argv) > 1 else "Столичные окна"
    location = sys.argv[2] if len(sys.argv) > 2 else "Чебоксары"
    asyncio.run(perform_scout_research(business, location))
