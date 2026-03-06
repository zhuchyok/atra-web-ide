import asyncio
import logging
import os

# Абсолютные импорты (для тестов)
try:
    from knowledge_os.app.ai_core import _run_cloud_agent_async, run_smart_agent_async
    from knowledge_os.app.local_router import LocalAIRouter
except ImportError:
    # Fallback для запуска из app/
    from ai_core import _run_cloud_agent_async, run_smart_agent_async  # type: ignore
    from local_router import LocalAIRouter  # type: ignore

logger = logging.getLogger(__name__)

# Environment flags
try:
    from knowledge_os.app.env_flags import is_strict_local
except ImportError:
    try:
        from env_flags import is_strict_local  # type: ignore
    except ImportError:
        # Fallback если модуль не найден
        def is_strict_local():
            return os.getenv("STRICT_LOCAL", "").lower() in ("1", "true", "yes")


class IntelligenceConsensus:
    """
    High-stakes decision engine. Runs both Local (L1) and Cloud (L2)
    models and compares results to ensure maximum quality.
    """

    async def get_consensus(self, prompt: str, expert_name: str = "Виктория"):
        """
        Run both models and find agreement.
        В STRICT_LOCAL режиме выполняет два локальных вызова вместо local + cloud.
        """
        router = LocalAIRouter()

        # В STRICT_LOCAL режиме: два локальных вызова с разными категориями
        if is_strict_local():
            logger.info("[STRICT_LOCAL] Consensus using two local calls (reasoning + coding)")

            # Два локальных вызова: reasoning и coding
            local_reasoning_task = router.run_local_llm(prompt, category="reasoning")
            local_coding_task = router.run_local_llm(prompt, category="coding")

            local_resp_1, local_resp_2 = await asyncio.gather(
                local_reasoning_task, local_coding_task
            )

            if not local_resp_1 and not local_resp_2:
                logger.error("[STRICT_LOCAL] Both local calls failed")
                return (
                    "⚠️ Локальные модели недоступны для консенсуса (STRICT_LOCAL). "
                    "Проверьте MLX/Ollama."
                ), "Consensus failed (STRICT_LOCAL)"

            # Если один из ответов пустой, используем непустой
            if not local_resp_1:
                return local_resp_2, "Consensus (Coding only, STRICT_LOCAL)"
            if not local_resp_2:
                return local_resp_1, "Consensus (Reasoning only, STRICT_LOCAL)"

            # Кросс-проверка: используем reasoning модель для синтеза
            cross_check_prompt = f"""
            ВЫ - ВЫСШИЙ СУДЬЯ ИИ (УРОВЕНЬ 5).
            ЗАДАЧА: Сравните два ответа эксперта {expert_name} на один и тот же запрос и сформируйте финальный, идеальный ответ.

            ЗАПРОС: {prompt}
            ОТВЕТ А (Reasoning): {local_resp_1}
            ОТВЕТ Б (Coding): {local_resp_2}

            ИНСТРУКЦИЯ:
            1. Если они согласны, объедините их в лучший текст.
            2. Если они противоречат, выберите более логичный и безопасный.
            3. Сохраните стиль ATRA.
            """

            final_resp = await router.run_local_llm(cross_check_prompt, category="reasoning")
            return final_resp, "Consensus (Local only, STRICT_LOCAL)"

        # Обычный режим: Local + Cloud
        # For consensus, always use the most powerful local model (Reasoning)
        local_task = router.run_local_llm(prompt, category="reasoning")
        cloud_task = _run_cloud_agent_async(prompt)

        local_resp, cloud_resp = await asyncio.gather(local_task, cloud_task)

        if not local_resp:
            return cloud_resp, "Cloud only (Local failed)"

        # Cross-check prompt
        cross_check_prompt = f"""
        ВЫ - ВЫСШИЙ СУДЬЯ ИИ (УРОВЕНЬ 5).
        ЗАДАЧА: Сравните два ответа эксперта {expert_name} на один и тот же запрос и сформируйте финальный, идеальный ответ.

        ЗАПРОС: {prompt}
        ОТВЕТ А (Локальный): {local_resp}
        ОТВЕТ Б (Облачный): {cloud_resp}

        ИНСТРУКЦИЯ:
        1. Если они согласны, объедините их в лучший текст.
        2. Если они противоречат, выберите более логичный и безопасный (обычно облачный).
        3. Сохраните стиль ATRA.
        """

        final_resp = await _run_cloud_agent_async(cross_check_prompt)
        return final_resp, "Consensus (Local + Cloud)"


if __name__ == "__main__":
    consensus = IntelligenceConsensus()
    # asyncio.run(consensus.get_consensus("Проверь стратегию risk-management"))
