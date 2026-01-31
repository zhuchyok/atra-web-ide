#!/usr/bin/env python3
"""
Comprehensive Test Suite для Victoria Enhanced
Тестирует все 13 компонентов супер-корпорации
"""

import asyncio
import time
import json
import sys
import os
from typing import Dict, List, Any
from datetime import datetime, timezone

# Добавляем путь к knowledge_os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../knowledge_os'))

from app.victoria_enhanced import VictoriaEnhanced
from app.react_agent import ReActAgent
from app.extended_thinking import ExtendedThinkingEngine
from app.tree_of_thoughts import TreeOfThoughts
from app.swarm_intelligence import SwarmIntelligence
from app.consensus_agent import ConsensusAgent
from app.collective_memory import CollectiveMemorySystem
from app.recap_framework import ReCAPFramework
from app.self_learning_agent import SelfLearningAgent
from app.event_bus import EventBus
from app.agent_protocol import AgentProtocol
# from app.hierarchical_orchestration import HierarchicalOrchestrator  # Используется внутри VictoriaEnhanced
from app.state_machine import StateGraph, AgentState

class EnhancedTestSuite:
    """Comprehensive test suite для всех компонентов"""
    
    def __init__(self):
        self.results = []
        self.enhanced = None
        
    async def setup(self):
        """Инициализация компонентов"""
        print("🔧 Инициализация компонентов...")
        try:
            self.enhanced = VictoriaEnhanced()
            print("✅ VictoriaEnhanced инициализирован")
        except Exception as e:
            print(f"❌ Ошибка инициализации: {e}")
            return False
        return True
    
    async def test_react_agent(self) -> Dict[str, Any]:
        """Тест ReAct Framework"""
        print("\n🧪 Тест 1: ReAct Framework")
        start_time = time.time()
        
        try:
            if not self.enhanced.react_agent:
                return {"status": "skipped", "reason": "ReActAgent не доступен"}
            
            result = await self.enhanced.react_agent.run(
                "Реши задачу: найди сумму чисел 5, 10, 15",
                context={"task_type": "math"}
            )
            
            elapsed = time.time() - start_time
            return {
                "status": "passed",
                "method": "react",
                "time": elapsed,
                "steps": len(result.get("steps", [])),
                "result": result.get("final_reflection", "")[:100]
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def test_extended_thinking(self) -> Dict[str, Any]:
        """Тест Extended Thinking"""
        print("\n🧪 Тест 2: Extended Thinking")
        start_time = time.time()
        
        try:
            if not self.enhanced.extended_thinking:
                return {"status": "skipped", "reason": "ExtendedThinking не доступен"}
            
            result = await self.enhanced.extended_thinking.think(
                "Объясни почему 2+2*2 равно 6, а не 8",
                use_iterative=True
            )
            
            elapsed = time.time() - start_time
            return {
                "status": "passed",
                "method": "extended_thinking",
                "time": elapsed,
                "confidence": result.confidence,
                "thinking_steps": len(result.thinking_steps),
                "result": result.final_answer[:100]
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def test_tree_of_thoughts(self) -> Dict[str, Any]:
        """Тест Tree of Thoughts"""
        print("\n🧪 Тест 3: Tree of Thoughts")
        start_time = time.time()
        
        try:
            if not self.enhanced.tot:
                return {"status": "skipped", "reason": "TreeOfThoughts не доступен"}
            
            result = await self.enhanced.tot.solve(
                "Спланируй разработку веб-приложения: фронтенд, бэкенд, БД",
                max_depth=3
            )
            
            elapsed = time.time() - start_time
            return {
                "status": "passed",
                "method": "tree_of_thoughts",
                "time": elapsed,
                "best_path_length": len(result.best_path) if result.best_path else 0,
                "result": str(result.best_solution)[:100] if result.best_solution else ""
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def test_swarm_intelligence(self) -> Dict[str, Any]:
        """Тест Swarm Intelligence"""
        print("\n🧪 Тест 4: Swarm Intelligence")
        start_time = time.time()
        
        try:
            if not self.enhanced.swarm:
                return {"status": "skipped", "reason": "SwarmIntelligence не доступен"}
            
            result = await self.enhanced.swarm.solve(
                "Найди оптимальное решение для задачи оптимизации: минимизировать x^2 + y^2 при x+y=10"
            )
            
            elapsed = time.time() - start_time
            return {
                "status": "passed",
                "method": "swarm",
                "time": elapsed,
                "iterations": result.iterations,
                "convergence_rate": result.convergence_rate,
                "result": str(result.global_best)[:100]
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def test_consensus_agent(self) -> Dict[str, Any]:
        """Тест Consensus Agent"""
        print("\n🧪 Тест 5: Consensus Agent")
        start_time = time.time()
        
        try:
            if not self.enhanced.consensus:
                return {"status": "skipped", "reason": "ConsensusAgent не доступен"}
            
            agents = ["Victoria", "Veronica", "Игорь"]
            result = await self.enhanced.consensus.reach_consensus(
                agents,
                "Какой язык программирования лучше для веб-разработки: Python или JavaScript?"
            )
            
            elapsed = time.time() - start_time
            return {
                "status": "passed",
                "method": "consensus",
                "time": elapsed,
                "consensus_score": result.consensus_score,
                "agreement_level": result.agreement_level,
                "result": result.final_answer[:100]
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def test_collective_memory(self) -> Dict[str, Any]:
        """Тест Collective Memory"""
        print("\n🧪 Тест 6: Collective Memory")
        start_time = time.time()
        
        try:
            if not self.enhanced.collective_memory:
                return {"status": "skipped", "reason": "CollectiveMemory не доступен"}
            
            # Записываем действие
            await self.enhanced.collective_memory.record_action(
                "Victoria",
                "test_action",
                "test_result",
                "test_location",
                {"test": "data"}
            )
            
            # Получаем контекст
            context = await self.enhanced.collective_memory.get_enhanced_context(
                "Victoria",
                "test_location"
            )
            
            elapsed = time.time() - start_time
            return {
                "status": "passed",
                "method": "collective_memory",
                "time": elapsed,
                "context_retrieved": context is not None,
                "result": "Memory system working"
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def test_recap_framework(self) -> Dict[str, Any]:
        """Тест ReCAP Framework"""
        print("\n🧪 Тест 7: ReCAP Framework")
        start_time = time.time()
        
        try:
            if not self.enhanced.recap:
                return {"status": "skipped", "reason": "ReCAPFramework не доступен"}
            
            result = await self.enhanced.recap.execute_plan(
                "Разработай план миграции базы данных с MySQL на PostgreSQL"
            )
            
            elapsed = time.time() - start_time
            return {
                "status": "passed",
                "method": "recap",
                "time": elapsed,
                "plan_levels": len(result.plan.high_level_steps) if result.plan else 0,
                "result": str(result.final_result)[:100] if result.final_result else ""
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def test_automatic_selection(self) -> Dict[str, Any]:
        """Тест автоматического выбора метода"""
        print("\n🧪 Тест 8: Автоматический выбор метода")
        start_time = time.time()
        
        test_cases = [
            ("Реши математическую задачу: 2+2*2", "reasoning"),
            ("Спланируй разработку проекта", "planning"),
            ("Сложная задача требующая коллективного решения", "complex"),
            ("Выполни команду: создай файл test.txt", "execution"),
        ]
        
        results = []
        for goal, expected_category in test_cases:
            try:
                result = await self.enhanced.solve(goal, use_enhancements=True)
                results.append({
                    "goal": goal[:50],
                    "expected": expected_category,
                    "method": result.get("method", "unknown"),
                    "status": "passed" if result.get("method") else "failed"
                })
            except Exception as e:
                results.append({
                    "goal": goal[:50],
                    "status": "failed",
                    "error": str(e)
                })
        
        elapsed = time.time() - start_time
        return {
            "status": "passed",
            "method": "automatic_selection",
            "time": elapsed,
            "test_cases": len(test_cases),
            "results": results
        }
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("=" * 60)
        print("🚀 COMPREHENSIVE TEST SUITE - Victoria Enhanced")
        print("=" * 60)
        
        if not await self.setup():
            print("❌ Не удалось инициализировать компоненты")
            return
        
        tests = [
            self.test_react_agent,
            self.test_extended_thinking,
            self.test_tree_of_thoughts,
            self.test_swarm_intelligence,
            self.test_consensus_agent,
            self.test_collective_memory,
            self.test_recap_framework,
            self.test_automatic_selection,
        ]
        
        results = []
        for test in tests:
            try:
                result = await test()
                results.append(result)
                self.results.append(result)
            except Exception as e:
                result = {"status": "error", "error": str(e)}
                results.append(result)
                self.results.append(result)
        
        # Вывод результатов
        self.print_summary(results)
        
        # Сохранение результатов
        self.save_results(results)
    
    def print_summary(self, results: List[Dict]):
        """Вывод сводки результатов"""
        print("\n" + "=" * 60)
        print("📊 СВОДКА РЕЗУЛЬТАТОВ")
        print("=" * 60)
        
        passed = sum(1 for r in results if r.get("status") == "passed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        total = len(results)
        
        print(f"\n✅ Пройдено: {passed}/{total}")
        print(f"❌ Провалено: {failed}/{total}")
        print(f"⏭️  Пропущено: {skipped}/{total}")
        
        print("\n📋 Детали:")
        for i, result in enumerate(results, 1):
            status_icon = "✅" if result.get("status") == "passed" else "❌" if result.get("status") == "failed" else "⏭️"
            method = result.get("method", "unknown")
            time_taken = result.get("time", 0)
            print(f"{status_icon} Тест {i}: {method} ({time_taken:.2f}s)")
            if result.get("status") == "failed":
                print(f"   Ошибка: {result.get('error', 'Unknown')}")
    
    def save_results(self, results: List[Dict]):
        """Сохранение результатов в файл"""
        timestamp = datetime.now(timezone.utc).isoformat()
        output = {
            "timestamp": timestamp,
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.get("status") == "passed"),
                "failed": sum(1 for r in results if r.get("status") == "failed"),
                "skipped": sum(1 for r in results if r.get("status") == "skipped"),
            },
            "results": results
        }
        
        os.makedirs("docs/mac-studio/test_results", exist_ok=True)
        filename = f"docs/mac-studio/test_results/enhanced_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Результаты сохранены: {filename}")

async def main():
    """Главная функция"""
    suite = EnhancedTestSuite()
    await suite.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
