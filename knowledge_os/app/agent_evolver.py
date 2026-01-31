#!/usr/bin/env python3
"""
AgentEvolver - механизмы самоэволюции агентов.
Self-Questioning, Self-Navigating, Self-Attributing.

Источник: AgentEvolver research (2025-2026)
Эффект: +50-70% на эффективности обучения и исследовании
"""
import asyncio
import logging
import random
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Question:
    """Вопрос для самоисследования"""
    question: str
    category: str  # curiosity, clarification, exploration
    priority: int
    created_at: str


@dataclass
class NavigationState:
    """Состояние навигации в пространстве задач"""
    current_position: str
    explored_paths: List[str]
    promising_directions: List[str]
    dead_ends: List[str]
    confidence: float


class AgentEvolver:
    """
    Механизмы самоэволюции:
    1. Self-Questioning - генерация вопросов для любопытства
    2. Self-Navigating - улучшенное исследование пространства задач
    3. Self-Attributing - улучшенная эффективность выборки
    """
    
    def __init__(self, agent_name: str = "Victoria"):
        self.agent_name = agent_name
        self.questions: List[Question] = []
        self.navigation_state = NavigationState(
            current_position="start",
            explored_paths=[],
            promising_directions=[],
            dead_ends=[],
            confidence=0.5
        )
        self.attribution_history: List[Dict] = []
    
    async def self_question(self, context: str, task: str) -> List[Question]:
        """
        Self-Questioning - генерация вопросов для любопытства
        
        Генерирует вопросы, которые помогают агенту лучше понять задачу
        и найти более эффективные решения.
        
        Args:
            context: Контекст задачи
            task: Описание задачи
        
        Returns:
            Список вопросов для исследования
        """
        logger.info(f"❓ [{self.agent_name}] Генерирую вопросы для исследования...")
        
        questions = []
        
        # Категория: Curiosity (любопытство)
        curiosity_questions = [
            f"Что произойдет, если попробовать другой подход к '{task}'?",
            f"Какие альтернативные методы можно использовать для '{task}'?",
            f"Что я не понимаю в '{context}'?",
            f"Какие скрытые зависимости есть в '{task}'?"
        ]
        
        # Категория: Clarification (уточнение)
        clarification_questions = [
            f"Что именно означает '{task}'?",
            f"Какие критерии успеха для '{task}'?",
            f"Какие ограничения нужно учесть в '{task}'?",
            f"Что является приоритетным в '{task}'?"
        ]
        
        # Категория: Exploration (исследование)
        exploration_questions = [
            f"Как можно разбить '{task}' на подзадачи?",
            f"Какие знания мне нужны для '{task}'?",
            f"С кем можно сотрудничать для решения '{task}'?",
            f"Какие инструменты лучше использовать для '{task}'?"
        ]
        
        # Выбираем релевантные вопросы
        all_questions = [
            (q, "curiosity", 3) for q in curiosity_questions[:2]
        ] + [
            (q, "clarification", 2) for q in clarification_questions[:2]
        ] + [
            (q, "exploration", 1) for q in exploration_questions[:2]
        ]
        
        for question_text, category, priority in all_questions:
            question = Question(
                question=question_text,
                category=category,
                priority=priority,
                created_at=datetime.now(timezone.utc).isoformat()
            )
            questions.append(question)
            self.questions.append(question)
        
        logger.info(f"✅ [{self.agent_name}] Сгенерировано {len(questions)} вопросов")
        
        return questions
    
    async def self_navigate(
        self,
        task_space: Dict[str, Any],
        current_solution: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Self-Navigating - улучшенное исследование пространства задач
        
        Помогает агенту эффективнее исследовать пространство решений,
        избегая тупиков и фокусируясь на перспективных направлениях.
        
        Args:
            task_space: Пространство задач
            current_solution: Текущее решение (если есть)
        
        Returns:
            План навигации с приоритетными направлениями
        """
        logger.info(f"🧭 [{self.agent_name}] Планирую навигацию в пространстве задач...")
        
        # Анализируем текущее положение
        if current_solution:
            current_path = current_solution.get('path', 'unknown')
            self.navigation_state.current_position = current_path
            
            # Оцениваем текущее решение
            quality = current_solution.get('quality', 0.5)
            if quality < 0.3:
                # Тупик
                if current_path not in self.navigation_state.dead_ends:
                    self.navigation_state.dead_ends.append(current_path)
                    logger.info(f"   ⚠️ Обнаружен тупик: {current_path}")
            elif quality > 0.7:
                # Перспективное направление
                if current_path not in self.navigation_state.promising_directions:
                    self.navigation_state.promising_directions.append(current_path)
                    logger.info(f"   ✅ Перспективное направление: {current_path}")
        
        # Определяем следующие шаги
        next_steps = []
        
        # Приоритет 1: Продолжить перспективные направления
        for promising_path in self.navigation_state.promising_directions[-3:]:
            next_steps.append({
                'path': promising_path,
                'priority': 'high',
                'reason': 'Продолжить перспективное направление'
            })
        
        # Приоритет 2: Исследовать новые направления (избегая тупиков)
        available_paths = task_space.get('paths', [])
        unexplored = [
            p for p in available_paths
            if p not in self.navigation_state.explored_paths
            and p not in self.navigation_state.dead_ends
        ]
        
        for new_path in unexplored[:2]:
            next_steps.append({
                'path': new_path,
                'priority': 'medium',
                'reason': 'Исследовать новое направление'
            })
        
        # Обновляем confidence на основе опыта
        explored_count = len(self.navigation_state.explored_paths)
        promising_count = len(self.navigation_state.promising_directions)
        
        if explored_count > 0:
            self.navigation_state.confidence = min(
                promising_count / explored_count,
                0.95
            )
        
        navigation_plan = {
            'current_position': self.navigation_state.current_position,
            'next_steps': next_steps,
            'confidence': self.navigation_state.confidence,
            'promising_directions': self.navigation_state.promising_directions[-5:],
            'dead_ends': self.navigation_state.dead_ends[-5:]
        }
        
        logger.info(f"✅ [{self.agent_name}] План навигации создан: {len(next_steps)} следующих шагов")
        
        return navigation_plan
    
    async def self_attributing(
        self,
        task_result: Dict[str, Any],
        actions_taken: List[Dict]
    ) -> Dict[str, Any]:
        """
        Self-Attributing - улучшенная эффективность выборки
        
        Помогает агенту понять, какие действия привели к успеху/неудаче,
        улучшая эффективность будущих выборок.
        
        Args:
            task_result: Результат задачи
            actions_taken: Действия, которые были выполнены
        
        Returns:
            Атрибуция успеха/неудачи к конкретным действиям
        """
        logger.info(f"🎯 [{self.agent_name}] Анализирую атрибуцию успеха...")
        
        success = task_result.get('success', False)
        quality = task_result.get('quality', 0.5)
        
        # Анализируем каждое действие
        action_attributions = []
        for action in actions_taken:
            action_type = action.get('type', 'unknown')
            action_result = action.get('result', 'neutral')
            
            # Определяем вклад действия
            if success and quality > 0.7:
                # Успешная задача - ищем действия, которые помогли
                contribution = "positive" if action_result in ['success', 'partial'] else "neutral"
            elif not success or quality < 0.3:
                # Неудачная задача - ищем действия, которые навредили
                contribution = "negative" if action_result == 'failure' else "neutral"
            else:
                contribution = "neutral"
            
            action_attributions.append({
                'action_type': action_type,
                'contribution': contribution,
                'quality_impact': quality if contribution == "positive" else (1 - quality) if contribution == "negative" else 0.5
            })
        
        # Сохраняем в историю
        attribution_record = {
            'task_id': task_result.get('task_id', 'unknown'),
            'success': success,
            'quality': quality,
            'attributions': action_attributions,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.attribution_history.append(attribution_record)
        
        # Извлекаем уроки
        positive_actions = [
            a['action_type'] for a in action_attributions
            if a['contribution'] == 'positive'
        ]
        negative_actions = [
            a['action_type'] for a in action_attributions
            if a['contribution'] == 'negative'
        ]
        
        lessons = {
            'positive_patterns': list(set(positive_actions)),
            'negative_patterns': list(set(negative_actions)),
            'recommendations': []
        }
        
        if positive_actions:
            lessons['recommendations'].append(
                f"Повторить действия: {', '.join(lessons['positive_patterns'][:3])}"
            )
        if negative_actions:
            lessons['recommendations'].append(
                f"Избегать действий: {', '.join(lessons['negative_patterns'][:3])}"
            )
        
        logger.info(f"✅ [{self.agent_name}] Атрибуция завершена: {len(positive_actions)} позитивных, {len(negative_actions)} негативных паттернов")
        
        return {
            'attributions': action_attributions,
            'lessons': lessons,
            'overall_quality': quality
        }
    
    def get_evolution_state(self) -> Dict:
        """Получить текущее состояние эволюции"""
        return {
            'questions_count': len(self.questions),
            'recent_questions': [
                {
                    'question': q.question,
                    'category': q.category,
                    'priority': q.priority
                }
                for q in self.questions[-5:]
            ],
            'navigation': asdict(self.navigation_state),
            'attribution_history_count': len(self.attribution_history)
        }


# Пример использования
async def main():
    evolver = AgentEvolver("Victoria")
    
    # Self-Questioning
    questions = await evolver.self_question(
        context="Разработка новой функции",
        task="Создать систему метакогнитивного обучения"
    )
    print(f"Вопросы: {len(questions)}")
    
    # Self-Navigating
    task_space = {
        'paths': ['approach1', 'approach2', 'approach3', 'approach4']
    }
    navigation = await evolver.self_navigate(task_space)
    print(f"Навигация: {navigation['next_steps']}")
    
    # Self-Attributing
    task_result = {
        'success': True,
        'quality': 0.85,
        'task_id': 'task-001'
    }
    actions = [
        {'type': 'planning', 'result': 'success'},
        {'type': 'execution', 'result': 'success'},
        {'type': 'validation', 'result': 'partial'}
    ]
    attribution = await evolver.self_attributing(task_result, actions)
    print(f"Атрибуция: {attribution['lessons']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
