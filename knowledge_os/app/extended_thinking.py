"""
Extended Thinking Mode - Расширенное рассуждение для сложных задач
Основано на практике Anthropic Claude Extended Thinking
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Используем ТОЛЬКО MLX API Server (порт 11435)
MLX_URL = os.getenv("MLX_API_URL", "http://localhost:11435")
DEFAULT_LLM_URL = MLX_URL

# Кэш для списка моделей (чтобы не делать частые запросы к /api/tags)
_models_cache = {"data": None, "timestamp": 0}
_MODELS_CACHE_TTL = 120  # 2 минуты кэш для списка моделей

# Кэш для скрытых рассуждений (Dual-channel reasoning)
# Хранит последние рассуждения для Summary Reader
_hidden_thoughts_cache = {}  # {session_id: [thoughts]}
_MAX_HIDDEN_CACHE_SIZE = 100


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
        model_name: str = "victoria-wisdom-30b",  # Самая мощная reasoning модель (Wisdom Era)
        thinking_budget: int = 15000,  # [SINGULARITY 14.1] Увеличен бюджет до 15к
        max_steps: int = 12,  # [SINGULARITY 14.1] Увеличено кол-во шагов
        use_intelligent_routing: bool = True,  # Использовать интеллектуальный роутинг
        dual_channel: bool = True,  # [SINGULARITY 10.0+] Включить разделение каналов (OpenAI o3 pattern)
    ):
        self.model_name = model_name  # Базовая модель (fallback)
        self.use_intelligent_routing = use_intelligent_routing
        # Используем только MLX
        self.llm_url = DEFAULT_LLM_URL
        self.thinking_budget = thinking_budget
        self.max_steps = max_steps
        self.dual_channel = dual_channel

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
                        import os
                        import sys

                        router_path = os.path.join(
                            os.path.dirname(__file__), "intelligent_model_router.py"
                        )
                        if os.path.exists(router_path):
                            sys.path.insert(0, os.path.dirname(__file__))
                            from intelligent_model_router import get_intelligent_router
                        else:
                            raise ImportError("intelligent_model_router.py not found")

                self.model_router = get_intelligent_router()
                logger.info(
                    f"✅ ExtendedThinkingEngine инициализирован с интеллектуальным роутингом: URL={self.llm_url}, базовая модель={self.model_name}"
                )
            except (ImportError, Exception) as e:
                logger.warning(f"⚠️ Intelligent router недоступен ({e}), используем базовую модель")
                self.use_intelligent_routing = False
                self.model_router = None
        else:
            self.model_router = None
            logger.info(
                f"✅ ExtendedThinkingEngine инициализирован: URL={self.llm_url}, модель={self.model_name}"
            )

    @classmethod
    def get_hidden_thoughts(cls, session_id: str) -> Optional[List[Dict]]:
        """Получить скрытые рассуждения для сессии (Summary Reader)"""
        return _hidden_thoughts_cache.get(session_id)

    async def pulse_warmup(self):
        """[SINGULARITY 24.0] Предиктивный прогрев моделей для Metal (Pulse)"""
        try:
            models = ["lfm2.5-thinking:1.2b", "tinyllama:1.1b-chat"]
            for model in models:
                logger.debug(f"💓 [PULSE] Warming up {model}...")
                await self._generate_response("ping", max_tokens=5, category="fast")
        except Exception as e:
            logger.debug(f"Pulse warmup failed: {e}")

    async def semantic_heartbeat(self):
        """[SINGULARITY 24.0] Семантический пульс: проверка здоровья через легкую модель"""
        try:
            # Анализируем последние 500 символов лога супервизора (если есть)
            log_path = "victoria_bot_supervisor.log"
            log_context = ""
            if os.path.exists(log_path):
                with open(log_path) as f:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    f.seek(max(0, size - 500))
                    log_context = f.read()

            prompt = f"""### ROLE: System Health Monitor
### TASK: Analyze logs and report status.
### LOGS:
{log_context}

### FORMAT: 1 sentence, concise.
STATUS REPORT:"""

            report = await self._generate_response(prompt, max_tokens=50, category="fast")
            if report:
                logger.info(f"💓 [HEARTBEAT] {report}")
                # Здесь можно добавить отправку в Telegram через TelegramAlerter
                try:
                    from app.telegram_alerter import get_telegram_alerter

                    alerter = get_telegram_alerter()
                    await alerter.send_alert(
                        f"💓 *HEARTBEAT:* {report}", priority="low", source="Pulse Check"
                    )
                except:
                    pass
        except Exception as e:
            logger.debug(f"Semantic heartbeat failed: {e}")

    async def think(
        self,
        prompt: str,
        context: Optional[str] = None,
        use_iterative: bool = True,
        category: Optional[str] = None,
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
        import os
        import time

        import httpx

        current_time = time.time()

        # Возвращаем кэшированный результат если еще валиден
        if (
            _models_cache["data"]
            and (current_time - _models_cache["timestamp"]) < _MODELS_CACHE_TTL
        ):
            logger.debug(
                f"📋 Используем кэшированный список моделей ({len(_models_cache['data'])} моделей)"
            )
            return _models_cache["data"]

        try:
            mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")
            if not mlx_url.startswith(("http://", "https://")):
                mlx_url = f"http://{mlx_url}"
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
        # Тяжёлые 70B/104B удалены из-за Apple Silicon Metal limits
        fallback_models = [
            "victoria-wisdom-30b",
            "victoria-wisdom-30b",
            "phi3.5:3.8b",
            "phi3:mini-4k",
            "tinyllama:1.1b-chat",
        ]
        return fallback_models

    async def _iterative_thinking(
        self, prompt: str, context: Optional[Any] = None, category: Optional[str] = None
    ) -> ExtendedThinkingResult:
        """Итеративное рассуждение - несколько шагов"""
        thinking_steps = []
        current_understanding = ""
        start_time = datetime.now(timezone.utc)

        # [SINGULARITY 10.0+] Deep Reasoning Channel (OpenAI o3 pattern)
        # Если включен dual_channel, мы разделяем "Analysis" и "Final Answer"

        # Начальный промпт для рассуждения
        ctx_str = context.get("kb_context") if isinstance(context, dict) else context
        thinking_prompt = self._build_thinking_prompt(prompt, ctx_str, step=1)

        for step_num in range(1, self.max_steps + 1):
            # [SINGULARITY 24.0] Meta-Cognitive Reflection: detect logic loops
            if step_num > 3:
                recent_thoughts = "\n".join([s.thought for s in thinking_steps[-3:]])
                if len(recent_thoughts) > 100:
                    # Простая проверка на повторение (логические петли)
                    reflection_prompt = f"### [META-REFLECTION]\nПроверь последние шаги на зацикливание или топтание на месте:\n{recent_thoughts}\n\nЕсли есть петля, предложи новый вектор мысли. Если нет, напиши 'CONTINUE'."
                    reflection = await self._generate_response(
                        reflection_prompt, max_tokens=100, category="fast"
                    )
                    if reflection and "CONTINUE" not in reflection.upper():
                        current_understanding += f"\n[META-CORRECTION]: {reflection}\n"

            # Генерируем шаг рассуждения
            step_thought = await self._generate_thinking_step(
                thinking_prompt, step_num, current_understanding, category
            )

            # Извлекаем мысль и вывод
            thought, conclusion = self._parse_thinking_step(step_thought)

            step = ThinkingStep(step_number=step_num, thought=thought, conclusion=conclusion)
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
                prompt, ctx_str, step=step_num + 1, previous_steps=current_understanding
            )

        # Формируем финальный ответ на основе всех рассуждений
        # Если dual_channel включен, мы делаем отдельный вызов для синтеза финального ответа
        # без утечки промежуточных мыслей пользователю.
        final_answer = await self._synthesize_final_answer(prompt, thinking_steps, category)

        # Сохраняем скрытые рассуждения для Summary Reader (Dual-channel)
        session_id = context.get("session_id") if isinstance(context, dict) else None
        if session_id:
            try:
                global _hidden_thoughts_cache
                # Ограничиваем размер кэша
                if len(_hidden_thoughts_cache) >= _MAX_HIDDEN_CACHE_SIZE:
                    oldest_key = next(iter(_hidden_thoughts_cache))
                    _hidden_thoughts_cache.pop(oldest_key)

                # Сохраняем цепочку мыслей
                _hidden_thoughts_cache[session_id] = [
                    {"step": s.step_number, "thought": s.thought, "conclusion": s.conclusion}
                    for s in thinking_steps
                ]

                # Если dual_channel активен, логируем это особо
                if self.dual_channel:
                    logger.info(
                        f"🧠 [DEEP REASONING CHANNEL] Скрытые рассуждения (o3 pattern) сохранены для сессии {session_id}"
                    )
                else:
                    logger.info(
                        f"🧠 [DUAL-CHANNEL] Скрытые рассуждения сохранены для сессии {session_id}"
                    )
            except Exception as e:
                logger.debug(f"Ошибка сохранения скрытых рассуждений: {e}")

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        return ExtendedThinkingResult(
            final_answer=final_answer,
            thinking_steps=thinking_steps,
            total_tokens_used=sum(len(s.thought) for s in thinking_steps) + len(final_answer),
            thinking_time_seconds=elapsed,
            confidence=self._calculate_confidence(thinking_steps),
        )

    async def _single_pass_thinking(
        self, prompt: str, context: Optional[Any] = None, category: Optional[str] = None
    ) -> ExtendedThinkingResult:
        """Одношаговое рассуждение - все сразу"""
        ctx_str = context.get("kb_context") if isinstance(context, dict) else context
        thinking_prompt = self._build_thinking_prompt(prompt, ctx_str, step=1)

        t_start = time.perf_counter()
        # Генерируем полное рассуждение
        full_thinking = await self._generate_response(
            thinking_prompt, max_tokens=self.thinking_budget, category=category
        )
        # Извлекаем финальный ответ
        final_answer = await self._extract_final_answer(full_thinking, prompt)
        # Разбиваем на шаги (если есть нумерация)
        thinking_steps = self._parse_thinking_into_steps(full_thinking)
        elapsed = time.perf_counter() - t_start

        return ExtendedThinkingResult(
            final_answer=final_answer,
            thinking_steps=thinking_steps,
            total_tokens_used=len(full_thinking) + len(final_answer),
            thinking_time_seconds=elapsed,
            confidence=self._calculate_confidence(thinking_steps),
        )

    def _build_thinking_prompt(
        self, prompt: str, context: Optional[str], step: int, previous_steps: Optional[str] = None
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
        self, prompt: str, step_num: int, current_understanding: str, category: Optional[str] = None
    ) -> str:
        """Сгенерировать один шаг рассуждения"""
        return await self._generate_response(prompt, max_tokens=1000, category=category)

    def _parse_thinking_step(self, step_text: str) -> Tuple[str, Optional[str]]:
        """Разобрать текст шага на мысль и вывод"""
        thought = step_text.strip()
        conclusion = None

        if "ФИНАЛЬНЫЙ ОТВЕТ:" in thought:
            parts = thought.split("ФИНАЛЬНЫЙ ОТВЕТ:", 1)
            thought = parts[0].strip()
            conclusion = parts[1].strip()

        return thought, conclusion

    def _is_final_conclusion(self, conclusion: str) -> bool:
        """Проверить, является ли вывод финальным"""
        return conclusion is not None and len(conclusion) > 0

    async def _synthesize_final_answer(
        self,
        prompt: str,
        thinking_steps: List[ThinkingStep],
        category: Optional[str] = None,
        incremental: bool = False,  # [SINGULARITY 14.2]
    ) -> str:
        """Сформировать финальный ответ на основе всех шагов"""
        # [SINGULARITY 14.2] Incremental Assembly for long reports
        if incremental or len(thinking_steps) > 8:
            return await self._synthesize_incremental(prompt, thinking_steps, category)

        if thinking_steps and thinking_steps[-1].conclusion:
            # [SINGULARITY 14.1] Проверка на полноту вывода
            last_step = thinking_steps[-1].thought
            if len(last_step) > 950:  # Близко к max_tokens=1000
                logger.warning("⚠️ Последний шаг рассуждения может быть неполным (лимит токенов).")
            return thinking_steps[-1].conclusion

        # Если нет явного вывода, просим модель суммировать
        steps_text = "\n".join([f"Шаг {s.step_number}: {s.thought}" for s in thinking_steps])

        # [SINGULARITY 14.1] Ограничение длины контекста для синтеза
        if len(steps_text) > 15000:
            logger.warning("⚠️ Слишком много рассуждений для синтеза, сокращаю контекст.")
            steps_text = steps_text[:7000] + "\n... [truncated] ...\n" + steps_text[-7000:]

        synthesis_prompt = f"""На основе твоих рассуждений, дай финальный ответ на задачу.
