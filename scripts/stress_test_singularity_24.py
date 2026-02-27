import asyncio
import httpx
import time
import json
import os
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("stress_test")

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")

async def simulate_chat(session_id: str, queries: list):
    """Симуляция одного чата с несколькими запросами"""
    results = []
    for query in queries:
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                logger.info(f"📡 Session {session_id[:8]} sending: '{query[:20]}...'")
                async with client.stream(
                    "POST",
                    f"{VICTORIA_URL}/stream",
                    json={
                        "goal": query,
                        "session_id": session_id,
                        "project_context": "stress-test"
                    }
                ) as response:
                    if response.status_code != 200:
                        logger.error(f"❌ Session {session_id[:8]} error: {response.status_code}")
                        results.append({"query": query, "elapsed": time.time() - start_time, "status": response.status_code, "length": 0})
                        continue

                    # Собираем SSE поток
                    full_content = ""
                    async for line in response.aiter_lines():
                        logger.debug(f"RAW LINE: {line}")
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if data.get("type") == "chunk":
                                    full_content += data.get("content", "")
                                elif data.get("type") == "error":
                                    logger.error(f"❌ Session {session_id[:8]} SSE error: {data.get('content')}")
                                elif data.get("type") == "end":
                                    logger.debug(f"🏁 Session {session_id[:8]} SSE end")
                            except Exception as parse_e:
                                logger.debug(f"Parse error: {parse_e} on line: {line}")

                    elapsed = time.time() - start_time
                    results.append({
                        "query": query,
                        "elapsed": elapsed,
                        "status": response.status_code,
                        "length": len(full_content)
                    })
                    logger.info(f"✅ Session {session_id[:8]}: '{query[:20]}...' took {elapsed:.2f}s (len: {len(full_content)})")
        except Exception as e:
            logger.error(f"❌ Session {session_id[:8]} critical failed: {e}")
            results.append({"query": query, "elapsed": time.time() - start_time, "status": 500, "length": 0})

    return results

async def run_stress_test():
    """Запуск параллельных сессий"""
    queries_fast = ["привет", "как дела?"]
    queries_complex = ["что ты умеешь?"]

    sessions = [
        ("user_1", queries_fast),
        ("user_2", queries_complex),
    ]

    logger.info(f"🚀 Starting stress test on {VICTORIA_URL}...")
    start_all = time.time()

    tasks = [simulate_chat(sid, q) for sid, q in sessions]
    all_results = await asyncio.gather(*tasks)

    total_elapsed = time.time() - start_all

    # Сбор статистики
    flat_results = [item for sublist in all_results for item in sublist]
    avg_time = sum(r['elapsed'] for r in flat_results) / len(flat_results)

    print("\n" + "="*50)
    print("📊 STRESS TEST RESULTS (Singularity 24.0)")
    print("="*50)
    print(f"Total requests: {len(flat_results)}")
    print(f"Total time: {total_elapsed:.2f}s")
    print(f"Average response time: {avg_time:.2f}s")
    print(f"Success rate: {len([r for r in flat_results if r['status'] == 200]) / len(flat_results):.2%}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_stress_test())
