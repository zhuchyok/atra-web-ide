"""
Adaptive Agent - Адаптивный агент с RL
Адаптация поведения на основе результатов и feedback
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from app.reinforcement_learning import get_rl, ReinforcementLearning
from app.human_in_the_loop import get_hitl

logger = logging.getLogger(__name__)


class AdaptiveAgent:
    """Адаптивный агент с reinforcement learning"""
    
    def __init__(self, agent_name: str = "Виктория"):
        self.agent_name = agent_name
        self.rl = get_rl(agent_name)
        self.hitl = get_hitl()
        
        # Статистика адаптации
        self.adaptation_history: List[Dict[str, Any]] = []
        self.performance_metrics: Dict[str, float] = {
            "success_rate": 0.0,
            "average_quality": 0.0,
            "efficiency": 0.0
        }
    
    async def adapt_from_feedback(
        self,
        action_id: str,
        feedback_type: str,
        feedback_value: float
    ) -> Dict[str, Any]:
        """
        Адаптироваться на основе feedback
        
        Args:
            action_id: ID действия
            feedback_type: Тип фидбека
            feedback_value: Значение фидбека
        
        Returns:
            Результат адаптации
        """
        # Преобразуем feedback в reward
        reward_value = feedback_value if -1.0 <= feedback_value <= 1.0 else 0.0
        
        # Назначаем reward
        reward = await self.rl.assign_reward(
            action_id=action_id,
            reward_value=reward_value,
            reward_type=feedback_type
        )
        
        # Анализируем и адаптируем
        adaptation = {
            "action_id": action_id,
            "reward": reward_value,
            "adaptation_type": "feedback_based",
            "timestamp": datetime.now(timezone.utc)
        }
        
        # Обновляем метрики
        await self._update_metrics(reward_value)
        
        # Адаптируем exploration rate
        if reward_value > 0.7:
            # Успешное действие - уменьшаем exploration
            self.rl.exploration_rate = max(0.05, self.rl.exploration_rate * 0.95)
        elif reward_value < -0.3:
            # Неудачное действие - увеличиваем exploration
            self.rl.exploration_rate = min(0.3, self.rl.exploration_rate * 1.1)
        
        self.adaptation_history.append(adaptation)
        
        logger.info(f"🔄 Адаптация: exploration_rate = {self.rl.exploration_rate:.3f}")
        
        return adaptation
    
    async def adapt_from_result(
        self,
        action_id: str,
        result: Any,
        expected_result: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Адаптироваться на основе результата действия
        
        Args:
            action_id: ID действия
            result: Фактический результат
            expected_result: Ожидаемый результат
        
        Returns:
            Результат адаптации
        """
        # Самонаграждение
        reward = await self.rl.self_reward(action_id, result, expected_result)
        
        # Адаптация
        adaptation = {
            "action_id": action_id,
            "reward": reward.reward_value,
            "adaptation_type": "result_based",
            "timestamp": datetime.now(timezone.utc)
        }
        
        # Обновляем метрики
        await self._update_metrics(reward.reward_value)
        
        self.adaptation_history.append(adaptation)
        
        return adaptation
    
    async def _update_metrics(self, reward_value: float):
        """Обновить метрики производительности"""
        # Обновляем success rate
        total_rewards = len(self.rl.reward_history)
        if total_rewards > 0:
            positive = sum(1 for r in self.rl.reward_history if r.reward_value > 0)
            self.performance_metrics["success_rate"] = positive / total_rewards
        
        # Обновляем average quality
        if total_rewards > 0:
            avg_reward = sum(r.reward_value for r in self.rl.reward_history) / total_rewards
            self.performance_metrics["average_quality"] = avg_reward
        
        # Обновляем efficiency (упрощенно)
        self.performance_metrics["efficiency"] = self.performance_metrics["success_rate"] * 0.7 + \
                                                  self.performance_metrics["average_quality"] * 0.3
    
    async def select_adaptive_action(
        self,
        state: str,
        available_actions: List[str],
        context: Dict[str, Any] = None
    ) -> str:
        """
        Выбрать действие с адаптацией
        
        Args:
            state: Текущее состояние
            available_actions: Доступные действия
            context: Контекст
        
        Returns:
            Выбранное действие
        """
        # Используем RL для выбора
        action = await self.rl.select_action(state, available_actions, context)
        
        # Логируем выбор
        logger.debug(f"🎯 Адаптивный выбор: {action} для состояния {state}")
        
        return action
    
    def get_adaptation_summary(self) -> Dict[str, Any]:
        """Получить сводку адаптации"""
        stats = self.rl.get_statistics()
        
        return {
            "agent_name": self.agent_name,
            "performance_metrics": self.performance_metrics,
            "rl_statistics": stats,
            "adaptation_count": len(self.adaptation_history),
            "exploration_rate": self.rl.exploration_rate,
            "recent_adaptations": self.adaptation_history[-10:] if self.adaptation_history else []
        }

# Глобальные экземпляры
_adaptive_agents: Dict[str, AdaptiveAgent] = {}

def get_adaptive_agent(agent_name: str = "Виктория") -> AdaptiveAgent:
    """Получить адаптивный агент"""
    if agent_name not in _adaptive_agents:
        _adaptive_agents[agent_name] = AdaptiveAgent(agent_name=agent_name)
    return _adaptive_agents[agent_name]
