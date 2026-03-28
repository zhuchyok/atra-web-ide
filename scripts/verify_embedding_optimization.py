import asyncio
import time
import logging
import sys
import os

# Добавляем путь к приложению
sys.path.append(os.path.join(os.getcwd(), "knowledge_os"))

try:
    from app.semantic_cache import get_embedding, _inflight_embeddings, _embedding_semaphore
    print("✅ Импорт semantic_cache успешен")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("verify_optimization")

async def test_request_collapsing():
    print("\n--- Тест 1: Request Collapsing ---")
    text = "Test collapsing request " + str(time.time())
    
    # Запускаем 5 идентичных запросов одновременно
    tasks = [get_embedding(text) for _ in range(5)]
    
    start_time = time.perf_counter()
    results = await asyncio.gather(*tasks)
    duration = time.perf_counter() - start_time
    
    print(f"Выполнено 5 запросов за {duration:.4f}с")
    
    # Проверяем, что результаты идентичны
    first_res = results[0]
    all_same = all(r == first_res for r in results)
    print(f"Все результаты идентичны: {all_same}")
    
    # Если collapsing работает, в логах должно быть "🔗 [COLLAPSING]"
    # И реально должен был выполниться только один запрос к Ollama

async def test_backpressure():
    print("\n--- Тест 2: Backpressure (Semaphore) ---")
    # Запускаем 10 разных запросов
    texts = [f"Different request {i} {time.time()}" for i in range(10)]
    tasks = [get_embedding(t) for t in texts]
    
    start_time = time.perf_counter()
    results = await asyncio.gather(*tasks)
    duration = time.perf_counter() - start_time
    
    print(f"Выполнено 10 разных запросов за {duration:.4f}с")
    # При лимите семафора 5, запросы должны идти пачками

async def main():
    print("🚀 Запуск верификации оптимизаций эмбеддингов (Singularity 24.3)")
    
    try:
        await test_request_collapsing()
        await test_backpressure()
        print("\n✅ Верификация завершена")
    except Exception as e:
        print(f"\n❌ Ошибка при верификации: {e}")

if __name__ == "__main__":
    asyncio.run(main())
