"""
Reinforcement Learning Framework для агентов
Self-reward система, policy optimization, adaptive behavior
"""

import os
import asyncio
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict
import random

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')


@dataclass
class Action:
    """Действие агента"""
    action_id: str
    action_type: str
    parameters: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Reward:
    """Награда за действие"""
    reward_id: str
    action_id: str
    reward_value: float  # -1.0 до 1.0
    reward_type: str  # "success", "failure", "quality", "efficiency"
    feedback: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Policy:
    """Политика агента"""
    policy_id: str
    agent_name: str
    state_action_values: Dict[str, Dict[str, float]]  # state -> action -> value
    learning_rate: float = 0.1
    discount_factor: float = 0.9
    exploration_rate: float = 0.1
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ReinforcementLearning:
    """Фреймворк Reinforcement Learning для агентов"""
    
    def __init__(self, agent_name: str = "Victoria"):
        self.agent_name = agent_name
        self.policies: Dict[str, Policy] = {}
        self.action_history: List[Action] = []
        self.reward_history: List[Reward] = []
        self.episodes: List[Dict[str, Any]] = []
        
        # Q-learning параметры
        self.learning_rate = float(os.getenv("RL_LEARNING_RATE", "0.1"))
        self.discount_factor = float(os.getenv("RL_DISCOUNT_FACTOR", "0.9"))
        self.exploration_rate = float(os.getenv("RL_EXPLORATION_RATE", "0.1"))
    
    def _get_state_key(self, context: Dict[str, Any]) -> str:
        """Преобразовать контекст в ключ состояния"""
        # Упрощенное представление состояния
        task_type = context.get("task_type", "general")
        complexity = context.get("complexity", "medium")
        return f"{task_type}:{complexity}"
    
    def _get_policy(self, state: str) -> Policy:
        """Получить или создать политику для состояния"""
        if state not in self.policies:
            self.policies[state] = Policy(
                policy_id=f"policy_{state}_{self.agent_name}",
                agent_name=self.agent_name,
                state_action_values={state: {}},
                learning_rate=self.learning_rate,
                discount_factor=self.discount_factor,
                exploration_rate=self.exploration_rate
            )
        return self.policies[state]
    
    async def select_action(
        self,
        state: str,
        available_actions: List[str],
        context: Dict[str, Any] = None
    ) -> str:
        """
        Выбрать действие используя policy (epsilon-greedy)
        
        Args:
            state: Текущее состояние
            available_actions: Доступные действия
            context: Дополнительный контекст
        
        Returns:
            Выбранное действие
        """
        if not available_actions:
            return None
        
        policy = self._get_policy(state)
        
        # Epsilon-greedy: exploration vs exploitation
        if random.random() < policy.exploration_rate:
            # Exploration: случайное действие
            action = random.choice(available_actions)
            logger.debug(f"🔍 Exploration: выбрано случайное действие {action}")
        else:
            # Exploitation: лучшее действие по Q-values
            state_values = policy.state_action_values.get(state, {})
            if state_values:
                # Выбираем действие с максимальным Q-value
                action = max(available_actions, key=lambda a: state_values.get(a, 0.0))
                logger.debug(f"🎯 Exploitation: выбрано лучшее действие {action}")
            else:
                # Если нет данных - случайное
                action = random.choice(available_actions)
                logger.debug(f"❓ Нет данных, случайное действие {action}")
        
        return action
    
    async def record_action(
        self,
        action_type: str,
        parameters: Dict[str, Any],
        state: str
    ) -> Action:
        """Записать выполненное действие"""
        action_id = f"action_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        action = Action(
            action_id=action_id,
            action_type=action_type,
            parameters=parameters
        )
        
        self.action_history.append(action)
        return action
    
    async def assign_reward(
        self,
        action_id: str,
        reward_value: float,
        reward_type: str = "success",
        feedback: Optional[str] = None
    ) -> Reward:
        """
        Назначить награду за действие
        
        Args:
            action_id: ID действия
            reward_value: Значение награды (-1.0 до 1.0)
            reward_type: Тип награды
            feedback: Обратная связь
        
        Returns:
            Reward объект
        """
        reward_id = f"reward_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        reward = Reward(
            reward_id=reward_id,
            action_id=action_id,
            reward_value=reward_value,
            reward_type=reward_type,
            feedback=feedback
        )
        
        self.reward_history.append(reward)
        
        # Обновляем Q-values
        await self._update_q_values(action_id, reward_value)
        
        logger.info(f"🎁 Награда назначена: {reward_value:.2f} ({reward_type})")
        
        return reward
    
    async def _update_q_values(self, action_id: str, reward: float):
        """Обновить Q-values используя Q-learning"""
        # Находим действие
        action = next((a for a in self.action_history if a.action_id == action_id), None)
        if not action:
            return
        
        # Находим состояние (упрощенно - из последнего действия)
        if len(self.action_history) < 2:
            return
        
        prev_action = self.action_history[-2]
        state = self._get_state_key(prev_action.parameters)
        
        policy = self._get_policy(state)
        action_type = action.action_type
        
        # Q-learning update: Q(s,a) = Q(s,a) + α[r + γ*max(Q(s',a')) - Q(s,a)]
        current_q = policy.state_action_values.get(state, {}).get(action_type, 0.0)
        
        # Максимальное Q-value для следующего состояния (упрощенно)
        next_state_values = policy.state_action_values.get(state, {})
        max_next_q = max(next_state_values.values()) if next_state_values else 0.0
        
        # Обновляем Q-value
        new_q = current_q + policy.learning_rate * (
            reward + policy.discount_factor * max_next_q - current_q
        )
        
        if state not in policy.state_action_values:
            policy.state_action_values[state] = {}
        policy.state_action_values[state][action_type] = new_q
        
        policy.updated_at = datetime.now(timezone.utc)
        
        logger.debug(f"📈 Q-value обновлен: {state}:{action_type} = {new_q:.3f}")
    
    async def self_reward(
        self,
        action_id: str,
        result: Any,
        expected_result: Optional[Any] = None
    ) -> Reward:
        """
        Самонаграждение на основе результата
        
        Args:
            action_id: ID действия
            result: Фактический результат
            expected_result: Ожидаемый результат (если есть)
        
        Returns:
            Reward объект
        """
        # Простая эвристика для самонаграждения
        reward_value = 0.5  # Базовое значение
        
        # Если результат успешный
        if result and not isinstance(result, Exception):
            reward_value = 0.8
        
        # Если есть ожидаемый результат - сравниваем
        if expected_result:
            if result == expected_result:
                reward_value = 1.0
            else:
                reward_value = 0.3
        
        # Если ошибка
        if isinstance(result, Exception):
            reward_value = -0.5
        
        return await self.assign_reward(
            action_id=action_id,
            reward_value=reward_value,
            reward_type="self_reward"
        )
    
    async def optimize_policy(self, state: str) -> Dict[str, Any]:
        """
        Оптимизировать политику для состояния
        
        Args:
            state: Состояние
        
        Returns:
            Статистика оптимизации
        """
        policy = self._get_policy(state)
        state_values = policy.state_action_values.get(state, {})
        
        if not state_values:
            return {"message": "Нет данных для оптимизации"}
        
        # Находим лучшее действие
        best_action = max(state_values.items(), key=lambda x: x[1])
        
        # Анализ распределения значений
        avg_value = sum(state_values.values()) / len(state_values)
        max_value = max(state_values.values())
        min_value = min(state_values.values())
        
        # Рекомендации
        recommendations = []
        if max_value - min_value < 0.1:
            recommendations.append("Низкая дифференциация - требуется больше exploration")
        if policy.exploration_rate > 0.2:
            recommendations.append("Высокий exploration rate - можно уменьшить")
        
        return {
            "state": state,
            "best_action": best_action[0],
            "best_value": best_action[1],
            "average_value": avg_value,
            "value_range": max_value - min_value,
            "total_actions": len(state_values),
            "recommendations": recommendations
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику обучения"""
        total_actions = len(self.action_history)
        total_rewards = len(self.reward_history)
        
        if total_rewards == 0:
            return {"message": "Нет данных для статистики"}
        
        avg_reward = sum(r.reward_value for r in self.reward_history) / total_rewards
        positive_rewards = sum(1 for r in self.reward_history if r.reward_value > 0)
        success_rate = positive_rewards / total_rewards if total_rewards > 0 else 0
        
        return {
            "total_actions": total_actions,
            "total_rewards": total_rewards,
            "average_reward": avg_reward,
            "success_rate": success_rate,
            "policies_count": len(self.policies),
            "exploration_rate": self.exploration_rate
        }

# Глобальные экземпляры по агентам
_rl_instances: Dict[str, ReinforcementLearning] = {}

def get_rl(agent_name: str = "Victoria") -> ReinforcementLearning:
    """Получить экземпляр RL для агента"""
    if agent_name not in _rl_instances:
        _rl_instances[agent_name] = ReinforcementLearning(agent_name=agent_name)
    return _rl_instances[agent_name]
