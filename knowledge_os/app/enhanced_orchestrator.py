"""
[KNOWLEDGE OS] Enhanced Orchestrator v3.1.
Enhanced Orchestrator with Task Prioritization and Workload Balancing.
Part of the ATRA Singularity framework.
"""

import asyncio
import getpass
import json
import logging
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, Optional

# Third-party imports with fallback
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

# Local project imports with fallback
try:
    from resource_manager import acquire_resource_lock
except ImportError:
    def acquire_resource_lock(name):  # pylint: disable=unused-argument
        """Fallback for acquire_resource_lock."""
        class MockLock:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
        return MockLock()

try:
    from ai_core import run_smart_agent_sync, run_smart_agent_async
except ImportError:
    def run_smart_agent_sync(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_sync."""
        return None

    async def run_smart_agent_async(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_async."""
        return None

try:
    from global_scout import run_global_scout_cycle
except ImportError:
    async def run_global_scout_cycle(): pass

try:
    from distillation_engine import KnowledgeDistiller
except ImportError:
    class KnowledgeDistiller:
        """Fallback for KnowledgeDistiller."""
        async def collect_high_quality_samples(self, **kwargs): return 0

try:
    from synthetic_generator import SyntheticKnowledgeGenerator
except ImportError:
    class SyntheticKnowledgeGenerator:
        """Fallback for SyntheticKnowledgeGenerator."""
        async def generate_synthetic_samples(self, **kwargs): pass

try:
    from training_pipeline import LocalTrainingPipeline
except ImportError:
    class LocalTrainingPipeline:
        """Fallback for LocalTrainingPipeline."""
        def trigger_auto_upgrade(self): return "MOCK_OFFLINE"

try:
    from swarm_orchestrator import SwarmOrchestrator
except ImportError:
    class SwarmOrchestrator:
        """Fallback for SwarmOrchestrator."""
        async def handle_critical_failures(self): pass

try:
    from meta_architect import MetaArchitect
except ImportError:
    class MetaArchitect:
        """Fallback for MetaArchitect."""
        async def self_repair_cycle(self): pass

try:
    from knowledge_graph import run_auto_link_detection
except ImportError:
    async def run_auto_link_detection(): pass

try:
    from evolution_monitor import SingularityEvolutionMonitor
except ImportError:
    class SingularityEvolutionMonitor:
        """Fallback for SingularityEvolutionMonitor."""
        async def run_daily_check(self): return "MOCK_EVOLUTION_OFFLINE"

try:
    from curiosity_engine import CuriosityEngine
except ImportError:
    class CuriosityEngine:
        """Fallback for CuriosityEngine."""
        async def scan_for_gaps(self): return "MOCK_CURIOSITY_OFFLINE"

try:
    from memory_consolidator import MemoryConsolidator
except ImportError:
    class MemoryConsolidator:
        """Fallback for MemoryConsolidator."""
        async def consolidate_memory(self): return "MOCK_CONSOLIDATION_OFFLINE"

# Add scripts directory to path for sync
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts")))
try:
    from server_knowledge_sync import ServerKnowledgeSync
except ImportError:
    ServerKnowledgeSync = None

logger = logging.getLogger(__name__)


def _mask_db_url(url: str) -> str:
    """Mask password in DATABASE_URL for logging."""
    if not url or "@" not in url:
        return "***"
    try:
        pre, rest = url.split("@", 1)
        if ":" in pre:
            user_part, _ = pre.rsplit(":", 1)
            return f"{user_part}:***@{rest}"
    except Exception:
        pass
    return "***"

USER_NAME = getpass.getuser()
# Локальная БД (Mac Studio): DATABASE_URL или localhost
DEFAULT_DB_URL = os.getenv('DATABASE_URL') or 'postgresql://admin:secret@localhost:5432/knowledge_os'
DB_URL = os.getenv('DATABASE_URL', DEFAULT_DB_URL)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

# Приоритеты задач
PRIORITY_WEIGHTS = {
    'urgent': 100,
    'high': 50,
    'medium': 25,
    'low': 10,
}


async def run_cursor_agent(prompt: str):
    """Запуск Cursor Agent для генерации контента через умное ядро"""
    if run_smart_agent_async:
        return await run_smart_agent_async(prompt, expert_name="Виктория", category="orchestrator")
    return run_smart_agent_sync(prompt, expert_name="Виктория", category="orchestrator")


async def get_expert_workload(conn, expert_id: str) -> Dict:
    """Получение текущей загрузки эксперта"""
    # Количество активных задач
    active_tasks = await conn.fetchval("""
        SELECT count(*)
        FROM tasks
        WHERE assignee_expert_id = $1
        AND status IN ('pending', 'in_progress')
    """, expert_id)

    # Среднее время выполнения задач
    avg_duration = await conn.fetchval("""
        SELECT AVG(actual_duration_minutes)
        FROM tasks
        WHERE assignee_expert_id = $1
        AND status = 'completed'
        AND actual_duration_minutes IS NOT NULL
        AND completed_at > NOW() - INTERVAL '30 days'
    """, expert_id) or 60  # По умолчанию 60 минут

    # Количество завершенных задач за последние 7 дней
    completed_recent = await conn.fetchval("""
        SELECT count(*)
        FROM tasks
        WHERE assignee_expert_id = $1
        AND status = 'completed'
        AND completed_at > NOW() - INTERVAL '7 days'
    """, expert_id) or 0

    # Успешность выполнения (процент завершенных)
    success_rate = await conn.fetchval("""
        SELECT
            CASE
                WHEN count(*) = 0 THEN 1.0
                ELSE count(*) FILTER (WHERE status = 'completed')::float / count(*)::float
            END
        FROM tasks
        WHERE assignee_expert_id = $1
        AND created_at > NOW() - INTERVAL '30 days'
    """, expert_id) or 1.0

    return {
        'active_tasks': active_tasks,
        'avg_duration_minutes': round(avg_duration, 1),
        'completed_recent': completed_recent,
        'success_rate': round(success_rate, 2),
        'workload_score': active_tasks * 10 + (avg_duration / 10),  # Простая метрика загрузки
    }


async def calculate_task_priority(
    conn,
    title: str,
    description: str,
    metadata: Dict,
    domain_id: Optional[str] = None
) -> str:
    """Автоматический расчет приоритета задачи"""
    priority_score = 0

    # Ключевые слова для urgent
    urgent_keywords = ['критично', 'срочно', 'urgent', 'critical', '🔥', '🚨']
    if any(kw in title.lower() or kw in description.lower() for kw in urgent_keywords):
        priority_score += 50

    # Ключевые слова для high
    high_keywords = ['важно', 'important', 'high', '⚠️']
    if any(kw in title.lower() or kw in description.lower() for kw in high_keywords):
        priority_score += 25

    # Метаданные
    if metadata.get('reason') == 'curiosity_engine_starvation':
        priority_score += 30  # Голодные домены - высокий приоритет

    if metadata.get('source') == 'code_auditor':
        severity = metadata.get('severity', 'medium')
        if severity == 'high':
            priority_score += 40
        elif severity == 'medium':
            priority_score += 20

    # Время с момента создания (старые задачи получают бонус)
    if domain_id:
        domain_starvation = await conn.fetchval("""
            SELECT count(*) < 50
            FROM knowledge_nodes
            WHERE domain_id = $1
        """, domain_id)
        if domain_starvation:
            priority_score += 20

    # Определение приоритета
    if priority_score >= 50:
        return 'urgent'
    if priority_score >= 30:
        return 'high'
    if priority_score >= 15:
        return 'medium'
    return 'low'


async def assign_task_to_best_expert(
    conn,
    task_id: str,
    domain_id: Optional[str] = None,
    required_role: Optional[str] = None
) -> Optional[str]:
    """Назначение задачи лучшему эксперту с учетом загрузки"""
    # Получаем кандидатов
    candidates = None
    
    if domain_id:
        # Пробуем найти экспертов по домену
        candidates = await conn.fetch("""
            SELECT id, name, role, department
            FROM experts
            WHERE is_active = true
            AND department = (SELECT name FROM domains WHERE id = $1)
        """, domain_id)
        
        # Если не нашли по домену, пробуем по связанным доменам через knowledge_nodes
        if not candidates:
            candidates = await conn.fetch("""
                SELECT DISTINCT e.id, e.name, e.role, e.department
                FROM experts e
                INNER JOIN knowledge_nodes kn ON kn.domain_id = $1
                WHERE e.is_active = true
                AND (e.department ILIKE '%' || (SELECT name FROM domains WHERE id = $1) || '%'
                     OR e.role ILIKE '%' || (SELECT name FROM domains WHERE id = $1) || '%')
                LIMIT 20
            """, domain_id)
    
    if not candidates and required_role:
        candidates = await conn.fetch("""
            SELECT id, name, role, department
            FROM experts
            WHERE is_active = true
            AND role ILIKE $1
        """, f"%{required_role}%")
    
    # Fallback: если не нашли, берем всех активных экспертов
    if not candidates:
        candidates = await conn.fetch("""
            SELECT id, name, role, department
            FROM experts
            WHERE is_active = true
            ORDER BY RANDOM()
            LIMIT 50
        """)

    if not candidates:
        logger.warning("No experts found for task %s (no active experts in system)", task_id)
        return None

    # Оцениваем каждого кандидата
    best_expert = None
    best_score = float('inf')  # Меньше загрузка = лучше

    for expert in candidates:
        workload = await get_expert_workload(conn, expert['id'])

        # Считаем score (меньше = лучше)
        # Учитываем: активные задачи, среднее время выполнения, успешность
        score = (
            workload['workload_score'] * 0.5 +  # Загрузка
            (1.0 - workload['success_rate']) * 100 * 0.3 +  # Неуспешность (штраф)
            (workload['avg_duration_minutes'] / 10) * 0.2  # Время выполнения
        )

        if score < best_score:
            best_score = score
            best_expert = expert

    if best_expert:
        # Назначаем задачу
        await conn.execute("""
            UPDATE tasks
            SET assignee_expert_id = $1,
                status = 'pending',
                updated_at = NOW()
            WHERE id = $2
        """, best_expert['id'], task_id)

        logger.info("✅ Task %s assigned to %s (workload: %.2f)", task_id, best_expert['name'], best_score)
        return best_expert['id']

    return None


async def rebalance_workload(conn):
    """Перебалансировка нагрузки между экспертами"""
    logger.info("⚖️ Starting workload rebalancing...")

    # Находим перегруженных экспертов (> 5 активных задач)
    overloaded = await conn.fetch("""
        SELECT assignee_expert_id, count(*) as task_count
        FROM tasks
        WHERE status IN ('pending', 'in_progress')
        GROUP BY assignee_expert_id
        HAVING count(*) > 5
    """)

    # Перераспределяем задачи
    for overloaded_expert in overloaded:
        expert_id = overloaded_expert['assignee_expert_id']
        excess_tasks = overloaded_expert['task_count'] - 5

        # Берем задачи с низким приоритетом для перераспределения
        tasks_to_reassign = await conn.fetch("""
            SELECT id, priority, domain_id
            FROM tasks
            WHERE assignee_expert_id = $1
            AND status = 'pending'
            ORDER BY
                CASE priority
                    WHEN 'urgent' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END DESC,
                created_at ASC
            LIMIT $2
        """, expert_id, excess_tasks)

        for task in tasks_to_reassign:
            # Назначаем незагруженному эксперту из того же домена
            if task['domain_id']:
                new_expert = await conn.fetchrow("""
                    SELECT e.id
                    FROM experts e
                    JOIN domains d ON e.department = d.name
                    WHERE d.id = $1
                    AND e.id != $2
                    AND e.id IN (
                        SELECT id FROM (
                            SELECT e2.id, count(t2.id) as task_count
                            FROM experts e2
                            LEFT JOIN tasks t2 ON t2.assignee_expert_id = e2.id
                                AND t2.status IN ('pending', 'in_progress')
                            GROUP BY e2.id
                            HAVING count(t2.id) < 2
                        ) underloaded_inner
                    )
                    ORDER BY RANDOM()
                    LIMIT 1
                """, task['domain_id'], expert_id)

                if new_expert:
                    await conn.execute("""
                        UPDATE tasks
                        SET assignee_expert_id = $1,
                            updated_at = NOW()
                        WHERE id = $2
                    """, new_expert['id'], task['id'])
                    logger.info("  ↻ Task %s reassigned from overloaded expert", task['id'])


async def run_enhanced_orchestration_cycle():
    """Запуск цикла Enhanced Orchestrator с обновлением знаний корпорации"""
    # Обновляем знания корпорации перед каждым циклом
    try:
        from corporation_knowledge_system import update_all_agents_knowledge
        await update_all_agents_knowledge()
        logger.info("✅ Знания корпорации обновлены перед циклом оркестрации")
    except Exception as e:
        logger.debug(f"Не удалось обновить знания корпорации: {e}")
    
    """Основной цикл улучшенного Orchestrator"""
    if not ASYNCPG_AVAILABLE:
        logger.error("❌ asyncpg is not installed. Orchestration aborted.")
        return

    async with acquire_resource_lock("orchestrator"):
        logger.info("[ENHANCED_ORCHESTRATOR] cycle start DATABASE_URL=%s", _mask_db_url(DB_URL))
        conn = await asyncpg.connect(DB_URL)
        try:
            unassigned_count = await conn.fetchval(
                "SELECT COUNT(*) FROM tasks WHERE assignee_expert_id IS NULL"
            )
            logger.info("[ENHANCED_ORCHESTRATOR] unassigned_tasks=%s", unassigned_count)
        except Exception as e:
            logger.warning("[ENHANCED_ORCHESTRATOR] could not count unassigned: %s", e)
        rd = None
        if REDIS_AVAILABLE:
            rd = await redis.from_url(REDIS_URL, decode_responses=True)

        try:
            # --- ФАЗА 0: AUTONOMOUS ERROR FIXING (Автоматическое исправление ошибок) ---
            t0 = time.time()
            logger.info("🔧 Phase 0: Auto-fixing errors...")
            phase_result = "skipped"
            try:
                from error_auto_fixer import auto_fix_all_errors
                fix_results = await auto_fix_all_errors(conn)
                if fix_results.get('stuck_tasks_fixed', 0) > 0 or fix_results.get('unassigned_tasks', 0) > 0:
                    phase_result = str(fix_results)
                else:
                    phase_result = "ok"
            except ImportError:
                logger.debug("error_auto_fixer module not found, skipping")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Auto-fix error: %s", exc)
                phase_result = str(exc)
            logger.info("[ENHANCED_ORCHESTRATOR] phase=0 duration_ms=%.0f result=%s", (time.time() - t0) * 1000, phase_result)

            # --- ФАЗА 0.5: AUTONOMOUS MIGRATIONS (работает без knowledge_nodes/domains) ---
            t05 = time.time()
            logger.info("🗄️ Phase 0.5: Autonomous Migrations...")
            try:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        id SERIAL PRIMARY KEY,
                        migration_name VARCHAR(255) UNIQUE NOT NULL,
                        applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                base_dir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                migration_dir = os.path.join(base_dir_path, "db", "migrations")
                if os.path.exists(migration_dir):
                    applied_list = await conn.fetch(
                        "SELECT migration_name FROM schema_migrations"
                    )
                    applied_set = {r["migration_name"] for r in applied_list}
                    for file_name in sorted(os.listdir(migration_dir)):
                        if not file_name.endswith(".sql"):
                            continue
                        if file_name in applied_set:
                            continue
                        logger.info("  ⚡ Applying migration: %s", file_name)
                        try:
                            with open(os.path.join(migration_dir, file_name), 'r', encoding='utf-8') as f:
                                await conn.execute(f.read())
                            await conn.execute(
                                "INSERT INTO schema_migrations (migration_name, applied_at) VALUES ($1, NOW()) ON CONFLICT (migration_name) DO NOTHING",
                                file_name
                            )
                            logger.info("  ✅ Applied: %s", file_name)
                        except Exception as mig_err:  # pylint: disable=broad-exception-caught
                            logger.error("  ❌ Migration %s failed: %s", file_name, mig_err)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Migration error: %s", exc)
            logger.info("[ENHANCED_ORCHESTRATOR] phase=0.5 duration_ms=%.0f result=migrations", (time.time() - t05) * 1000)

            victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
            if not victoria_id:
                logger.warning("Victoria not found, creating...")
                victoria_id = await conn.fetchval("""
                    INSERT INTO experts (name, role, system_prompt, department)
                    VALUES ('Виктория', 'Team Lead', 'Team Lead and Coordinator', 'Management')
                    RETURNING id
                """)

            # --- ФАЗА 1: ПРИОРИТИЗАЦИЯ СУЩЕСТВУЮЩИХ ЗАДАЧ ---
            t1 = time.time()
            logger.info("📊 Phase 1: Prioritizing existing tasks...")
            unprioritized_tasks = await conn.fetch("""
                SELECT id, title, description, metadata, domain_id
                FROM tasks
                WHERE priority = 'medium'
                AND status = 'pending'
                AND created_at > NOW() - INTERVAL '24 hours'
            """)

            for task in unprioritized_tasks:
                task_meta = json.loads(task['metadata']) if isinstance(task['metadata'], str) else task['metadata']
                new_priority = await calculate_task_priority(
                    conn, task['title'], task['description'], task_meta, task['domain_id']
                )
                if new_priority != 'medium':
                    await conn.execute("""
                        UPDATE tasks
                        SET priority = $1,
                            updated_at = NOW()
                        WHERE id = $2
                    """, new_priority, task['id'])
                    logger.info("  📌 Task %s: priority updated to %s", task['id'], new_priority)
            logger.info("[ENHANCED_ORCHESTRATOR] phase=1 duration_ms=%.0f result=%s tasks reprioritized", (time.time() - t1) * 1000, len(unprioritized_tasks))

            # --- ФАЗА 2: НАЗНАЧЕНИЕ ЗАДАЧ БЕЗ ИСПОЛНИТЕЛЯ ---
            t2 = time.time()
            logger.info("👥 Phase 2: Assigning unassigned tasks...")
            unassigned_tasks = await conn.fetch("""
                SELECT id, title, description, domain_id, priority, metadata
                FROM tasks
                WHERE assignee_expert_id IS NULL
                AND status = 'pending'
                ORDER BY
                    CASE priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    created_at ASC
            """)

            for task in unassigned_tasks:
                await assign_task_to_best_expert(conn, task['id'], task['domain_id'])
            logger.info("[ENHANCED_ORCHESTRATOR] phase=2 duration_ms=%.0f result=%s tasks assigned", (time.time() - t2) * 1000, len(unassigned_tasks))

            # --- ФАЗА 3: ПЕРЕБАЛАНСИРОВКА НАГРУЗКИ ---
            t3 = time.time()
            logger.info("⚖️ Phase 3: Rebalancing workload...")
            await rebalance_workload(conn)
            logger.info("[ENHANCED_ORCHESTRATOR] phase=3 duration_ms=%.0f result=rebalance", (time.time() - t3) * 1000)

            # --- ФАЗА 4: АССОЦИАТИВНЫЙ МОЗГ (как в оригинале) ---
            logger.info("🧩 Phase 4: Cross-domain linking...")
            new_knowledge = await conn.fetch("""
                SELECT k.id, k.content, d.name as domain, k.metadata, k.domain_id
                FROM knowledge_nodes k
                JOIN domains d ON k.domain_id = d.id
                WHERE k.created_at > NOW() - INTERVAL '6 hours'
                AND (k.metadata->>'orchestrated' IS NULL OR k.metadata->>'orchestrated' = 'false')
                LIMIT 10
            """)

            for node in new_knowledge:
                random_node = await conn.fetchrow("""
                    SELECT k.content, d.name as domain
                    FROM knowledge_nodes k JOIN domains d ON k.domain_id = d.id
                    WHERE k.domain_id != $1 ORDER BY RANDOM() LIMIT 1
                """, node['domain_id'])

                if random_node:
                    link_prompt = f"""
                    Вы - Виктория (Team Lead). Найдите неочевидную связь между двумя фактами:
                    ФАКТ А ({node['domain']}): {node['content']}
                    ФАКТ Б ({random_node['domain']}): {random_node['content']}

                    ЗАДАЧА: Сформулируйте одну инновационную гипотезу на стыке этих знаний.
                    Верните ТОЛЬКО текст гипотезы.
                    """
                    hypothesis = await run_cursor_agent(link_prompt)
                    if hypothesis:
                        await conn.execute("""
                            INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                            VALUES ($1, $2, 0.95, $3, true)
                        """, node['domain_id'], f"🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА: {hypothesis}",
                        json.dumps({"source": "cross_domain_linker", "parents": [str(node['id'])]}))
                        if rd:
                            await rd.xadd("knowledge_stream", {"type": "synthetic_link", "content": hypothesis})

                await conn.execute("""
                    UPDATE knowledge_nodes
                    SET metadata = metadata || '{"orchestrated": "true"}'::jsonb
                    WHERE id = $1
                """, node['id'])

            # --- ФАЗА 5: ДВИГАТЕЛЬ ЛЮБОПЫТСТВА (с приоритизацией) ---
            logger.info("🔍 Phase 5: Curiosity Engine...")
            deserts = await conn.fetch("""
                SELECT d.id, d.name, count(k.id) as node_count
                FROM domains d LEFT JOIN knowledge_nodes k ON d.id = k.domain_id
                GROUP BY d.id, d.name
                HAVING count(k.id) < 50 OR max(k.created_at) < NOW() - INTERVAL '48 hours'
                ORDER BY count(k.id) ASC
                LIMIT 5
            """)

            for desert in deserts:
                expert_count = await conn.fetchval("SELECT count(*) FROM experts WHERE department = $1", desert['name'])
                if expert_count == 0:
                    logger.info("  🔍 Recruiting expert for %s...", desert['name'])
                    expert_gen_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expert_generator.py")
                    subprocess.run(["python3", expert_gen_path, desert['name']], check=False)

                curiosity_task = (
                    f"Проведи глубокое исследование новых технологий и трендов 2026 "
                    f"в области {desert['name']}. Найди 3 прорывных инсайта."
                )
                priority = 'high' if desert['node_count'] < 20 else 'medium'
                task_id = await conn.fetchval("""
                    INSERT INTO tasks (title, description, status, priority, creator_expert_id, domain_id, metadata)
                    VALUES ($1, $2, 'pending', $3, $4, $5, $6)
                    RETURNING id
                """, f"🔥 ИССЛЕДОВАНИЕ: {desert['name']}", curiosity_task, priority, victoria_id, desert['id'],
                json.dumps({"reason": "curiosity_engine_starvation", "node_count": desert['node_count']}))
                await assign_task_to_best_expert(conn, task_id, desert['id'])

            logger.info("🌐 Phase 5: Running Global Scout validation...")
            try:
                await run_global_scout_cycle()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Global Scout error: %s", exc)

            logger.info("🔗 Phase 6: Running auto-link detection...")
            try:
                await run_auto_link_detection()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Auto-link detection error: %s", exc)

            logger.info("🧬 Phase 7: Knowledge Distillation & Auto-Upgrade...")
            try:
                distiller = KnowledgeDistiller()
                distilled_count = await distiller.collect_high_quality_samples(days=1)
                if distilled_count > 0:
                    logger.info("  ✨ Distilled %d high-quality samples.", distilled_count)
                generator = SyntheticKnowledgeGenerator()
                await generator.generate_synthetic_samples(limit=5)
                pipeline = LocalTrainingPipeline()
                status = pipeline.trigger_auto_upgrade()
                if "ЗАПУЩЕН" in status or "ГОТОВ" in status:
                    logger.info("  🔥 AUTONOMOUS UPGRADE STATUS: %s", status)
                    await conn.execute("INSERT INTO notifications (message) VALUES ($1)", status)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Distillation error: %s", exc)

            logger.info("🔧 Phase 8: Self-Repair Engine...")
            try:
                errors = await conn.fetch("""
                    SELECT id, user_query, assistant_response, metadata
                    FROM interaction_logs
                    WHERE (assistant_response LIKE '❌%' OR assistant_response LIKE '⚠️%')
                    AND created_at > NOW() - INTERVAL '1 hour'
                    AND (metadata->>'repaired' IS NULL OR metadata->>'repaired' = 'false')
                    LIMIT 5
                """)
                for err in errors:
                    repair_task = (
                        f"ОШИБКА В СИСТЕМЕ: {err['assistant_response']}\n"
                        f"ЗАПРОС: {err['user_query']}\n\n"
                        f"ЗАДАЧА: Проанализируй логи и код, найди причину и предложи исправление."
                    )
                    await conn.execute("""
                        INSERT INTO tasks (title, description, status, priority, creator_expert_id, metadata)
                        VALUES ($1, $2, 'pending', 'urgent', $3, $4)
                    """, "🚨 АВТО-РЕМОНТ: Ошибка", repair_task, victoria_id,
                    json.dumps({"source": "self_repair", "log_id": str(err['id'])}))
                    await conn.execute("""
                        UPDATE interaction_logs
                        SET metadata = metadata || '{"repaired": "true"}'::jsonb
                        WHERE id = $1
                    """, err['id'])
                    logger.info("  🔧 Created repair task for log %s", err['id'])
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Self-repair error: %s", exc)

            logger.info("🐝 Phase 10: Swarm War-Room...")
            try:
                swarm = SwarmOrchestrator()
                await swarm.handle_critical_failures()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Swarm error: %s", exc)

            logger.info("🏗️ Phase 11: Meta-Architect Review...")
            try:
                architect = MetaArchitect()
                await architect.self_repair_cycle()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Meta-Architect error: %s", exc)

            logger.info("🧬 Phase 12: Autonomous Evolution...")
            try:
                evolution = SingularityEvolutionMonitor()
                evolution_report = await evolution.run_daily_check()
                logger.info("  %s", evolution_report)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Evolution error: %s", exc)

            logger.info("🔍 Phase 13: Curiosity Engine Gap Analysis...")
            try:
                curiosity = CuriosityEngine()
                gap_result = await curiosity.scan_for_gaps()
                logger.info("  %s", gap_result)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Curiosity error: %s", exc)

            logger.info("🧠 Phase 14: Memory Consolidation (The Dreaming)...")
            try:
                consolidator = MemoryConsolidator()
                consolidation_result = await consolidator.consolidate_memory()
                logger.info("  %s", consolidation_result)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Consolidation error: %s", exc)

            logger.info("🌐 Phase 15: Global Team Knowledge Sync...")
            if ServerKnowledgeSync:
                try:
                    last_sync_key = "last_global_sync"
                    last_sync = None
                    if rd:
                        last_sync = await rd.get(last_sync_key)
                    now_str = datetime.now().isoformat()
                    should_sync = True
                    if last_sync:
                        last_sync_dt = datetime.fromisoformat(last_sync)
                        if datetime.now() - last_sync_dt < timedelta(hours=1):
                            should_sync = False
                    if should_sync:
                        sync_manager = ServerKnowledgeSync()
                        await sync_manager.sync_experts()
                        synced_count = await sync_manager.sync_reports(limit=50)
                        logger.info("  📥 Synced %d reports and full team hierarchy.", synced_count)
                        if rd:
                            await rd.set(last_sync_key, now_str)
                    else:
                        logger.info("  ⏭️ Sync skipped (already synced recently).")
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.error("Sync error: %s", exc)
            else:
                logger.info("  ⚠️ ServerKnowledgeSync module not found.")

            logger.info("📦 Phase 16: Knowledge Archivation...")
            try:
                from knowledge_archiver import KnowledgeArchiver
                from strategy_session_manager import StrategySessionManager
                session_manager = StrategySessionManager()
                archiver = KnowledgeArchiver(session_manager)
                archive_key = "last_knowledge_archive"
                last_archive = None
                if rd:
                    last_archive = await rd.get(archive_key)
                now_str = datetime.now().isoformat()
                should_archive = True
                if last_archive:
                    last_archive_dt = datetime.fromisoformat(last_archive)
                    if datetime.now() - last_archive_dt < timedelta(days=1):
                        should_archive = False
                if should_archive:
                    await archiver.periodic_archive_task()
                    if rd:
                        await rd.set(archive_key, now_str)
                    logger.info("  ✅ Knowledge archivation completed.")
                else:
                    logger.info("  ⏭️ Archive skipped (already archived today).")
            except ImportError:
                logger.info("  ⚠️ KnowledgeArchiver module not found.")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Archive error: %s", exc)

            await conn.close()
            logger.info("[ENHANCED_ORCHESTRATOR] cycle finished successfully.")
        except Exception as cycle_exc:  # pylint: disable=broad-exception-caught
            logger.error("[ENHANCED_ORCHESTRATOR] cycle exception: %s", cycle_exc)
            logger.error(traceback.format_exc())
            try:
                await conn.close()
            except Exception:
                pass
            raise


async def run_continuous(interval_seconds: int = 60, quick_poll_seconds: int = 30):
    """
    Бесконечный цикл: оркестратор «все время слушает» — периодически запускает цикл оркестрации.
    После каждого цикла спит interval_seconds; если есть нераспределённые задачи — следующий цикл
    через quick_poll_seconds (реагируем быстрее при появлении работы).
    """
    logger.info(
        "[ENHANCED_ORCHESTRATOR] continuous mode: interval=%ss, quick_poll=%ss",
        interval_seconds,
        quick_poll_seconds,
    )
    while True:
        try:
            await run_enhanced_orchestration_cycle()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("[ENHANCED_ORCHESTRATOR] cycle error: %s", e)
            logger.error(traceback.format_exc())
        # Решаем, сколько спать: если есть нераспределённые задачи — короткий сон
        sleep_sec = interval_seconds
        if ASYNCPG_AVAILABLE and interval_seconds > quick_poll_seconds:
            try:
                conn = await asyncpg.connect(DB_URL)
                try:
                    unassigned = await conn.fetchval(
                        "SELECT COUNT(*) FROM tasks WHERE assignee_expert_id IS NULL AND status = 'pending'"
                    )
                    if unassigned and unassigned > 0:
                        sleep_sec = quick_poll_seconds
                        logger.info("[ENHANCED_ORCHESTRATOR] %s unassigned tasks, next cycle in %ss", unassigned, sleep_sec)
                finally:
                    await conn.close()
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.debug("Quick poll failed: %s, using full interval", e)
        await asyncio.sleep(sleep_sec)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Enhanced Orchestrator")
    parser.add_argument("--prompt", nargs="*", help="Single prompt (for Telegram gateway)")
    parser.add_argument("--continuous", action="store_true", help="Run forever: listen and orchestrate on interval")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between cycles in continuous mode (default: 60)")
    parser.add_argument("--quick-poll", type=int, default=30, help="Seconds to next cycle when unassigned tasks exist (default: 30)")
    args = parser.parse_args()

    # Поддержка прямого вызова через аргументы (для Telegram шлюза)
    if args.prompt:
        PROMPT_TEXT_INPUT = " ".join(args.prompt)
        try:
            main_result = asyncio.run(run_cursor_agent(PROMPT_TEXT_INPUT))
        except RuntimeError:
            main_result = run_smart_agent_sync(PROMPT_TEXT_INPUT, expert_name="Виктория", category="orchestrator")
        if main_result:
            print(main_result)
        else:
            print("❌ Ошибка генерации ответа в ядре.")
    elif args.continuous:
        asyncio.run(run_continuous(interval_seconds=args.interval, quick_poll_seconds=args.quick_poll))
    else:
        asyncio.run(run_enhanced_orchestration_cycle())
