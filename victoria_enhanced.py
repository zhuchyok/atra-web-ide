"""
Victoria Enhanced - Интеграция новых компонентов супер-корпорации с Victoria
Подключает: ReAct, Extended Thinking, Swarm, Consensus, Collective Memory и др.
"""

import os
import asyncio
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# OpenTelemetry для трассировки
try:
    from app.observability import get_observability_manager, trace_span
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False
    logger.debug("Observability не доступен")

# Enhanced Cache для кэширования результатов
try:
    from app.enhanced_cache import get_enhanced_cache
    ENHANCED_CACHE_AVAILABLE = True
except ImportError:
    ENHANCED_CACHE_AVAILABLE = False
    logger.debug("Enhanced Cache не доступен")

# Импорты новых компонентов
try:
    from app.react_agent import ReActAgent
    REACT_AVAILABLE = True
except ImportError:
    REACT_AVAILABLE = False
    logger.warning("⚠️ ReActAgent не доступен")

try:
    from app.extended_thinking import ExtendedThinkingEngine
    EXTENDED_THINKING_AVAILABLE = True
except ImportError:
    EXTENDED_THINKING_AVAILABLE = False
    logger.warning("⚠️ ExtendedThinkingEngine не доступен")

try:
    from app.swarm_intelligence import SwarmIntelligence
    SWARM_AVAILABLE = True
except ImportError:
    SWARM_AVAILABLE = False
    logger.warning("⚠️ SwarmIntelligence не доступен")

try:
    from app.consensus_agent import ConsensusAgent
    CONSENSUS_AVAILABLE = True
except ImportError:
    CONSENSUS_AVAILABLE = False
    logger.warning("⚠️ ConsensusAgent не доступен")

try:
    from app.collective_memory import CollectiveMemorySystem
    COLLECTIVE_MEMORY_AVAILABLE = True
except ImportError:
    COLLECTIVE_MEMORY_AVAILABLE = False
    logger.warning("⚠️ CollectiveMemorySystem не доступен")

try:
    from app.hierarchical_orchestration import HierarchicalOrchestrator
    HIERARCHICAL_AVAILABLE = True
except ImportError:
    HIERARCHICAL_AVAILABLE = False
    logger.warning("⚠️ HierarchicalOrchestrator не доступен")

try:
    from app.recap_framework import ReCAPFramework
    RECAP_AVAILABLE = True
except ImportError:
    RECAP_AVAILABLE = False
    logger.warning("⚠️ ReCAPFramework не доступен")

try:
    from app.tree_of_thoughts import TreeOfThoughts
    TOT_AVAILABLE = True
except ImportError:
    TOT_AVAILABLE = False
    logger.warning("⚠️ TreeOfThoughts не доступен")


