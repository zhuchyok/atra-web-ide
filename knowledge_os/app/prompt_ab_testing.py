"""
Prompt A/B Testing System
Система A/B тестирования промптов для автоматического выбора лучших вариантов
AGENT IMPROVEMENTS: A/B Testing для промптов
"""

import asyncio
import logging
import os
import json
import hashlib
import random
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from collections import defaultdict

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
class PromptVariant:
    """Вариант промпта для A/B тестирования"""
    variant_id: str
    prompt_text: str
    version: str
    created_at: datetime
    metadata: Dict[str, Any]  # Дополнительные метаданные

@dataclass
class ABTestResult:
    """Результат A/B теста"""
    test_id: str
    variant_a_id: str
    variant_b_id: str
    variant_a_metrics: Dict[str, float]  # quality, speed, tokens
    variant_b_metrics: Dict[str, float]
    winner: Optional[str]  # 'A', 'B', или None (ничья)
    confidence: float  # Уровень уверенности (0-1)
    total_samples: int
    created_at: datetime

class PromptABTesting:
    """
    Система A/B тестирования промптов.
    
    Функционал:
    - Создание вариантов промптов
    - Случайное распределение запросов между вариантами
    - Сбор метрик (качество, скорость, токены)
    - Автоматический выбор победителя на основе метрик
    - Автоматическое применение лучшего варианта
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        self._active_tests: Dict[str, Dict[str, Any]] = {}  # test_id -> test_config
        self._variant_cache: Dict[str, PromptVariant] = {}
        
    async def _get_conn(self):
        """Получить подключение к БД"""
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg is not installed. Database connection unavailable.")
            return None
        try:
            conn = await asyncpg.connect(self.db_url)
            return conn
        except Exception as e:
            logger.error(f"❌ [AB TEST] Ошибка подключения к БД: {e}")
            return None
    
    async def create_prompt_variant(
        self,
        prompt_text: str,
        version: str = "v1",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Создает новый вариант промпта.
        
        Args:
            prompt_text: Текст промпта
            version: Версия промпта
            metadata: Дополнительные метаданные
        
        Returns:
            variant_id
        """
        try:
            # Генерируем ID на основе текста и версии
            variant_key = f"{prompt_text}:{version}"
            variant_id = hashlib.md5(variant_key.encode()).hexdigest()[:16]
            
            variant = PromptVariant(
                variant_id=variant_id,
                prompt_text=prompt_text,
                version=version,
                created_at=datetime.now(timezone.utc),
                metadata=metadata or {}
            )
            
            # Сохраняем в БД
            conn = await self._get_conn()
            if not conn:
                return variant_id
            
            try:
                # Проверяем наличие таблицы prompt_variants
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'prompt_variants'
                    )
                """)
                
                if table_exists:
                    await conn.execute("""
                        INSERT INTO prompt_variants (variant_id, prompt_text, version, created_at, metadata)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (variant_id) DO UPDATE
                        SET prompt_text = EXCLUDED.prompt_text, metadata = EXCLUDED.metadata
                    """, variant_id, prompt_text, version, variant.created_at, json.dumps(metadata or {}))
                
                # Обновляем кэш
                self._variant_cache[variant_id] = variant
                
                logger.info(f"✅ [AB TEST] Создан вариант промпта {variant_id} (версия {version})")
                return variant_id
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [AB TEST] Ошибка создания варианта промпта: {e}")
            return ""
    
    async def start_ab_test(
        self,
        variant_a_id: str,
        variant_b_id: str,
        test_name: str = "prompt_ab_test",
        traffic_split: float = 0.5,  # 50/50 по умолчанию
        min_samples: int = 100,  # Минимум выборок для статистической значимости
        metrics_weights: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Запускает A/B тест между двумя вариантами промптов.
        
        Args:
            variant_a_id: ID варианта A
            variant_b_id: ID варианта B
            test_name: Название теста
            traffic_split: Доля трафика для варианта A (0.0-1.0)
            min_samples: Минимум выборок для завершения теста
            metrics_weights: Веса метрик {'quality': 0.5, 'speed': 0.3, 'tokens': 0.2}
        
        Returns:
            test_id
        """
        try:
            # Генерируем test_id
            test_key = f"{test_name}:{variant_a_id}:{variant_b_id}"
            test_id = hashlib.md5(test_key.encode()).hexdigest()[:16]
            
            test_config = {
                'test_id': test_id,
                'test_name': test_name,
                'variant_a_id': variant_a_id,
                'variant_b_id': variant_b_id,
                'traffic_split': traffic_split,
                'min_samples': min_samples,
                'metrics_weights': metrics_weights or {'quality': 0.5, 'speed': 0.3, 'tokens': 0.2},
                'started_at': datetime.now(timezone.utc),
                'status': 'active'
            }
            
            # Сохраняем в БД
            conn = await self._get_conn()
            if not conn:
                return test_id
            
            try:
                # Проверяем наличие таблицы ab_tests
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'ab_tests'
                    )
                """)
                
                if table_exists:
                    await conn.execute("""
                        INSERT INTO ab_tests (test_id, test_name, variant_a_id, variant_b_id, traffic_split, min_samples, metrics_weights, started_at, status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (test_id) DO UPDATE
                        SET status = EXCLUDED.status
                    """, test_id, test_name, variant_a_id, variant_b_id, traffic_split, min_samples, json.dumps(test_config['metrics_weights']), test_config['started_at'], 'active')
                
                # Сохраняем в кэш
                self._active_tests[test_id] = test_config
                
                logger.info(f"✅ [AB TEST] Запущен тест {test_id}: {variant_a_id} vs {variant_b_id}")
                return test_id
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [AB TEST] Ошибка запуска теста: {e}")
            return ""
    
    async def select_variant(self, test_id: str) -> Optional[str]:
        """
        Выбирает вариант промпта для запроса (случайное распределение).
        
        Args:
            test_id: ID теста
        
        Returns:
            variant_id ('A' или 'B') или None
        """
        try:
            # Получаем конфигурацию теста
            test_config = self._active_tests.get(test_id)
            if not test_config:
                # Пробуем загрузить из БД
                conn = await self._get_conn()
                if conn:
                    try:
                        row = await conn.fetchrow("""
                            SELECT variant_a_id, variant_b_id, traffic_split, status
                            FROM ab_tests
                            WHERE test_id = $1
                        """, test_id)
                        if row and row['status'] == 'active':
                            test_config = {
                                'variant_a_id': row['variant_a_id'],
                                'variant_b_id': row['variant_b_id'],
                                'traffic_split': float(row['traffic_split'])
                            }
                            self._active_tests[test_id] = test_config
                    finally:
                        await conn.close()
            
            if not test_config:
                return None
            
            # Случайное распределение на основе traffic_split
            if random.random() < test_config['traffic_split']:
                return test_config['variant_a_id']
            else:
                return test_config['variant_b_id']
                
        except Exception as e:
            logger.error(f"❌ [AB TEST] Ошибка выбора варианта: {e}")
            return None
    
    async def record_metrics(
        self,
        test_id: str,
        variant_id: str,
        quality_score: float,
        response_time: float,
        tokens_used: int,
        user_satisfaction: Optional[float] = None
    ) -> bool:
        """
        Записывает метрики для варианта промпта.
        
        Args:
            test_id: ID теста
            variant_id: ID варианта
            quality_score: Оценка качества (0-1)
            response_time: Время ответа в секундах
            tokens_used: Количество использованных токенов
            user_satisfaction: Удовлетворенность пользователя (0-1, опционально)
        
        Returns:
            True если запись успешна
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return False
            
            try:
                # Проверяем наличие таблицы ab_test_metrics
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'ab_test_metrics'
                    )
                """)
                
                if table_exists:
                    await conn.execute("""
                        INSERT INTO ab_test_metrics (test_id, variant_id, quality_score, response_time, tokens_used, user_satisfaction, recorded_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, test_id, variant_id, quality_score, response_time, tokens_used, user_satisfaction, datetime.now(timezone.utc))
                
                logger.debug(f"📊 [AB TEST] Записаны метрики для {variant_id} в тесте {test_id}")
                return True
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [AB TEST] Ошибка записи метрик: {e}")
            return False
    
    async def analyze_test(self, test_id: str) -> Optional[ABTestResult]:
        """
        Анализирует результаты A/B теста и определяет победителя.
        
        Args:
            test_id: ID теста
        
        Returns:
            ABTestResult или None
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return None
            
            try:
                # Получаем конфигурацию теста
                test_config = await conn.fetchrow("""
                    SELECT variant_a_id, variant_b_id, min_samples, metrics_weights
                    FROM ab_tests
                    WHERE test_id = $1
                """, test_id)
                
                if not test_config:
                    return None
                
                variant_a_id = test_config['variant_a_id']
                variant_b_id = test_config['variant_b_id']
                min_samples = test_config['min_samples']
                metrics_weights = json.loads(test_config['metrics_weights']) if isinstance(test_config['metrics_weights'], str) else test_config['metrics_weights']
                
                # Получаем метрики для обоих вариантов
                metrics_a = await conn.fetchrow("""
                    SELECT 
                        AVG(quality_score) as avg_quality,
                        AVG(response_time) as avg_speed,
                        AVG(tokens_used) as avg_tokens,
                        AVG(user_satisfaction) as avg_satisfaction,
                        COUNT(*) as samples
                    FROM ab_test_metrics
                    WHERE test_id = $1 AND variant_id = $2
                """, test_id, variant_a_id)
                
                metrics_b = await conn.fetchrow("""
                    SELECT 
                        AVG(quality_score) as avg_quality,
                        AVG(response_time) as avg_speed,
                        AVG(tokens_used) as avg_tokens,
                        AVG(user_satisfaction) as avg_satisfaction,
                        COUNT(*) as samples
                    FROM ab_test_metrics
                    WHERE test_id = $1 AND variant_id = $2
                """, test_id, variant_b_id)
                
                if not metrics_a or not metrics_b:
                    return None
                
                samples_a = metrics_a['samples'] or 0
                samples_b = metrics_b['samples'] or 0
                total_samples = samples_a + samples_b
                
                # Проверяем, достаточно ли выборок
                if total_samples < min_samples:
                    logger.info(f"⚠️ [AB TEST] Недостаточно выборок для {test_id}: {total_samples}/{min_samples}")
                    return None
                
                # Нормализуем метрики (чем выше качество/удовлетворенность - лучше, чем меньше скорость/токены - лучше)
                variant_a_metrics = {
                    'quality': float(metrics_a['avg_quality'] or 0),
                    'speed': 1.0 / (float(metrics_a['avg_speed'] or 1.0) + 0.001),  # Инвертируем скорость
                    'tokens': 1.0 / (float(metrics_a['avg_tokens'] or 1.0) + 0.001),  # Инвертируем токены
                    'satisfaction': float(metrics_a['avg_satisfaction'] or 0.5)
                }
                
                variant_b_metrics = {
                    'quality': float(metrics_b['avg_quality'] or 0),
                    'speed': 1.0 / (float(metrics_b['avg_speed'] or 1.0) + 0.001),
                    'tokens': 1.0 / (float(metrics_b['avg_tokens'] or 1.0) + 0.001),
                    'satisfaction': float(metrics_b['avg_satisfaction'] or 0.5)
                }
                
                # Рассчитываем взвешенный score
                score_a = (
                    variant_a_metrics['quality'] * metrics_weights.get('quality', 0.5) +
                    variant_a_metrics['speed'] * metrics_weights.get('speed', 0.3) +
                    variant_a_metrics['tokens'] * metrics_weights.get('tokens', 0.2)
                )
                
                score_b = (
                    variant_b_metrics['quality'] * metrics_weights.get('quality', 0.5) +
                    variant_b_metrics['speed'] * metrics_weights.get('speed', 0.3) +
                    variant_b_metrics['tokens'] * metrics_weights.get('tokens', 0.2)
                )
                
                # Определяем победителя
                winner = None
                confidence = 0.0
                
                if abs(score_a - score_b) < 0.05:  # Разница < 5% = ничья
                    winner = None
                    confidence = 0.5
                elif score_a > score_b:
                    winner = 'A'
                    confidence = min(abs(score_a - score_b) / score_b, 1.0)
                else:
                    winner = 'B'
                    confidence = min(abs(score_b - score_a) / score_a, 1.0)
                
                result = ABTestResult(
                    test_id=test_id,
                    variant_a_id=variant_a_id,
                    variant_b_id=variant_b_id,
                    variant_a_metrics=variant_a_metrics,
                    variant_b_metrics=variant_b_metrics,
                    winner=winner,
                    confidence=confidence,
                    total_samples=total_samples,
                    created_at=datetime.now(timezone.utc)
                )
                
                logger.info(f"📊 [AB TEST] Анализ теста {test_id}: Победитель = {winner}, Уверенность = {confidence:.2%}")
                return result
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [AB TEST] Ошибка анализа теста: {e}")
            return None
    
    async def get_active_tests(self) -> List[Dict[str, Any]]:
        """
        Получает список активных A/B тестов.
        
        Returns:
            Список активных тестов
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return []
            
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'ab_tests'
                    )
                """)
                
                if not table_exists:
                    return []
                
                rows = await conn.fetch("""
                    SELECT test_id, test_name, variant_a_id, variant_b_id, started_at, status
                    FROM ab_tests
                    WHERE status = 'active'
                    ORDER BY started_at DESC
                """)
                
                return [
                    {
                        'test_id': row['test_id'],
                        'test_name': row['test_name'],
                        'variant_a_id': row['variant_a_id'],
                        'variant_b_id': row['variant_b_id'],
                        'started_at': row['started_at'],
                        'status': row['status']
                    }
                    for row in rows
                ]
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [AB TEST] Ошибка получения активных тестов: {e}")
            return []

# Singleton instance
_ab_testing_instance: Optional[PromptABTesting] = None

def get_prompt_ab_testing(db_url: str = DB_URL) -> PromptABTesting:
    """Получить singleton экземпляр PromptABTesting"""
    global _ab_testing_instance
    if _ab_testing_instance is None:
        _ab_testing_instance = PromptABTesting(db_url=db_url)
    return _ab_testing_instance

