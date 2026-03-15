import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EnsembleVerifier:
    """
    [SINGULARITY 21.22] Logic for cross-verification and refinement.
    """

    def __init__(self, router, expert_name: str):
        self.router = router
        self.expert_name = expert_name

    async def verify_and_refine(
        self, initial_prompt: str, initial_response: str, depth: int = 0
    ) -> str:
        if depth >= 1:
            return initial_response

        logger.info(f"🧠 [ENSEMBLE] Verifying response for {self.expert_name}")

        verify_prompt = f"""Ты - AI-аудитор. Проверь ответ на наличие критических ошибок, галлюцинаций или нарушения логики.
ЗАПРОС ПОЛЬЗОВАТЕЛЯ: {initial_prompt}
ОТВЕТ ДЛЯ ПРОВЕРКИ: {initial_response}

Если всё верно, напиши 'OK'. Если есть ошибка, опиши её кратко и предложи исправление."""

        try:
            if self.router:
                verify_result = await self.router.run_local_llm(
                    verify_prompt, category="general", model_hint="lfm2.5-thinking:1.2b"
                )
                verify_text = (
                    verify_result[0] if isinstance(verify_result, tuple) else verify_result
                )

                if verify_text and "OK" not in verify_text.upper()[:10]:
                    logger.warning(f"⚠️ [ENSEMBLE] Critic found issues: {verify_text[:100]}...")

                    refine_prompt = f"""Основная модель выдала ответ с ошибкой. Исправь его, учитывая замечания критика.
ЗАМЕЧАНИЯ КРИТИКА: {verify_text}
ИСХОДНЫЙ ЗАПРОС: {initial_prompt}
ИСПРАВЬ И ВЕРНИ ПОЛНЫЙ ОТВЕТ:"""

                    refined_result = await self.router.run_local_llm(
                        refine_prompt, category="coding"
                    )
                    return (
                        refined_result[0] if isinstance(refined_result, tuple) else refined_result
                    )
            return initial_response
        except Exception as e:
            logger.error(f"❌ [ENSEMBLE] Verification error: {e}")
            return initial_response
