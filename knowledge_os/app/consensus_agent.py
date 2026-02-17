"""
Consensus Agent - Механизм консенсуса для мультиагентных систем
Основано на CONSENSAGENT (2025) и Aegean (2025)
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import Counter
from ai_core import FactExtractor, ContextSwapper

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')


@dataclass
class AgentResponse:
    """Ответ агента"""
    agent_name: str
    response: str
    confidence: float = 0.5
    reasoning: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ConsensusResult:
    """Результат консенсуса"""
    final_answer: str
    consensus_score: float
    agreement_level: float
    agent_responses: List[AgentResponse]
    sycophancy_detected: bool = False
    iterations: int = 0


class ConsensusAgent:
    """
    Consensus Agent - достижение консенсуса между агентами
    
    Компоненты:
    1. Sycophancy mitigation (CONSENSAGENT)
    2. Quorum convergence (Aegean-style)
    3. Dynamic prompt refinement
    """
    
    def __init__(
        self,
        model_name: str = "phi3.5:3.8b",
        ollama_url: str = OLLAMA_URL,
        quorum_threshold: float = 0.67,  # 67% для консенсуса
        max_iterations: int = 5
    ):
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.quorum_threshold = quorum_threshold
        self.max_iterations = max_iterations
    
    async def reach_consensus(
        self,
        agents: List[str],
        question: str,
        initial_context: Optional[Dict] = None
    ) -> ConsensusResult:
        """
        Достичь консенсуса между агентами
        
        Args:
            agents: Список агентов
            question: Вопрос для консенсуса
            initial_context: Начальный контекст
        
        Returns:
            Результат консенсуса
        """
        logger.info(f"🤝 Начинаю консенсус между {len(agents)} агентами: {question[:80]}")
        
        agent_responses: List[AgentResponse] = []
        iterations = 0
        previous_responses: List[List[AgentResponse]] = []
        
        while iterations < self.max_iterations:
            iterations += 1
            logger.info(f"🔄 Итерация консенсуса {iterations}/{self.max_iterations}")
            
            # 1. Генерируем ответы агентов
            current_responses = await self._collect_responses(
                agents, question, initial_context, previous_responses
            )
            
            agent_responses = current_responses
            previous_responses.append(current_responses)
            
            # 2. Проверяем sycophancy
            sycophancy_detected = self._detect_sycophancy(current_responses)
            
            # 3. Проверяем quorum convergence (Aegean-style)
            consensus_reached, consensus_answer = self._check_quorum_convergence(
                current_responses
            )
            
            if consensus_reached:
                logger.info(f"✅ Консенсус достигнут на итерации {iterations}")
                break
            
            # 4. Если нет консенсуса и есть sycophancy - уточняем промпты
            if sycophancy_detected and iterations < self.max_iterations:
                logger.info("⚠️ Обнаружена sycophancy, уточняю промпты...")
                # Динамическое уточнение промптов (CONSENSAGENT)
                initial_context = await self._refine_prompts(
                    question, current_responses, initial_context
                )
        
        # 5. Формируем финальный результат
        final_answer, consensus_score = self._synthesize_final_answer(agent_responses)
        agreement_level = self._calculate_agreement_level(agent_responses)
        
        return ConsensusResult(
            final_answer=final_answer,
            consensus_score=consensus_score,
            agreement_level=agreement_level,
            agent_responses=agent_responses,
            sycophancy_detected=sycophancy_detected,
            iterations=iterations
        )
    
    async def _collect_responses(
        self,
        agents: List[str],
        question: str,
        context: Optional[Dict],
        previous_responses: List[List[AgentResponse]]
    ) -> List[AgentResponse]:
        """Собрать ответы от агентов"""
        # [SINGULARITY 14.2] Pre-process history with FactExtractor if needed
        if previous_responses and sum(len(r.response) for round in previous_responses for r in round) > 3000:
            logger.info("✂️ [CONSENSUS] History too long, extracting facts for next round...")
            extractor = FactExtractor()
            all_prev = "\n".join([f"{r.agent_name}: {r.response}" for round in previous_responses for r in round])
            summary = await extractor.extract_facts(all_prev, context_description="Consensus history")
            # Заменяем историю на суммаризированную (упрощенно для промпта)
            # В реальной логике можно было бы создать фиктивный раунд с summary
            context = context or {}
            context["history_summary"] = summary

        # Строим промпт с учетом предыдущих ответов (для избежания sycophancy)
        base_prompt = self._build_consensus_prompt(question, context, previous_responses)
        
        # Генерируем ответы параллельно
        tasks = []
        for agent in agents:
            # Персонализируем промпт для каждого агента
            agent_prompt = f"{base_prompt}\n\nТЫ - {agent}. Дай СВОЕ независимое мнение, не повторяй других."
            task = self._generate_agent_response(agent, agent_prompt)
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Формируем AgentResponse объекты
        agent_responses = []
        for agent, response in zip(agents, responses):
            if isinstance(response, Exception):
                logger.warning(f"⚠️ Ошибка ответа от {agent}: {response}")
                continue
            
            agent_response = AgentResponse(
                agent_name=agent,
                response=response.get("response", ""),
                confidence=response.get("confidence", 0.5),
                reasoning=response.get("reasoning")
            )
            agent_responses.append(agent_response)
        
        return agent_responses
    
    def _detect_sycophancy(self, responses: List[AgentResponse]) -> bool:
        """Обнаружить sycophancy (поддакивание)"""
        if len(responses) < 2:
            return False
        
        # Проверяем на слишком похожие ответы
        response_texts = [r.response.lower().strip() for r in responses]
        
        # Простая проверка: если ответы слишком похожи (>80% совпадение)
        similarities = []
        for i, resp1 in enumerate(response_texts):
            for j, resp2 in enumerate(response_texts[i+1:], i+1):
                similarity = self._calculate_similarity(resp1, resp2)
                similarities.append(similarity)
        
        if similarities:
            avg_similarity = sum(similarities) / len(similarities)
            # Если средняя похожесть > 0.8 - возможна sycophancy
            return avg_similarity > 0.8
        
        return False
    
    def _check_quorum_convergence(
        self,
        responses: List[AgentResponse]
    ) -> Tuple[bool, Optional[str]]:
        """Проверить quorum convergence (Aegean-style)"""
        if not responses:
            return False, None
        
        # Группируем похожие ответы
        answer_groups = {}
        for resp in responses:
            # Нормализуем ответ для группировки
            normalized = self._normalize_answer(resp.response)
            
            if normalized not in answer_groups:
                answer_groups[normalized] = []
            answer_groups[normalized].append(resp)
        
        # Находим группу с большинством
        max_group_size = max(len(group) for group in answer_groups.values())
        total_agents = len(responses)
        
        # Проверяем quorum threshold
        if max_group_size / total_agents >= self.quorum_threshold:
            # Находим ответ группы большинства
            for normalized, group in answer_groups.items():
                if len(group) == max_group_size:
                    # Берем ответ с наибольшей уверенностью
                    best_response = max(group, key=lambda r: r.confidence)
                    return True, best_response.response
        
        return False, None
    
    async def _refine_prompts(
        self,
        question: str,
        responses: List[AgentResponse],
        context: Optional[Dict]
    ) -> Dict:
        """Уточнить промпты на основе взаимодействий (CONSENSAGENT)"""
        # Анализируем ответы и генерируем уточнения
        prompt = f"""На основе следующих ответов агентов, создай уточненный промпт для избежания группового мышления:

