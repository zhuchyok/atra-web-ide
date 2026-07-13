"""
[SINGULARITY 28.X] Symbol Tuning - управление поведением агентов.
Позволяет явным образом управлять стилем и поведением агентов через symbols.
"""

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger("SymbolTuner")

# Symbol tuning prompts - явные инструкции для изменения поведения
TUNING_SYMBOLS = {
    "concise": {
        "symbol": "📏",
        "prompt_modifier": "Отвечай КРАТКО и ПО СУЩЕСТВУ. Максимум 2-3 предложения. Без лишних слов.",
        "description": "Краткий ответ без воды",
    },
    "detailed": {
        "symbol": "📚",
        "prompt_modifier": "Отвечай ПОДРОБНО с техническими деталями. Приводи примеры кода и ссылки на документацию.",
        "description": "Детальный технический ответ",
    },
    "creative": {
        "symbol": "🎨",
        "prompt_modifier": "Используй НЕСТАНДАРТНЫЕ подходы и аналогии. Предлагай неочевидные решения.",
        "description": "Креативный подход",
    },
    "diplomatic": {
        "symbol": "🤝",
        "prompt_modifier": "Будь ВЕЖЛИВ и учитывай эмоции собеседника. Предлагай решения, а не критикуй.",
        "description": "Дипломатичный стиль",
    },
    "technical": {
        "symbol": "⚙️",
        "prompt_modifier": "Отвечай С ТЕХНИЧЕСКИМИ деталями. Используй код, схемы, API названия.",
        "description": "Технический стиль",
    },
    "educational": {
        "symbol": "🎓",
        "prompt_modifier": "Обучай пользователя. Объясняй принципы работы, а не просто давай ответ.",
        "description": "Образовательный стиль",
    },
    "fast": {
        "symbol": "🚀",
        "prompt_modifier": "Действуй БЫСТРО. Минимум рассуждений - максимум результата.",
        "description": "Быстрый результат",
    },
    "safe": {
        "symbol": "🛡️",
        "prompt_modifier": "Проверяй БЕЗОПАСНОСТЬ перед каждым действием. Предотвращай ошибки.",
        "description": "Безопасный стиль",
    },
}

# Expert default behaviors
EXPERT_DEFAULT_BEHAVIORS = {
    "Виктория": ["detailed", "safe"],
    "Игорь": ["technical", "detailed"],
    "Анна": ["educational", "detailed"],
    "Дмитрий": ["technical", "concise"],
    "Сергей": ["creative", "fast"],
    "Екатерина": ["diplomatic", "safe"],
}


class SymbolTuner:
    """
    [SINGULARITY 28.X] Symbol Tuner for behavior control.
    """

    def __init__(self):
        self.symbols = TUNING_SYMBOLS
        self.expert_behaviors = EXPERT_DEFAULT_BEHAVIORS

    def get_available_symbols(self) -> List[str]:
        """Return list of available tuning symbols."""
        return list(self.symbols.keys())

    def get_symbol_prompt(self, symbol: str) -> Optional[str]:
        """Get prompt modifier for a symbol."""
        if symbol in self.symbols:
            return self.symbols[symbol]["prompt_modifier"]
        return None

    def apply_symbols(self, prompt: str, symbols: List[str]) -> str:
        """Apply symbol modifiers to a prompt."""
        if not symbols:
            return prompt

        modifiers = []
        for symbol in symbols:
            if symbol in self.symbols:
                modifiers.append(self.symbols[symbol]["prompt_modifier"])

        if modifiers:
            modifier_text = "\n".join(modifiers)
            return f"{prompt}\n\n### Symbol Tuning:\n{modifier_text}"

        return prompt

    def get_expert_default_symbols(self, expert_name: str) -> List[str]:
        """Get default behavior symbols for an expert."""
        return self.expert_behaviors.get(expert_name, ["concise"])

    def tune_for_task(self, task_type: str, category: str = "general") -> List[str]:
        """Suggest symbols for a task type."""
        # Task-type based tuning
        task_symbols = {
            "coding": ["technical", "safe"],
            "analysis": ["detailed", "educational"],
            "search": ["concise", "fast"],
            "creative": ["creative"],
            "debate": ["diplomatic", "detailed"],
            "review": ["detailed", "safe"],
            "debug": ["technical", "concise"],
            "explain": ["educational", "detailed"],
        }

        default_symbols = task_symbols.get(category, ["concise"])

        # Adjust based on task type
        if "write" in task_type.lower() or "create" in task_type.lower():
            return ["technical", "detailed"]
        elif "fix" in task_type.lower() or "debug" in task_type.lower():
            return ["technical", "safe"]
        elif "explain" in task_type.lower() or "learn" in task_type.lower():
            return ["educational"]

        return default_symbols

    def format_symbols_for_prompt(self, symbols: List[str]) -> str:
        """Format symbols as a readable prompt section."""
        if not symbols:
            return ""

        lines = ["### 🎯 Symbol Tuning Applied:"]
        for symbol in symbols:
            if symbol in self.symbols:
                s = self.symbols[symbol]
                lines.append(f"- {s['symbol']} **{symbol}**: {s['description']}")

        return "\n".join(lines)


_symbol_tuner = None


def get_symbol_tuner() -> SymbolTuner:
    """Get singleton SymbolTuner instance."""
    global _symbol_tuner
    if _symbol_tuner is None:
        _symbol_tuner = SymbolTuner()
    return _symbol_tuner