Если рассуждения обрываются, постарайся логически завершить их.

ЗАДАЧА: {prompt}

ТВОИ РАССУЖДЕНИЯ:
{steps_text}

ФИНАЛЬНЫЙ ОТВЕТ:"""

        return await self._generate_response(synthesis_prompt, max_tokens=3000, category=category)

    async def _synthesize_incremental(
        self, prompt: str, thinking_steps: List[ThinkingStep], category: Optional[str] = None
    ) -> str:
        """[SINGULARITY 14.2] Incremental Assembly of the final report"""
        logger.info(f"🧱 [INCREMENTAL] Assembling final answer from {len(thinking_steps)} steps...")

        from task_orchestration.task_decomposer import TaskDecomposer

        decomposer = TaskDecomposer()

        # 1. Decompose the goal into sections
        sections = await decomposer.decompose_task_async(prompt)
        if not sections or len(sections) < 2:
            # Fallback if decomposition fails
            sections = ["Introduction", "Analysis", "Findings", "Conclusion"]
        else:
            sections = [s.title for s in sections]

        final_report = ""
        accumulated_facts = ""

        # 2. Extract facts from all thinking steps first (Map phase)
        from ai_core import FactExtractor

        extractor = FactExtractor()
        all_thoughts = "\n".join([f"Step {s.step_number}: {s.thought}" for s in thinking_steps])
        global_facts = await extractor.extract_facts(
            all_thoughts, context_description="Global thinking steps"
        )

        # 3. Generate each section (Reduce phase)
        for i, section in enumerate(sections):
            logger.info(f"📝 [SECTION] Generating section {i + 1}/{len(sections)}: {section}")

            section_prompt = f"""### ROLE: Technical Writer
