"""
Threat Detector для детектирования угроз безопасности.
Улучшенная версия с интеграцией в anomaly_detector и логированием.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


class ThreatType(Enum):
    DATA_LEAK = "data_leak"
    PROMPT_INJECTION = "prompt_injection"
    MODEL_POISONING = "model_poisoning"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


class ThreatSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatDetector:
    """Детектор угроз безопасности"""

    # Паттерны для детектирования
    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+(previous|above|all)\s+instructions?",
        r"system\s*:\s*",
        r"<\|.*?\|>",
        r"\[INST\]",
    ]

    SENSITIVE_DATA_PATTERNS = [
        r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",  # Credit card
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email (может быть ложное срабатывание)
        r"password\s*[:=]\s*\S+",
        r"api[_-]?key\s*[:=]\s*\S+",
    ]

    def detect_prompt_injection(self, text: str) -> Optional[Dict]:
        """Детектировать prompt injection"""
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return {
                    "threat_type": ThreatType.PROMPT_INJECTION.value,
                    "severity": ThreatSeverity.HIGH.value,
                    "pattern": pattern,
                    "matched_text": re.search(pattern, text, re.IGNORECASE).group(0),
                }
        return None

    def detect_data_leak(self, text: str) -> Optional[Dict]:
        """Детектировать утечку данных"""
        for pattern in self.SENSITIVE_DATA_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return {
                    "threat_type": ThreatType.DATA_LEAK.value,
                    "severity": ThreatSeverity.MEDIUM.value,
                    "pattern": pattern,
                    "matches_count": len(matches),
                }
        return None

    def detect_resource_exhaustion(
        self, prompt_length: int, response_length: int
    ) -> Optional[Dict]:
        """Детектировать попытку исчерпания ресурсов"""
        if prompt_length > 50000:  # Очень длинный промпт
            return {
                "threat_type": ThreatType.RESOURCE_EXHAUSTION.value,
                "severity": ThreatSeverity.MEDIUM.value,
                "prompt_length": prompt_length,
            }
        return None

    def analyze(self, query: str, response: str = "") -> List[Dict]:
        """Проанализировать на наличие угроз"""
        threats = []

        # Проверка промпта
        prompt_threat = self.detect_prompt_injection(query)
        if prompt_threat:
            prompt_threat["detected_in"] = "query"
            threats.append(prompt_threat)

        data_leak = self.detect_data_leak(response or query)
        if data_leak:
            data_leak["detected_in"] = "response" if response else "query"
            threats.append(data_leak)

        resource = self.detect_resource_exhaustion(len(query), len(response))
        if resource:
            resource["detected_in"] = "query"
            threats.append(resource)

        # Логируем угрозы в БД
        if threats:
            asyncio.create_task(self._log_threats(threats, query, response))

        return threats

    async def _log_threats(self, threats: List[Dict], query: str, response: str):
        """Логирует угрозы в БД"""
        if not ASYNCPG_AVAILABLE:
            return

        try:
            conn = await asyncpg.connect(DB_URL)
            try:
                for threat in threats:
                    await conn.execute(
                        """
                        INSERT INTO anomaly_detection_logs
                        (anomaly_type, severity, description, metadata, detected_at)
                        VALUES ($1, $2, $3, $4, NOW())
                    """,
                        threat.get("threat_type", "unknown"),
                        threat.get("severity", "medium"),
                        f"Обнаружена угроза: {threat.get('threat_type', 'unknown')}",
                        json.dumps(
                            {
                                "threat": threat,
                                "query_preview": query[:200],
                                "response_preview": response[:200] if response else None,
                            }
                        ),
                    )

                logger.warning(f"🚨 [THREAT DETECTOR] Обнаружено {len(threats)} угроз")
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сохранить угрозы в БД: {e}")


# Глобальный экземпляр
_threat_detector: Optional[ThreatDetector] = None


def get_threat_detector() -> ThreatDetector:
    """Получить глобальный экземпляр ThreatDetector"""
    global _threat_detector
    if _threat_detector is None:
        _threat_detector = ThreatDetector()
    return _threat_detector
