"""
Model Enhancer - Комплексная система улучшения качества и скорости моделей
Объединяет: Self-Consistency, Speculative Decoding, Enhanced RAG, CoT, Ensemble
"""

import asyncio
import json
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class SelfConsistencyEngine:
    """Self-Consistency: множественные генерации и выбор лучшего ответа"""

    def __init__(self, ollama_url: str = OLLAMA_URL):
        self.ollama_url = ollama_url

    async def generate_multiple(
        self, prompt: str, model_name: str, num_samples: int = 5, temperature: float = 0.7
    ) -> List[str]:
        """
        Генерировать несколько вариантов ответа

        Args:
            prompt: Промпт
            model_name: Имя модели
            num_samples: Количество вариантов
            temperature: Температура для разнообразия

        Returns:
            Список вариантов ответов
        """
        import httpx

        tasks = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(num_samples):
                # Немного варьируем temperature для разнообразия
                current_temp = temperature + (i * 0.1) % 0.3
                task = client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": current_temp, "num_predict": 2048},
                    },
                )
                tasks.append(task)

            responses = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for resp in responses:
            if isinstance(resp, Exception):
                logger.warning(f"⚠️ Ошибка генерации: {resp}")
                continue
            if resp.status_code == 200:
                data = resp.json()
                results.append(data.get("response", ""))

        logger.info(f"✅ Сгенерировано {len(results)} вариантов из {num_samples}")
        return results

    def select_best_answer(
        self, responses: List[str], method: str = "majority_voting"
    ) -> Tuple[str, float]:
        """
        Выбрать лучший ответ из множественных генераций

        Args:
            responses: Список ответов
            method: Метод выбора (majority_voting, longest, most_confident)

        Returns:
            (лучший ответ, уверенность)
        """
        if not responses:
            return "", 0.0

        if method == "majority_voting":
            # Для задач с конкретным ответом - большинство голосов
            # Для свободных ответов - самый частый паттерн
            response_lengths = [len(r) for r in responses]
            avg_length = sum(response_lengths) / len(response_lengths)

            # Выбираем ответы близкие к среднему (не слишком короткие/длинные)
            filtered = [r for r in responses if 0.7 * avg_length <= len(r) <= 1.3 * avg_length]

            if filtered:
                # Выбираем самый длинный из отфильтрованных (обычно более полный)
                best = max(filtered, key=len)
                confidence = len(filtered) / len(responses)
                return best, confidence
            else:
                # Fallback на средний
                best = responses[len(responses) // 2]
                return best, 0.5

        elif method == "longest":
            # Самый длинный ответ (обычно более полный)
            best = max(responses, key=len)
            return best, 0.7

        elif method == "most_confident":
            # Ответ с наибольшим количеством утверждений (можно улучшить через LLM)
            best = max(responses, key=lambda x: x.count("✅") + x.count("."))
            return best, 0.6

        return responses[0], 0.5

    async def generate_with_consistency(
        self,
        prompt: str,
        model_name: str,
        num_samples: int = 5,
        use_for: str = "reasoning",  # reasoning, coding, general
    ) -> Dict:
        """
        Генерировать ответ с использованием Self-Consistency

        Args:
            prompt: Промпт
            model_name: Имя модели
            num_samples: Количество вариантов
            use_for: Тип задачи

        Returns:
            Результат с лучшим ответом и метаданными
        """
        start_time = datetime.now(timezone.utc)

        # Генерируем множественные варианты
        responses = await self.generate_multiple(prompt, model_name, num_samples)

        if not responses:
            return {
                "response": "",
                "confidence": 0.0,
                "method": "self_consistency",
                "num_samples": num_samples,
                "error": "Не удалось сгенерировать варианты",
            }

        # Выбираем лучший
        method = "majority_voting" if use_for == "reasoning" else "longest"
        best_answer, confidence = self.select_best_answer(responses, method)

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        return {
            "response": best_answer,
            "confidence": confidence,
            "method": "self_consistency",
            "num_samples": len(responses),
            "all_responses": responses[:3],  # Первые 3 для анализа
            "time_elapsed": elapsed,
        }


class SpeculativeDecodingEngine:
    """Speculative Decoding: ускорение через draft модель"""

    def __init__(self, ollama_url: str = OLLAMA_URL):
        self.ollama_url = ollama_url

        # Draft модели (быстрые) для разных target моделей
        self.draft_models = {
            "command-r-plus:104b": "phi3.5:3.8b",
            "deepseek-r1-distill-llama:70b": "phi3.5:3.8b",
            "llama3.3:70b": "phi3.5:3.8b",
            "qwen2.5-coder:32b": "qwen2.5:3b",
            "phi3.5:3.8b": "tinyllama:1.1b-chat",  # Tiny для маленькой
        }

    async def generate_with_speculation(
        self,
        prompt: str,
        target_model: str,
        draft_model: Optional[str] = None,
        num_draft_tokens: int = 5,
    ) -> Dict:
        """
        Генерировать ответ с использованием Speculative Decoding

        Args:
            prompt: Промпт
            target_model: Целевая модель (большая, качественная)
            draft_model: Draft модель (быстрая, опционально)
            num_draft_tokens: Количество токенов для draft

        Returns:
            Результат с ускоренной генерацией
        """
        if draft_model is None:
            draft_model = self.draft_models.get(target_model, "tinyllama:1.1b-chat")

        import httpx

        start_time = datetime.now(timezone.utc)

        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Draft модель генерирует быстрый черновик
            # Singularity 10.0: Спекулятивная связка MLX (Draft) + Ollama (Target)
            logger.info(
                f"🚀 [SPECULATIVE] Запуск связки: Draft={draft_model} (MLX) -> Target={target_model} (Ollama)"
            )

            # Пробуем получить черновик из MLX (он быстрее на Apple Silicon)
            mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
            try:
                draft_resp = await client.post(
                    f"{mlx_url}/api/generate",
                    json={
                        "model": draft_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": num_draft_tokens},
                    },
                    timeout=5.0,
                )
            except:
                draft_resp = None

            if not draft_resp or draft_resp.status_code != 200:
                # Fallback на локальный Ollama для draft
                draft_resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": draft_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"num_predict": num_draft_tokens},
                    },
                )

            if draft_resp.status_code != 200:
                # Fallback на обычную генерацию
                return await self._fallback_generate(client, prompt, target_model)

            draft_text = draft_resp.json().get("response", "")

            # 2. Target модель проверяет и дополняет draft
            full_prompt = f"{prompt}\n\n[Draft]: {draft_text}\n\n[Complete the response]:"

            target_resp = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": target_model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 2048},
                },
            )

            if target_resp.status_code != 200:
                return await self._fallback_generate(client, prompt, target_model)

            final_response = target_resp.json().get("response", "")
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

            return {
                "response": final_response,
                "method": "speculative_decoding",
                "draft_model": draft_model,
                "target_model": target_model,
                "draft_text": draft_text[:100],  # Первые 100 символов
                "time_elapsed": elapsed,
                "speedup_estimate": 1.5,  # Примерная оценка ускорения
            }

    async def _fallback_generate(self, client, prompt: str, model: str) -> Dict:
        """Fallback на обычную генерацию"""
        resp = await client.post(
            f"{self.ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
        )

        if resp.status_code == 200:
            return {
                "response": resp.json().get("response", ""),
                "method": "standard",
                "time_elapsed": 0.0,
            }

        return {"response": "", "method": "error", "error": "Generation failed"}