class VictoriaEnhanced:
    """
    Victoria Enhanced - Victoria с интеграцией всех новых компонентов
    
    Автоматически выбирает оптимальный метод для задачи:
    - Reasoning → Extended Thinking + ReCAP
    - Planning → Tree of Thoughts + Hierarchical Orchestration
    - Complex → Swarm Intelligence + Consensus
    - Execution → ReAct Framework
    """
    
    def __init__(
        self,
        model_name: str = "deepseek-r1-distill-llama:70b",
        use_react: bool = True,
        use_extended_thinking: bool = True,
        use_swarm: bool = True,
        use_consensus: bool = True,
        use_collective_memory: bool = True
    ):
        self.model_name = model_name
        self.use_react = use_react and REACT_AVAILABLE
        self.use_extended_thinking = use_extended_thinking and EXTENDED_THINKING_AVAILABLE
        self.use_swarm = use_swarm and SWARM_AVAILABLE
        self.use_consensus = use_consensus and CONSENSUS_AVAILABLE
        self.use_collective_memory = use_collective_memory and COLLECTIVE_MEMORY_AVAILABLE
        
        # Инициализируем компоненты
        self.react_agent = None
        self.extended_thinking = None
        self.swarm = None
        self.consensus = None
        self.collective_memory = None
        self.hierarchical_orch = None
        self.recap = None
        self.tot = None
        
        # Инициализация observability
        self.observability = None
        if OBSERVABILITY_AVAILABLE:
            try:
                self.observability = get_observability_manager("victoria-enhanced")
                logger.info("✅ Observability инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации Observability: {e}")
        
        # Инициализация кэша
        self.cache = None
        self.use_cache = ENHANCED_CACHE_AVAILABLE
        if self.use_cache:
            try:
                self.cache = get_enhanced_cache()
                logger.info("✅ Enhanced Cache инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации Enhanced Cache: {e}")
                self.use_cache = False
        
        self._initialize_components()
    
    def _initialize_components(self):
        """Инициализировать доступные компоненты"""
        if self.use_react:
            try:
                self.react_agent = ReActAgent(
                    agent_name="Victoria",
                    model_name=self.model_name
                )
                logger.info("✅ ReActAgent инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ReActAgent: {e}")
        
        if self.use_extended_thinking:
            try:
                self.extended_thinking = ExtendedThinkingEngine(
                    model_name=self.model_name
                )
                logger.info("✅ ExtendedThinkingEngine инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ExtendedThinkingEngine: {e}")
        
        if self.use_swarm:
            try:
                self.swarm = SwarmIntelligence(
                    swarm_size=16,
                    model_name=self.model_name
                )
                logger.info("✅ SwarmIntelligence инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации SwarmIntelligence: {e}")
        
        if self.use_consensus:
            try:
                self.consensus = ConsensusAgent(model_name=self.model_name)
                logger.info("✅ ConsensusAgent инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ConsensusAgent: {e}")
        
        if self.use_collective_memory:
            try:
                self.collective_memory = CollectiveMemorySystem()
                logger.info("✅ CollectiveMemorySystem инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации CollectiveMemorySystem: {e}")
        
        if HIERARCHICAL_AVAILABLE:
            try:
                self.hierarchical_orch = HierarchicalOrchestrator(root_agent="Victoria")
                logger.info("✅ HierarchicalOrchestrator инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации HierarchicalOrchestrator: {e}")
        
        if RECAP_AVAILABLE:
            try:
                self.recap = ReCAPFramework(model_name=self.model_name)
                logger.info("✅ ReCAPFramework инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ReCAPFramework: {e}")
        
        if TOT_AVAILABLE:
            try:
                self.tot = TreeOfThoughts(model_name=self.model_name)
                logger.info("✅ TreeOfThoughts инициализирован")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации TreeOfThoughts: {e}")
    
    def _categorize_task(self, goal: str) -> str:
        """Определить категорию задачи"""
        goal_lower = goal.lower()
        
        if any(word in goal_lower for word in ["реши", "рассчитай", "вычисли", "reasoning", "логика"]):
            return "reasoning"
        elif any(word in goal_lower for word in ["спланируй", "организуй", "plan", "планирование"]):
            return "planning"
        elif any(word in goal_lower for word in ["сложн", "комплекс", "много", "complex"]):
            return "complex"
        elif any(word in goal_lower for word in ["выполни", "сделай", "execute", "действие"]):
            return "execution"
        else:
            return "general"
    
    async def solve(
        self,
        goal: str,
        method: Optional[str] = None,
        use_enhancements: bool = True
    ) -> Dict:
        """
        Решить задачу используя оптимальный метод
        
        Args:
            goal: Цель задачи
            method: Предпочтительный метод (опционально)
            use_enhancements: Использовать ли улучшения
        
        Returns:
            Результат с метаданными
        """
        if not use_enhancements:
            # Fallback на простой метод
            return {"result": "Enhanced methods disabled", "method": "simple"}
        
        # Трассировка через OpenTelemetry
        span_attributes = {"goal": goal[:100], "use_enhancements": use_enhancements}
        span_context = None
        if hasattr(self, 'observability') and self.observability:
            try:
                span_context = self.observability.trace_span("victoria_enhanced.solve", span_attributes)
            except Exception as e:
                logger.debug(f"Observability недоступен: {e}")
                span_context = None
        
        try:
            if span_context:
                span_context.__enter__()
            
            # Определяем категорию задачи
            category = self._categorize_task(goal)
            
            # Выбираем метод
            if method is None:
                method = self._select_optimal_method(category, goal)
            
            logger.info(f"🎯 Victoria Enhanced: категория={category}, метод={method}")
            
            # Добавляем атрибуты в span
            if hasattr(self, 'observability') and self.observability:
                try:
                    self.observability.set_attribute("task.category", category)
                    self.observability.set_attribute("task.method", method)
                except Exception as e:
                    logger.debug(f"Не удалось установить атрибуты observability: {e}")
            
            # Получаем контекст из Collective Memory
            context = None
            if self.collective_memory:
                try:
                    context = await self.collective_memory.get_enhanced_context(
                        agent_name="Victoria",
                        location="general"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка получения collective memory: {e}")
            
            # Проверяем кэш
            if self.use_cache and self.cache:
                cached_result = await self.cache.get(method, goal, context)
                if cached_result:
                    logger.info(f"✅ Cache hit для метода {method}")
                    if hasattr(self, 'observability') and self.observability:
                        try:
                            self.observability.set_attribute("cache.hit", True)
                        except Exception:
                            pass
                    return cached_result
                if hasattr(self, 'observability') and self.observability:
                    try:
                        self.observability.set_attribute("cache.hit", False)
                    except Exception:
                        pass
            
            # Выполняем через выбранный метод
            result = await self._execute_method(method, goal, category, context)
            
            # Сохраняем в кэш
            if self.use_cache and self.cache:
                try:
                    await self.cache.set(method, goal, result, context)
                    logger.debug(f"💾 Результат сохранен в кэш: {method}")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка сохранения в кэш: {e}")
            
            # Добавляем метрики в span
            if hasattr(self, 'observability') and self.observability:
                try:
                    self.observability.set_attribute("result.method", result.get("method", ""))
                    self.observability.add_event("task.completed", {
                        "method": result.get("method", ""),
                        "success": True
                    })
                except Exception as e:
                    logger.debug(f"Не удалось добавить метрики observability: {e}")
            
            # Сохраняем в Collective Memory
            if self.collective_memory:
                try:
                    await self.collective_memory.record_action(
                        agent_name="Victoria",
                        action="solve",
                        result=result.get("result", ""),
                        location=category
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка сохранения в collective memory: {e}")
            
            return result
        finally:
            if span_context:
                span_context.__exit__(None, None, None)
    
    def _select_optimal_method(self, category: str, goal: str) -> str:
        """Выбрать оптимальный метод для категории"""
        method_map = {
            "reasoning": "extended_thinking" if self.extended_thinking else "recap",
            "planning": "tree_of_thoughts" if self.tot else "hierarchical",
            "complex": "swarm" if self.swarm else "consensus",
            "execution": "react" if self.react_agent else "simple",
            "general": "extended_thinking" if self.extended_thinking else "simple"
        }
        
        method = method_map.get(category, "simple")
        
        # Проверяем доступность метода
        if method == "extended_thinking" and not self.extended_thinking:
            method = "simple"
        elif method == "swarm" and not self.swarm:
            method = "consensus" if self.consensus else "simple"
        elif method == "react" and not self.react_agent:
            method = "simple"
        elif method == "tree_of_thoughts" and not self.tot:
            method = "hierarchical" if self.hierarchical_orch else "simple"
        elif method == "recap" and not self.recap:
            method = "extended_thinking" if self.extended_thinking else "simple"
        
        return method
    
    async def _execute_method(
        self,
        method: str,
        goal: str,
        category: str,
        context: Optional[Dict]
    ) -> Dict:
        """Выполнить задачу через выбранный метод"""
        start_time = datetime.now(timezone.utc)
        
        try:
            if method == "react" and self.react_agent:
                result = await self.react_agent.run(goal, context)
                return {
                    "result": result.get("final_reflection", result.get("response", "")),
                    "method": "react",
                    "steps": len(result.get("steps", [])),
                    "metadata": result
                }
            
            elif method == "extended_thinking" and self.extended_thinking:
                result = await self.extended_thinking.think(goal, context, use_iterative=True)
                return {
                    "result": result.final_answer,
                    "method": "extended_thinking",
                    "confidence": result.confidence,
                    "thinking_steps": len(result.thinking_steps),
                    "metadata": {
                        "total_tokens": result.total_tokens_used,
                        "thinking_time": result.thinking_time_seconds
                    }
                }
            
            elif method == "swarm" and self.swarm:
                result = await self.swarm.solve(goal)
                return {
                    "result": str(result.global_best),
                    "method": "swarm",
                    "global_best_score": result.global_best_score,
                    "iterations": result.iterations,
                    "convergence_rate": result.convergence_rate,
                    "metadata": result
                }
            
            elif method == "consensus" and self.consensus:
                # Используем команду экспертов для consensus
                agents = ["Victoria", "Veronica", "Игорь", "Сергей", "Дмитрий"]
                result = await self.consensus.reach_consensus(agents, goal)
                return {
                    "result": result.final_answer,
                    "method": "consensus",
                    "consensus_score": result.consensus_score,
                    "agreement_level": result.agreement_level,
                    "iterations": result.iterations,
                    "metadata": result
                }
            
            elif method == "tree_of_thoughts" and self.tot:
                result = await self.tot.solve(goal)
                return {
                    "result": result.final_answer,
                    "method": "tree_of_thoughts",
                    "confidence": result.confidence,
                    "total_thoughts": result.total_thoughts,
                    "exploration_depth": result.exploration_depth,
                    "metadata": result
                }
            
            elif method == "recap" and self.recap:
                result = await self.recap.solve(goal, context)
                return {
                    "result": result["final_result"],
                    "method": "recap",
                    "high_level_steps": len(result["plan"].high_level_steps),
                    "metadata": result
                }
            
            elif method == "hierarchical" and self.hierarchical_orch:
                # Нужны агенты для hierarchical
                agents = {
                    "Victoria": {"role": "team_lead"},
                    "Veronica": {"role": "developer"},
                    "Игорь": {"role": "backend"},
                    "Сергей": {"role": "devops"}
                }
                state = await self.hierarchical_orch.orchestrate(goal, agents)
                return {
                    "result": "Hierarchical orchestration completed",
                    "method": "hierarchical",
                    "goals_count": len(state.goals),
                    "dependencies": len(state.dependencies),
                    "metadata": state.visualization_data
                }
            
            else:
                # Fallback на простой метод
                return {
                    "result": f"Задача: {goal} (простой метод, enhancements недоступны)",
                    "method": "simple",
                    "note": "Enhanced methods not available"
                }
        
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения метода {method}: {e}")
            return {
                "result": f"Ошибка: {str(e)}",
                "method": method,
                "error": str(e)
            }
        finally:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"⏱️ Метод {method} выполнен за {elapsed:.2f}с")
    
    async def get_status(self) -> Dict:
        """Получить статус всех компонентов"""
        return {
            "react_available": self.react_agent is not None,
            "extended_thinking_available": self.extended_thinking is not None,
            "swarm_available": self.swarm is not None,
            "consensus_available": self.consensus is not None,
            "collective_memory_available": self.collective_memory is not None,
            "hierarchical_available": self.hierarchical_orch is not None,
            "recap_available": self.recap is not None,
            "tot_available": self.tot is not None,
            "model": self.model_name
        }


async def main():
    """Тестирование Victoria Enhanced"""
    victoria = VictoriaEnhanced()
    
    # Проверяем статус
    status = await victoria.get_status()
    print("Статус компонентов:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Тестируем разные типы задач
    test_tasks = [
        ("Реши задачу: 2+2*2", "reasoning"),
        ("Спланируй оптимизацию базы данных", "planning"),
        ("Сложная задача требующая коллективного интеллекта", "complex"),
        ("Выполни анализ кода", "execution")
    ]
    
    print("\n🧪 Тестирование задач:")
    for goal, expected_category in test_tasks:
        print(f"\n📋 Задача: {goal}")
        result = await victoria.solve(goal)
        print(f"  Метод: {result.get('method')}")
        print(f"  Результат: {str(result.get('result', ''))[:200]}...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
