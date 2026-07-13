"""
Token Efficiency Audit (Singularity 21.32)
Механизм отсечения избыточных слов и фраз для экономии контекста.
"""

import logging
import re

logger = logging.getLogger(__name__)


class TokenAuditor:
    """Аудитор эффективности токенов."""

    def __init__(self):
        # Фразы-паразиты и избыточные конструкции
        self.redundant_patterns = [
            r"пожалуйста,\s+",
            r"будьте\s+добры,\s+",
            r"я\s+хотел\s+бы\s+попросить\s+вас\s+",
            r"не\s+могли\s+бы\s+вы\s+",
            r"в\s+данный\s+момент\s+",
            r"как\s+можно\s+скорее",
            r"заранее\s+спасибо",
            r"с\s+уважением",
        ]

    def apply_chain_of_density(self, text: str, iterations: int = 3) -> str:
        """
        [SINGULARITY 21.33] Chain of Density (CoD):
        Делает текст более информативным, заменяя общие фразы на конкретные сущности.
        """
        if not text or len(text) < 100:
            return text

        logger.info(f"🧬 [CoD] Applying Chain of Density (iterations={iterations})")
        # В реальности CoD требует вызова LLM, здесь мы реализуем логику
        # подготовки инструкций для модели, чтобы она сама применяла CoD.
        cod_instruction = f"""
        ### [SYSTEM: CHAIN OF DENSITY ENABLED]
        Сделай свой ответ максимально информативным (Entity-Dense).
        1. Напиши краткий ответ.
        2. Выдели 3-5 ключевых сущностей (entities), которые были упущены.
        3. Перепиши ответ, вставив эти сущности, сохраняя ту же длину.
        Повтори {iterations} раза. Верни только финальный, максимально плотный текст.
        """
        return f"{cod_instruction}\n\n{text}"

    def audit_prompt(self, prompt: str) -> str:
        """Очищает промпт от избыточных токенов и вредоносных символов."""
        if not prompt:
            return ""

        original_len = len(prompt)
        cleaned_prompt = prompt

        # [SINGULARITY 21.36] Защита от Zero-Width Steganography
        # Удаляем невидимые символы Unicode, которые могут содержать скрытые команды
        zero_width_pattern = r"[\u200B-\u200D\uFEFF]"
        cleaned_prompt = re.sub(zero_width_pattern, "", cleaned_prompt)

        for pattern in self.redundant_patterns:
            cleaned_prompt = re.sub(pattern, "", cleaned_prompt, flags=re.IGNORECASE)

        # Удаляем лишние пробелы
        cleaned_prompt = re.sub(r"\s+", " ", cleaned_prompt).strip()

        new_len = len(cleaned_prompt)
        if original_len > new_len:
            tokens_saved = (original_len - new_len) // 4
            logger.info(f"[TOKEN AUDIT] Saved ~{tokens_saved} tokens by removing redundancies")

        return cleaned_prompt


_auditor = TokenAuditor()


def audit_efficiency(prompt: str) -> str:
    """Выполняет аудит эффективности промпта."""
    return _auditor.audit_prompt(prompt)
