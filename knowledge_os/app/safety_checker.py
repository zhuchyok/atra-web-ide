"""
Safety Checker для проверки качества ответов локальных моделей
Использует существующие компоненты: adversarial_critic, code_auditor
Singularity 5.0: Predictive & Adaptive Intelligence
"""

import logging
import re
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

# Опасные паттерны в коде
DANGEROUS_PATTERNS = [
    r'eval\s*\(',
    r'exec\s*\(',
    r'__import__\s*\(',
    r'os\.system\s*\(',
    r'subprocess\.call\s*\(',
    r'subprocess\.Popen\s*\(',
    r'open\s*\([^)]*[\'"]w[\'"]',  # Запись в файлы без контекста
    r'rm\s+-rf',  # Опасные команды
    r'drop\s+table',  # SQL инъекции
]

class SafetyChecker:
    """
    Легковесный checker для проверки ответов локальных моделей.
    Использует простые эвристики для быстрой проверки.
    """
    
    def __init__(self):
        self.dangerous_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in DANGEROUS_PATTERNS]
    
    def check_response(self, response: str, response_type: str = "code") -> Tuple[bool, Optional[str], float]:
        """
        Проверяет ответ на безопасность и качество.
        
        Returns:
            (is_safe, warning_message, quality_score)
            - is_safe: True если ответ безопасен
            - warning_message: Сообщение о проблеме (если есть)
            - quality_score: Оценка качества (0.0-1.0)
        """
        if not response:
            return False, "Empty response", 0.0
        
        quality_score = 1.0
        warnings = []
        
        # 1. Проверка на опасные паттерны
        for pattern in self.dangerous_patterns:
            if pattern.search(response):
                warnings.append(f"Dangerous pattern detected: {pattern.pattern}")
                quality_score -= 0.5
        
        # 2. Проверка на очевидные галлюцинации (для кода)
        if response_type == "code":
            # Проверка на placeholder'ы
            if any(placeholder in response.lower() for placeholder in ['your_code', 'table_name', 'your_function', 'TODO', 'FIXME']):
                warnings.append("Contains placeholders - likely incomplete")
                quality_score -= 0.3
            
            # Проверка на синтаксическую валидность (базовая)
            if 'def ' in response or 'class ' in response:
                # Проверяем, что есть закрывающие скобки
                open_brackets = response.count('(') + response.count('[') + response.count('{')
                close_brackets = response.count(')') + response.count(']') + response.count('}')
                if abs(open_brackets - close_brackets) > 2:
                    warnings.append("Unbalanced brackets - possible syntax error")
                    quality_score -= 0.2
        
        # 3. Проверка на минимальную длину и осмысленность
        if len(response.strip()) < 10:
            warnings.append("Response too short - likely incomplete")
            quality_score -= 0.4
        
        # 4. Проверка на повторяющиеся фразы (признак зацикливания модели)
        words = response.split()
        if len(words) > 20:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.3:
                warnings.append("High repetition - possible model loop")
                quality_score -= 0.3
        
        quality_score = max(0.0, min(1.0, quality_score))
        is_safe = quality_score >= 0.5 and len(warnings) == 0
        
        warning_message = "; ".join(warnings) if warnings else None
        
        return is_safe, warning_message, quality_score
    
    def should_reroute_to_cloud(self, response: str, response_type: str = "code") -> bool:
        """
        Определяет, нужно ли перенаправить ответ в облако для перегенерации.
        """
        is_safe, warning, score = self.check_response(response, response_type)
        
        # Перенаправляем в облако если:
        # 1. Ответ небезопасен
        # 2. Качество ниже порога
        # 3. Есть критические предупреждения
        
        if not is_safe:
            logger.warning(f"🛡️ [SAFETY CHECK FAILED] Rerouting to cloud: {warning}")
            return True
        
        if score < 0.6:
            logger.warning(f"⚠️ [LOW QUALITY] Score {score:.2f}, rerouting to cloud")
            return True
        
        return False

