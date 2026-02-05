"""
Anomaly Detector для детектирования аномалий в запросах.
Обнаруживает подозрительные паттерны: DDoS, brute force, инъекции.
"""

import asyncio
import os
import logging
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

@dataclass
class AnomalyAlert:
    """Алерт об аномалии"""
    anomaly_type: str  # 'ddos', 'brute_force', 'injection', 'rate_spike'
    severity: str  # 'high', 'medium', 'low'
    description: str
    detected_at: datetime
    metadata: Dict[str, Any]

class AnomalyDetector:
    """
    Детектор аномалий в запросах.
    Обнаруживает подозрительные паттерны и блокирует их.
    """
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        
        # Окна для анализа (скользящие окна)
        self.request_history: deque = deque(maxlen=1000)  # Последние 1000 запросов
        self.request_counts: Dict[str, int] = defaultdict(int)  # Счетчики по IP/пользователю
        
        # Пороги для детектирования
        self.thresholds = {
            "requests_per_minute": 60,  # Более 60 запросов в минуту = подозрительно
            "requests_per_hour": 500,  # Более 500 запросов в час = подозрительно
            "repeated_prompts": 10,  # Более 10 одинаковых промптов = brute force
            "injection_patterns": [
                r"<script[^>]*>",
                r"javascript:",
                r"onerror\s*=",
                r"union\s+select",
                r"drop\s+table",
                r"exec\s*\(",
                r"eval\s*\(",
                r"system\s*\(",
                r"__import__",
                r"subprocess"
            ]
        }
        
        self.blocked_ips: Dict[str, datetime] = {}  # Заблокированные IP
        self.block_duration = timedelta(hours=1)  # Длительность блокировки
    
    def detect_injection(self, prompt: str) -> Tuple[bool, Optional[str]]:
        """Детектирует попытки инъекций в промпт"""
        prompt_lower = prompt.lower()
        
        for pattern in self.thresholds["injection_patterns"]:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                return True, f"Обнаружен паттерн инъекции: {pattern}"
        
        # Проверка на подозрительные последовательности
        suspicious_sequences = [
            "'; drop",
            "'; delete",
            "'; update",
            "'; insert",
            "'; exec",
            "'; eval",
            "<script>",
            "javascript:alert"
        ]
        
        for seq in suspicious_sequences:
            if seq in prompt_lower:
                return True, f"Обнаружена подозрительная последовательность: {seq}"
        
        return False, None
    
    def detect_repeated_prompts(self, prompt: str, time_window: int = 300) -> Tuple[bool, int]:
        """
        Детектирует повторяющиеся промпты (brute force).
        
        Returns:
            (is_anomaly, count)
        """
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(seconds=time_window)
        
        # Подсчитываем одинаковые промпты в окне времени
        prompt_hash = hash(prompt.strip().lower())
        count = sum(
            1 for req_time, req_hash in self.request_history
            if req_time > cutoff_time and req_hash == prompt_hash
        )
        
        is_anomaly = count >= self.thresholds["repeated_prompts"]
        return is_anomaly, count
    
    def detect_rate_spike(
        self,
        identifier: str,  # IP или user_id
        time_window: int = 60
    ) -> Tuple[bool, int]:
        """
        Детектирует резкий рост запросов (DDoS).
        
        Returns:
            (is_anomaly, request_count)
        """
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(seconds=time_window)
        
        # Подсчитываем запросы в окне времени
        count = sum(
            1 for req_time, req_id in self.request_history
            if req_time > cutoff_time and req_id == identifier
        )
        
        threshold = self.thresholds["requests_per_minute"] if time_window == 60 else self.thresholds["requests_per_hour"]
        is_anomaly = count >= threshold
        
        return is_anomaly, count
    
    async def analyze_request(
        self,
        prompt: str,
        identifier: str = "unknown",  # IP или user_id
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[AnomalyAlert]]:
        """
        Анализирует запрос на наличие аномалий.
        
        Returns:
            (should_block, alert)
        """
        current_time = datetime.now()
        
        # Добавляем запрос в историю
        prompt_hash = hash(prompt.strip().lower())
        self.request_history.append((current_time, prompt_hash))
        self.request_counts[identifier] += 1
        
        # ВАЖНО: Запросы от worker/экспертов (tasks) НИКОГДА не блокируем
        # Иначе все задачи уходят в deferred_to_human
        if metadata and metadata.get('expert_name'):
            logger.debug(f"🔄 [ANOMALY] Пропуск проверок для эксперта: {metadata.get('expert_name')}")
            return False, None
        
        alerts = []
        
        # 1. Проверка на инъекции
        has_injection, injection_reason = self.detect_injection(prompt)
        if has_injection:
            alert = AnomalyAlert(
                anomaly_type="injection",
                severity="high",
                description=f"Попытка инъекции: {injection_reason}",
                detected_at=current_time,
                metadata={"prompt_preview": prompt[:100], "identifier": identifier}
            )
            alerts.append(alert)
            await self._log_anomaly(alert)
            return True, alert
        
        # 2. Проверка на повторяющиеся промпты (brute force)
        # ИСКЛЮЧЕНИЕ: Внутренние системные запросы (worker, эксперты) НИКОГДА не блокируются
        _internal_categories = {'task_processing', 'research', 'internal', 'autonomous_worker', 'orchestrator', 'planning', 'execution', 'synthesis', 'report', 'architecture'}
        is_internal_request = (
            (metadata and (
                metadata.get('expert_name') or  # Запрос от эксперта (Ирина, Виктория, etc.)
                metadata.get('category') in _internal_categories or
                (isinstance(metadata.get('category'), str) and (metadata.get('category') or '').startswith('task_'))
            )) or
            (identifier and (
                identifier.startswith('worker_') or
                identifier.startswith('expert_') or
                identifier.startswith('Виктория_') or  # ai_core: expert_name_timestamp
                identifier == 'unknown'
            ))
        )
        
        is_repeated, repeat_count = self.detect_repeated_prompts(prompt)
        if is_repeated and not is_internal_request:
            alert = AnomalyAlert(
                anomaly_type="brute_force",
                severity="high",
                description=f"Обнаружен brute force: {repeat_count} одинаковых запросов за 5 минут",
                detected_at=current_time,
                metadata={"repeat_count": repeat_count, "identifier": identifier}
            )
            alerts.append(alert)
            await self._log_anomaly(alert)
            return True, alert
        elif is_repeated and is_internal_request:
            # Логируем, но не блокируем внутренние запросы
            logger.debug(f"🔄 [ANOMALY] Пропускаем внутренний запрос (repeat_count={repeat_count})")
        
        # 3. Проверка на резкий рост запросов (DDoS)
        is_rate_spike, request_count = self.detect_rate_spike(identifier, time_window=60)
        if is_rate_spike:
            alert = AnomalyAlert(
                anomaly_type="rate_spike",
                severity="high" if request_count > 100 else "medium",
                description=f"Резкий рост запросов: {request_count} запросов за минуту",
                detected_at=current_time,
                metadata={"request_count": request_count, "identifier": identifier}
            )
            alerts.append(alert)
            await self._log_anomaly(alert)
            
            # Блокируем при критическом уровне
            if request_count > 100:
                self.blocked_ips[identifier] = current_time
                return True, alert
        
        # 4. Проверка на длинные промпты (возможная атака на ресурсы)
        if len(prompt) > 50000:  # Очень длинный промпт
            alert = AnomalyAlert(
                anomaly_type="resource_attack",
                severity="medium",
                description=f"Подозрительно длинный промпт: {len(prompt)} символов",
                detected_at=current_time,
                metadata={"prompt_length": len(prompt), "identifier": identifier}
            )
            alerts.append(alert)
            await self._log_anomaly(alert)
        
        # Если есть алерты, но не критичные, возвращаем False (не блокируем)
        if alerts:
            return False, alerts[0]
        
        return False, None
    
    def is_blocked(self, identifier: str) -> bool:
        """Проверяет, заблокирован ли идентификатор"""
        if identifier not in self.blocked_ips:
            return False
        
        block_time = self.blocked_ips[identifier]
        if datetime.now() - block_time > self.block_duration:
            # Блокировка истекла
            del self.blocked_ips[identifier]
            return False
        
        return True
    
    async def _log_anomaly(self, alert: AnomalyAlert):
        """Логирует аномалию в БД"""
        if not ASYNCPG_AVAILABLE:
            return
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                await conn.execute("""
                    INSERT INTO anomaly_detection_logs
                    (anomaly_type, severity, description, metadata, detected_at)
                    VALUES ($1, $2, $3, $4, $5)
                """,
                alert.anomaly_type, alert.severity, alert.description,
                json.dumps(alert.metadata), alert.detected_at)
                
                logger.warning(f"🚨 [ANOMALY DETECTOR] {alert.anomaly_type}: {alert.description}")
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сохранить аномалию в БД: {e}")
    
    async def get_anomaly_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Получает статистику по аномалиям за указанный период"""
        if not ASYNCPG_AVAILABLE:
            return {}
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                rows = await conn.fetch("""
                    SELECT 
                        anomaly_type,
                        severity,
                        COUNT(*) as count
                    FROM anomaly_detection_logs
                    WHERE detected_at > NOW() - INTERVAL '1 hour' * $1
                    GROUP BY anomaly_type, severity
                    ORDER BY count DESC
                """, hours)
                
                stats = {}
                for row in rows:
                    key = f"{row['anomaly_type']}_{row['severity']}"
                    stats[key] = row['count']
                
                return stats
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики аномалий: {e}")
            return {}

# Глобальный экземпляр
_anomaly_detector: Optional[AnomalyDetector] = None

def get_anomaly_detector() -> AnomalyDetector:
    """Получить глобальный экземпляр AnomalyDetector"""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector

