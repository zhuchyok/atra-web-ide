import asyncio
import json
import logging
import os

import asyncpg
import httpx

logger = logging.getLogger(__name__)

# URL для локальных моделей
MLX_API_URL = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


async def run_simulation(simulation_id: int):
    """Запускает симуляцию бизнес-идеи через локальные модели"""
    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5)

    async with pool.acquire() as conn:
        idea = await conn.fetchval("SELECT idea FROM simulations WHERE id = $1", simulation_id)
        if not idea:
            logger.error(f"Симуляция {simulation_id} не найдена")
            await pool.close()
            return

        logger.info(f"🚀 Simulating Idea: {idea}")

        # Шаг 1: Собираем контекст из базы знаний
        context_nodes = await conn.fetch(
            """
            SELECT content FROM knowledge_nodes
            WHERE content ILIKE $1 OR content ILIKE $2
            ORDER BY confidence_score DESC LIMIT 10
        """,
            f"%{idea.split()[0] if idea.split() else ''}%",
            f"%{idea}%",
        )

        context = (
            "\n---\n".join([r["content"] for r in context_nodes])
            if context_nodes
            else "Контекст не найден"
        )

        # Шаг 2: Формируем промпт с мировыми практиками бизнес-анализа
        prompt = f"""ТЫ - ЭКСПЕРТ ПО СТРАТЕГИЧЕСКОМУ ПЛАНИРОВАНИЮ И БИЗНЕС-АНАЛИЗУ. Используй ВСЕ мировые практики для максимально глубокого анализа бизнес-идеи.

ИДЕЯ: {idea}

КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ:
{context}

ЗАДАЧА: Проведи МАКСИМАЛЬНО ДЕТАЛЬНЫЙ анализ, используя следующие фреймворки:

---

## 1. BUSINESS MODEL CANVAS (9 блоков)

**1.1 Customer Segments (Целевые сегменты):**
- Кто ваши клиенты?
- Какие сегменты рынка?

**1.2 Value Propositions (Ценностное предложение):**
- Какую ценность вы создаете?
- Какие проблемы решаете?

**1.3 Channels (Каналы):**
- Как вы доставляете ценность?
- Какие каналы продаж?

**1.4 Customer Relationships (Отношения с клиентами):**
- Как вы взаимодействуете с клиентами?
- Тип отношений?

**1.5 Revenue Streams (Потоки доходов):**
- Как вы зарабатываете?
- Модель монетизации?

**1.6 Key Resources (Ключевые ресурсы):**
- Какие ресурсы нужны?
- Что критично для работы?

**1.7 Key Activities (Ключевые активности):**
- Что нужно делать?
- Основные процессы?

**1.8 Key Partners (Ключевые партнеры):**
- Кто ваши партнеры?
- Критические альянсы?

**1.9 Cost Structure (Структура затрат):**
- Какие основные затраты?
- Фиксированные vs переменные?

---

## 2. SWOT-АНАЛИЗ (Strengths, Weaknesses, Opportunities, Threats)

**Strengths (Сильные стороны):**
- Внутренние преимущества
- Конкурентные преимущества

**Weaknesses (Слабые стороны):**
- Внутренние недостатки
- Области для улучшения

**Opportunities (Возможности):**
- Внешние возможности
- Рыночные тренды

**Threats (Угрозы):**
- Внешние угрозы
- Конкурентные риски

---

## 3. PORTER'S FIVE FORCES (Конкурентный анализ)

**3.1 Rivalry Among Existing Competitors (Конкуренция в отрасли):**
- Уровень конкуренции
- Интенсивность соперничества

**3.2 Threat of New Entrants (Угроза новых игроков):**
- Барьеры входа
- Легкость входа на рынок

**3.3 Threat of Substitute Products (Угроза товаров-заменителей):**
- Альтернативные решения
- Риск замены

**3.4 Bargaining Power of Suppliers (Власть поставщиков):**
- Зависимость от поставщиков
- Переговорная сила

**3.5 Bargaining Power of Buyers (Власть покупателей):**
- Зависимость от клиентов
- Переговорная сила клиентов

---

## 4. PEST/PESTLE-АНАЛИЗ (Макро-окружение)

**Political (Политические факторы):**
- Регулирование
- Политическая стабильность

**Economic (Экономические факторы):**
- Экономический рост
- Инфляция, процентные ставки

**Social (Социальные факторы):**
- Демография
- Социальные тренды

**Technological (Технологические факторы):**
- Технологические инновации
- R&D активность

**Legal (Правовые факторы) - опционально:**
- Законы и регулирование
- Правовые риски

**Environmental (Экологические факторы) - опционально:**
- Экологические требования
- Устойчивое развитие

---

## 5. RISK ASSESSMENT (Оценка рисков)

**Risk Matrix (Матрица рисков):**
- Высокий риск (вероятность × влияние)
- Средний риск
- Низкий риск

**Конкретные риски:**
- Технические риски
- Рыночные риски
- Финансовые риски
- Операционные риски

**Общая оценка риска:** X% (0-100%)

---

## 6. LEAN STARTUP VALIDATION (Валидация для стартапов)

**Problem-Solution Fit:**
- Решает ли идея реальную проблему?
- Есть ли спрос?

**Product-Market Fit:**
- Соответствует ли продукт рынку?
- Готовность рынка?

**Key Metrics (Ключевые метрики):**
- MVP метрики
- Метрики роста

---

## 7. VALUE PROPOSITION CANVAS (Холст ценностного предложения)

**Customer Jobs (Задачи клиента):**
- Что клиент пытается сделать?
- Функциональные/эмоциональные задачи

**Customer Pains (Боли клиента):**
- Какие проблемы у клиента?
- Что его беспокоит?

**Customer Gains (Выгоды клиента):**
- Что клиент хочет получить?
- Желаемые результаты

**Value Proposition:**
- Как ваше решение решает боли и создает выгоды?

---

## 8. MARKET ANALYSIS (Анализ рынка)

**Market Size (Размер рынка):**
- TAM (Total Addressable Market)
- SAM (Serviceable Addressable Market)
- SOM (Serviceable Obtainable Market)

**Market Trends (Рыночные тренды):**
- Текущие тренды
- Будущие прогнозы

**Competitive Landscape (Конкурентный ландшафт):**
- Основные конкуренты
- Позиционирование

---

## 9. FINANCIAL FEASIBILITY (Финансовая осуществимость)

**Revenue Projections (Прогноз доходов):**
- Прогноз на 1-3 года
- Модель роста

**Cost Structure (Структура затрат):**
- Начальные инвестиции
- Операционные затраты

**Break-Even Analysis (Анализ безубыточности):**
- Точка безубыточности
- Срок окупаемости

---

## 10. IMPLEMENTATION ROADMAP (Дорожная карта реализации)

**Phase 1: MVP (Minimum Viable Product) - 0-3 месяца:**
- Первые шаги
- Ключевые задачи

**Phase 2: Market Entry - 3-6 месяцев:**
- Выход на рынок
- Первые клиенты

**Phase 3: Growth - 6-12 месяцев:**
- Масштабирование
- Оптимизация

---

## 11. FINAL VERDICT (Финальный вердикт)

**Рекомендация:**
- [ЗАПУСКАТЬ] - Идея готова к реализации
- [ДОРАБОТАТЬ] - Нужны улучшения (укажи что именно)
- [ОТКЛОНИТЬ] - Идея нежизнеспособна (объясни почему)

**Confidence Score (Уверенность):** X% (0-100%)

**Priority (Приоритет):** [HIGH/MEDIUM/LOW]

---

ФОРМАТ ОТВЕТА: Используй markdown с четкой структурой. Будь конкретным, используй цифры и факты из контекста. Ответ должен быть профессиональным и детальным."""

        # Вызываем локальную модель через MLX API
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{MLX_API_URL}/api/generate",
                    json={
                        "model": "phi3.5:3.8b",
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9,
                            "num_predict": 4000,  # Увеличено для детального анализа с мировыми практиками
                        },
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    analysis = result.get("response", "Ошибка: ответ не получен")
                    await conn.execute(
                        "UPDATE simulations SET result = $1 WHERE id = $2", analysis, simulation_id
                    )
                    logger.info(f"✅ Simulation {simulation_id} completed and saved.")
                else:
                    error_msg = f"MLX API Error: {response.status_code} - {response.text}"
                    await conn.execute(
                        "UPDATE simulations SET result = $1 WHERE id = $2", error_msg, simulation_id
                    )
                    logger.error(f"❌ Simulation {simulation_id} failed: {error_msg}")

        except httpx.TimeoutException:
            error_msg = "Ошибка: Превышено время ожидания ответа от модели (180 сек)"
            await conn.execute(
                "UPDATE simulations SET result = $1 WHERE id = $2", error_msg, simulation_id
            )
            logger.error(f"❌ Simulation {simulation_id} timed out")
        except Exception as e:
            error_msg = f"Internal Error: {str(e)}"
            await conn.execute(
                "UPDATE simulations SET result = $1 WHERE id = $2", error_msg, simulation_id
            )
            logger.error(f"❌ Simulation {simulation_id} failed: {e}")

    await pool.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        asyncio.run(run_simulation(int(sys.argv[1])))