ВОПРОС: {question}

ОТВЕТЫ АГЕНТОВ:
"""
        for i, resp in enumerate(responses, 1):
            prompt += f"\n{i}. {resp.agent_name}: {resp.response[:200]}\n"
        
        prompt += """
Создай уточненный промпт, который:
1. Поощряет независимое мышление
2. Требует критического анализа
3. Избегает простого согласия с другими

УТОЧНЕННЫЙ ПРОМПТ:"""
        
        refined = await self._generate_response(prompt)
        
        # Обновляем контекст
        if context is None:
            context = {}
        
        context["refined_prompt"] = refined
        context["anti_sycophancy"] = True
        
        return context
    
    def _synthesize_final_answer(self, responses: List[AgentResponse]) -> Tuple[str, float]:
        """Синтезировать финальный ответ"""
        if not responses:
            return "Нет ответов", 0.0
        
        # Группируем по похожести
        answer_groups = {}
        for resp in responses:
            normalized = self._normalize_answer(resp.response)
            if normalized not in answer_groups:
                answer_groups[normalized] = []
            answer_groups[normalized].append(resp)
        
        # Выбираем группу большинства
        largest_group = max(answer_groups.values(), key=len)
        
        # Берем ответ с наибольшей уверенностью
        best_response = max(largest_group, key=lambda r: r.confidence)
        
        # Рассчитываем consensus score
        consensus_score = len(largest_group) / len(responses)
        
        return best_response.response, consensus_score
    
    def _calculate_agreement_level(self, responses: List[AgentResponse]) -> float:
        """Рассчитать уровень согласия"""
        if len(responses) < 2:
            return 1.0
        
        # Группируем ответы
        answer_groups = {}
        for resp in responses:
            normalized = self._normalize_answer(resp.response)
            if normalized not in answer_groups:
                answer_groups[normalized] = 0
            answer_groups[normalized] += 1
        
        # Максимальная группа
        max_group_size = max(answer_groups.values())
        agreement = max_group_size / len(responses)
        
        return agreement
    
    def _build_consensus_prompt(
        self,
        question: str,
        context: Optional[Dict],
        previous_responses: List[List[AgentResponse]]
    ) -> str:
        """Построить промпт для консенсуса"""
        # [SINGULARITY 14.2] Use FactExtractor for previous responses to save context
        history_text = ""
        if previous_responses:
            history_text = "ПРЕДЫДУЩИЕ ОТВЕТЫ (для справки, НЕ повторяй их):\n"
            # Собираем все ответы в один текст
            all_prev = ""
            for round_responses in previous_responses:
                for resp in round_responses:
                    all_prev += f"- {resp.agent_name}: {resp.response}\n"
            
            # Если история слишком большая, сжимаем её
            if len(all_prev) > 2000:
                import asyncio
                extractor = FactExtractor()
                # В синхронном методе используем loop.run_until_complete или просто обрезаем, 
                # но лучше сделать метод асинхронным или использовать пре-обработку.
                # Для простоты здесь используем обрезку + пометку, так как _build_consensus_prompt вызывается из асинхронного _collect_responses
                history_text += "[СЖАТО] " + all_prev[:1000] + "..."
            else:
                history_text += all_prev

        prompt = f"""Ты участвуешь в достижении консенсуса по следующему вопросу:

