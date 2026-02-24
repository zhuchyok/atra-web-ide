#!/usr/bin/env python3
"""
Benchmark тесты для измерения реального улучшения качества
Сравнивает Enhanced режим vs Standard режим
"""

import asyncio
import time
import json
import sys
import os
from typing import Dict, List, Any
from datetime import datetime, timezone
import statistics

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../knowledge_os'))

from app.victoria_enhanced import VictoriaEnhanced

class EnhancedBenchmark:
    """Benchmark для сравнения Enhanced vs Standard"""

    def __init__(self):
        self.enhanced = None
        self.benchmark_tasks = [
            {
                "id": "math_reasoning",
                "task": "Реши сложную математическую задачу: Найди сумму всех простых чисел от 1 до 100",
                "category": "reasoning",
                "expected_method": "extended_thinking"
            },
            {
                "id": "planning",
                "task": "Спланируй разработку веб-приложения с нуля: архитектура, технологии, этапы",
                "category": "planning",
                "expected_method": "tree_of_thoughts"
            },
            {
                "id": "complex_problem",
                "task": "Найди оптимальное решение для задачи: минимизировать стоимость разработки при максимальном качестве",
                "category": "complex",
                "expected_method": "swarm"
            },
            {
                "id": "execution",
                "task": "Выполни задачу: создай план тестирования для API сервиса",
                "category": "execution",
                "expected_method": "react"
            },
        ]

    async def setup(self):
        """Инициализация"""
        print("🔧 Инициализация benchmark...")
        try:
            self.enhanced = VictoriaEnhanced()
            print("✅ VictoriaEnhanced готов")
            return True
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    async def benchmark_task(self, task: Dict, use_enhanced: bool, iterations: int = 3) -> Dict[str, Any]:
        """Benchmark одной задачи"""
        times = []
        results = []

        for i in range(iterations):
            start_time = time.time()
            try:
                result = await self.enhanced.solve(
                    task["task"],
                    use_enhancements=use_enhanced
                )
                elapsed = time.time() - start_time
                times.append(elapsed)
                results.append({
                    "iteration": i + 1,
                    "time": elapsed,
                    "method": result.get("method", "unknown"),
                    "success": result.get("result") is not None
                })
            except Exception as e:
                elapsed = time.time() - start_time
                times.append(elapsed)
                results.append({
                    "iteration": i + 1,
                    "time": elapsed,
                    "error": str(e),
                    "success": False
                })

        return {
            "task_id": task["id"],
            "category": task["category"],
            "use_enhanced": use_enhanced,
            "iterations": iterations,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "success_rate": sum(1 for r in results if r.get("success", False)) / iterations,
            "results": results
        }

    async def run_benchmarks(self):
        """Запуск всех benchmark тестов"""
        print("=" * 60)
        print("📊 BENCHMARK TESTS - Enhanced vs Standard")
        print("=" * 60)

        if not await self.setup():
            return

        all_results = []

        for task in self.benchmark_tasks:
            print(f"\n🧪 Тестирование: {task['id']} ({task['category']})")

            # Standard режим
            print("  ⏳ Standard режим...")
            standard_result = await self.benchmark_task(task, use_enhanced=False)
            all_results.append(standard_result)

            # Enhanced режим
            print("  ⏳ Enhanced режим...")
            enhanced_result = await self.benchmark_task(task, use_enhanced=True)
            all_results.append(enhanced_result)

            # Сравнение
            improvement = ((standard_result["avg_time"] - enhanced_result["avg_time"]) / standard_result["avg_time"]) * 100
            print(f"  📈 Улучшение времени: {improvement:.1f}%")
            print(f"  ✅ Success rate: Standard={standard_result['success_rate']*100:.1f}%, Enhanced={enhanced_result['success_rate']*100:.1f}%")

        # Вывод сводки
        self.print_summary(all_results)

        # Сохранение результатов
        self.save_results(all_results)

    def print_summary(self, results: List[Dict]):
        """Вывод сводки"""
        print("\n" + "=" * 60)
        print("📊 СВОДКА BENCHMARK")
        print("=" * 60)

        # Группировка по задачам
        tasks = {}
        for result in results:
            task_id = result["task_id"]
            if task_id not in tasks:
                tasks[task_id] = {}
            mode = "enhanced" if result["use_enhanced"] else "standard"
            tasks[task_id][mode] = result

        for task_id, modes in tasks.items():
            standard = modes.get("standard", {})
            enhanced = modes.get("enhanced", {})

            if standard and enhanced:
                time_improvement = ((standard["avg_time"] - enhanced["avg_time"]) / standard["avg_time"]) * 100
                success_improvement = (enhanced["success_rate"] - standard["success_rate"]) * 100

                print(f"\n📋 {task_id}:")
                print(f"  Время: {standard['avg_time']:.2f}s → {enhanced['avg_time']:.2f}s ({time_improvement:+.1f}%)")
                print(f"  Success rate: {standard['success_rate']*100:.1f}% → {enhanced['success_rate']*100:.1f}% ({success_improvement:+.1f}%)")
                print(f"  Метод: {enhanced.get('results', [{}])[0].get('method', 'unknown')}")

    def save_results(self, results: List[Dict]):
        """Сохранение результатов"""
        timestamp = datetime.now(timezone.utc).isoformat()
        output = {
            "timestamp": timestamp,
            "benchmark_results": results,
            "summary": self._calculate_summary(results)
        }

        os.makedirs("docs/mac-studio/test_results", exist_ok=True)
        filename = f"docs/mac-studio/test_results/benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Результаты сохранены: {filename}")

    def _calculate_summary(self, results: List[Dict]) -> Dict:
        """Расчет сводной статистики"""
        standard_results = [r for r in results if not r["use_enhanced"]]
        enhanced_results = [r for r in results if r["use_enhanced"]]

        avg_time_standard = statistics.mean([r["avg_time"] for r in standard_results]) if standard_results else 0
        avg_time_enhanced = statistics.mean([r["avg_time"] for r in enhanced_results]) if enhanced_results else 0

        avg_success_standard = statistics.mean([r["success_rate"] for r in standard_results]) if standard_results else 0
        avg_success_enhanced = statistics.mean([r["success_rate"] for r in enhanced_results]) if enhanced_results else 0

        return {
            "avg_time_improvement": ((avg_time_standard - avg_time_enhanced) / avg_time_standard * 100) if avg_time_standard > 0 else 0,
            "avg_success_improvement": (avg_success_enhanced - avg_success_standard) * 100,
            "total_tasks": len(set(r["task_id"] for r in results))
        }

async def main():
    """Главная функция"""
    benchmark = EnhancedBenchmark()
    await benchmark.run_benchmarks()

if __name__ == "__main__":
    asyncio.run(main())
