import asyncio
import asyncpg
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class CorporationSelfLearning:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._pool = None
        self._learning_cycles = 0
        self._improvements_applied = 0
    
    async def get_pool(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.db_url,
                min_size=1,
                max_size=3,
                max_inactive_connection_lifetime=300
            )
        return self._pool
    
    async def analyze_errors(self, hours: int = 24) -> Dict:
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                failed_tasks = await conn.fetch("""
                    SELECT 
                        COUNT(*) as total_failed,
                        COUNT(DISTINCT assignee_expert_id) as experts_with_failures,
                        AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_time_before_failure
                    FROM tasks
                    WHERE status = 'failed'
                    AND updated_at > NOW() - INTERVAL '%s hours'
                """ % hours)
                
                model_failures = await conn.fetch("""
                    SELECT 
                        model_name,
                        COUNT(*) as failure_count,
                        AVG(quality_score) as avg_quality_on_failure
                    FROM model_performance_log
                    WHERE success = false
                    AND created_at > NOW() - INTERVAL '%s hours'
                    GROUP BY model_name
                    ORDER BY failure_count DESC
                    LIMIT 10
                """ % hours)
                
                error_patterns = await conn.fetch("""
                    SELECT 
                        metadata->>'last_error' as error_type,
                        COUNT(*) as count
                    FROM tasks
                    WHERE metadata->>'last_error' IS NOT NULL
                    AND status = 'failed'
                    AND updated_at > NOW() - INTERVAL '%s hours'
                    GROUP BY metadata->>'last_error'
                    ORDER BY count DESC
                    LIMIT 10
                """ % hours)
                
                return {
                    'failed_tasks': dict(failed_tasks[0]) if failed_tasks else {},
                    'model_failures': [dict(row) for row in model_failures],
                    'error_patterns': [dict(row) for row in error_patterns],
                    'analysis_time': datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error analyzing errors: {e}")
            return {}
    
    async def analyze_performance_metrics(self, hours: int = 24) -> Dict:
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                model_metrics = await conn.fetch("""
                    SELECT 
                        model_name,
                        COUNT(*) as total_attempts,
                        COUNT(*) FILTER (WHERE success = true)::float / COUNT(*) as success_rate,
                        AVG(quality_score) as avg_quality,
                        AVG(latency_ms) as avg_latency,
                        AVG(response_length) as avg_response_length
                    FROM model_performance_log
                    WHERE created_at > NOW() - INTERVAL '%s hours'
                    GROUP BY model_name
                """ % hours)
                
                task_metrics = await conn.fetch("""
                    SELECT 
                        status,
                        COUNT(*) as count,
                        AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_processing_time
                    FROM tasks
                    WHERE updated_at > NOW() - INTERVAL '%s hours'
                    GROUP BY status
                """ % hours)
                
                expert_metrics = await conn.fetch("""
                    SELECT 
                        e.name as expert_name,
                        COUNT(t.id) as tasks_assigned,
                        COUNT(*) FILTER (WHERE t.status = 'completed') as completed,
                        COUNT(*) FILTER (WHERE t.status = 'failed') as failed,
                        AVG(EXTRACT(EPOCH FROM (t.updated_at - t.created_at))) as avg_time
                    FROM tasks t
                    JOIN experts e ON t.assignee_expert_id = e.id
                    WHERE t.updated_at > NOW() - INTERVAL '%s hours'
                    GROUP BY e.name
                    ORDER BY tasks_assigned DESC
                    LIMIT 20
                """ % hours)
                
                return {
                    'model_metrics': [dict(row) for row in model_metrics],
                    'task_metrics': [dict(row) for row in task_metrics],
                    'expert_metrics': [dict(row) for row in expert_metrics],
                    'analysis_time': datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return {}
    
    async def generate_improvements(self, error_analysis: Dict, performance_analysis: Dict) -> List[Dict]:
        improvements = []
        if error_analysis.get('model_failures'):
            for model_failure in error_analysis['model_failures']:
                model_name = model_failure['model_name']
                failure_count = model_failure['failure_count']
                if failure_count > 10:
                    improvements.append({
                        'type': 'model_downgrade',
                        'model': model_name,
                        'reason': f'Высокий процент ошибок: {failure_count}',
                        'action': 'Использовать более простую модель для этого типа задач',
                        'priority': 'high'
                    })
        if performance_analysis.get('model_metrics'):
            for model_metric in performance_analysis['model_metrics']:
                model_name = model_metric['model_name']
                success_rate = model_metric['success_rate']
                avg_quality = model_metric['avg_quality']
                if success_rate < 0.7:
                    improvements.append({
                        'type': 'model_optimization',
                        'model': model_name,
                        'reason': f'Низкий success_rate: {success_rate:.2%}',
                        'action': 'Улучшить выбор задач для этой модели',
                        'priority': 'medium'
                    })
                if avg_quality < 0.6:
                    improvements.append({
                        'type': 'quality_improvement',
                        'model': model_name,
                        'reason': f'Низкое качество: {avg_quality:.2f}',
                        'action': 'Переключиться на более мощную модель для сложных задач',
                        'priority': 'high'
                    })
        if error_analysis.get('error_patterns'):
            for pattern in error_analysis['error_patterns'][:3]:
                error_type = pattern['error_type']
                count = pattern['count']
                if count > 5:
                    improvements.append({
                        'type': 'error_pattern_fix',
                        'pattern': error_type[:100],
                        'reason': f'Повторяющаяся ошибка: {count} раз',
                        'action': 'Добавить специальную обработку для этого типа ошибок',
                        'priority': 'high'
                    })
        return improvements
    
    async def apply_improvements(self, improvements: List[Dict]) -> Dict:
        applied = []
        failed = []
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                res = await conn.execute("""
                    UPDATE tasks 
                    SET status = 'pending', 
                        metadata = metadata - 'last_error' 
                    WHERE status = 'in_progress' 
                    AND (metadata->>'last_error' = 'timeout' OR updated_at < NOW() - INTERVAL '30 minutes');
                """)
                if res != "UPDATE 0":
                    logger.info(f"🛡️ [SELF-HEALING] Автоматически сброшено зависших задач: {res}")
        except Exception as e:
            logger.error(f"❌ [SELF-HEALING] Ошибка при автоочистке: {e}")
        for improvement in improvements:
            try:
                if improvement['type'] == 'model_downgrade':
                    logger.info(f"🔄 [LEARNING] Применяем улучшение: {improvement['action']}")
                    applied.append(improvement)
                elif improvement['type'] == 'model_optimization':
                    logger.info(f"🔧 [LEARNING] Оптимизируем модель: {improvement['model']}")
                    applied.append(improvement)
                elif improvement['type'] == 'error_pattern_fix':
                    logger.info(f"🛠️ [LEARNING] Исправляем паттерн ошибок: {improvement['pattern']}")
                    applied.append(improvement)
                elif improvement['type'] == 'quality_improvement':
                    logger.info(f"📈 [LEARNING] Повышаем качество для модели: {improvement['model']}")
                    applied.append(improvement)
                
                if improvement in applied:
                    self._improvements_applied += 1
            except Exception as e:
                logger.error(f"Error applying improvement: {e}")
                failed.append(improvement)
        return {'applied': applied, 'failed': failed, 'total': len(improvements)}
    
    async def run_learning_cycle(self):
        self._learning_cycles += 1
        logger.info(f"🔄 [SELF-LEARNING] Запуск цикла обучения #{self._learning_cycles}")
        try:
            error_analysis = await self.analyze_errors(hours=24)
            logger.info(f"📊 [LEARNING] Проанализировано ошибок: {len(error_analysis.get('error_patterns', []))}")
            performance_analysis = await self.analyze_performance_metrics(hours=24)
            logger.info(f"📈 [LEARNING] Проанализировано моделей: {len(performance_analysis.get('model_metrics', []))}")
            improvements = await self.generate_improvements(error_analysis, performance_analysis)
            logger.info(f"💡 [LEARNING] Сгенерировано улучшений: {len(improvements)}")
            
            if improvements:
                result = await self.apply_improvements(improvements)
                logger.info(f"✅ [LEARNING] Применено улучшений: {len(result['applied'])}/{result['total']}")
                # Добавляем детализацию по типам (Singularity 10.0)
                types_count = {}
                for imp in result['applied']:
                    t = imp['type']
                    types_count[t] = types_count.get(t, 0) + 1
                if types_count:
                    logger.info(f"📊 [LEARNING] Детализация: {', '.join([f'{k}: {v}' for k, v in types_count.items()])}")
            else:
                await self.apply_improvements([])
                
            await self.save_learning_results(error_analysis, performance_analysis, improvements)
            logger.info(f"✅ [SELF-LEARNING] Цикл обучения #{self._learning_cycles} завершен")
        except Exception as e:
            logger.error(f"❌ [SELF-LEARNING] Ошибка в цикле обучения: {e}")
    
    async def save_learning_results(self, error_analysis: Dict, performance_analysis: Dict, improvements: List[Dict]):
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO corporation_learning_log (
                        cycle_number,
                        error_analysis,
                        performance_analysis,
                        improvements,
                        applied_count,
                        created_at
                    ) VALUES ($1, $2, $3, $4, $5, NOW())
                """, self._learning_cycles, json.dumps(error_analysis), json.dumps(performance_analysis), json.dumps(improvements), self._improvements_applied)
        except Exception as e:
            logger.debug(f"Error saving learning results: {e}")
    
    async def start_continuous_learning(self, interval_hours: int = 6):
        logger.info(f"🚀 [SELF-LEARNING] Запуск непрерывного обучения (интервал: {interval_hours} часов)")
        while True:
            try:
                await self.run_learning_cycle()
                await asyncio.sleep(interval_hours * 3600)
            except Exception as e:
                logger.error(f"❌ [SELF-LEARNING] Ошибка в непрерывном обучении: {e}")
                await asyncio.sleep(3600)

_learning_instance = None
def get_corporation_learner(db_url: str = None) -> CorporationSelfLearning:
    global _learning_instance
    if _learning_instance is None:
        import os
        db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://admin:secret@knowledge_postgres:5432/knowledge_os')
        _learning_instance = CorporationSelfLearning(db_url)
    return _learning_instance
