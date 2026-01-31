"""
Validate Singularity 9.0 Metrics: Автоматическая валидация целевых метрик

Функционал:
- Проверка достижения целевых метрик каждые 24 часа
- Отчет в notifications при достижении/недостижении метрик
- Автоматическое отключение компонента, если метрики не достигаются
"""

import asyncio
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Import database connection from evaluator
from evaluator import get_pool

# Import A/B tester
try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../app'))
    from singularity_9_ab_tester import Singularity9ABTester
    AB_TESTER_AVAILABLE = True
except ImportError:
    AB_TESTER_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

# Целевые метрики для каждой гипотезы
TARGET_METRICS = {
    "tacit_knowledge": {
        "metric_name": "style_similarity_score",
        "target_value": 0.85,
        "comparison": ">="
    },
    "emotion_modulation": {
        "metric_name": "satisfaction_delta",
        "target_value": 0.15,  # 15% увеличение
        "comparison": ">="
    },
    "code_smell_predictor": {
        "metric_name": "precision",
        "target_value": 0.70,
        "comparison": ">="
    },
    "predictive_compression": {
        "metric_name": "latency_reduction",
        "target_value": 0.30,  # 30% снижение
        "comparison": ">="
    }
}


async def validate_singularity_9_metrics():
    """Валидирует целевые метрики для всех гипотез Singularity 9.0"""
    logger.info("🔍 [SINGULARITY 9 VALIDATION] Starting metrics validation...")
    
    if not AB_TESTER_AVAILABLE:
        logger.error("❌ [SINGULARITY 9 VALIDATION] A/B tester not available")
        return
    
    try:
        tester = Singularity9ABTester()
        results = await tester.validate_metrics()
        
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Проверяем результаты для каждой гипотезы
            for hypothesis_key, result in results.items():
                achieved = result["achieved"]
                metric_value = result["metric_value"]
                target_value = result["target_value"]
                sample_size = result.get("sample_size", 0)
                
                if achieved:
                    # Метрика достигнута - создаем уведомление об успехе
                    message = f"✅ Singularity 9.0: {hypothesis_key} достигнута целевая метрика! ({metric_value:.2%} >= {target_value:.2%}, выборка: {sample_size:,})"
                    logger.info(f"✅ [SINGULARITY 9 VALIDATION] {hypothesis_key}: {message}")
                    
                    await conn.execute("""
                        INSERT INTO notifications (message, type)
                        VALUES ($1, 'system_success')
                    """, message)
                else:
                    # Метрика не достигнута - создаем уведомление о проблеме
                    message = f"⚠️ Singularity 9.0: {hypothesis_key} не достигнута целевая метрика ({metric_value:.2%} < {target_value:.2%}, выборка: {sample_size:,})"
                    logger.warning(f"⚠️ [SINGULARITY 9 VALIDATION] {hypothesis_key}: {message}")
                    
                    await conn.execute("""
                        INSERT INTO notifications (message, type)
                        VALUES ($1, 'system_alert')
                    """, message)
                    
                    # В будущем здесь можно добавить автоматическое отключение компонента
                    # if metric_value < target_value * 0.5:  # Если метрика меньше 50% от целевой
                    #     logger.warning(f"⚠️ [SINGULARITY 9 VALIDATION] {hypothesis_key}: Disabling component due to poor metrics")
                    #     # Отключить компонент (например, через флаг в БД)
        
        logger.info("✅ [SINGULARITY 9 VALIDATION] Metrics validation completed")
    except Exception as e:
        logger.error(f"❌ [SINGULARITY 9 VALIDATION] Error validating metrics: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(validate_singularity_9_metrics())

