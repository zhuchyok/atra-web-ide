#!/usr/bin/env python3
"""
🕵️ УЛУЧШЕННЫЙ МОДУЛЬ КОНКУРЕНТНОЙ РАЗВЕДКИ (ГЛЕБ ENHANCED)
Максимальная разведка со всех источников + глубокий анализ по мировым практикам

Основано на:
- Competitive Intelligence Best Practices 2025
- OSINT frameworks
- Multi-source data collection
- Structured analysis frameworks (SWOT, Porter's Five Forces, PEST)
"""

import asyncio
import json
import logging
import os
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg  # type: ignore # pylint: disable=import-error
import httpx
from duckduckgo_search import DDGS  # type: ignore # pylint: disable=import-error

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
VECTOR_CORE_URL = os.getenv("VECTOR_CORE_URL", "http://knowledge_vector_core:8001")
MLX_API_URL = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")


@dataclass
class CompetitorInfo:
    """Структурированная информация о конкуренте"""

    name: str
    sources: List[str]  # URL источников
    mentions: int = 0
    sentiment: str = "neutral"  # positive, negative, neutral
    pricing_info: Optional[str] = None
    services: List[str] = None
    reviews_count: int = 0
    avg_rating: float = 0.0
    location: Optional[str] = None
    contact_info: Optional[str] = None
    strengths: List[str] = None
    weaknesses: List[str] = None

    def __post_init__(self):
        if self.services is None:
            self.services = []
        if self.strengths is None:
            self.strengths = []
        if self.weaknesses is None:
            self.weaknesses = []


