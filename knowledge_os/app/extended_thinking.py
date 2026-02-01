"""
Extended Thinking Mode - Расширенное рассуждение для сложных задач
Основано на практике Anthropic Claude Extended Thinking
"""

import os
import asyncio
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Используем ТОЛЬКО MLX API Server (порт 11435)
# Используется только MLX API Server
MLX_URL = os.getenv('MLX_API_URL', 'http://localhost:11435')
# Всегда используем MLX
DEFAULT_LLM_URL = MLX_URL

# Кэш для списка моделей (чтобы не делать частые запросы к /api/tags)
_models_cache = {"data": None, "timestamp": 0}
_MODELS_CACHE_TTL = 120  # 2 минуты кэш для списка моделей


@dataclass
class ThinkingStep:
    """Один шаг рассуждения"""
    step_number: int
    thought: str
    conclusion: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class ExtendedThinkingResult:
    """Результат расширенного рассуждения"""
    final_answer: str
    thinking_steps: List[ThinkingStep]
    total_tokens_used: int
    thinking_time_seconds: float
    confidence: float


class ExtendedThinkingEngine:
    """
    Extended Thinking Mode - внутреннее рассуждение перед ответом
    
    Модель сначала рассуждает пошагово (внутренне),
    затем формирует финальный ответ на основе рассуждений.
    """
    
    def __init__(
        self,
        model_name: str = "deepseek-r1-distill-llama:70b",
        thinking_budget: int = 10000,  # Токены для рассуждения
        max_steps: int = 10,
        use_intelligent_routing: bool = True  # Использовать интеллектуальный роутинг
    ):
        self.model_name = model_name  # Базовая модель (fallback)
        self.use_intelligent_routing = use_intelligent_routing
        # Используем только MLX
        self.llm_url = DEFAULT_LLM_URL
        self.thinking_budget = thinking_budget
        self.max_steps = max_steps
        
        # Инициализируем интеллектуальный роутер если включен
        if self.use_intelligent_routing:
            try:
                # Пробуем разные варианты импорта
                try:
                    from app.intelligent_model_router import get_intelligent_router
                except ImportError:
                    try:
                        from intelligent_model_router import get_intelligent_router
                    except ImportError:
                        import sys
                        import os
                        router_path = os.path.join(os.path.dirname(__file__), 'intelligent_model_router.py')
                        if os.path.exists(router_path):
                            sys.path.insert(0, os.path.dirname(__file__))
                            from intelligent_model_router import get_intelligent_router
                        else:
                            raise ImportError("intelligent_model_router.py not found")
                
                self.model_router = get_intelligent_router()
                logger.info(f"✅ ExtendedThinkingEngine инициализирован с интеллектуальным роутингом: URL={self.llm_url}, базовая модель={self.model_name}")
            except (ImportError, Exception) as e:
                logger.warning(f"⚠️ Intelligent router недоступен ({e}), используем базовую модель")
                self.use_intelligent_routing = False
                self.model_router = None
        else:
            self.model_router = None
            logger.info(f"✅ ExtendedThinkingEngine инициализирован: URL={self.llm_url}, модель={self.model_name}")
    
    async def think(
        self,
        prompt: str,
        context: Optional[str] = None,
        use_iterative: bool = True,
        category: Optional[str] = None
    ) -> ExtendedThinkingResult:
        """
        Расширенное рассуждение для сложной задачи
        
        Args:
            prompt: Запрос пользователя
            context: Дополнительный контекст
            use_iterative: Использовать ли итеративное рассуждение
        
        Returns:
            Результат с финальным ответом и шагами рассуждения
        """
        start_time = datetime.now(timezone.utc)
        
        if use_iterative:
            return await self._iterative_thinking(prompt, context, category)
        else:
            return await self._single_pass_thinking(prompt, context, category)
    
    async def _get_available_models(self) -> List[str]:
        """
        Получает список доступных моделей из MLX API Server с кэшированием
        """
        global _models_cache
        import httpx
        import os
        import time
        
        current_time = time.time()
        
        # Возвращаем кэшированный результат если еще валиден
        if _models_cache["data"] and (current_time - _models_cache["timestamp"]) < _MODELS_CACHE_TTL:
            logger.debug(f"📋 Используем кэшированный список моделей ({len(_models_cache['data'])} моделей)")
            return _models_cache["data"]
        
        try:
            mlx_url = os.getenv('MLX_API_URL', 'http://localhost:11435')
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{mlx_url}/api/tags")
                if response.status_code == 200:
                    models_data = response.json()
                    models = models_data.get("models", [])
                    available = [m.get("name") for m in models if m.get("exists", True)]
                    logger.debug(f"📋 Доступно моделей в MLX: {len(available)}")
                    
                    # Обновляем кэш
                    _models_cache = {"data": available, "timestamp": current_time}
                    return available
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить список моделей: {e}")
            # Если есть кэш, используем его даже если истек
            if _models_cache["data"]:
                logger.debug("📋 Используем устаревший кэш из-за ошибки")
                return _models_cache["data"]
        
        # Fallback: возвращаем все известные модели из PLAN.md
        # ВАЖНО: tinyllama исключена - используется только для внутренней коммуникации агентов
        fallback_models = [
            "command-r-plus:104b",
            "deepseek-r1-distill-llama:70b",
            "llama3.3:70b",
            "qwen2.5-coder:32b",
            "phi3.5:3.8b",
            "phi3:mini-4k",
            "qwen2.5:3b"
        ]
    
    async def _iterative_thinking(
        self,
        prompt: str,
        context: Optional[str] = None,
        category: Optional[str] = None
    ) -> ExtendedThinkingResult:
        """Итеративное рассуждение - несколько шагов"""
        thinking_steps = []
        current_understanding = ""
        
        # Начальный промпт для рассуждения
        thinking_prompt = self._build_thinking_prompt(prompt, context, step=1)
        
        for step_num in range(1, self.max_steps + 1):
            # Генерируем шаг рассуждения
            step_thought = await self._generate_thinking_step(
                thinking_prompt,
                step_num,
                current_understanding,
                category
            )
            
            # Извлекаем мысль и вывод
            thought, conclusion = self._parse_thinking_step(step_thought)
            
            step = ThinkingStep(
                step_number=step_num,
                thought=thought,
                conclusion=conclusion
            )
            thinking_steps.append(step)
            
            # Обновляем понимание
            current_understanding += f"\nШаг {step_num}: {thought}\n"
            if conclusion:
                current_understanding += f"Вывод: {conclusion}\n"
            
            # Проверяем, можно ли завершить
            if conclusion and self._is_final_conclusion(conclusion):
                break
            
            # Обновляем промпт для следующего шага
            thinking_prompt = self._build_thinking_prompt(
                prompt, context, step=step_num + 1, previous_steps=current_understanding
            )
        
        # Формируем финальный ответ на основе всех рассуждений
        final_answer = await self._synthesize_final_answer(prompt, thinking_steps, category)
        
        elapsed = (datetime.now(timezone.utc) - datetime.now(timezone.utc)).total_seconds()
        
        return ExtendedThinkingResult(
            final_answer=final_answer,
            thinking_steps=thinking_steps,
            total_tokens_used=sum(len(s.thought) for s in thinking_steps) + len(final_answer),
            thinking_time_seconds=elapsed,
            confidence=self._calculate_confidence(thinking_steps)
        )
    
    async def _single_pass_thinking(
        self,
        prompt: str,
        context: Optional[str] = None,
        category: Optional[str] = None
    ) -> ExtendedThinkingResult:
        """Одношаговое рассуждение - все сразу"""
        thinking_prompt = self._build_thinking_prompt(prompt, context, step=1)
        
        # Генерируем полное рассуждение
        full_thinking = await self._generate_response(thinking_prompt, max_tokens=self.thinking_budget, category=category)
        
        # Извлекаем финальный ответ
        final_answer = await self._extract_final_answer(full_thinking, prompt)
        
        # Разбиваем на шаги (если есть нумерация)
        thinking_steps = self._parse_thinking_into_steps(full_thinking)
        
        elapsed = 0.0  # TODO: реальное время
        
        return ExtendedThinkingResult(
            final_answer=final_answer,
            thinking_steps=thinking_steps,
            total_tokens_used=len(full_thinking) + len(final_answer),
            thinking_time_seconds=elapsed,
            confidence=0.8  # TODO: реальная уверенность
        )
    
    def _build_thinking_prompt(
        self,
        prompt: str,
        context: Optional[str],
        step: int,
        previous_steps: Optional[str] = None
    ) -> str:
        """Построить промпт для рассуждения"""
        thinking_prompt = f"""Ты решаешь сложную задачу. Сначала подумай пошагово, затем дай ответ.

ЗАДАЧА: {prompt}

"""
        
        if context:
            thinking_prompt += f"КОНТЕКСТ:\n{context}\n\n"
        
        if previous_steps:
            thinking_prompt += f"ПРЕДЫДУЩИЕ ШАГИ РАССУЖДЕНИЯ:\n{previous_steps}\n\n"
        
        if step == 1:
            thinking_prompt += """НАЧНИ РАССУЖДЕНИЕ:

Шаг 1. Проанализируй задачу:
"""
        else:
            thinking_prompt += f"""ПРОДОЛЖИ РАССУЖДЕНИЕ:

Шаг {step}. На основе предыдущих шагов, что дальше?
"""
        
        thinking_prompt += """
Формат:
1. Мысль/анализ
2. Вывод (если готов дать финальный ответ, напиши "ФИНАЛЬНЫЙ ОТВЕТ: ...")

ТВОЕ РАССУЖДЕНИЕ:"""
        
        return thinking_prompt
    
    async def _generate_thinking_step(
        self,
        prompt: str,
        step_num: int,
        current_understanding: str,
        category: Optional[str] = None
    ) -> str:
        """Генерировать один шаг рассуждения"""
        return await self._generate_response(prompt, max_tokens=2048, category=category)
    
    def _parse_thinking_step(self, step_text: str) -> tuple[str, Optional[str]]:
        """Парсить шаг рассуждения"""
        lines = step_text.strip().split('\n')
        thought = ""
        conclusion = None
        
        for line in lines:
            if "ФИНАЛЬНЫЙ ОТВЕТ:" in line or "ВЫВОД:" in line:
                conclusion = line.split(":", 1)[1].strip() if ":" in line else line
            else:
                thought += line + "\n"
        
        return thought.strip(), conclusion
    
    def _is_final_conclusion(self, conclusion: str) -> bool:
        """Проверить, является ли вывод финальным"""
        return "ФИНАЛЬНЫЙ ОТВЕТ" in conclusion.upper() or len(conclusion) > 50
    
    async def _synthesize_final_answer(
        self,
        original_prompt: str,
        thinking_steps: List[ThinkingStep],
        category: Optional[str] = None
    ) -> str:
        """Синтезировать финальный ответ на основе всех рассуждений"""
        # Собираем все выводы
        all_conclusions = [s.conclusion for s in thinking_steps if s.conclusion]
        
        if all_conclusions:
            # Берем последний вывод или объединяем
            if len(all_conclusions) == 1:
                return all_conclusions[0]
            else:
                # Объединяем выводы
                synthesis_prompt = f"""На основе следующих шагов рассуждения, сформируй финальный ответ:

ЗАДАЧА: {original_prompt}

ШАГИ РАССУЖДЕНИЯ:
"""
                for i, step in enumerate(thinking_steps, 1):
                    synthesis_prompt += f"\n{i}. {step.thought}\n"
                    if step.conclusion:
                        synthesis_prompt += f"   Вывод: {step.conclusion}\n"
                
                synthesis_prompt += "\nФИНАЛЬНЫЙ ОТВЕТ:"
                
                return await self._generate_response(synthesis_prompt, max_tokens=2048, category=category)
        
        # Fallback: берем последнюю мысль
        if thinking_steps:
            return thinking_steps[-1].thought
        
        return "Не удалось сформировать ответ"
    
    async def _extract_final_answer(self, thinking: str, original_prompt: str) -> str:
        """Извлечь финальный ответ из рассуждения"""
        # Ищем маркеры финального ответа
        markers = ["ФИНАЛЬНЫЙ ОТВЕТ:", "ОТВЕТ:", "ИТОГ:", "ВЫВОД:"]
        
        for marker in markers:
            if marker in thinking:
                parts = thinking.split(marker, 1)
                if len(parts) > 1:
                    return parts[1].strip()
        
        # Если маркеров нет, берем последний абзац
        paragraphs = thinking.split('\n\n')
        if paragraphs:
            return paragraphs[-1].strip()
        
        return thinking.strip()
    
    def _parse_thinking_into_steps(self, thinking: str) -> List[ThinkingStep]:
        """Разобрать рассуждение на шаги"""
        steps = []
        
        # Ищем нумерованные шаги
        import re
        step_pattern = r'(?:Шаг|Step|Шаг)\s*(\d+)[:.]\s*(.+?)(?=(?:Шаг|Step|Шаг)\s*\d+|$)'
        matches = re.finditer(step_pattern, thinking, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            step_num = int(match.group(1))
            thought = match.group(2).strip()
            steps.append(ThinkingStep(step_number=step_num, thought=thought))
        
        # Если не нашли, создаем один шаг
        if not steps:
            steps.append(ThinkingStep(step_number=1, thought=thinking))
        
        return steps
    
    def _calculate_confidence(self, thinking_steps: List[ThinkingStep]) -> float:
        """Рассчитать уверенность на основе шагов рассуждения"""
        if not thinking_steps:
            return 0.0
        
        # Базовая уверенность
        confidence = 0.5
        
        # Бонус за количество шагов (больше шагов = более тщательное рассуждение)
        if len(thinking_steps) >= 3:
            confidence += 0.2
        
        # Бонус за наличие выводов
        conclusions_count = sum(1 for s in thinking_steps if s.conclusion)
        if conclusions_count > 0:
            confidence += 0.2 * min(conclusions_count / len(thinking_steps), 1.0)
        
        # Бонус за финальный вывод
        if thinking_steps[-1].conclusion:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    async def _get_available_models(self) -> List[str]:
        """
        Получает список доступных моделей из MLX API Server с кэшированием
        """
        global _models_cache
        import httpx
        import os
        import time
        from typing import List
        
        current_time = time.time()
        
        # Возвращаем кэшированный результат если еще валиден
        if _models_cache["data"] and (current_time - _models_cache["timestamp"]) < _MODELS_CACHE_TTL:
            logger.debug(f"📋 Используем кэшированный список моделей ({len(_models_cache['data'])} моделей)")
            return _models_cache["data"]
        
        try:
            mlx_url = os.getenv('MLX_API_URL', 'http://localhost:11435')
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{mlx_url}/api/tags")
                if response.status_code == 200:
                    models_data = response.json()
                    models = models_data.get("models", [])
                    available = [m.get("name") for m in models if m.get("exists", True)]
                    logger.debug(f"📋 Доступно моделей в MLX: {len(available)}")
                    
                    # Обновляем кэш
                    _models_cache = {"data": available, "timestamp": current_time}
                    return available
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить список моделей: {e}")
            # Если есть кэш, используем его даже если истек
            if _models_cache["data"]:
                logger.debug("📋 Используем устаревший кэш из-за ошибки")
                return _models_cache["data"]
        
        # Fallback: возвращаем все известные модели из PLAN.md
        return [
            "command-r-plus:104b",
            "deepseek-r1-distill-llama:70b",
            "llama3.3:70b",
            "qwen2.5-coder:32b",
            "phi3.5:3.8b",
            "phi3:mini-4k",
            "qwen2.5:3b"
            # "tinyllama:1.1b-chat"  # Исключена - только для внутренней коммуникации агентов
        ]
    
    async def _generate_response(
        self,
        prompt: str,
        max_tokens: int = 2048,
        category: Optional[str] = None
    ) -> str:
        """
        Генерирует ответ через модель (только MLX)
        Использует интеллектуальный роутинг для выбора оптимальной модели
        
        Args:
            prompt: Промпт для генерации
            max_tokens: Максимум токенов
            category: Категория задачи (для роутинга)
        """
        import httpx
        from typing import List
        
        logger.info("[VICTORIA_CYCLE] extended_thinking _generate_response prompt_preview=%s category=%s",
                    (prompt or "")[:60], category)
        # КРИТИЧНО: Интеллектуальный выбор модели на основе задачи
        selected_model = self.model_name  # Fallback на базовую модель
        
        if self.use_intelligent_routing and self.model_router:
            try:
                # Получаем список доступных моделей из MLX Server
                available_models = await self._get_available_models()
                
                # Выбираем оптимальную модель
                # Для reasoning задач приоритет качества (нужны мощные модели)
                is_reasoning = category and category.lower() in ["reasoning", "логика", "анализ", "planning"]
                prioritize_quality = is_reasoning or "подумай" in prompt.lower() or "логика" in prompt.lower()
                
                optimal_model, task_category, confidence = await self.model_router.select_optimal_model(
                    prompt=prompt,
                    category=category,
                    available_models=available_models,
                    prioritize_quality=prioritize_quality,
                    prioritize_speed=False
                )
                
                if optimal_model:
                    selected_model = optimal_model
                    logger.info(
                        f"🎯 Интеллектуальный роутинг: выбрана модель {selected_model} "
                        f"для категории {task_category.value} (confidence: {confidence:.3f})"
                    )
                else:
                    logger.warning(f"⚠️ Интеллектуальный роутинг не нашел модель, используем базовую: {self.model_name}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка интеллектуального роутинга: {e}, используем базовую модель")
        
        # Используем выбранную модель
        model_to_use = selected_model
        
        # Используем MLX API Server с fallback на Ollama
        mlx_url = os.getenv('MLX_API_URL', 'http://localhost:11435')
        is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
        ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        if is_docker:
            ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
        
        # Начинаем с MLX, Ollama будет добавлен при rate limit
        urls_to_try = [mlx_url] if mlx_url else []
        
        try:
            # КРИТИЧНО: Таймаут увеличен до 300 секунд (5 минут)
            # Генерации deepseek-r1-distill-llama:70b занимают 120-125 секунд
            # Старый таймаут 120 секунд был слишком коротким
            async with httpx.AsyncClient(timeout=300.0) as client:
                for llm_url in urls_to_try:
                    try:
                        # Используем выбранную модель (через интеллектуальный роутинг или базовую)
                        # Чат с Викторией использует приоритет HIGH
                        headers = {"X-Request-Priority": "high"}
                        response = await client.post(
                            f"{llm_url}/api/generate",
                            json={
                                "model": model_to_use,  # Используем выбранную модель
                                "prompt": prompt,
                                "stream": False,
                                "options": {
                                    "temperature": 0.5,  # Низкая для reasoning
                                    "num_predict": max_tokens
                                }
                            },
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            result = response.json().get('response', '')
                            if result:
                                source = "MLX"
                                logger.debug(f"✅ ExtendedThinking использует {source}: {llm_url} (модель: {model_to_use})")
                                return result
                        elif response.status_code == 429:
                            # Rate limit - для MLX пробуем Ollama fallback
                            is_mlx = "11435" in llm_url or "mlx" in llm_url.lower()
                            if is_mlx:
                                logger.warning(f"⚠️ [RATE LIMIT] MLX rate limit на {llm_url}, пробуем Ollama fallback...")
                                # Добавляем Ollama в список для следующей попытки
                                ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
                                is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
                                if is_docker:
                                    ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
                                if ollama_url not in urls_to_try:
                                    urls_to_try.append(ollama_url)
                                    logger.info(f"🔄 [FALLBACK] Добавлен Ollama для обработки rate limit: {ollama_url}")
                            else:
                                logger.warning(f"⚠️ [RATE LIMIT] Rate limit на {llm_url}, пробуем следующий URL...")
                            # Ждем немного перед следующей попыткой
                            await asyncio.sleep(2)
                            continue
                        elif response.status_code >= 500:
                            # Серверная ошибка - для MLX пробуем Ollama fallback
                            is_mlx = "11435" in llm_url or "mlx" in llm_url.lower()
                            if is_mlx:
                                logger.warning(f"⚠️ [SERVER ERROR] MLX серверная ошибка {response.status_code} на {llm_url}, пробуем Ollama fallback...")
                                # Добавляем Ollama в список для следующей попытки
                                ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
                                is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
                                if is_docker:
                                    ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
                                if ollama_url not in urls_to_try:
                                    urls_to_try.append(ollama_url)
                                    logger.info(f"🔄 [FALLBACK] Добавлен Ollama для обработки серверной ошибки: {ollama_url}")
                            else:
                                logger.warning(f"⚠️ [SERVER ERROR] Серверная ошибка {response.status_code} на {llm_url}")
                            continue
                        elif response.status_code == 404:
                            # Модель не найдена, используем интеллектуальный fallback
                            if self.use_intelligent_routing and self.model_router:
                                try:
                                    # Получаем fallback модели через роутер
                                    task_category = self.model_router.classify_task(prompt, category)
                                    fallback_models = self.model_router.get_fallback_models(
                                        model_to_use,
                                        task_category,
                                        max_fallbacks=5
                                    )
                                    logger.info(f"🔄 Интеллектуальный fallback для {model_to_use}: {fallback_models}")
                                except Exception as e:
                                    logger.warning(f"⚠️ Ошибка получения fallback моделей: {e}, используем стандартный список")
                                    fallback_models = [
                                        "deepseek-r1-distill-llama:70b",
                                        "llama3.3:70b",
                                        "qwen2.5-coder:32b",
                                        "phi3.5:3.8b",
                                        "qwen2.5:3b",
                                        "phi3:mini-4k"
                                        # tinyllama исключена - только для внутренней коммуникации агентов
                                    ]
                            else:
                                # Стандартный fallback список
                                fallback_models = [
                                    "deepseek-r1-distill-llama:70b",
                                    "llama3.3:70b",
                                    "qwen2.5-coder:32b",
                                    "phi3.5:3.8b",
                                    "qwen2.5:3b",
                                    "phi3:mini-4k"
                                    # tinyllama исключена - только для внутренней коммуникации агентов
                                ]
                            
                            logger.warning(f"Модель {model_to_use} не найдена на {llm_url}, пробуем fallback модели...")
                            for fallback_model in fallback_models:
                                if fallback_model == model_to_use:
                                    continue  # Пропускаем уже проверенную модель
                                try:
                                    # Чат с Викторией использует приоритет HIGH
                                    headers = {"X-Request-Priority": "high"}
                                    fallback_response = await client.post(
                                        f"{llm_url}/api/generate",
                                        json={
                                            "model": fallback_model,
                                            "prompt": prompt,
                                            "stream": False,
                                            "options": {
                                                "temperature": 0.5,
                                                "num_predict": max_tokens
                                            }
                                        },
                                        headers=headers,
                                        timeout=300.0  # Увеличен таймаут для fallback моделей
                                    )
                                    if fallback_response.status_code == 200:
                                        source = "MLX"
                                        logger.info(f"✅ Использована {source} fallback модель: {fallback_model}")
                                        return fallback_response.json().get('response', '')
                                    elif fallback_response.status_code == 429:
                                        # Rate limit на fallback модели - пропускаем
                                        logger.warning(f"⚠️ [RATE LIMIT] Fallback модель {fallback_model} на {llm_url} - rate limit")
                                        await asyncio.sleep(2)  # Ждем перед следующей попыткой
                                        continue
                                    elif fallback_response.status_code >= 500:
                                        # Серверная ошибка на fallback - пропускаем
                                        logger.warning(f"⚠️ [SERVER ERROR] Fallback модель {fallback_model} на {llm_url} - серверная ошибка {fallback_response.status_code}")
                                        continue
                                except Exception as e:
                                    logger.debug(f"Fallback модель {fallback_model} недоступна на {llm_url}: {e}")
                                    continue
                            
                            # Пробуем следующий URL (только MLX)
                            continue
                    except Exception as e:
                        logger.debug(f"Ошибка при использовании {llm_url}: {e}")
                        continue
                
                logger.error(f"❌ Все модели и URL недоступны")
                return ""
        except Exception as e:
            logger.error(f"Ошибка запроса к модели: {e}")
            return ""


async def main():
    """Пример использования"""
    engine = ExtendedThinkingEngine(
        model_name="deepseek-r1-distill-llama:70b",
        thinking_budget=10000
    )
    
    result = await engine.think(
        "Реши задачу: У Маши было 5 яблок, она отдала 2 другу, затем купила еще 3. Сколько яблок у Маши теперь?",
        use_iterative=True
    )
    
    print("Финальный ответ:", result.final_answer)
    print("Уверенность:", result.confidence)
    print("Шагов рассуждения:", len(result.thinking_steps))
    for step in result.thinking_steps:
        print(f"\nШаг {step.step_number}: {step.thought[:100]}...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