class EnhancedRAGEngine:
    """Улучшенный RAG с реранкингом и фильтрацией"""

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def retrieve_enhanced_context(
        self, query: str, limit: int = 5, min_confidence: float = 0.7, use_reranking: bool = True
    ) -> List[Dict]:
        """
        Получить улучшенный контекст с реранкингом

        Args:
            query: Запрос
            limit: Количество результатов
            min_confidence: Минимальная уверенность
            use_reranking: Использовать ли реранкинг

        Returns:
            Список релевантных контекстов
        """
        import asyncpg

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # 1. Векторный поиск через pgvector (если есть embedding у запроса)
                rows = []
                try:
                    from semantic_cache import get_embedding

                    query_embedding = await get_embedding(query[:8000])
                    if query_embedding and len(query_embedding) == 768:
                        vector_rows = await conn.fetch(
                            """
                            SELECT id, content, confidence_score, usage_count,
                                metadata, domain_id, is_verified,
                                (1 - (embedding <=> $1::vector)) as relevance_score
                            FROM knowledge_nodes
                            WHERE embedding IS NOT NULL AND is_verified = TRUE AND confidence_score >= $2
                            ORDER BY embedding <=> $1::vector
                            LIMIT $3
                        """,
                            query_embedding,
                            min_confidence,
                            limit * 2,
                        )
                        if vector_rows:
                            rows = list(vector_rows)
                except Exception as e:
                    logger.debug("model_enhancer: pgvector search: %s", e)

                # 2. При отсутствии результатов — поиск по ключевым словам
                if not rows:
                    keywords = query.lower().split()[:10]
                    keyword_pattern = "|".join(keywords)
                    rows = await conn.fetch(
                        """
                        SELECT id, content, confidence_score, usage_count,
                            metadata, domain_id, is_verified,
                            (CASE WHEN is_verified THEN 1.0 ELSE 0.8 END * confidence_score
                                * (1.0 + LEAST(COALESCE(usage_count, 0) / 100.0, 0.2))) as relevance_score
                        FROM knowledge_nodes
                        WHERE is_verified = TRUE AND confidence_score >= $1
                        AND (content ILIKE ANY($2)
                            OR metadata::text ILIKE ANY($2))
                        ORDER BY relevance_score DESC
                        LIMIT $3
                    """,
                        min_confidence,
                        [f"%{k}%" for k in keywords],
                        limit * 2,
                    )

                # 3. Реранкинг (если включен)
                if use_reranking and len(rows) > limit:
                    # Простой реранкинг: учитываем длину контекста, свежесть и т.д.
                    scored = []
                    for row in rows:
                        score = float(row["relevance_score"])
                        # Бонус за оптимальную длину (не слишком короткий/длинный)
                        content_len = len(row["content"])
                        if 100 <= content_len <= 1000:
                            score *= 1.1
                        scored.append((score, row))

                    scored.sort(reverse=True, key=lambda x: x[0])
                    rows = [row for _, row in scored[:limit]]
                else:
                    rows = rows[:limit]

                # 4. Формируем результат
                context = []
                for row in rows:
                    domain = (
                        await conn.fetchval(
                            "SELECT name FROM domains WHERE id = $1", row["domain_id"]
                        )
                        if row["domain_id"]
                        else None
                    )

                    context.append(
                        {
                            "content": row["content"],
                            "confidence": float(row["confidence_score"]),
                            "relevance": float(row["relevance_score"]),
                            "domain": domain,
                            "metadata": row["metadata"],
                            "is_verified": row["is_verified"],
                        }
                    )

                logger.info(f"✅ Найдено {len(context)} релевантных контекстов")
                return context

            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Ошибка получения контекста: {e}")
            return []

    def build_enhanced_prompt(self, query: str, context: List[Dict], use_cot: bool = False) -> str:
        """
        Построить улучшенный промпт с контекстом

        Args:
            query: Запрос
            context: Контекст из RAG
            use_cot: Использовать ли Chain-of-Thought

        Returns:
            Улучшенный промпт
        """
        prompt = (
            "Ты - точный и надежный ассистент. Используй предоставленный контекст для ответа.\n\n"
        )

        if context:
            prompt += "📚 РЕЛЕВАНТНЫЙ КОНТЕКСТ:\n\n"
            for i, ctx in enumerate(context, 1):
                prompt += f"[Контекст {i}] (уверенность: {ctx['confidence']:.2f}, релевантность: {ctx['relevance']:.2f})\n"
                prompt += f"{ctx['content']}\n\n"

        if use_cot:
            prompt += "\n\nРЕШИ ЗАДАЧУ ПОШАГОВО:\n"
            prompt += "1. Анализ проблемы\n"
            prompt += "2. Применение контекста\n"
            prompt += "3. Формирование ответа\n"
            prompt += "4. Проверка точности\n\n"

        prompt += f"ВОПРОС: {query}\n\n"
        prompt += "ОТВЕТ (на основе контекста, если он есть):"

        return prompt


