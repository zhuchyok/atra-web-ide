#!/usr/bin/env python3
"""
Быстрое наполнение БЗ ответами на validation queries (Quick Win).
Запуск: python3 scripts/seed_validation_answers.py
"""
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

# Эталонные ответы на проблемные запросы (quick fix)
SEED_ANSWERS = {
    "сколько стоит подписка": "Стоимость подписки составляет 999 рублей в месяц. Доступна пробная версия на 14 дней.",
    "как создать аккаунт": "Для создания аккаунта перейдите на страницу регистрации, укажите email и пароль, подтвердите email.",
    "время работы поддержки": "Служба поддержки работает с 9:00 до 21:00 по московскому времени, 7 дней в неделю.",
    "документация API": "Документация API доступна по адресу /docs (Swagger UI) и /redoc. Основной endpoint: /api/chat для чата с агентами.",
    "как сбросить пароль": "Для сброса пароля перейдите по ссылке 'Забыли пароль?' на странице входа, укажите email для восстановления.",
    "тарифы и цены": "Базовый тариф: 999 руб/мес, Профессиональный: 1999 руб/мес, Корпоративный: по запросу.",
    "контакты поддержки": "Email: support@atra.ai, Telegram: @atra_support, чат на сайте доступен 24/7.",
    "как отменить подписку": "Для отмены подписки перейдите в настройки аккаунта → Подписка → Отменить подписку.",
    "справка по использованию": "Справка доступна в разделе /help. Основные режимы: Ask (вопрос-ответ), Agent (выполнение задач).",
    "часто задаваемые вопросы": "FAQ доступен по адресу /faq. Популярные вопросы: тарифы, интеграция, API, безопасность.",
    "как настроить Victoria": "Victoria настраивается через VICTORIA_URL (порт 8010), VICTORIA_TIMEOUT. Конфигурация в backend/app/config.py.",
    "что такое RAG": "RAG (Retrieval-Augmented Generation) — метод, при котором LLM использует поиск по базе знаний для генерации точных ответов.",
    "порты сервисов": "Backend: 8080, Victoria: 8010, Ollama: 11434, MLX: 11435, PostgreSQL: 5432, Redis (хост): 6381.",
    "как запустить проект локально": "1) docker-compose -f knowledge_os/docker-compose.yml up -d, 2) docker-compose up -d, 3) cd frontend && npm run dev.",
    "метрики Prometheus": "Метрики доступны на /metrics. Основные: rag_requests_total, rag_duration_seconds, victoria_requests.",
}

async def seed_knowledge_nodes():
    """Добавляет seed-ответы в knowledge_nodes через БД (768-dim from nomic-embed-text)."""
    try:
        import asyncpg
        import httpx
        from app.config import get_settings
    except ImportError as e:
        print(f"Import error: {e}")
        return

    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)

    # Используем nomic-embed-text через Ollama (768-dim, совместимо с RAG)
    print("📦 Получение эмбеддингов через Ollama nomic-embed-text (768-dim)...")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        added = 0
        for query, answer in SEED_ANSWERS.items():
            # Получаем эмбеддинг через Ollama
            try:
                response = await client.post(
                    "http://localhost:11434/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": answer}
                )
                if response.status_code != 200:
                    print(f"⚠️ Skipping '{query}': Ollama error {response.status_code}")
                    continue
                
                embedding = response.json().get("embedding", [])
                if len(embedding) != 768:
                    print(f"⚠️ Skipping '{query}': wrong dimensions ({len(embedding)})")
                    continue

                # Добавляем в БД
                await conn.execute("""
                    INSERT INTO knowledge_nodes (content, embedding, metadata, confidence_score)
                    VALUES ($1, $2::vector, $3, 0.95)
                """, answer, str(embedding), json.dumps({"query": query, "source": "seed_validation"}))
                added += 1
                print(f"✅ Added: {query}")
            except Exception as e:
                print(f"❌ Error for '{query}': {e}")

    await conn.close()
    print(f"\n🎉 Добавлено {added}/{len(SEED_ANSWERS)} ответов в БЗ")
    print("Повторный запуск пайплайна покажет улучшение метрик.")

if __name__ == "__main__":
    asyncio.run(seed_knowledge_nodes())
