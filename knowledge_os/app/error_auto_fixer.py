"""
Автоматическое обнаружение и исправление ошибок
Интегрируется в Enhanced Orchestrator для проактивного исправления проблем
"""
import asyncio
import asyncpg
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')


async def check_and_fix_stuck_tasks(conn) -> int:
    """Проверка и исправление застрявших задач"""
    try:
        # Находим застрявшие задачи (in_progress > 1 дня)
        stuck_count = await conn.fetchval("""
            SELECT COUNT(*) FROM tasks 
            WHERE status = 'in_progress' 
            AND updated_at < NOW() - INTERVAL '1 day'
        """)
        
        if stuck_count > 0:
            await conn.execute("""
                UPDATE tasks 
                SET status = 'pending', updated_at = NOW()
                WHERE status = 'in_progress' 
                AND updated_at < NOW() - INTERVAL '1 day'
            """)
            logger.info(f"✅ Автоматически исправлено {stuck_count} застрявших задач")
            return stuck_count
        
        return 0
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке застрявших задач: {e}")
        return 0


async def check_and_assign_unassigned_tasks(conn) -> int:
    """Проверка и назначение задач без экспертов"""
    try:
        unassigned_count = await conn.fetchval("""
            SELECT COUNT(*) FROM tasks 
            WHERE status = 'pending' 
            AND assignee_expert_id IS NULL
        """)
        
        if unassigned_count > 10:  # Если много задач без экспертов
            logger.info(f"⚠️ Найдено {unassigned_count} задач без экспертов, требуется назначение")
            # Возвращаем количество для обработки в orchestrator
            return unassigned_count
        
        return 0
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке неназначенных задач: {e}")
        return 0


async def check_migration_errors(conn) -> List[str]:
    """Проверка ошибок миграций"""
    errors = []
    try:
        # Проверяем наличие проблемных таблиц
        missing_tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('adaptive_learning_logs', 'contextual_patterns', 'user_preferences')
            AND table_name NOT IN (
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
            )
        """)
        
        if missing_tables:
            errors.append(f"Отсутствуют таблицы: {[t['table_name'] for t in missing_tables]}")
        
        # Проверяем проблемные foreign keys
        problematic_fks = await conn.fetch("""
            SELECT tc.constraint_name, tc.table_name
            FROM information_schema.table_constraints tc
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = 'adaptive_learning_logs'
            AND tc.constraint_name LIKE '%interaction_log%'
        """)
        
        if problematic_fks:
            errors.append("Обнаружены проблемные foreign keys в adaptive_learning_logs")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке миграций: {e}")
    
    return errors


async def check_db_connections(conn) -> Dict[str, any]:
    """Проверка и исправление проблем с подключениями к БД"""
    issues = []
    try:
        # Проверяем количество активных подключений
        active_connections = await conn.fetchval("""
            SELECT count(*) 
            FROM pg_stat_activity 
            WHERE datname = current_database()
            AND state = 'active'
        """)
        
        max_connections = await conn.fetchval("SHOW max_connections")
        
        if active_connections and max_connections:
            usage_percent = (active_connections / int(max_connections)) * 100
            if usage_percent > 80:
                issues.append(f"Высокое использование подключений: {active_connections}/{max_connections} ({usage_percent:.1f}%)")
                logger.warning(f"⚠️ Высокое использование подключений к БД: {usage_percent:.1f}%")
        
    except Exception as e:
        logger.debug(f"Не удалось проверить подключения: {e}")
    
    return {'issues': issues, 'active_connections': active_connections if 'active_connections' in locals() else None}


async def auto_fix_all_errors(conn) -> Dict[str, any]:
    """Автоматическое исправление всех обнаруженных ошибок"""
    results = {
        'stuck_tasks_fixed': 0,
        'unassigned_tasks': 0,
        'migration_errors': [],
        'db_connection_issues': [],
        'warnings': []
    }
    
    try:
        # 1. Проверяем подключения к БД
        db_check = await check_db_connections(conn)
        if db_check['issues']:
            results['db_connection_issues'] = db_check['issues']
            logger.warning(f"⚠️ Проблемы с подключениями: {db_check['issues']}")
        
        # 2. Исправляем застрявшие задачи
        results['stuck_tasks_fixed'] = await check_and_fix_stuck_tasks(conn)
        
        # 3. Проверяем неназначенные задачи
        results['unassigned_tasks'] = await check_and_assign_unassigned_tasks(conn)
        
        # 4. Проверяем ошибки миграций
        results['migration_errors'] = await check_migration_errors(conn)
        
        if results['stuck_tasks_fixed'] > 0 or results['unassigned_tasks'] > 0 or results['migration_errors'] or results['db_connection_issues']:
            logger.info(f"🔧 Автоматическое исправление: {results}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в auto_fix_all_errors: {e}")
        results['warnings'].append(str(e))
    
    return results