class ModelEnsemble:
    """Ensemble: комбинирование нескольких моделей"""

    def __init__(self, ollama_url: str = OLLAMA_URL):
        self.ollama_url = ollama_url

    async def ensemble_generate(
        self,
        prompt: str,
        models: List[str],
        strategy: str = "vote",  # vote, average, best
    ) -> Dict:
        """
        Генерировать ответ через ensemble моделей

        Args:
            prompt: Промпт
            models: Список моделей
            strategy: Стратегия комбинирования

        Returns:
            Результат ensemble
        """
        import httpx

        async with httpx.AsyncClient(timeout=60.0) as client:
            tasks = []
            for model in models:
                task = client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                tasks.append((model, task))

            results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)

            responses = {}
            for (model, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    continue
                if result.status_code == 200:
                    responses[model] = result.json().get("response", "")

            if not responses:
                return {"response": "", "error": "All models failed"}

            # Комбинируем ответы
            if strategy == "vote":
                # Выбираем самый частый паттерн
                combined = self._vote_combine(list(responses.values()))
            elif strategy == "best":
                # Выбираем самый длинный (обычно более полный)
                combined = max(responses.values(), key=len)
            else:
                # Average - берем средний по длине
                avg_len = sum(len(r) for r in responses.values()) / len(responses)
                combined = min(responses.values(), key=lambda x: abs(len(x) - avg_len))

            return {
                "response": combined,
                "method": "ensemble",
                "models_used": list(responses.keys()),
                "num_models": len(responses),
                "strategy": strategy,
            }

    def _vote_combine(self, responses: List[str]) -> str:
        """Комбинировать через голосование"""
        # Простая стратегия: выбираем самый длинный (обычно более полный)
        return max(responses, key=len)


class ModelEnhancer:
    """Главный класс - объединяет все методы улучшения"""

    def __init__(self, db_url: str = DB_URL, ollama_url: str = OLLAMA_URL):
        self.self_consistency = SelfConsistencyEngine(ollama_url)
        self.speculative = SpeculativeDecodingEngine(ollama_url)
        self.enhanced_rag = EnhancedRAGEngine(db_url)
        self.ensemble = ModelEnsemble(ollama_url)

    async def enhance_response(
        self,
        query: str,
        model_name: str,
        enhancement_methods: List[str] = None,
        task_type: str = "general",
    ) -> Dict:
        """
        Улучшить ответ используя различные методы

        Args:
            query: Запрос
            model_name: Имя модели
            enhancement_methods: Методы улучшения (self_consistency, speculative, rag, ensemble)
            task_type: Тип задачи (reasoning, coding, general)

        Returns:
            Улучшенный ответ с метаданными
        """
        if enhancement_methods is None:
            # Автоматический выбор методов в зависимости от типа задачи
            if task_type == "reasoning":
                enhancement_methods = ["self_consistency", "rag", "cot"]
            elif task_type == "coding":
                enhancement_methods = ["rag", "speculative"]
            else:
                enhancement_methods = ["rag"]

        result = {
            "query": query,
            "model": model_name,
            "task_type": task_type,
            "methods_used": enhancement_methods,
            "response": "",
            "metadata": {},
        }

        # 1. Enhanced RAG (если включен)
        context = []
        if "rag" in enhancement_methods:
            context = await self.enhanced_rag.retrieve_enhanced_context(query)
            if context:
                query = self.enhanced_rag.build_enhanced_prompt(
                    query, context, use_cot=("cot" in enhancement_methods)
                )

        # 2. Выбор метода генерации
        if "self_consistency" in enhancement_methods:
            # Self-Consistency для reasoning
            consistency_result = await self.self_consistency.generate_with_consistency(
                query, model_name, num_samples=5, use_for=task_type
            )
            result["response"] = consistency_result["response"]
            result["metadata"]["consistency"] = consistency_result

        elif "speculative" in enhancement_methods:
            # Speculative Decoding для скорости
            speculative_result = await self.speculative.generate_with_speculation(query, model_name)
            result["response"] = speculative_result["response"]
            result["metadata"]["speculative"] = speculative_result

        elif "ensemble" in enhancement_methods:
            # Ensemble для максимального качества
            # Выбираем несколько моделей для ensemble
            if task_type == "coding":
                ensemble_models = ["qwen2.5-coder:32b", "qwen2.5:3b"]
            elif task_type == "reasoning":
                ensemble_models = ["phi3.5:3.8b", "qwen2.5-coder:32b"]
            else:
                ensemble_models = [model_name, "phi3.5:3.8b"]

            ensemble_result = await self.ensemble.ensemble_generate(query, ensemble_models)
            result["response"] = ensemble_result["response"]
            result["metadata"]["ensemble"] = ensemble_result

        else:
            # Стандартная генерация (можно добавить)
            result["response"] = "[Standard generation not implemented]"

        result["metadata"]["rag_context_count"] = len(context)
        result["metadata"]["rag_context"] = context[:2] if context else []  # Первые 2 для примера

        return result


async def main():
    """Пример использования"""
    enhancer = ModelEnhancer()

    # Пример 1: Reasoning с Self-Consistency
    result1 = await enhancer.enhance_response(
        "Реши задачу: У Маши было 5 яблок, она отдала 2. Сколько осталось?",
        "phi3.5:3.8b",
        enhancement_methods=["self_consistency", "rag", "cot"],
        task_type="reasoning",
    )
    print("Reasoning результат:", result1["response"][:200])

    # Пример 2: Coding с Speculative Decoding
    result2 = await enhancer.enhance_response(
        "Напиши функцию для сортировки списка",
        "qwen2.5-coder:32b",
        enhancement_methods=["speculative", "rag"],
        task_type="coding",
    )
    print("Coding результат:", result2["response"][:200])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