ВОПРОС: {question}

"""
        
        if context:
            prompt += f"КОНТЕКСТ: {context}\n\n"
        
        if history_text:
            prompt += history_text + "\n"
        
        prompt += """ВАЖНО:
- Дай СВОЕ независимое мнение
- Критически анализируй вопрос
- НЕ просто соглашайся с другими
- Обоснуй свой ответ

ТВОЙ ОТВЕТ:"""
        
        return prompt
    
    def _normalize_answer(self, answer: str) -> str:
        """Нормализовать ответ для сравнения"""
        # Простая нормализация: lowercase, убрать пунктуацию, первые 100 символов
        normalized = answer.lower().strip()
        # Убираем пунктуацию для сравнения
        import re
        normalized = re.sub(r'[^\w\s]', '', normalized)
        return normalized[:100]
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Рассчитать похожесть двух текстов"""
        # Простая метрика: Jaccard similarity
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _confidence_from_response_length(response: str) -> float:
        """
        Оценка уверенности по длине ответа (эвристика).
        Пустой/очень короткий ответ — низкая уверенность, развёрнутый — выше.
        """
        if not response or not response.strip():
            return 0.0
        n = len(response.strip())
        if n < 20:
            return 0.25
        if n < 100:
            return 0.4
        if n < 300:
            return 0.55
        if n < 600:
            return 0.7
        if n < 1200:
            return 0.82
        return min(0.95, 0.82 + (n - 1200) / 8000)
    
    async def _generate_agent_response(self, agent_name: str, prompt: str) -> Dict:
        """Генерировать ответ агента"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 1024
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json().get('response', '')
                    confidence = self._confidence_from_response_length(result)
                    return {
                        "response": result,
                        "confidence": confidence,
                        "reasoning": None
                    }
                else:
                    return {"response": "", "confidence": 0.0}
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            return {"response": "", "confidence": 0.0}
    
    async def _generate_response(self, prompt: str) -> str:
        """Генерировать ответ через модель"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                
                if response.status_code == 200:
                    return response.json().get('response', '')
                else:
                    return ""
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return ""


async def main():
    """Пример использования"""
    consensus = ConsensusAgent(quorum_threshold=0.67)
    try:
        from app.expert_services import get_all_expert_names
        agents = get_all_expert_names(max_count=10)
    except ImportError:
        agents = ["Виктория", "Вероника", "Игорь", "Сергей", "Дмитрий"]
    
    result = await consensus.reach_consensus(
        agents=agents,
        question="Какой лучший подход к оптимизации производительности базы данных?"
    )
    
    print("Результат консенсуса:")
    print(f"  Финальный ответ: {result.final_answer[:200]}...")
    print(f"  Consensus score: {result.consensus_score:.2f}")
    print(f"  Agreement level: {result.agreement_level:.2f}")
    print(f"  Sycophancy detected: {result.sycophancy_detected}")
    print(f"  Iterations: {result.iterations}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
