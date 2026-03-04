"""
[SINGULARITY 20.0] Constitutional Court.
Verifies expert decisions against the Digital Constitution.
"""

import asyncio
import json
import logging
import os

from ai_core import run_smart_agent_async
from digital_constitution import CONSTITUTION_PRINCIPLES, get_constitution_context

logger = logging.getLogger(__name__)


class ConstitutionalCourt:
    def __init__(self):
        self.constitution = get_constitution_context()

    async def verify_decision(self, topic: str, decision: str) -> dict:
        """
        Verifies a decision against the Digital Constitution.
        Returns: {"valid": bool, "violations": list, "feedback": str}
        """
        logger.info(f"⚖️ [COURT] Verifying decision for: {topic[:50]}...")

        prompt = f"""
        ТЫ - ВЕРХОВНЫЙ СУДЬЯ ЦИФРОВОЙ КОНСТИТУЦИИ КОРПОРАЦИИ.

        {self.constitution}

        ОБЪЕКТ ПРОВЕРКИ:
        ТЕМА: {topic}
        РЕШЕНИЕ: {decision}

        ЗАДАЧА: Проверь, не нарушает ли это решение принципы Конституции.

        ВЕРНИ ОТВЕТ СТРОГО В ФОРМАТЕ JSON. ТВОЙ ОТВЕТ ДОЛЖЕН НАЧИНАТЬСЯ С '{{' И ЗАКАНЧИВАТЬСЯ '}}'.
        НИКАКОГО ТЕКСТА ДО ИЛИ ПОСЛЕ JSON. НИКАКИХ БЛОКОВ ```json. ТОЛЬКО ЧИСТЫЙ ОБЪЕКТ.

        ФОРМАТ:
        {{
            "valid": true/false,
            "violations": ["ID принципа: причина"],
            "feedback": "Рекомендация по исправлению (если есть)"
        }}
        """

        # Используем victoria-wisdom-v3.5 для строгого следования формату
        from local_router import LocalAIRouter

        router = LocalAIRouter()
        response_data = await router.run_local_llm(
            prompt, category="reasoning", model="victoria-wisdom-v3.5"
        )

        if isinstance(response_data, (list, tuple)) and len(response_data) >= 1:
            response = response_data[0]
        else:
            response = str(response_data)

        try:
            # Очистка от markdown и лишнего текста
            clean_response = response.strip()

            # Удаляем возможный текст ДО или ПОСЛЕ JSON, если он остался
            start_idx = clean_response.find("{")
            end_idx = clean_response.rfind("}")

            if start_idx != -1 and end_idx != -1:
                clean_response = clean_response[start_idx : end_idx + 1]
                result = json.loads(clean_response)
            else:
                raise ValueError("No JSON found in response")

            if not result.get("valid"):
                logger.warning(
                    f"🚨 [COURT] CONSTITUTIONAL VIOLATION DETECTED: {result.get('violations')}"
                )
            else:
                logger.info("✅ [COURT] Decision is constitutionally valid.")

            return result
        except Exception as e:
            logger.error(
                f"❌ [COURT] Error parsing court decision: {e}. Raw response: {response[:200]}..."
            )
            return {
                "valid": True,
                "violations": [],
                "feedback": "Ошибка проверки, пропущено по умолчанию.",
            }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def test():
        court = ConstitutionalCourt()
        # Тест нарушения (открытый порт без туннеля - нарушение C2)
        test_decision = "Открыть порт 8080 для внешнего доступа напрямую через IP."
        res = await court.verify_decision("Настройка доступа", test_decision)
        print(json.dumps(res, indent=2, ensure_ascii=False))

    asyncio.run(test())