class EnhancedScoutResearcher:
    """
    Улучшенный разведчик с множественными источниками и глубоким анализом.
    """

    def __init__(self):
        self.competitors: Dict[str, CompetitorInfo] = {}
        self.market_insights: List[Dict] = []
        self.pricing_data: List[Dict] = []
        self.review_sentiments: Dict[str, List[str]] = defaultdict(list)

    async def get_embedding(self, text: str) -> List[float]:
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

    async def search_multiple_sources(self, query: str, max_results: int = 15) -> List[Dict]:
        """
        Поиск по множественным источникам (мировые практики).
        """
        all_results = []

        # 1. DuckDuckGo (основной источник)
        try:
            with DDGS() as ddgs:
                ddg_results = list(ddgs.text(query, max_results=max_results))
                logger.debug(f"🔍 DuckDuckGo для '{query}': найдено {len(ddg_results)} результатов")
                for res in ddg_results:
                    all_results.append(
                        {
                            "title": res.get("title", ""),
                            "url": res.get("href", ""),
                            "snippet": res.get("body", ""),
                            "source": "duckduckgo",
                            "query": query,
                        }
                    )
        except Exception as e:
            logger.error(f"❌ Ошибка DuckDuckGo поиска для '{query}': {e}")
            import traceback

            logger.debug(traceback.format_exc())

        # 2. Дополнительные запросы с вариациями
        query_variations = [
            f"{query} отзывы",
            f"{query} цены",
            f"{query} рейтинг",
            f"{query} официальный сайт",
            f"{query} контакты",
        ]

        for var_query in query_variations[:3]:  # Ограничиваем для скорости
            try:
                with DDGS() as ddgs:
                    var_results = list(ddgs.text(var_query, max_results=5))
                    logger.debug(
                        f"🔍 Вариация '{var_query}': найдено {len(var_results)} результатов"
                    )
                    for res in var_results:
                        # Проверяем на дубликаты по URL
                        if not any(r["url"] == res.get("href", "") for r in all_results):
                            all_results.append(
                                {
                                    "title": res.get("title", ""),
                                    "url": res.get("href", ""),
                                    "snippet": res.get("body", ""),
                                    "source": "duckduckgo_variation",
                                    "query": var_query,
                                }
                            )
            except Exception as e:
                logger.debug(f"⚠️ Ошибка вариации поиска '{var_query}': {e}")

        logger.info(f"📊 Итого для '{query}': собрано {len(all_results)} уникальных результатов")
        return all_results

    def extract_competitor_info(
        self, results: List[Dict], business_name: str, location: str
    ) -> Dict[str, CompetitorInfo]:
        """
        Извлекает структурированную информацию о конкурентах из результатов поиска.
        """
        competitors = {}

        # Паттерны для извлечения информации
        competitor_patterns = [
            r"компания\s+([А-ЯЁ][А-Яа-яё\s]+)",
            r"фирма\s+([А-ЯЁ][А-Яа-яё\s]+)",
            r"([А-ЯЁ][А-Яа-яё\s]+Окна)",
            r"([А-ЯЁ][А-Яа-яё\s]+Остекление)",
        ]

        price_pattern = r"(\d+[\s,.]?\d*)\s*(руб|₽|рублей|руб\.)"
        phone_pattern = (
            r"(\+?7|8)?[\s\-\(]?(\d{3})[\s\-\)]?[\s\-]?(\d{3})[\s\-]?(\d{2})[\s\-]?(\d{2})"
        )
        rating_pattern = r"(\d+[.,]\d+)\s*(звезд|★|⭐|балл)"

        for result in results:
            text = f"{result['title']} {result['snippet']}".lower()

            # Ищем конкурентов
            for pattern in competitor_patterns:
                matches = re.findall(
                    pattern, result["title"] + " " + result["snippet"], re.IGNORECASE
                )
                for match in matches:
                    comp_name = match.strip() if isinstance(match, str) else match[0].strip()
                    # Пропускаем целевой бизнес
                    if (
                        business_name.lower() in comp_name.lower()
                        or comp_name.lower() in business_name.lower()
                    ):
                        continue

                    if comp_name not in competitors:
                        competitors[comp_name] = CompetitorInfo(
                            name=comp_name, sources=[], location=location
                        )

                    comp = competitors[comp_name]
                    comp.mentions += 1
                    if result["url"] not in comp.sources:
                        comp.sources.append(result["url"])

                    # Извлекаем цену
                    price_match = re.search(price_pattern, result["snippet"], re.IGNORECASE)
                    if price_match and not comp.pricing_info:
                        comp.pricing_info = price_match.group(0)

                    # Извлекаем контакты
                    phone_match = re.search(phone_pattern, result["snippet"])
                    if phone_match and not comp.contact_info:
                        comp.contact_info = phone_match.group(0)

                    # Извлекаем рейтинг
                    rating_match = re.search(rating_pattern, result["snippet"])
                    if rating_match:
                        try:
                            rating = float(rating_match.group(1).replace(",", "."))
                            if comp.avg_rating == 0.0:
                                comp.avg_rating = rating
                            else:
                                comp.avg_rating = (comp.avg_rating + rating) / 2
                            comp.reviews_count += 1
                        except (ValueError, AttributeError, IndexError):
                            pass

                    # Анализ тональности (простой)
                    negative_words = ["плохо", "недоволен", "проблема", "ошибка", "жалоба"]
                    positive_words = ["отлично", "рекомендую", "доволен", "качество", "хорошо"]

                    if any(word in text for word in negative_words):
                        comp.sentiment = "negative"
                        comp.weaknesses.append(result["snippet"][:100])
                    elif any(word in text for word in positive_words):
                        comp.sentiment = "positive"
                        comp.strengths.append(result["snippet"][:100])

        return competitors

    async def deep_analysis_with_llm(
        self, data_summary: str, business_name: str, location: str
    ) -> Dict[str, Any]:
        """
        Глубокий анализ через локальную модель с использованием мировых фреймворков.
        """
        analysis_prompt = f"""ТЫ - ЭКСПЕРТ ПО КОНКУРЕНТНОЙ РАЗВЕДКЕ. Проведи максимально глубокий анализ рынка.

ЦЕЛЕВОЙ БИЗНЕС: {business_name}
ЛОКАЦИЯ: {location}

СОБРАННЫЕ ДАННЫЕ:
{data_summary}

ЗАДАЧА: Создай ДЕТАЛЬНЫЙ отчет по следующим фреймворкам:

1. SWOT-АНАЛИЗ (Strengths, Weaknesses, Opportunities, Threats)
   - Сильные стороны рынка
   - Слабые стороны рынка
   - Возможности для роста
   - Угрозы для бизнеса

2. PORTER'S FIVE FORCES
   - Угроза новых игроков
   - Угроза товаров-заменителей
   - Рыночная власть поставщиков
   - Рыночная власть покупателей
   - Конкуренция в отрасли

3. PEST-АНАЛИЗ (Political, Economic, Social, Technological)
   - Политические факторы
   - Экономические факторы
   - Социальные факторы
   - Технологические факторы

4. КОНКУРЕНТНАЯ КАРТА
   - ТОП-10 конкурентов с детальной характеристикой
   - Позиционирование каждого
   - Рыночная доля (оценка)
   - Ключевые отличия

5. АНАЛИЗ ЦЕНООБРАЗОВАНИЯ
   - Диапазон цен на рынке
   - Факторы ценообразования
   - Рекомендации по ценообразованию

6. АНАЛИЗ ОТЗЫВОВ И СЕНТИМЕНТА
   - Основные боли клиентов
   - Что ценят клиенты
   - Неудовлетворенные потребности

7. СТРАТЕГИЧЕСКИЕ РЕКОМЕНДАЦИИ
   - Краткосрочные действия (1-3 месяца)
   - Среднесрочные действия (3-12 месяцев)
   - Долгосрочная стратегия (1-3 года)
   - Ключевые метрики успеха (KPI)

8. РИСКИ И МИТИГАЦИЯ
   - Основные риски
   - План митигации рисков

ФОРМАТ: Структурированный отчет с конкретными данными, цифрами, примерами.
Используй маркдаун для форматирования."""

        # Пробуем сначала MLX (более мощная модель)
        models_to_try = [
            (MLX_API_URL, "phi3.5:3.8b", "MLX"),
            (MLX_API_URL, "qwen2.5-coder:32b", "MLX"),
            (OLLAMA_URL, "glm-4.7-flash:q8_0", "Ollama"),
            (OLLAMA_URL, "phi3.5:3.8b", "Ollama"),
        ]

        last_error = None
        for api_url, model_name, source in models_to_try:
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    logger.info(f"🧠 Пробую {source} модель {model_name} для глубокого анализа...")
                    response = await client.post(
                        f"{api_url}/api/generate",
                        json={
                            "model": model_name,
                            "prompt": analysis_prompt,
                            "stream": False,
                            "options": {
                                "temperature": 0.7,
                                "top_p": 0.9,
                                "num_predict": 4000
                                if "deepseek" in model_name or "glm" in model_name
                                else 2000,
                            },
                        },
                    )
                    if response.status_code == 200:
                        result = response.json()
                        analysis = result.get("response", "")
                        if (
                            analysis and len(analysis.strip()) > 100
                        ):  # Проверяем, что получили реальный ответ
                            logger.info(
                                f"✅ Глубокий анализ завершен через {source} ({len(analysis)} символов)"
                            )
                            return {
                                "analysis": analysis,
                                "model_used": model_name,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        else:
                            logger.warning(
                                f"⚠️ {source} {model_name} вернул пустой ответ, пробую следующую модель..."
                            )
                            continue
                    else:
                        logger.warning(
                            f"⚠️ {source} {model_name} вернул статус {response.status_code}, пробую следующую модель..."
                        )
                        continue
            except httpx.TimeoutException as e:
                last_error = f"Timeout при обращении к {source} {model_name}: {e}"
                logger.warning(f"⏱️ {last_error}, пробую следующую модель...")
                continue
            except httpx.ConnectError as e:
                last_error = f"Не удалось подключиться к {source} {model_name}: {e}"
                logger.warning(f"🔌 {last_error}, пробую следующую модель...")
                continue
            except Exception as e:
                last_error = f"Ошибка при использовании {source} {model_name}: {e}"
                logger.warning(f"❌ {last_error}, пробую следующую модель...")
                continue

        # Если все модели недоступны, возвращаем базовый анализ
        logger.error(f"❌ Все модели недоступны. Последняя ошибка: {last_error}")
        return {
            "analysis": f"⚠️ Глубокий анализ через LLM недоступен (все модели не отвечают).\n\nПоследняя ошибка: {last_error}\n\n**Собранные данные:**\n{data_summary[:2000]}",
            "model_used": "N/A (все модели недоступны)",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def perform_enhanced_research(
        self, business_name: str, locations: str, extra_competitors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Выполняет максимально полную разведку со всех источников.
        """
        logger.info(
            f"🕵️ Глеб Enhanced: Начинаю максимальную разведку для '{business_name}' в {locations}..."
        )

        pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)

        # 🌟 МИРОВЫЕ ПРАКТИКИ: Множественные типы запросов
        query_categories = {
            "competitors": [
                f"компании по установке пластиковых окон {locations} 2025",
                f"конкуренты {business_name} {locations}",
                f"оконные компании {locations} список",
                f"производители окон ПВХ {locations}",
            ],
            "pricing": [
                f"цены на пластиковые окна {locations} 2025",
                f"стоимость окон ПВХ {locations}",
                f"прайс лист окна {locations}",
            ],
            "reviews": [
                f"отзывы о компаниях по окнам {locations}",
                f"рейтинг оконных компаний {locations}",
                f"жалобы на установку окон {locations}",
            ],
            "services": [
                f"услуги по установке окон {locations}",
                f"остекление балконов {locations}",
                f"ремонт окон {locations}",
            ],
            "market_trends": [
                f"тренды рынка окон {locations} 2025",
                f"развитие оконного рынка {locations}",
            ],
        }

        # Добавляем конкретных конкурентов
        if extra_competitors:
            for comp in extra_competitors:
                query_categories["competitors"].append(f"{comp} {locations} отзывы цены")

        all_results = []
        total_queries = sum(len(queries) for queries in query_categories.values())
        completed_queries = 0

        # Параллельный поиск по всем категориям
        async def search_category(category: str, queries: List[str]):
            nonlocal completed_queries
            category_results = []
            for query in queries:
                try:
                    results = await self.search_multiple_sources(query, max_results=10)
                    for res in results:
                        res["category"] = category
                        category_results.append(res)
                    completed_queries += 1
                    logger.info(f"✅ [{completed_queries}/{total_queries}] {category}: {query}")
                except Exception as e:
                    logger.error(f"Ошибка поиска '{query}': {e}")
            return category_results

        # Запускаем параллельный поиск
        tasks = [search_category(cat, queries) for cat, queries in query_categories.items()]
        category_results_list = await asyncio.gather(*tasks)

        # Объединяем результаты
        for category_results in category_results_list:
            all_results.extend(category_results)

        logger.info(f"✅ Собрано {len(all_results)} результатов из всех источников")

        if len(all_results) == 0:
            logger.warning(
                f"⚠️ ВНИМАНИЕ: Поиск не вернул результатов для '{business_name}' в {locations}. Возможные причины:"
            )
            logger.warning("   - Проблемы с DuckDuckGo API")
            logger.warning("   - Неправильные запросы")
            logger.warning("   - Слишком специфичная локация/бизнес")

        # Извлекаем структурированную информацию
        competitors = self.extract_competitor_info(all_results, business_name, locations)
        logger.info(f"✅ Найдено {len(competitors)} конкурентов")

        if len(competitors) == 0 and len(all_results) > 0:
            logger.warning(
                f"⚠️ ВНИМАНИЕ: Найдено {len(all_results)} результатов, но не удалось извлечь конкурентов."
            )
            logger.warning(
                "   - Возможно, паттерны извлечения не подходят для данного типа бизнеса"
            )
            logger.warning("   - Или результаты не содержат информации о конкурентах")

        # Сохраняем в БД
        async with pool.acquire() as conn:
            expert = await conn.fetchrow("SELECT id, name FROM experts WHERE name = 'Глеб'")
            if not expert:
                logger.error("❌ Эксперт Глеб не найден")
                await pool.close()
                return {}

            domain_id = await conn.fetchval(
                "SELECT id FROM domains WHERE name = 'Competitive Intelligence'"
            )
            if not domain_id:
                domain_id = await conn.fetchval(
                    "INSERT INTO domains (name) VALUES ('Competitive Intelligence') RETURNING id"
                )

            # Сохраняем все результаты
            total_saved = 0
            for result in all_results:
                content = f"{result['title']}\nИсточник: {result['url']}\n{result['snippet']}"
                embedding = await self.get_embedding(content)

                metadata = {
                    "source": "enhanced_scout_research",
                    "category": result.get("category", "general"),
                    "query": result.get("query", ""),
                    "expert_id": str(expert["id"]),
                    "expert_name": expert["name"],
                    "url": result["url"],
                    "business_target": business_name,
                    "location": locations,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (domain_id, content, embedding, confidence_score, metadata, is_verified)
                    VALUES ($1, $2, $3, 0.95, $4, FALSE)
                """,
                    domain_id,
                    content,
                    str(embedding),
                    json.dumps(metadata),
                )
                total_saved += 1

            # Подготавливаем данные для глубокого анализа
            data_summary = f"""
КОЛИЧЕСТВО ИСТОЧНИКОВ: {len(all_results)}
КОЛИЧЕСТВО КОНКУРЕНТОВ: {len(competitors)}

ТОП КОНКУРЕНТЫ:
{
                chr(10).join(
                    [
                        f"- {name}: {info.mentions} упоминаний, рейтинг {info.avg_rating:.1f}, тональность {info.sentiment}"
                        for name, info in sorted(
                            competitors.items(), key=lambda x: x[1].mentions, reverse=True
                        )[:10]
                    ]
                )
            }

ДЕТАЛИ КОНКУРЕНТОВ:
{
                json.dumps(
                    {name: asdict(info) for name, info in list(competitors.items())[:5]},
                    ensure_ascii=False,
                    indent=2,
                )
            }

ПРИМЕРЫ РЕЗУЛЬТАТОВ:
{
                chr(10).join(
                    [
                        f"- {r['title'][:80]}... ({r.get('category', 'general')})"
                        for r in all_results[:20]
                    ]
                )
            }
"""

            # Глубокий анализ через локальную модель
            logger.info("🧠 Запускаю глубокий анализ через локальную модель...")
            analysis_result = await self.deep_analysis_with_llm(
                data_summary, business_name, locations
            )

            # Убеждаемся, что model_used не None
            model_used_display = analysis_result.get("model_used") or "N/A (модель недоступна)"

            # Создаем детальный отчет
            detailed_report = f"""# 🕵️ ДЕТАЛЬНЫЙ ОТЧЕТ КОНКУРЕНТНОЙ РАЗВЕДКИ

**Целевой бизнес:** {business_name}
**Локация:** {locations}
**Дата:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
**Модель анализа:** {model_used_display}

---

## 📊 СТАТИСТИКА СБОРА ДАННЫХ

- **Всего источников:** {len(all_results)}
- **Найдено конкурентов:** {len(competitors)}
- **Сохранено в БД:** {total_saved} записей
- **Категории данных:**
  - Конкуренты: {len([r for r in all_results if r.get("category") == "competitors"])}
  - Ценообразование: {len([r for r in all_results if r.get("category") == "pricing"])}
  - Отзывы: {len([r for r in all_results if r.get("category") == "reviews"])}
  - Услуги: {len([r for r in all_results if r.get("category") == "services"])}
  - Тренды рынка: {len([r for r in all_results if r.get("category") == "market_trends"])}

---

## 🏆 ТОП КОНКУРЕНТЫ

{
                chr(10).join(
                    [
                        f"### {i + 1}. {name}"
                        + chr(10)
                        + f"- Упоминаний: {info.mentions}"
                        + chr(10)
                        + f"- Рейтинг: {info.avg_rating:.1f}/5"
                        + chr(10)
                        + f"- Тональность: {info.sentiment}"
                        + chr(10)
                        + f"- Источников: {len(info.sources)}"
                        + chr(10)
                        for i, (name, info) in enumerate(
                            sorted(competitors.items(), key=lambda x: x[1].mentions, reverse=True)[
                                :10
                            ]
                        )
                    ]
                )
            }

---

## 🧠 ГЛУБОКИЙ АНАЛИЗ (ЧЕРЕЗ ЛОКАЛЬНУЮ МОДЕЛЬ)

{analysis_result.get("analysis", "Анализ не выполнен")}

---

## 📋 ИСХОДНЫЕ ДАННЫЕ

<details>
<summary>Детальная информация о конкурентах (JSON)</summary>

```json
{
                json.dumps(
                    {name: asdict(info) for name, info in competitors.items()},
                    ensure_ascii=False,
                    indent=2,
                )
            }
```

</details>

---

**Сгенерировано:** Глеб Enhanced (Competitive Intelligence Expert)
**Использованы:** Локальные модели (MLX API Server), множественные источники данных
"""

            # Сохраняем детальный отчет
            report_embedding = await self.get_embedding(detailed_report)

            # Убеждаемся, что model_used не None (для корректного отображения в дашборде)
            model_used = analysis_result.get("model_used")
            if model_used is None:
                model_used = "N/A (модель недоступна)"

            metadata_for_report = {
                "source": "enhanced_scout_report",
                "expert_id": str(expert["id"]),
                "expert_name": expert["name"],
                "business_target": business_name,
                "location": locations,
                "competitors_count": len(competitors),
                "sources_count": len(all_results),
                "model_used": model_used,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                f"💾 Сохраняю отчет: {len(competitors)} конкурентов, {len(all_results)} источников, модель: {model_used}"
            )

            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, embedding, confidence_score, metadata, is_verified)
                VALUES ($1, $2, $3, 0.95, $4, TRUE)
            """,
                domain_id,
                detailed_report,
                str(report_embedding),
                json.dumps(metadata_for_report),
            )

            # Создаем задачу для дополнительного анализа (если нужно)
            victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
            task_desc = (
                f"Глеб Enhanced завершил максимальную разведку для '{business_name}' в {locations}. "
                f"Собрано {len(all_results)} источников, найдено {len(competitors)} конкурентов. "
                f"Детальный отчет с SWOT, Porter's Five Forces, PEST анализом готов. "
                f"Проверь отчет и подготовь презентацию для руководства."
            )

            await conn.execute(
                """
                INSERT INTO tasks (title, description, status, assignee_expert_id, creator_expert_id, metadata)
                VALUES ($1, $2, 'pending', $3, $4, $5)
                ON CONFLICT (title, COALESCE(project_context, 'default'::character varying))
                WHERE (status = ANY (ARRAY['pending'::text, 'in_progress'::text]))
                DO UPDATE SET updated_at = NOW()
            """,
                f"🕵️ Enhanced Разведка: {business_name}",
                task_desc,
                expert["id"],
                victoria_id,
                json.dumps(
                    {
                        "source": "enhanced_scout_orchestrator",
                        "business": business_name,
                        "location": locations,
                        "competitors_count": len(competitors),
                        "sources_count": len(all_results),
                        "report_type": "enhanced",
                    }
                ),
            )

            logger.info(
                f"✅ Enhanced разведка завершена: {len(competitors)} конкурентов, {len(all_results)} источников"
            )

        await pool.close()

        return {
            "competitors": {name: asdict(info) for name, info in competitors.items()},
            "total_sources": len(all_results),
            "analysis": analysis_result.get("analysis", ""),
            "report": detailed_report,
        }


async def perform_enhanced_scout_research(
    business_name: str, locations: str, extra_competitors: Optional[List[str]] = None
):
    """Главная функция для запуска улучшенной разведки."""
    researcher = EnhancedScoutResearcher()

    # Извлекаем дополнительные конкуренты из аргументов (если не переданы)
    if extra_competitors is None and len(sys.argv) > 3:
        extra_competitors = [c.strip() for c in sys.argv[3].split(",")]

    result = await researcher.perform_enhanced_research(business_name, locations, extra_competitors)

    return result


if __name__ == "__main__":
    business = sys.argv[1] if len(sys.argv) > 1 else "Столичные окна"
    location = sys.argv[2] if len(sys.argv) > 2 else "Чебоксары и Новочебоксарск"
    asyncio.run(perform_enhanced_scout_research(business, location))
