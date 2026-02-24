#!/usr/bin/env python3
"""
⚡ PERFORMANCE BENCHMARKS
Комплексные бенчмарки производительности для всех компонентов системы
"""

import asyncio
import concurrent.futures
import json
import logging
import multiprocessing
import statistics
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psutil

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Результат бенчмарка"""

    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    p95_time: float
    p99_time: float
    throughput: float  # operations per second
    memory_usage: float  # MB
    cpu_usage: float  # percentage
    success_rate: float  # percentage


class PerformanceBenchmark:
    """Класс для проведения бенчмарков производительности"""

    def __init__(self):
        self.results: List[BenchmarkResult] = []
        self.process = psutil.Process()

    def measure_execution_time(self, func, *args, **kwargs):
        """Измеряет время выполнения функции"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        return result, end_time - start_time

    async def measure_async_execution_time(self, func, *args, **kwargs):
        """Измеряет время выполнения асинхронной функции"""
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        return result, end_time - start_time

    def get_memory_usage(self):
        """Получает текущее использование памяти в MB"""
        memory_info = self.process.memory_info()
        return memory_info.rss / 1024 / 1024  # Convert to MB

    def get_cpu_usage(self):
        """Получает текущее использование CPU в процентах"""
        return self.process.cpu_percent()

    def run_benchmark(
        self, name: str, func, iterations: int = 1000, *args, **kwargs
    ) -> BenchmarkResult:
        """Запускает бенчмарк для функции"""
        logger.info("Запуск бенчмарка: %s (%d итераций)", name, iterations)

        # Измеряем базовое использование ресурсов
        initial_memory = self.get_memory_usage()
        initial_cpu = self.get_cpu_usage()

        execution_times = []
        successes = 0

        start_time = time.time()

        for i in range(iterations):
            try:
                _, exec_time = self.measure_execution_time(func, *args, **kwargs)
                execution_times.append(exec_time)
                successes += 1
            except Exception as e:
                logger.warning("Ошибка в итерации %d: %s", i, e)

        end_time = time.time()

        # Измеряем финальное использование ресурсов
        final_memory = self.get_memory_usage()
        final_cpu = self.get_cpu_usage()

        # Рассчитываем статистики
        total_time = end_time - start_time
        avg_time = statistics.mean(execution_times) if execution_times else 0
        min_time = min(execution_times) if execution_times else 0
        max_time = max(execution_times) if execution_times else 0

        # Перцентили
        sorted_times = sorted(execution_times)
        p95_time = sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0
        p99_time = sorted_times[int(len(sorted_times) * 0.99)] if sorted_times else 0

        throughput = successes / total_time if total_time > 0 else 0
        memory_usage = final_memory - initial_memory
        cpu_usage = (final_cpu - initial_cpu) / iterations if iterations > 0 else 0
        success_rate = (successes / iterations) * 100 if iterations > 0 else 0

        result = BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            p95_time=p95_time,
            p99_time=p99_time,
            throughput=throughput,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
            success_rate=success_rate,
        )

        self.results.append(result)
        logger.info("Бенчмарк завершен: %s (%.2f ops/sec)", name, throughput)

        return result

    async def run_async_benchmark(
        self, name: str, func, iterations: int = 1000, *args, **kwargs
    ) -> BenchmarkResult:
        """Запускает бенчмарк для асинхронной функции"""
        logger.info("Запуск асинхронного бенчмарка: %s (%d итераций)", name, iterations)

        initial_memory = self.get_memory_usage()
        initial_cpu = self.get_cpu_usage()

        execution_times = []
        successes = 0

        start_time = time.time()

        for i in range(iterations):
            try:
                _, exec_time = await self.measure_async_execution_time(func, *args, **kwargs)
                execution_times.append(exec_time)
                successes += 1
            except Exception as e:
                logger.warning("Ошибка в итерации %d: %s", i, e)

        end_time = time.time()

        final_memory = self.get_memory_usage()
        final_cpu = self.get_cpu_usage()

        # Рассчитываем статистики
        total_time = end_time - start_time
        avg_time = statistics.mean(execution_times) if execution_times else 0
        min_time = min(execution_times) if execution_times else 0
        max_time = max(execution_times) if execution_times else 0

        sorted_times = sorted(execution_times)
        p95_time = sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0
        p99_time = sorted_times[int(len(sorted_times) * 0.99)] if sorted_times else 0

        throughput = successes / total_time if total_time > 0 else 0
        memory_usage = final_memory - initial_memory
        cpu_usage = (final_cpu - initial_cpu) / iterations if iterations > 0 else 0
        success_rate = (successes / iterations) * 100 if iterations > 0 else 0

        result = BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            p95_time=p95_time,
            p99_time=p99_time,
            throughput=throughput,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
            success_rate=success_rate,
        )

        self.results.append(result)
        logger.info("Асинхронный бенчмарк завершен: %s (%.2f ops/sec)", name, throughput)

        return result

    def run_concurrent_benchmark(
        self, name: str, func, iterations: int = 1000, max_workers: int = 10, *args, **kwargs
    ) -> BenchmarkResult:
        """Запускает бенчмарк с параллельным выполнением"""
        logger.info(
            "Запуск параллельного бенчмарка: %s (%d итераций, %d workers)",
            name,
            iterations,
            max_workers,
        )

        initial_memory = self.get_memory_usage()
        initial_cpu = self.get_cpu_usage()

        execution_times = []
        successes = 0

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []

            for i in range(iterations):
                future = executor.submit(self.measure_execution_time, func, *args, **kwargs)
                futures.append(future)

            for future in concurrent.futures.as_completed(futures):
                try:
                    _, exec_time = future.result()
                    execution_times.append(exec_time)
                    successes += 1
                except Exception as e:
                    logger.warning("Ошибка в параллельном выполнении: %s", e)

        end_time = time.time()

        final_memory = self.get_memory_usage()
        final_cpu = self.get_cpu_usage()

        # Рассчитываем статистики
        total_time = end_time - start_time
        avg_time = statistics.mean(execution_times) if execution_times else 0
        min_time = min(execution_times) if execution_times else 0
        max_time = max(execution_times) if execution_times else 0

        sorted_times = sorted(execution_times)
        p95_time = sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0
        p99_time = sorted_times[int(len(sorted_times) * 0.99)] if sorted_times else 0

        throughput = successes / total_time if total_time > 0 else 0
        memory_usage = final_memory - initial_memory
        cpu_usage = (final_cpu - initial_cpu) / iterations if iterations > 0 else 0
        success_rate = (successes / iterations) * 100 if iterations > 0 else 0

        result = BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total_time,
            avg_time=avg_time,
            min_time=min_time,
            max_time=max_time,
            p95_time=p95_time,
            p99_time=p99_time,
            throughput=throughput,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
            success_rate=success_rate,
        )

        self.results.append(result)
        logger.info("Параллельный бенчмарк завершен: %s (%.2f ops/sec)", name, throughput)

        return result

    def generate_report(self) -> str:
        """Генерирует отчет по всем бенчмаркам"""
        report = f"""
# 📊 ОТЧЕТ ПО БЕНЧМАРКАМ ПРОИЗВОДИТЕЛЬНОСТИ
Генерирован: {get_utc_now().strftime("%Y-%m-%d %H:%M:%S")}

## 📈 Сводка результатов

| Бенчмарк | Итерации | Avg Time | P95 Time | P99 Time | Throughput | Success Rate |
|----------|----------|----------|----------|----------|------------|--------------|
"""

        for result in self.results:
            report += f"| {result.name} | {result.iterations} | {result.avg_time:.3f}s | {result.p95_time:.3f}s | {result.p99_time:.3f}s | {result.throughput:.2f} ops/sec | {result.success_rate:.1f}% |\n"

        report += "\n## 🔍 Детальные результаты\n\n"

        for result in self.results:
            report += f"""
### {result.name}

- **Итерации:** {result.iterations}
- **Общее время:** {result.total_time:.3f}s
- **Среднее время:** {result.avg_time:.3f}s
- **Минимальное время:** {result.min_time:.3f}s
- **Максимальное время:** {result.max_time:.3f}s
- **P95 время:** {result.p95_time:.3f}s
- **P99 время:** {result.p99_time:.3f}s
- **Пропускная способность:** {result.throughput:.2f} ops/sec
- **Использование памяти:** {result.memory_usage:.2f} MB
- **Использование CPU:** {result.cpu_usage:.2f}%
- **Процент успеха:** {result.success_rate:.1f}%

"""

        return report

    def save_report(self, filename: Optional[str] = None):
        """Сохраняет отчет в файл"""
        if filename is None:
            timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_benchmark_report_{timestamp}.md"

        report = self.generate_report()

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(report)
            logger.info("Отчет по бенчмаркам сохранен: %s", filename)
        except Exception as e:
            logger.error("Ошибка сохранения отчета: %s", e)

    def save_json_report(self, filename: Optional[str] = None):
        """Сохраняет отчет в JSON формате"""
        if filename is None:
            timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_benchmark_report_{timestamp}.json"

        json_data = {
            "timestamp": get_utc_now().isoformat(),
            "results": [
                {
                    "name": result.name,
                    "iterations": result.iterations,
                    "total_time": result.total_time,
                    "avg_time": result.avg_time,
                    "min_time": result.min_time,
                    "max_time": result.max_time,
                    "p95_time": result.p95_time,
                    "p99_time": result.p99_time,
                    "throughput": result.throughput,
                    "memory_usage": result.memory_usage,
                    "cpu_usage": result.cpu_usage,
                    "success_rate": result.success_rate,
                }
                for result in self.results
            ],
        }

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            logger.info("JSON отчет по бенчмаркам сохранен: %s", filename)
        except Exception as e:
            logger.error("Ошибка сохранения JSON отчета: %s", e)


