"""
State Machine для оркестрации агентов (LangGraph-style)
Основано на практике LangGraph и Microsoft AutoGen
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class NodeState(Enum):
    """Состояния узла"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentState:
    """Состояние агента в workflow"""
    goal: str = ""
    current_node: Optional[str] = None
    node_results: Dict[str, Any] = field(default_factory=dict)
    node_states: Dict[str, NodeState] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict] = field(default_factory=list)
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class StateGraph:
    """
    State Graph для оркестрации агентов
    
    Моделирует workflow как граф с узлами и ребрами
    """
    
    def __init__(self, state_class: type = AgentState):
        self.state_class = state_class
        self.nodes: Dict[str, Callable] = {}
        self.edges: List[tuple] = []  # (from_node, to_node, condition)
        self.entry_point: Optional[str] = None
        self.checkpoints: Dict[str, AgentState] = {}
    
    def add_node(self, name: str, func: Callable):
        """
        Добавить узел в граф
        
        Args:
            name: Имя узла
            func: Функция узла (async, принимает state, возвращает обновленный state)
        """
        self.nodes[name] = func
        logger.debug(f"✅ Добавлен узел: {name}")
    
    def add_edge(self, from_node: str, to_node: str, condition: Optional[Callable] = None):
        """
        Добавить ребро между узлами
        
        Args:
            from_node: Исходный узел
            to_node: Целевой узел
            condition: Условие перехода (опционально, принимает state, возвращает bool)
        """
        self.edges.append((from_node, to_node, condition))
        logger.debug(f"✅ Добавлено ребро: {from_node} → {to_node}")
    
    def add_conditional_edges(
        self,
        from_node: str,
        condition_func: Callable,
        edge_map: Dict[str, str]
    ):
        """
        Добавить условные ребра
        
        Args:
            from_node: Исходный узел
            condition_func: Функция условия (принимает state, возвращает ключ из edge_map)
            edge_map: Маппинг ключей на узлы
        """
        for key, to_node in edge_map.items():
            self.edges.append((from_node, to_node, lambda s, k=key: condition_func(s) == k))
        logger.debug(f"✅ Добавлены условные ребра из {from_node}: {edge_map}")
    
    def set_entry_point(self, node_name: str):
        """Установить точку входа"""
        if node_name not in self.nodes:
            raise ValueError(f"Узел {node_name} не существует")
        self.entry_point = node_name
        logger.debug(f"✅ Точка входа: {node_name}")
    
    async def run(self, initial_state: Optional[AgentState] = None) -> AgentState:
        """
        Запустить выполнение графа
        
        Args:
            initial_state: Начальное состояние
        
        Returns:
            Финальное состояние
        """
        if initial_state is None:
            initial_state = self.state_class()
        
        if self.entry_point is None:
            raise ValueError("Точка входа не установлена")
        
        current_node = self.entry_point
        state = initial_state
        
        logger.info(f"🚀 Запуск State Graph, начальный узел: {current_node}")
        
        visited = set()
        max_iterations = 100
        iteration = 0
        
        while current_node and iteration < max_iterations:
            iteration += 1
            
            if current_node in visited:
                logger.warning(f"⚠️ Обнаружен цикл: {current_node}")
                break
            
            visited.add(current_node)
            
            if current_node not in self.nodes:
                logger.error(f"❌ Узел {current_node} не найден")
                state.error = f"Узел {current_node} не найден"
                break
            
            # Выполняем узел
            try:
                logger.info(f"🔄 Выполнение узла: {current_node}")
                state.current_node = current_node
                state.node_states[current_node] = NodeState.RUNNING
                
                # Сохраняем checkpoint
                self.checkpoints[f"{current_node}_{iteration}"] = state
                
                # Выполняем функцию узла
                node_func = self.nodes[current_node]
                state = await node_func(state)
                
                state.node_states[current_node] = NodeState.COMPLETED
                logger.info(f"✅ Узел {current_node} выполнен")
                
            except Exception as e:
                logger.error(f"❌ Ошибка в узле {current_node}: {e}")
                state.node_states[current_node] = NodeState.FAILED
                state.error = str(e)
                break
            
            # Определяем следующий узел
            next_node = self._get_next_node(current_node, state)
            
            if next_node is None:
                logger.info(f"🏁 Достигнут конец workflow")
                break
            
            current_node = next_node
        
        if iteration >= max_iterations:
            logger.warning(f"⚠️ Достигнут лимит итераций: {max_iterations}")
        
        return state
    
    def _get_next_node(self, current_node: str, state: AgentState) -> Optional[str]:
        """Определить следующий узел на основе ребер"""
        candidates = []
        
        for from_node, to_node, condition in self.edges:
            if from_node == current_node:
                if condition is None:
                    candidates.append(to_node)
                else:
                    try:
                        if condition(state):
                            candidates.append(to_node)
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка в условии перехода: {e}")
        
        if len(candidates) == 0:
            return None
        elif len(candidates) == 1:
            return candidates[0]
        else:
            # Если несколько кандидатов, берем первый (можно улучшить через приоритеты)
            logger.warning(f"⚠️ Несколько кандидатов для перехода из {current_node}, выбран: {candidates[0]}")
            return candidates[0]
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[AgentState]:
        """Получить сохраненное состояние"""
        return self.checkpoints.get(checkpoint_id)
    
    def restore_from_checkpoint(self, checkpoint_id: str) -> AgentState:
        """Восстановить состояние из checkpoint"""
        checkpoint = self.checkpoints.get(checkpoint_id)
        if checkpoint is None:
            raise ValueError(f"Checkpoint {checkpoint_id} не найден")
        return checkpoint


# Пример использования
async def victoria_node(state: AgentState) -> AgentState:
    """Узел Victoria - анализ и планирование"""
    logger.info("👑 Victoria анализирует задачу...")
    
    # Симуляция работы Victoria
    state.context["victoria_analysis"] = f"Анализ задачи: {state.goal}"
    state.node_results["victoria"] = "Задача проанализирована"
    
    return state


async def veronica_node(state: AgentState) -> AgentState:
    """Узел Veronica - выполнение"""
    logger.info("🔧 Veronica выполняет задачу...")
    
    # Симуляция работы Veronica
    state.context["veronica_execution"] = "Выполнение задачи"
    state.node_results["veronica"] = "Задача выполнена"
    
    return state


async def finish_node(state: AgentState) -> AgentState:
    """Узел завершения"""
    logger.info("✅ Workflow завершен")
    state.context["finished"] = True
    return state


def route_decision(state: AgentState) -> str:
    """Функция маршрутизации"""
    if state.context.get("needs_execution"):
        return "veronica"
    else:
        return "finish"


async def example_workflow():
    """Пример workflow"""
    # Создаем граф
    graph = StateGraph(AgentState)
    
    # Добавляем узлы
    graph.add_node("victoria", victoria_node)
    graph.add_node("veronica", veronica_node)
    graph.add_node("finish", finish_node)
    
    # Добавляем ребра
    graph.add_conditional_edges(
        "victoria",
        route_decision,
        {
            "veronica": "veronica",
            "finish": "finish"
        }
    )
    graph.add_edge("veronica", "finish")
    
    # Устанавливаем точку входа
    graph.set_entry_point("victoria")
    
    # Создаем начальное состояние
    initial_state = AgentState(goal="Пример задачи")
    initial_state.context["needs_execution"] = True
    
    # Запускаем
    final_state = await graph.run(initial_state)
    
    print("Финальное состояние:")
    print(f"  Цель: {final_state.goal}")
    print(f"  Результаты: {final_state.node_results}")
    print(f"  Ошибка: {final_state.error}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_workflow())
