import asyncio
import json
import os
import re
import subprocess
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
BOARD_LLM_TIMEOUT_SECONDS = int(os.getenv("BOARD_LLM_TIMEOUT_SECONDS", "600"))

# Connection pool для PostgreSQL (решает проблему "too many clients already")
_db_pool: Optional[asyncpg.Pool] = None

# MLX Request Queue для приоритетной обработки Совета
try:
    from mlx_request_queue import RequestPriority, get_request_queue

    _mlx_queue = get_request_queue()
except ImportError:
    _mlx_queue = None
    RequestPriority = None


async def get_db_pool() -> asyncpg.Pool:
    """Получить или создать connection pool для PostgreSQL"""
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            DB_URL,
            min_size=2,
            max_size=10,
            command_timeout=60,
            max_inactive_connection_lifetime=300,
        )
    return _db_pool


async def close_db_pool():
    """Закрыть connection pool"""
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None




async def auto_apply_decision(
    decision_id: Optional[str],
    structured_decision: Dict[str, Any],
    board_question: str,
    risk_level: str,
    recommend_human_review: bool,
    source: str = "nightly",
) -> bool:
    """
    [AUTOPILOT] Автоматически применяет решение Совета:
    - Создаёт задачи в PostgreSQL (tasks table)
    - Отправляет в Redis Stream для экспертов
    - Обновляет статус board_decisions на 'applied'

    Запускается только если:
    - confidence >= 0.8
    - risk_level != 'high'
    - not recommend_human_review
    """
    print(
        f"[{datetime.now()}] 🤖 [AUTOPILOT] Checking decision: confidence={structured_decision.get('confidence')}, "
        f"risk={risk_level}, human_review={recommend_human_review}"
    )

    if recommend_human_review or risk_level == "high" or structured_decision.get("confidence", 0) < 0.8:
        print("  ⏭️ Autopilot skipped: needs human review or low confidence")
        return False

    action_items = structured_decision.get("action_items", [])
    if not action_items:
        # Fallback: create a generic task from the decision text
        decision_text = structured_decision.get("decision", board_question)[:200]
        action_items = [{"task": decision_text, "owner": "auto", "deadline": "24h"}]
        print(f"  📋 No explicit action items, using decision text: {decision_text[:60]}")

    print(f"  🚀 Autopilot creating {len(action_items)} tasks...")
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            task_ids = []
            for item in action_items:
                task_goal = f"[BOARD] {item['task']}"
                task_id = str(uuid.uuid4())
                task_ids.append(task_id)
                await conn.execute(
                    """
                    INSERT INTO tasks (id, goal, status, priority, expert_name, project_context, created_at)
                    VALUES ($1, $2, 'pending', 8, $3, $4, NOW())
                """,
                    task_id,
                    task_goal,
                    item.get("owner", "auto"),
                    "board_autopilot",
                )

            # Отправляем в Redis Stream для экспертов
            try:
                import redis.asyncio as aioredis

                redis_url = os.getenv("REDIS_URL", "redis://host.docker.internal:6379/0")
                r = aioredis.from_url(redis_url, decode_responses=True)
                for task_id in task_ids:
                    await r.xadd(
                        "expert_tasks:auto",
                        {
                            "task_id": task_id,
                            "source": "board_autopilot",
                            "priority": "8",
                            "correlation_id": decision_id or "",
                        },
                    )
                await r.aclose()
                print(f"  ✅ {len(task_ids)} tasks pushed to Redis")
            except Exception as e:
                print(f"  ⚠️ Redis push failed (tasks saved in DB): {e}")

            # Обновляем статус решения
            if decision_id:
                try:
                    await conn.execute(
                        "UPDATE board_decisions SET status = 'applied', applied_at = NOW() WHERE id = $1::uuid",
                        decision_id,
                    )
                except Exception:
                    await conn.execute(
                        "UPDATE board_decisions SET status = 'applied', applied_at = NOW() WHERE id = $1",
                        decision_id,
                    )

        print(f"  ✅ [AUTOPILOT] Decision applied: {len(action_items)} tasks created")
        return True
    except Exception as e:
        print(f"  ❌ [AUTOPILOT] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def consult_board(
    question: str,
    context: Optional[Dict] = None,
    correlation_id: Optional[str] = None,
    source: str = "api",
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Консультация Совета Директоров по единичному вопросу.

    Args:
        question: Вопрос пользователя/чата
        context: Дополнительный контекст (опционально)
        correlation_id: ID для трассировки запроса
        source: Источник запроса (chat, api, nightly, dashboard)
        session_id: ID сессии (для чата)
        user_id: ID пользователя (для чата)

    Returns:
        {"directive_text": str, "structured_decision": dict} или None при ошибке
    """
    print(
        f"[{datetime.now()}] 🏛 BOARD CONSULT starting (source={source}, correlation_id={correlation_id})..."
    )

    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # 1. Сбор контекста
            okr_context = ""
            try:
                okrs = await conn.fetch("SELECT objective, department, period FROM okrs LIMIT 5")
                okr_context = (
                    "\n".join(
                        [f"- {o['objective']} ({o['department']}, {o['period']})" for o in okrs]
                    )
                    if okrs
                    else ""
                )
            except Exception as e:
                print(
                    f"⚠️ Не удалось получить OKR (таблица может отсутствовать или схема иная): {e}"
                )
                okr_context = ""

            tasks_context = ""
            try:
                tasks_stats = await conn.fetch(
                    "SELECT status, count(*) FROM tasks GROUP BY status LIMIT 10"
                )
                tasks_context = (
                    "\n".join([f"{t['status']}: {t['count']}" for t in tasks_stats])
                    if tasks_stats
                    else ""
                )
            except Exception as e:
                print(f"⚠️ Не удалось получить статус задач: {e}")
                tasks_context = ""

            # Последняя директива (для контекста)
            last_directive = ""
            try:
                last_dir_row = await conn.fetchrow("""
                    SELECT content FROM knowledge_nodes
                    WHERE metadata->>'type' = 'board_directive'
                    ORDER BY created_at DESC LIMIT 1
                """)
                if last_dir_row:
                    last_directive = last_dir_row["content"][:300] + "..."
            except Exception as e:
                print(f"⚠️ Не удалось получить последнюю директиву: {e}")

        # 2. Формирование промпта для Совета
        board_prompt = f"""
ВЫ - СОВЕТ ДИРЕКТОРОВ КОРПОРАЦИИ (CEO Владимир, Lead Виктория, CTO Дмитрий).

КОНТЕКСТ:
{f"OKR: {okr_context}" if okr_context else "OKR: не заданы"}
{f"Задачи: {tasks_context}" if tasks_context else "Задачи: нет данных"}
{f"Последняя директива: {last_directive}" if last_directive else ""}

ВОПРОС ОТ ПОЛЬЗОВАТЕЛЯ:
{question}

ЗАДАЧА: Примите стратегическое решение. Ответьте в структурированном формате:

РЕШЕНИЕ: [одна фраза - что делать]
ОБОСНОВАНИЕ: [почему это решение оптимально с точки зрения OKR и текущей ситуации]
РИСКИ: [если есть, укажите риски и митигацию]
УВЕРЕННОСТЬ: [0.0-1.0 - насколько Совет уверен в решении]

Если решение критично (архитектура/бюджет/сроки) и уверенность < 0.8, укажите:
ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ ЧЕЛОВЕКОМ

ФОРМАТ: Строгий корпоративный стиль, без лишних комментариев.
"""

        # 3. Вызов LLM через ai_core (динамический выбор модели)
        # С ВЫСОКИМ ПРИОРИТЕТОМ через MLX Request Queue!
        try:
            # Импорт ai_core для вызова локальных моделей
            from ai_core import run_smart_agent_async

            # Оборачиваем в HIGH priority callback для очереди
            async def board_llm_call():
                return await asyncio.wait_for(
                    run_smart_agent_async(
                        board_prompt,
                        expert_name="Совет Директоров",
                        category="reasoning",  # Роутер выберет модель 20B+ (deepseek-r1:32b)
                        is_critical=True,  # Максимальное качество + отключение параллельной обработки
                        is_vip=True,  # [VIP ROUTE] Форсируем использование лучших моделей
                    ),
                    timeout=BOARD_LLM_TIMEOUT_SECONDS,
                )

            # Если доступна очередь, используем HIGH priority
            if _mlx_queue and RequestPriority:
                print("🏛️ [BOARD] Запрос с HIGH приоритетом через MLX Queue...")
                success, request_id, position = await _mlx_queue.add_request(
                    priority=RequestPriority.HIGH,  # ВЫСОКИЙ ПРИОРИТЕТ для Совета!
                    callback=board_llm_call,
                    timeout=300.0,  # 5 минут для reasoning
                    metadata={"source": source, "correlation_id": correlation_id},
                )
                if success:
                    print(f"✅ [BOARD] Запрос в очереди (ID: {request_id}, позиция: {position})")
                    # Ждем выполнения через callback
                    directive = await board_llm_call()
                else:
                    print("⚠️ [BOARD] Очередь переполнена, прямой вызов...")
                    directive = await board_llm_call()
            else:
                # Fallback: прямой вызов без очереди
                directive = await board_llm_call()

        except ImportError:
            print("⚠️ ai_core не доступен, используем fallback директиву")
            directive = None

        if not directive or len(directive) < 20:
            print("❌ Совет не смог принять решение (пустой ответ от LLM)")
            return None

        # 4. Парсинг структуры
        structured_decision = parse_directive_structure(directive)

        # Определение risk_level на основе ключевых слов и confidence
        risk_level = "low"
        directive_lower = directive.lower()
        if any(
            word in directive_lower
            for word in ["архитектура", "бюджет", "критичн", "серьезн", "риск"]
        ):
            risk_level = "high"
        elif any(word in directive_lower for word in ["важн", "изменен", "рефактор", "переработ"]):
            risk_level = "medium"

        if structured_decision.get("confidence", 1.0) < 0.7:
            risk_level = "high"  # Низкая уверенность = высокий риск

        recommend_human_review = structured_decision.get("recommend_human_review", False)
        if risk_level == "high" or structured_decision.get("confidence", 1.0) < 0.7:
            recommend_human_review = True

        # 5. Сохранение в board_decisions (используем pool.acquire() снова)
        context_snapshot = {
            "okr": okr_context[:500] if okr_context else "",
            "tasks": tasks_context[:300] if tasks_context else "",
            "last_directive": last_directive[:200] if last_directive else "",
        }

        # Получаем новое подключение из пула для записи
        pool = await get_db_pool()
        async with pool.acquire() as write_conn:
            decision_id = await write_conn.fetchval(
                """
                INSERT INTO board_decisions (
                    source, correlation_id, session_id, user_id, question, context_snapshot,
                    directive_text, structured_decision, risk_level, recommend_human_review, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'pending')
                RETURNING id::text
            """,
                source,
                correlation_id,
                session_id,
                user_id,
                question,
                json.dumps(context_snapshot),
                directive,
                json.dumps(structured_decision),
                risk_level,
                recommend_human_review,
            )

            # 6. Опционально: краткий узел в knowledge_nodes для истории (по возможности с embedding — VERIFICATION §5)
            try:
                domain_id = await write_conn.fetchval(
                    "SELECT id FROM domains WHERE name = 'Management' LIMIT 1"
                )
                if domain_id:
                    content_kn = (
                        f"🏛 Консультация Совета: {structured_decision.get('decision', '')[:100]}"
                    )
                    meta_kn = json.dumps(
                        {
                            "type": "board_consult",
                            "correlation_id": correlation_id,
                            "date": datetime.now().isoformat(),
                        }
                    )
                    conf = structured_decision.get("confidence", 0.8)
                    embedding = None
                    try:
                        from semantic_cache import get_embedding

                        embedding = await get_embedding(content_kn[:8000])
                    except Exception:
                        pass
                    if embedding is not None:
                        await write_conn.execute(
                            """
                            INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                            VALUES ($1, $2, $3, $4, true, $5::vector)
                        """,
                            domain_id,
                            content_kn,
                            conf,
                            meta_kn,
                            str(embedding),
                        )
                    else:
                        await write_conn.execute(
                            """
                            INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                            VALUES ($1, $2, $3, $4, true)
                        """,
                            domain_id,
                            content_kn,
                            conf,
                            meta_kn,
                        )
            except Exception as e:
                print(f"⚠️ Не удалось сохранить узел в knowledge_nodes: {e}")

        # 7. ExpertCouncil validation: проверяем решение через совет экспертов
        try:
            from expert_council_discussion import ExpertCouncil

            council = ExpertCouncil()
            debate_result = await council.start_debate(
                topic=f"Валидация решения Совета: {structured_decision.get('decision', '')[:80]}",
                initial_proposal=(
                    f"РЕШЕНИЕ: {structured_decision.get('decision', '')}\n"
                    f"ОБОСНОВАНИЕ: {structured_decision.get('rationale', '')[:200]}\n"
                    f"ДЕЙСТВИЯ:\n"
                    + "\n".join(f"- {a['task']}" for a in structured_decision.get('action_items', []))
                ),
                beautiful_mode=False,
            )
            print(f"  ✅ ExpertCouncil validation: {len(debate_result or '')} chars")
        except Exception as e:
            print(f"  ⚠️ ExpertCouncil validation skipped: {e}")

        # 8. Autopilot: автоматическое применение решения
        try:
            await auto_apply_decision(
                decision_id=decision_id,
                structured_decision=structured_decision,
                board_question=question,
                risk_level=risk_level,
                recommend_human_review=recommend_human_review,
                source=source,
            )
        except Exception as e:
            print(f"⚠️ Autopilot error (non-critical): {e}")

        print(
            f"✅ Board consult completed: decision='{structured_decision.get('decision', '')[:50]}...', risk={risk_level}, recommend_review={recommend_human_review}"
        )

        return {
            "directive_text": directive,
            "structured_decision": structured_decision,
            "risk_level": risk_level,
            "recommend_human_review": recommend_human_review,
        }

    except Exception as e:
        print(f"❌ Board consult error: {e}")
        import traceback

        traceback.print_exc()
        return None


async def run_board_simulation(conn, proposed_goal: str) -> Dict[str, Any]:
    """[Strategic Simulator] Прогон цели через исторические данные и экспертов."""
    print(f"🚀 [SIMULATOR] Запуск симуляции для цели: {proposed_goal}")

    # 1. Сбор исторических данных об успехах/ошибках
    stats = await conn.fetchrow("""
        SELECT
            AVG(feedback_score) as avg_score,
            COUNT(*) FILTER (WHERE metadata->>'error' IS NOT NULL) as error_count,
            COUNT(*) as total_tasks
        FROM interaction_logs
        WHERE created_at > NOW() - INTERVAL '30 days'
    """)

    # 2. Промпт для симуляции
    sim_prompt = f"""
    ВЫ - СТРАТЕГИЧЕСКИЙ СИМУЛЯТОР Singularity 10.0.
    ПРЕДЛОЖЕННАЯ ЦЕЛЬ: {proposed_goal}

    ИСТОРИЧЕСКИЙ КОНТЕКСТ (30 дней):
    - Средний фидбек: {stats["avg_score"] or "N/A"}
    - Ошибок: {stats["error_count"]} из {stats["total_tasks"]} задач

    ЗАДАЧА: Спрогнозируйте вероятность успеха (0-100%) и выявите 2 критических узких места.
    ОТВЕТЬТЕ В JSON: {{"probability": 85, "bottlenecks": ["...", "..."], "recommendation": "..."}}
    """

    from ai_core import run_smart_agent_async

    result = await run_smart_agent_async(
        sim_prompt, expert_name="Симулятор", category="reasoning", is_vip=True
    )

    try:
        # Очистка и парсинг
        if "```" in result:
            result = result.split("```")[1].replace("json", "").strip()
        return json.loads(result)
    except:
        return {
            "probability": 50,
            "bottlenecks": ["Не удалось провести точный расчет"],
            "recommendation": "Требуется ручной анализ",
        }


async def run_board_meeting():
    print(f"[{datetime.now()}] 🏛 STRATEGIC BOARD OF DIRECTORS MEETING starting...")

    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # 1. Сбор данных для заседания
            # - Текущие OKR
            okr_context = ""
            try:
                okrs = await conn.fetch("SELECT objective, department, period FROM okrs")
                okr_context = (
                    "\n".join(
                        [f"- {o['objective']} ({o['department']}, {o['period']})" for o in okrs]
                    )
                    if okrs
                    else ""
                )
            except Exception as e:
                print(
                    f"⚠️ Не удалось получить OKR (таблица может отсутствовать или схема иная): {e}"
                )
                okr_context = ""

            # - Новые знания за 24 часа
            insights_context = ""
            try:
                new_insights = await conn.fetch("""
                    SELECT k.content, d.name as domain
                    FROM knowledge_nodes k
                    JOIN domains d ON k.domain_id = d.id
                    WHERE k.created_at > NOW() - INTERVAL '24 hours'
                    LIMIT 50
                """)
                insights_context = (
                    "\n".join([f"[{i['domain']}] {i['content'][:200]}..." for i in new_insights])
                    if new_insights
                    else ""
                )
            except Exception as e:
                print(f"⚠️ Не удалось получить знания: {e}")
                insights_context = ""

            # - Статус задач
            tasks_context = ""
            try:
                tasks_stats = await conn.fetch("SELECT status, count(*) FROM tasks GROUP BY status")
                tasks_context = (
                    "\n".join([f"{t['status']}: {t['count']}" for t in tasks_stats])
                    if tasks_stats
                    else ""
                )
            except Exception as e:
                print(f"⚠️ Не удалось получить статус задач: {e}")
                tasks_context = ""

            # 2. Промпт для Совета Директоров
            board_prompt = f"""
ВЫ - СОВЕТ ДИРЕКТОРОВ КОРПОРАЦИИ (CEO Владимир, Lead Виктория, CTO Дмитрий).

ТЕКУЩИЕ ЦЕЛИ (OKR):
{okr_context if okr_context else "Не заданы"}

ДОСТИЖЕНИЯ ЗА 24 ЧАСА:
{insights_context if insights_context else "Новых критических знаний не добавлено."}

СТАТУС ОПЕРАЦИЙ:
{tasks_context if tasks_context else "Нет данных по задачам"}

ЗАДАЧА: Проведите стратегический анализ. Сформулируйте "ДИРЕКТИВУ СОВЕТА ДИРЕКТОРОВ" на следующие 24 часа.

Директива должна содержать:
1. РЕШЕНИЕ: Резюме текущего состояния и главное направление.
2. ОБОСНОВАНИЕ: Почему это важно сейчас.
3. 3 ГЛАВНЫХ ФОКУСА для всех экспертов.
4. ОДНО РАДИКАЛЬНОЕ РЕШЕНИЕ для ускорения роста.

ФОРМАТ: СТРОГИЙ КОРПОРАТИВНЫЙ СТИЛЬ.
"""

            # 3. Вызов LLM
            try:
                from ai_core import run_smart_agent_async

                # Ежедневное заседание Совета требует мощную модель (минимум 30B)
                # Роутер автоматически выберет deepseek-r1:70b или qwq:32b
                directive = await asyncio.wait_for(
                    run_smart_agent_async(
                        board_prompt,
                        expert_name="Совет Директоров",
                        category="reasoning",  # Роутер выберет модель 30B+ (deepseek-r1:32b)
                        is_critical=True,
                        is_vip=True,  # [VIP ROUTE] Форсируем использование лучших моделей
                    ),
                    timeout=BOARD_LLM_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                print(
                    f"⏱️ Board LLM timed out after {BOARD_LLM_TIMEOUT_SECONDS}s, using fallback directive."
                )
                directive = None
            except ImportError:
                print("⚠️ ai_core не доступен, используем fallback директиву")
                directive = None

            fallback_mode = False
            if not directive or len(directive) <= 20 or "Ошибка" in directive or "❌" in directive:
                fallback_mode = True
                directive = (
                    "РЕШЕНИЕ: Работать в режиме операционной стабильности до восстановления LLM-контура Совета.\n"
                    "ОБОСНОВАНИЕ: Планировщик, задачи и дистилляция активны, но стратегическая генерация директив недоступна.\n"
                    "РИСКИ: Потеря стратегического фокуса при длительном отсутствии автоматических решений Совета.\n"
                    "УВЕРЕННОСТЬ: 0.62\n"
                    "ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ ЧЕЛОВЕКОМ\n"
                    "ФОКУСЫ:\n"
                    "1) Восстановить LLM-контур Совета и завершение заседаний без зависаний.\n"
                    "2) Контролировать stale источники в дашборде и подтверждать свежесть каждые 60 минут.\n"
                    "3) Сохранять throughput задач и нулевые критические ошибки в контейнерах."
                )
                print("⚠️ Board LLM unavailable, using deterministic fallback directive.")

            if directive and len(directive) > 20:
                # 4. Парсинг структуры
                structured_decision = parse_directive_structure(directive)

                # 5. Сохранение в board_decisions (новое!)
                context_snapshot = {
                    "okr": okr_context[:500] if okr_context else "",
                    "insights": insights_context[:500] if insights_context else "",
                    "tasks": tasks_context[:300] if tasks_context else "",
                    "fallback_mode": fallback_mode,
                }

                try:
                    meeting_decision_id = await conn.fetchval(
                        """
                        INSERT INTO board_decisions (
                            source, question, context_snapshot, directive_text,
                            structured_decision, risk_level, status
                        ) VALUES ($1, $2, $3, $4, $5, $6, 'pending')
                        RETURNING id::text
                    """,
                        "nightly",
                        "Daily Strategic Board Meeting",
                        json.dumps(context_snapshot),
                        directive,
                        json.dumps(structured_decision),
                        "high" if fallback_mode else "medium",
                    )
                    print("✅ Директива сохранена в board_decisions")
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить в board_decisions: {e}")

                # 6. Сохраняем директиву в спец. узел знаний (Domain: Management); по возможности с embedding (VERIFICATION §5)
                try:
                    domain_id = await conn.fetchval(
                        "SELECT id FROM domains WHERE name = 'Management'"
                    )
                    if domain_id:
                        content_kn = f"🏛 СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА: {directive}"
                        now_dt = datetime.now()
                        directive_ts = now_dt.isoformat()
                        directive_completed_ts = int(now_dt.timestamp())
                        # Board directives are already structured operational summaries.
                        # Mark them as distilled at write time to prevent artificial tail growth.
                        meta_kn = json.dumps(
                            {
                                "source": "strategic_board",
                                "type": "board_directive",
                                "date": directive_ts,
                                "fallback_mode": fallback_mode,
                                "distilled": "true",
                                "distill_status": "done",
                                "distilled_by": "system:strategic_board",
                                "distill_rework_reason": "pre_distilled_board_directive",
                                "distill_completed_at": directive_completed_ts,
                            }
                        )
                        embedding = None
                        try:
                            from semantic_cache import get_embedding

                            embedding = await get_embedding(content_kn[:8000])
                        except Exception:
                            pass
                        if embedding is not None:
                            await conn.execute(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                                VALUES ($1, $2, 1.0, $3, true, $4::vector)
                            """,
                                domain_id,
                                content_kn,
                                meta_kn,
                                str(embedding),
                            )
                        else:
                            await conn.execute(
                                """
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                                VALUES ($1, $2, 1.0, $3, true)
                            """,
                                domain_id,
                                content_kn,
                                meta_kn,
                            )
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить в knowledge_nodes: {e}")

                # 7. Также сохраняем в дебаты для истории - как было
                try:
                    await conn.execute(
                        """
                        INSERT INTO expert_discussions (topic, consensus_summary, status)
                        VALUES ('Daily Strategic Board Meeting', $1, 'closed')
                    """,
                        directive,
                    )
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить в expert_discussions: {e}")

                print("✅ Strategic Directive issued and stored.")

                # 8. Публикация в Markdown для истории (Singularity 10.0: Transparency)
                try:
                    reports_dir = "/app/docs/board_reports"
                    # Если запуск локальный (не в Docker), используем относительный путь
                    if not os.path.exists("/.dockerenv"):
                        reports_dir = "docs/board_reports"
                    elif not os.access("/app/docs", os.W_OK):
                        reports_dir = "/tmp/board_reports"

                    os.makedirs(reports_dir, exist_ok=True)

                    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
                    filepath = os.path.join(reports_dir, f"directive_{date_str}.md")
                    md_content = f"""# 🏛 СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА ДИРЕКТОРОВ
**Дата:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} MSK
**Статус:** ДЕЙСТВУЕТ (24 часа)

## 📊 КОНТЕКСТ ЗАСЕДАНИЯ
### Текущие цели (OKR)
{okr_context if okr_context else "Цели не заданы."}

### Операционный статус
{tasks_context if tasks_context else "Нет данных по задачам."}

---

## 📜 ТЕКСТ ДИРЕКТИВЫ
{directive}

---
*Документ сформирован автоматически ИИ-корпорацией Singularity 10.0. Все решения подлежат исполнению экспертами Atra Core.*
"""
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(md_content)
                    print(f"📄 Директива опубликована: {filepath}")

                    # Обновляем индексный файл последних отчетов
                    index_path = os.path.join(reports_dir, "LATEST.md")
                    with open(index_path, "w", encoding="utf-8") as f:
                        f.write(md_content)

                except Exception as e:
                    print(f"⚠️ Не удалось опубликовать Markdown отчет: {e}")

                # 9. ExpertCouncil validation
                if not fallback_mode:
                    try:
                        from expert_council_discussion import ExpertCouncil
                        council = ExpertCouncil()
                        debate_result = await council.start_debate(
                            topic=f"Валидация директивы: {structured_decision.get('decision', '')[:80]}",
                            initial_proposal=(
                                f"ДИРЕКТИВА: {structured_decision.get('decision', '')}\n"
                                f"ФОКУСЫ:\n"
                                + "\n".join(f"- {a['task']}" for a in structured_decision.get('action_items', []))
                            ),
                            beautiful_mode=False,
                        )
                        print(f"  ✅ Council validation: {len(debate_result or '')} chars")
                    except Exception as e:
                        print(f"  ⚠️ Council validation skipped: {e}")

                # 10. Autopilot: автоматическое применение директивы
                try:
                    await auto_apply_decision(
                        decision_id=meeting_decision_id if not fallback_mode else None,
                        structured_decision=structured_decision,
                        board_question="Daily Strategic Board Meeting",
                        risk_level="high" if fallback_mode else "medium",
                        recommend_human_review=fallback_mode or structured_decision.get("recommend_human_review", True),
                        source="nightly",
                    )
                except Exception as e:
                    print(f"⚠️ Autopilot error (non-critical): {e}")
            else:
                print("❌ Директива не получена. Сохранение пропущено.")

    except Exception as e:
        print(f"❌ Board meeting error: {e}")
        import traceback

        traceback.print_exc()
    print(f"[{datetime.now()}] Strategic Board Meeting finished.")


if __name__ == "__main__":
    asyncio.run(run_board_meeting())