# Тестовые функции для бенчмарков
def test_simple_calculation():
    """Простая функция для тестирования"""
    return sum(range(1000))


def test_data_processing():
    """Функция обработки данных"""
    data = [i * 2 for i in range(1000)]
    return sum(data)


def test_string_processing():
    """Функция обработки строк"""
    text = "test" * 1000
    return text.upper()


async def test_async_operation():
    """Асинхронная операция для тестирования"""
    await asyncio.sleep(0.001)  # Имитация асинхронной работы
    return "async_result"


async def test_async_data_processing():
    """Асинхронная обработка данных"""
    data = [i * 3 for i in range(1000)]
    await asyncio.sleep(0.001)
    return sum(data)


def run_comprehensive_benchmarks():
    """Запускает все бенчмарки"""
    logger.info("🚀 Запуск комплексных бенчмарков производительности")

    benchmark = PerformanceBenchmark()

    # Синхронные бенчмарки
    benchmark.run_benchmark("Simple Calculation", test_simple_calculation, 10000)
    benchmark.run_benchmark("Data Processing", test_data_processing, 5000)
    benchmark.run_benchmark("String Processing", test_string_processing, 3000)

    # Параллельные бенчмарки
    benchmark.run_concurrent_benchmark("Concurrent Calculation", test_simple_calculation, 5000, 5)
    benchmark.run_concurrent_benchmark("Concurrent Data Processing", test_data_processing, 3000, 10)

    # Асинхронные бенчмарки
    async def run_async_benchmarks():
        await benchmark.run_async_benchmark("Async Operation", test_async_operation, 2000)
        await benchmark.run_async_benchmark(
            "Async Data Processing", test_async_data_processing, 1500
        )

    # Запускаем асинхронные бенчмарки
    asyncio.run(run_async_benchmarks())

    # Генерируем отчеты
    benchmark.save_report()
    benchmark.save_json_report()

    # Выводим сводку
    print(benchmark.generate_report())

    logger.info("✅ Комплексные бенчмарки завершены")

    return benchmark.results


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Запуск бенчмарков
    results = run_comprehensive_benchmarks()

    print(f"\n🎯 Выполнено {len(results)} бенчмарков")
    print("📊 Отчеты сохранены в файлы")
