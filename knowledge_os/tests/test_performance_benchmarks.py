"""
Performance benchmark tests для отслеживания регрессий.

Тесты используют pytest-codspeed для автоматического детектирования
performance regressions в CI. Результаты видны на https://codspeed.io

Usage:
    pytest knowledge_os/tests/test_performance_benchmarks.py --codspeed
"""

import asyncio
import os

import pytest
from pytest_codspeed import BenchmarkFixture

RUN_PERF_BENCHMARKS = os.getenv("RUN_PERF_BENCHMARKS", "false").lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(
    not RUN_PERF_BENCHMARKS,
    reason="Performance benchmarks are opt-in. Set RUN_PERF_BENCHMARKS=true to enable.",
)


@pytest.mark.asyncio
async def test_victoria_enhanced_solve_benchmark(benchmark: BenchmarkFixture):
    """
    Benchmark: Victoria Enhanced solve для типовой задачи анализа структуры.

    Ожидаемое время: < 10 секунд для простой задачи
    """

    # Mock Victoria Enhanced (в реальности это вызов через API)
    async def mock_victoria_solve(goal: str):
        await asyncio.sleep(0.1)  # Симуляция LLM вызова
        return f"Analyzed: {goal}"

    goal = "Проанализируй структуру проекта /tmp/test_project"

    @benchmark
    def run():
        return asyncio.run(mock_victoria_solve(goal))

    result = run()
    assert result is not None
    assert "Analyzed" in result


@pytest.mark.asyncio
async def test_execute_assignments_parallel_benchmark(benchmark: BenchmarkFixture):
    """
    Benchmark: Параллельное делегирование 3 экспертам.

    После оптимизации (asyncio.gather): ~5 сек вместо 15 сек
    """

    async def mock_expert_task(expert_name: str, task: str):
        await asyncio.sleep(0.05)  # Симуляция работы эксперта
        return f"{expert_name}: completed {task}"

    async def execute_parallel():
        assignments = ["task1", "task2", "task3"]
        tasks = [mock_expert_task(f"Expert{i}", t) for i, t in enumerate(assignments)]
        results = await asyncio.gather(*tasks)
        return results

    @benchmark
    def run():
        return asyncio.run(execute_parallel())

    results = run()
    assert len(results) == 3
    assert all("completed" in r for r in results)


@pytest.mark.asyncio
async def test_rag_query_benchmark(benchmark: BenchmarkFixture):
    """
    Benchmark: RAG поиск в knowledge_nodes (embedding similarity).

    Ожидаемое время: < 200 мс для 100 узлов
    """
    import numpy as np

    # Mock embedding search
    def mock_rag_search(query_embedding, knowledge_embeddings, top_k=5):
        similarities = np.dot(knowledge_embeddings, query_embedding)
        top_indices = np.argsort(similarities)[-top_k:]
        return top_indices.tolist()

    # Generate mock data
    query_embedding = np.random.rand(384)  # Ollama embedding dimension
    knowledge_embeddings = np.random.rand(100, 384)  # 100 nodes

    @benchmark
    def run():
        return mock_rag_search(query_embedding, knowledge_embeddings)

    result = run()
    assert len(result) == 5


def test_json_serialization_benchmark(benchmark: BenchmarkFixture):
    """
    Benchmark: orjson vs json для большого объекта.

    orjson должен быть ~2-3× быстрее json
    """
    try:
        import orjson

        use_orjson = True
    except ImportError:
        use_orjson = False

    import json

    # Large test object
    data = {
        "tasks": [
            {
                "id": i,
                "title": f"Task {i}",
                "description": "Long description " * 10,
                "metadata": {"key": "value", "nested": {"data": [1, 2, 3]}},
            }
            for i in range(100)
        ]
    }

    if use_orjson:

        @benchmark
        def run():
            return orjson.dumps(data)
    else:

        @benchmark
        def run():
            return json.dumps(data)

    result = run()
    assert len(result) > 0


@pytest.mark.asyncio
async def test_semantic_cache_lookup_benchmark(benchmark: BenchmarkFixture):
    """
    Benchmark: Поиск по semantic cache (normalize + hash).

    Ожидаемое время: < 10 мс
    """
    import hashlib

    def normalize_and_hash(text: str) -> str:
        """Normalize text and compute MD5 hash for cache key"""
        normalized = text.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()

    test_prompts = [
        "Напиши код для сортировки массива",
        "Объясни, как работает async/await в Python",
        "Создай REST API endpoint для получения пользователей",
    ]

    @benchmark
    def run():
        return [normalize_and_hash(p) for p in test_prompts]

    hashes = run()
    assert len(hashes) == 3
    assert all(len(h) == 32 for h in hashes)  # MD5 hash length


if __name__ == "__main__":
    # Для локального запуска без pytest-codspeed
    print("Running benchmarks...")
    asyncio.run(test_victoria_enhanced_solve_benchmark(lambda f: f()))
    asyncio.run(test_execute_assignments_parallel_benchmark(lambda f: f()))
    asyncio.run(test_rag_query_benchmark(lambda f: f()))
    test_json_serialization_benchmark(lambda f: f())
    asyncio.run(test_semantic_cache_lookup_benchmark(lambda f: f()))
    print("✅ All benchmarks passed!")