### TASK: Generate the '{section}' part of the final report.
### GOAL: {prompt}
### GLOBAL FACTS:
{global_facts}

### PREVIOUS SECTIONS:
{final_report[-2000:] if final_report else "None"}

### SECTION TO GENERATE: {section}
### FORMAT: Professional, detailed, Markdown.

{section.upper()}:"""

            section_content = await self._generate_response(
                section_prompt, max_tokens=1500, category=category
            )
            final_report += f"\n\n## {section}\n{section_content}"

        return final_report

    def _calculate_confidence(self, thinking_steps: List[ThinkingStep]) -> float:
        """Рассчитать уверенность в ответе"""
        if not thinking_steps:
            return 0.0

        # Простая эвристика: чем больше шагов (до предела), тем выше уверенность
        # Также наличие вывода в последнем шаге повышает уверенность
        base_confidence = min(0.5 + (len(thinking_steps) * 0.05), 0.9)

        if thinking_steps[-1].conclusion:
            base_confidence += 0.1

        return min(base_confidence, 1.0)

    def _parse_thinking_into_steps(self, full_text: str) -> List[ThinkingStep]:
        """Разбить полный текст рассуждения на шаги"""
        import re

        steps = []

        # Ищем паттерны типа "Шаг 1", "1.", "Step 1"
        raw_steps = re.split(r"(?:Шаг|Step|Step\s*#)?\s*(\d+)[\.:\)]", full_text)

        if len(raw_steps) > 1:
            for i in range(1, len(raw_steps), 2):
                step_num = int(raw_steps[i])
                step_content = raw_steps[i + 1].strip()

                thought, conclusion = self._parse_thinking_step(step_content)
                steps.append(
                    ThinkingStep(step_number=step_num, thought=thought, conclusion=conclusion)
                )
        else:
            # Если не удалось разбить, считаем все одним шагом
            thought, conclusion = self._parse_thinking_step(full_text)
            steps.append(ThinkingStep(step_number=1, thought=thought, conclusion=conclusion))

        return steps

    async def _extract_final_answer(self, full_text: str, original_prompt: str) -> str:
        """Извлечь финальный ответ из полного текста"""
        if "ФИНАЛЬНЫЙ ОТВЕТ:" in full_text:
            return full_text.split("ФИНАЛЬНЫЙ ОТВЕТ:", 1)[1].strip()

        # Если нет явного маркера, пробуем найти последний абзац
        paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
        if paragraphs:
            return paragraphs[-1]

        return full_text

    async def _generate_response(
        self, prompt: str, max_tokens: int = 2000, category: Optional[str] = None
    ) -> str:
        """
        Генерация ответа через MLX API Server или Ollama (fallback)
        """
        import httpx

        # Выбираем модель
        model_to_use = self.model_name
        if self.use_intelligent_routing and self.model_router:
            try:
                # Используем интеллектуальный роутер для выбора модели
                # Передаем доступные модели из MLX
                available_models = await self._get_available_models()

                # Классифицируем задачу если категория не задана
                task_category = category or self.model_router.classify_task(prompt)

                # Выбираем оптимальную модель
                optimal_model, _task_cat, confidence = await self.model_router.select_optimal_model(
                    prompt=prompt,
                    category=task_category,
                    available_models=available_models,
                    optimize_for="quality",  # Для рассуждений важно качество
                )

                if optimal_model and confidence > 0.5:
                    model_to_use = optimal_model
                    logger.info(
                        f"🧠 [INTELLIGENT ROUTER] Выбрана модель: {model_to_use} (confidence: {confidence:.2f})"
                    )
            except Exception as e:
                logger.warning(
                    f"⚠️ Ошибка интеллектуального роутера: {e}, используем базовую модель {model_to_use}"
                )

        # Список URL для попыток (сначала MLX, затем Ollama)
        urls_to_try = [self.llm_url]
        if not urls_to_try[0].startswith(("http://", "https://")):
            urls_to_try[0] = f"http://{urls_to_try[0]}"

        # Добавляем Ollama как fallback
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        is_docker = (
            os.path.exists("/.dockerenv")
            or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
        )
        if is_docker:
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

        if ollama_url not in urls_to_try:
            urls_to_try.append(ollama_url)

        async with httpx.AsyncClient() as client:
            for llm_url in urls_to_try:
                try:
                    # Чат с Викторией использует приоритет HIGH
                    headers = {"X-Request-Priority": "high"}

                    # Для MLX API Server используем /api/generate с параметром category
                    # Для Ollama используем /api/generate с параметром model
                    is_mlx = "11435" in llm_url or "mlx" in llm_url.lower()

                    if is_mlx:
                        payload = {
                            "category": "reasoning",  # Принудительно используем категорию reasoning для MLX
                            "prompt": prompt,
                            "stream": False,
                            "options": {"temperature": 0.5, "num_predict": max_tokens},
                        }
                    else:
                        payload = {
                            "model": model_to_use,
                            "prompt": prompt,
                            "stream": False,
                            "options": {"temperature": 0.5, "num_predict": max_tokens},
                        }

                    response = await client.post(
                        f"{llm_url.rstrip('/')}/api/generate",
                        json=payload,
                        headers=headers,
                        timeout=300.0,  # 5 минут на генерацию
                    )

                    if response.status_code == 200:
                        data = response.json()
                        return data.get("response", "")
                    elif response.status_code == 429:
                        # Rate limit - пробуем подождать или другой сервер
                        logger.warning(f"⚠️ [RATE LIMIT] Сервер {llm_url} перегружен (429)")
                        if llm_url == urls_to_try[-1]:
                            # Если это последний сервер, ждем и пробуем еще раз
                            await asyncio.sleep(5)
                            # Рекурсивный вызов (осторожно с бесконечной рекурсией)
                            # return await self._generate_response(prompt, max_tokens, category)
                        continue
                    elif response.status_code >= 500:
                        logger.warning(
                            f"⚠️ [SERVER ERROR] Ошибка сервера {llm_url}: {response.status_code}"
                        )
                        continue
                    elif response.status_code == 404:
                        # Модель не найдена, пробуем fallback модели
                        logger.warning(
                            f"⚠️ [NOT FOUND] Модель {model_to_use} не найдена на {llm_url}"
                        )
                        continue

                except Exception as e:
                    logger.debug(f"Ошибка при обращении к {llm_url}: {e}")
                    continue

            logger.error("❌ Все LLM бэкенды недоступны для генерации")
            return ""
