"""
Load Balancer
Распределение нагрузки между узлами для оптимального использования ресурсов
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class NodeLoad:
    """Информация о загрузке узла"""
    node_name: str
    routing_key: str
    active_requests: int = 0
    total_requests: int = 0
    avg_latency: float = 0.0
    success_rate: float = 1.0
    last_update: float = 0.0

class LoadBalancer:
    """
    Load Balancer для распределения нагрузки между узлами.
    """
    
    def __init__(self):
        self.node_loads: Dict[str, NodeLoad] = {}
        self._lock = asyncio.Lock()
        self._load_history: Dict[str, List[float]] = defaultdict(list)
        self._max_history = 100
    
    def update_node_load(
        self,
        node_name: str,
        routing_key: str,
        latency: float,
        success: bool = True
    ):
        """Обновляет информацию о загрузке узла"""
        async def _update():
            async with self._lock:
                if routing_key not in self.node_loads:
                    self.node_loads[routing_key] = NodeLoad(
                        node_name=node_name,
                        routing_key=routing_key
                    )
                
                load = self.node_loads[routing_key]
                load.total_requests += 1
                if success:
                    # Обновляем среднюю задержку (exponential moving average)
                    if load.avg_latency == 0:
                        load.avg_latency = latency
                    else:
                        load.avg_latency = 0.7 * load.avg_latency + 0.3 * latency
                    
                    # Обновляем success rate
                    successful = int(load.success_rate * (load.total_requests - 1)) + (1 if success else 0)
                    load.success_rate = successful / load.total_requests
                else:
                    # Уменьшаем success rate
                    successful = int(load.success_rate * (load.total_requests - 1))
                    load.success_rate = successful / load.total_requests
                
                load.last_update = time.time()
                
                # Сохраняем в историю
                self._load_history[routing_key].append(latency)
                if len(self._load_history[routing_key]) > self._max_history:
                    self._load_history[routing_key].pop(0)
        
        # Выполняем обновление асинхронно
        asyncio.create_task(_update())
    
    def start_request(self, routing_key: str):
        """Отмечает начало запроса к узлу"""
        async def _start():
            async with self._lock:
                if routing_key in self.node_loads:
                    self.node_loads[routing_key].active_requests += 1
        
        asyncio.create_task(_start())
    
    def end_request(self, routing_key: str):
        """Отмечает окончание запроса к узлу"""
        async def _end():
            async with self._lock:
                if routing_key in self.node_loads:
                    self.node_loads[routing_key].active_requests = max(0, 
                        self.node_loads[routing_key].active_requests - 1)
        
        asyncio.create_task(_end())
    
    def select_best_node(self, available_nodes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Выбирает лучший узел на основе загрузки.
        
        Args:
            available_nodes: Список доступных узлов
        
        Returns:
            Выбранный узел или None
        """
        if not available_nodes:
            return None
        
        # Если нет данных о загрузке, используем первый узел
        if not self.node_loads:
            return available_nodes[0]
        
        best_node = None
        best_score = float('inf')
        
        for node in available_nodes:
            routing_key = node.get('routing_key', '')
            if routing_key not in self.node_loads:
                # Новый узел - даем ему шанс
                return node
            
            load = self.node_loads[routing_key]
            
            # Вычисляем score (меньше = лучше)
            # Учитываем: активные запросы, среднюю задержку, success rate
            score = (
                load.active_requests * 10.0 +  # Штраф за активные запросы
                load.avg_latency * 0.1 +       # Штраф за задержку
                (1.0 - load.success_rate) * 50.0  # Штраф за низкий success rate
            )
            
            if score < best_score:
                best_score = score
                best_node = node
        
        return best_node or available_nodes[0]
    
    def get_node_statistics(self) -> Dict[str, Any]:
        """Получает статистику по узлам"""
        async def _get_stats():
            async with self._lock:
                stats = {}
                for routing_key, load in self.node_loads.items():
                    stats[routing_key] = {
                        'node_name': load.node_name,
                        'active_requests': load.active_requests,
                        'total_requests': load.total_requests,
                        'avg_latency': load.avg_latency,
                        'success_rate': load.success_rate,
                        'last_update': load.last_update
                    }
                return stats
        
        # Синхронный вызов для получения статистики
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Если loop уже запущен, создаем task
            future = asyncio.create_task(_get_stats())
            return {}  # Возвращаем пустой dict, так как не можем ждать
        else:
            return loop.run_until_complete(_get_stats())
    
    def increment_load(self, employee_id: Any):
        """Увеличивает загрузку сотрудника (для совместимости с Task Distribution)"""
        # Используем employee_id как routing_key для отслеживания загрузки
        routing_key = str(employee_id)
        self.start_request(routing_key)
    
    def decrement_load(self, employee_id: Any):
        """Уменьшает загрузку сотрудника (для совместимости с Task Distribution)"""
        # Используем employee_id как routing_key для отслеживания загрузки
        routing_key = str(employee_id)
        self.end_request(routing_key)
    
    def record_completion_time(self, employee_id: Any, execution_time: float):
        """Записывает время выполнения задачи (для совместимости с Task Distribution)"""
        # Используем employee_id как routing_key
        routing_key = str(employee_id)
        # Обновляем метрики загрузки
        async def _update():
            async with self._lock:
                if routing_key in self.node_loads:
                    load = self.node_loads[routing_key]
                    # Обновляем среднюю задержку
                    if load.avg_latency == 0:
                        load.avg_latency = execution_time
                    else:
                        load.avg_latency = 0.7 * load.avg_latency + 0.3 * execution_time
                    load.last_update = time.time()
        
        asyncio.create_task(_update())
    
    def round_robin_select(self, available_nodes: List[Dict[str, Any]], last_selected: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Round-robin выбор узла с учетом производительности.
        
        Args:
            available_nodes: Список доступных узлов
            last_selected: Последний выбранный узел (routing_key)
        
        Returns:
            Выбранный узел
        """
        if not available_nodes:
            return None
        
        # Если нет информации о последнем выборе, выбираем первый
        if last_selected is None:
            return available_nodes[0]
        
        # Находим индекс последнего выбранного узла
        last_index = -1
        for i, node in enumerate(available_nodes):
            if node.get('routing_key') == last_selected:
                last_index = i
                break
        
        # Выбираем следующий узел
        next_index = (last_index + 1) % len(available_nodes)
        return available_nodes[next_index]

# Singleton instance
_load_balancer_instance = None

def get_load_balancer() -> LoadBalancer:
    """Получает singleton instance load balancer"""
    global _load_balancer_instance
    if _load_balancer_instance is None:
        _load_balancer_instance = LoadBalancer()
    return _load_balancer_instance

