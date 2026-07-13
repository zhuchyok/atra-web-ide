import asyncio
import time
import httpx
import json
import os
import statistics

# Настройки
PROXY_URL = "http://localhost:8040/v1/chat/completions"
TEST_PROMPT = "Как нам улучшить систему мониторинга Mac Studio?"
MODELS_TO_TEST = ["discuss"]  # Мы тестируем именно наш новый режим
ITERATIONS = 3

async def measure_request(model: str, prompt: str):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }

    start_time = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(PROXY_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            end_time = time.perf_counter()

            content = data["choices"][0]["message"]["content"]
            tokens = len(content.split()) # Грубая оценка токенов по словам
            duration = end_time - start_time
            tps = tokens / duration if duration > 0 else 0

            return {
                "duration": duration,
                "tokens": tokens,
                "tps": tps,
                "success": True,
                "preview": content[:100] + "..."
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

async def run_benchmarks():
    print(f"🚀 Запуск замеров для модели: {MODELS_TO_TEST[0]}")
    print(f"📝 Промпт: {TEST_PROMPT}")
    print("-" * 50)

    results = []
    for i in range(ITERATIONS):
        print(f"🔄 Итерация {i+1}/{ITERATIONS}...")
        res = await measure_request(MODELS_TO_TEST[0], TEST_PROMPT)
        if res["success"]:
            results.append(res)
            print(f"   ✅ Успешно: {res['duration']:.2f} сек, {res['tps']:.2f} слов/сек")
        else:
            print(f"   ❌ Ошибка: {res['error']}")
        await asyncio.sleep(1) # Пауза между тестами

    if results:
        avg_dur = statistics.mean([r["duration"] for r in results])
        avg_tps = statistics.mean([r["tps"] for r in results])
        print("-" * 50)
        print(f"📊 ИТОГИ (среднее за {len(results)} тестов):")
        print(f"⏱ Время ответа: {avg_dur:.2f} сек")
        print(f"🚀 Скорость: {avg_tps:.2f} слов/сек")
        print(f"📄 Пример ответа: {results[0]['preview']}")
    else:
        print("❌ Не удалось получить результаты для замеров.")

if __name__ == "__main__":
    asyncio.run(run_benchmarks())
