import asyncio
import os
import sys
from datetime import datetime

# Добавляем пути для импорта
sys.path.append(os.path.join(os.getcwd(), "knowledge_os"))


async def test_search_quality():
    """Тестирование качества поиска: Hybrid vs Hybrid + Reranker"""
    from app.enhanced_search import SearchMode, enhanced_search_knowledge

    test_queries = [
        "Как работают системные промпты в Claude?",
        "Лимиты API Anthropic для Claude 3.5 Sonnet",
        "Методы защиты от инъекций в промпты",
        "Как настроить RAG для больших документов?",
    ]

    print("🧪 [TEST START] Сравнение качества поиска (Hybrid v2 + Reranker)")
    print(f"📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)

    for query in test_queries:
        print(f"\n🔍 ЗАПРОС: '{query}'")

        # 1. Тест Hybrid Search (уже включает Reranker по умолчанию в нашей новой версии)
        # Чтобы сравнить, мы можем временно вызвать семантический или просто посмотреть на скоры
        try:
            start_time = asyncio.get_event_loop().time()
            res = await enhanced_search_knowledge(
                query=query, mode=SearchMode.HYBRID, limit=3, use_cache=False
            )
            elapsed = asyncio.get_event_loop().time() - start_time

            print(f"⏱️ Время выполнения: {elapsed:.3f} сек")
            print(f"📊 Найдено результатов: {res.get('results_count', 0)}")

            if res.get("results"):
                for i, r in enumerate(res["results"]):
                    sim = r.get("similarity", 0)
                    rerank = r.get("rerank_score", 0)
                    content = r["content"][:150].replace("\n", " ")
                    source = r.get("metadata", {}).get("source_url") or "DB"

                    print(f"  {i + 1}. [Sim: {sim:.3f} | Rerank: {rerank:.3f}]")
                    print(f"     Источник: {source}")
                    print(f"     Контент: {content}...")
            else:
                print("  ❌ Ничего не найдено.")

        except Exception as e:
            print(f"  ⚠️ Ошибка при поиске: {e}")

        print("-" * 40)


if __name__ == "__main__":
    # Убеждаемся, что DATABASE_URL установлен
    os.environ["DATABASE_URL"] = "postgresql://admin:secret@localhost:5432/knowledge_os"
    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

    asyncio.run(test_search_quality())
