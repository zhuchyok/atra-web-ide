"""
Skill Mapper — автоматический маппинг типа задачи на соответствующий скилл.
Реализует "жёсткую дисциплину скиллов" как в Cursor assistant.
"""
import re
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


# Маппинг паттернов задачи → скилл
SKILL_PATTERNS = {
    "brainstorming": {
        "patterns": [
            r"созда(й|ть|ние)\s+(новую|фичу|компонент|функци)",
            r"добав(ь|ить)\s+(новую|фичу|функционал)",
            r"разработ(ай|ать)\s+",
            r"придума(й|ть)\s+",
            r"спроектиру(й|ть)\s+",
            r"design\s+",
            r"architect",
            r"plan\s+new",
        ],
        "skill_path": "/Users/bikos/.cursor/plugins/cache/cursor-public/superpowers/*/skills/brainstorming/SKILL.md",
        "description": "Креативная задача (новая фича, компонент) — требуется brainstorming",
    },
    "tdd": {
        "patterns": [
            r"напиш(и|ать)\s+(тест|unit|интеграц)",
            r"созда(й|ть)\s+тест",
            r"test.+implement",
            r"write\s+test",
            r"add\s+test",
        ],
        "skill_path": "/Users/bikos/.cursor/plugins/cache/cursor-public/superpowers/*/skills/test-driven-development/SKILL.md",
        "description": "Задача с тестами — TDD (test before implementation)",
    },
    "debugging": {
        "patterns": [
            r"исправ(ь|ить)\s+(ошибк|баг)",
            r"почему\s+не\s+работает",
            r"ошибка\s+",
            r"провал(ился|ен)\s+тест",
            r"fix\s+bug",
            r"debug\s+",
            r"error\s+in\s+",
            r"failing\s+test",
            r"unexpected\s+behavior",
        ],
        "skill_path": "/Users/bikos/.cursor/plugins/cache/cursor-public/superpowers/*/skills/systematic-debugging/SKILL.md",
        "description": "Ошибка или баг — systematic debugging",
    },
    "verification": {
        "patterns": [
            r"проверь\s+",
            r"убед(ись|иться)\s+",
            r"тест(ы)?\s+прошли",
            r"verify\s+",
            r"check\s+if\s+",
            r"ensure\s+",
            r"confirm\s+",
            r"validate\s+",
        ],
        "skill_path": "/Users/bikos/.cursor/plugins/cache/cursor-public/superpowers/*/skills/verification-before-completion/SKILL.md",
        "description": "Проверка результата — verification before completion",
    },
    "code_review": {
        "patterns": [
            r"ревью\s+код",
            r"review\s+code",
            r"проверь\s+изменени",
            r"review\s+changes",
            r"assess\s+quality",
        ],
        "skill_path": "/Users/bikos/.cursor/plugins/cache/cursor-public/superpowers/*/skills/requesting-code-review/SKILL.md",
        "description": "Запрос ревью — requesting code review",
    },
}


class SkillMapper:
    """Определяет, какой скилл нужен для задачи."""
    
    def __init__(self):
        self.patterns = SKILL_PATTERNS
        
    def classify_task(self, goal: str) -> Optional[Dict[str, str]]:
        """
        Классифицирует задачу и возвращает соответствующий скилл.
        
        Args:
            goal: текст задачи
            
        Returns:
            {"skill": "brainstorming", "path": "...", "description": "..."}
            или None если скилл не нужен
        """
        goal_lower = goal.lower()
        
        # Проверяем каждый тип скилла
        for skill_type, config in self.patterns.items():
            for pattern in config["patterns"]:
                if re.search(pattern, goal_lower, re.IGNORECASE):
                    logger.info(
                        f"[SKILL_MAPPER] Обнаружен триггер '{skill_type}': паттерн '{pattern}' в задаче"
                    )
                    return {
                        "skill": skill_type,
                        "path": config["skill_path"],
                        "description": config["description"],
                    }
                    
        # Дополнительная эвристика: если упоминается "new" + существительное
        if re.search(r"\bnew\s+\w+(ion|ent|ure|ity)\b", goal_lower):
            logger.info("[SKILL_MAPPER] Эвристика: 'new + noun' → brainstorming")
            return {
                "skill": "brainstorming",
                "path": self.patterns["brainstorming"]["skill_path"],
                "description": self.patterns["brainstorming"]["description"],
            }
            
        return None
        
    def should_invoke_skill(self, goal: str, force: bool = False) -> bool:
        """
        Правило "1% шанс = вызывать скилл".
        
        Args:
            goal: текст задачи
            force: принудительный вызов (для тестов)
            
        Returns:
            True если нужно вызвать скилл
        """
        if force:
            return True
            
        skill_info = self.classify_task(goal)
        return skill_info is not None
        
    def get_skill_instructions(self, skill_type: str) -> str:
        """
        Возвращает краткие инструкции для скилла.
        (Полная загрузка SKILL.md — в отдельном модуле)
        """
        instructions = {
            "brainstorming": (
                "1. Изучи контекст проекта\n"
                "2. Задай 1 уточняющий вопрос (цель, ограничения)\n"
                "3. Предложи 2-3 подхода с плюсами/минусами\n"
                "4. Представь дизайн по секциям, спрашивай одобрение после каждой\n"
                "5. Запиши утверждённый дизайн в docs/plans/YYYY-MM-DD-<topic>-design.md\n"
                "6. Следующий шаг — writing-plans (план внедрения), НЕ код"
            ),
            "tdd": (
                "1. Напиши тест ДО реализации (test first)\n"
                "2. Запусти тест → убедись что failed\n"
                "3. Напиши минимальный код для прохождения теста\n"
                "4. Refactor (при необходимости)\n"
                "5. Повтори цикл Red-Green-Refactor"
            ),
            "debugging": (
                "1. Воспроизведи ошибку (minimal reproducible example)\n"
                "2. Изучи логи/traceback\n"
                "3. Сформулируй гипотезу (что сломано?)\n"
                "4. Проверь гипотезу (добавь логи, breakpoints)\n"
                "5. Исправь причину (не симптом!)\n"
                "6. Добавь тест для регрессии"
            ),
            "verification": (
                "1. Запусти все затронутые тесты\n"
                "2. Проверь линты (ReadLints)\n"
                "3. Подтверди что фича работает (manual QA)\n"
                "4. Проверь что не сломалось смежное\n"
                "5. ТОЛЬКО после проверки — заявляй о завершении"
            ),
            "code_review": (
                "1. Проверь соответствие требованиям\n"
                "2. Оцени архитектуру (SOLID, KISS, DRY)\n"
                "3. Проверь безопасность (secrets, SQL injection, XSS)\n"
                "4. Проверь тесты и покрытие\n"
                "5. Дай конструктивный feedback"
            ),
        }
        return instructions.get(skill_type, "")


# Singleton instance
_skill_mapper = None


def get_skill_mapper() -> SkillMapper:
    """Возвращает singleton instance SkillMapper."""
    global _skill_mapper
    if _skill_mapper is None:
        _skill_mapper = SkillMapper()
    return _skill_mapper
