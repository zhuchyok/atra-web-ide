import asyncio
import os
import json
import asyncpg
import subprocess
import re
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

# Connection pool для PostgreSQL (решает проблему "too many clients already")
_db_pool: Optional[asyncpg.Pool] = None

# MLX Request Queue для приоритетной обработки Совета
try:
    from mlx_request_queue import get_request_queue, RequestPriority
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
            max_inactive_connection_lifetime=300
        )
    return _db_pool

async def close_db_pool():
    """Закрыть connection pool"""
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None

def run_cursor_agent(prompt: str):
    try:
        env = os.environ.copy()
        result = subprocess.run(
            ['/root/.local/bin/cursor-agent', '--print', prompt],
            capture_output=True, text=True, check=True, timeout=300, env=env
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Board of Directors Agent error: {e}")
        return None


def parse_directive_structure(directive_text: str) -> Dict[str, Any]:
    """
    Парсинг текста директивы в структурированный формат.
    Извлекает: decision, rationale, risks, confidence, recommend_human_review
    """
    structured = {
        "decision": "",
        "rationale": "",
        "risks": [],
        "confidence": 0.8,
        "action_items": []
    }
    
    # Попытка извлечь decision (первая строка после "РЕШЕНИЕ:" или просто первое предложение)
    decision_match = re.search(r'(?:РЕШЕНИЕ|DECISION):\s*(.+?)(?:\n|$)', directive_text, re.IGNORECASE)
    if decision_match:
        structured["decision"] = decision_match.group(1).strip()
    else:
        # Берем первое предложение как decision
        first_sentence = directive_text.split('.')[0] if '.' in directive_text else directive_text[:200]
        structured["decision"] = first_sentence.strip()
    
    # Извлечь rationale (обоснование)
    rationale_match = re.search(r'(?:ОБОСНОВАНИЕ|RATIONALE):\s*(.+?)(?:\n\n|\n[А-ЯA-Z]|$)', directive_text, re.IGNORECASE | re.DOTALL)
    if rationale_match:
        structured["rationale"] = rationale_match.group(1).strip()
    else:
        # Если не найдено явное обоснование, берем весь текст как rationale
        structured["rationale"] = directive_text[:500].strip()
    
    # Извлечь risks
    risks_match = re.search(r'(?:РИСКИ|RISKS):\s*(.+?)(?:\n\n|\n[А-ЯA-Z]|$)', directive_text, re.IGNORECASE | re.DOTALL)
    if risks_match:
        risks_text = risks_match.group(1).strip()
        # Разбить на список по дефисам или цифрам
        risk_items = re.split(r'[-•]\s*|\d+\.\s*', risks_text)
        structured["risks"] = [r.strip() for r in risk_items if r.strip()]
    
    # Извлечь confidence
    confidence_match = re.search(r'(?:УВЕРЕННОСТЬ|CONFIDENCE):\s*([\d.]+)', directive_text, re.IGNORECASE)
    if confidence_match:
        try:
            structured["confidence"] = float(confidence_match.group(1))
        except:
            pass
    
    # Проверка на рекомендацию подтверждения человеком
    if re.search(r'(?:ТРЕБУЕТ.*ПОДТВЕРЖДЕНИЯ|HUMAN.*REVIEW|ПОДТВЕРДИТЬ)', directive_text, re.IGNORECASE):
        structured["recommend_human_review"] = True
    else:
        structured["recommend_human_review"] = False
    
    return structured


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
    print(f"[{datetime.now()}] 🏛 BOARD CONSULT starting (source={source}, correlation_id={correlation_id})...")
    
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # 1. Сбор контекста
            okr_context = ""
            try:
                okrs = await conn.fetch("SELECT objective, department, period FROM okrs LIMIT 5")
                okr_context = "\n".join([f"- {o['objective']} ({o['department']}, {o['period']})" for o in okrs]) if okrs else ""
            except Exception as e:
                print(f"⚠️ Не удалось получить OKR (таблица может отсутствовать или схема иная): {e}")
                okr_context = ""
            
            tasks_context = ""
            try:
                tasks_stats = await conn.fetch("SELECT status, count(*) FROM tasks GROUP BY status LIMIT 10")
                tasks_context = "\n".join([f"{t['status']}: {t['count']}" for t in tasks_stats]) if tasks_stats else ""
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
                    last_directive = last_dir_row['content'][:300] + "..."
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
                return await run_smart_agent_async(
                    board_prompt,
                    expert_name="Совет Директоров",
                    category="reasoning",  # Роутер выберет модель 20B+ (deepseek-r1:32b)
                    is_critical=True,      # Максимальное качество + отключение параллельной обработки
                    is_vip=True            # [VIP ROUTE] Форсируем использование лучших моделей
                )
            
            # Если доступна очередь, используем HIGH priority
            if _mlx_queue and RequestPriority:
                print("🏛️ [BOARD] Запрос с HIGH приоритетом через MLX Queue...")
                success, request_id, position = await _mlx_queue.add_request(
                    priority=RequestPriority.HIGH,  # ВЫСОКИЙ ПРИОРИТЕТ для Совета!
                    callback=board_llm_call,
                    timeout=300.0,  # 5 минут для reasoning
                    metadata={"source": source, "correlation_id": correlation_id}
                )
                if success:
                    print(f"✅ [BOARD] Запрос в очереди (ID: {request_id}, позиция: {position})")
                    # Ждем выполнения через callback
                    directive = await board_llm_call()
                else:
                    print(f"⚠️ [BOARD] Очередь переполнена, прямой вызов...")
                    directive = await board_llm_call()
            else:
                # Fallback: прямой вызов без очереди
                directive = await board_llm_call()
                
        except ImportError:
            print("⚠️ ai_core не доступен, используем run_cursor_agent как fallback")
            directive = run_cursor_agent(board_prompt)
        
        if not directive or len(directive) < 20:
            print("❌ Совет не смог принять решение (пустой ответ от LLM)")
            return None
        
        # 4. Парсинг структуры
        structured_decision = parse_directive_structure(directive)
        
        # Определение risk_level на основе ключевых слов и confidence
        risk_level = "low"
        directive_lower = directive.lower()
        if any(word in directive_lower for word in ['архитектура', 'бюджет', 'критичн', 'серьезн', 'риск']):
            risk_level = "high"
        elif any(word in directive_lower for word in ['важн', 'изменен', 'рефактор', 'переработ']):
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
            "last_directive": last_directive[:200] if last_directive else ""
        }
        
        # Получаем новое подключение из пула для записи
        pool = await get_db_pool()
        async with pool.acquire() as write_conn:
            await write_conn.execute("""
                INSERT INTO board_decisions (
                    source, correlation_id, session_id, user_id, question, context_snapshot,
                    directive_text, structured_decision, risk_level, recommend_human_review
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, source, correlation_id, session_id, user_id, question, json.dumps(context_snapshot),
                 directive, json.dumps(structured_decision), risk_level, recommend_human_review)
            
            # 6. Опционально: краткий узел в knowledge_nodes для истории (по возможности с embedding — VERIFICATION §5)
            try:
                domain_id = await write_conn.fetchval("SELECT id FROM domains WHERE name = 'Management' LIMIT 1")
                if domain_id:
                    content_kn = f"🏛 Консультация Совета: {structured_decision.get('decision', '')[:100]}"
                    meta_kn = json.dumps({"type": "board_consult", "correlation_id": correlation_id, "date": datetime.now().isoformat()})
                    conf = structured_decision.get("confidence", 0.8)
                    embedding = None
                    try:
                        from semantic_cache import get_embedding
                        embedding = await get_embedding(content_kn[:8000])
                    except Exception:
                        pass
                    if embedding is not None:
                        await write_conn.execute("""
                            INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                            VALUES ($1, $2, $3, $4, true, $5::vector)
                        """, domain_id, content_kn, conf, meta_kn, str(embedding))
                    else:
                        await write_conn.execute("""
                            INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                            VALUES ($1, $2, $3, $4, true)
                        """, domain_id, content_kn, conf, meta_kn)
            except Exception as e:
                print(f"⚠️ Не удалось сохранить узел в knowledge_nodes: {e}")
        
        print(f"✅ Board consult completed: decision='{structured_decision.get('decision', '')[:50]}...', risk={risk_level}, recommend_review={recommend_human_review}")
        
        return {
            "directive_text": directive,
            "structured_decision": structured_decision,
            "risk_level": risk_level,
            "recommend_human_review": recommend_human_review
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
    - Средний фидбек: {stats['avg_score'] or 'N/A'}
    - Ошибок: {stats['error_count']} из {stats['total_tasks']} задач
    
    ЗАДАЧА: Спрогнозируйте вероятность успеха (0-100%) и выявите 2 критических узких места.
    ОТВЕТЬТЕ В JSON: {{"probability": 85, "bottlenecks": ["...", "..."], "recommendation": "..."}}
    """
    
    from ai_core import run_smart_agent_async
    result = await run_smart_agent_async(sim_prompt, expert_name="Симулятор", category="reasoning", is_vip=True)
    
    try:
        # Очистка и парсинг
        if '```' in result:
            result = result.split('```')[1].replace('json', '').strip()
        return json.loads(result)
    except:
        return {"probability": 50, "bottlenecks": ["Не удалось провести точный расчет"], "recommendation": "Требуется ручной анализ"}

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
                okr_context = "\n".join([f"- {o['objective']} ({o['department']}, {o['period']})" for o in okrs]) if okrs else ""
            except Exception as e:
                print(f"⚠️ Не удалось получить OKR (таблица может отсутствовать или схема иная): {e}")
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
                insights_context = "\n".join([f"[{i['domain']}] {i['content'][:200]}..." for i in new_insights]) if new_insights else ""
            except Exception as e:
                print(f"⚠️ Не удалось получить знания: {e}")
                insights_context = ""
            
            # - Статус задач
            tasks_context = ""
            try:
                tasks_stats = await conn.fetch("SELECT status, count(*) FROM tasks GROUP BY status")
                tasks_context = "\n".join([f"{t['status']}: {t['count']}" for t in tasks_stats]) if tasks_stats else ""
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
                directive = await run_smart_agent_async(
                    board_prompt,
                    expert_name="Совет Директоров",
                    category="reasoning",  # Роутер выберет модель 30B+ (deepseek-r1:32b)
                    is_critical=True,
                    is_vip=True            # [VIP ROUTE] Форсируем использование лучших моделей
                )
            except ImportError:
                print("⚠️ ai_core не доступен, используем run_cursor_agent как fallback")
                directive = run_cursor_agent(board_prompt)
            
            if directive and len(directive) > 20 and "Ошибка" not in directive and "❌" not in directive:
                # 4. Парсинг структуры
                structured_decision = parse_directive_structure(directive)
                
                # 5. Сохранение в board_decisions (новое!)
                context_snapshot = {
                    "okr": okr_context[:500] if okr_context else "",
                    "insights": insights_context[:500] if insights_context else "",
                    "tasks": tasks_context[:300] if tasks_context else ""
                }
                
                try:
                    await conn.execute("""
                        INSERT INTO board_decisions (
                            source, question, context_snapshot, directive_text, 
                            structured_decision, risk_level
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                    """, 'nightly', 'Daily Strategic Board Meeting', json.dumps(context_snapshot), 
                         directive, json.dumps(structured_decision), 'medium')
                    print("✅ Директива сохранена в board_decisions")
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить в board_decisions: {e}")
                
                # 6. Сохраняем директиву в спец. узел знаний (Domain: Management); по возможности с embedding (VERIFICATION §5)
                try:
                    domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'Management'")
                    if domain_id:
                        content_kn = f"🏛 СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА: {directive}"
                        meta_kn = json.dumps({"type": "board_directive", "date": datetime.now().isoformat()})
                        embedding = None
                        try:
                            from semantic_cache import get_embedding
                            embedding = await get_embedding(content_kn[:8000])
                        except Exception:
                            pass
                        if embedding is not None:
                            await conn.execute("""
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                                VALUES ($1, $2, 1.0, $3, true, $4::vector)
                            """, domain_id, content_kn, meta_kn, str(embedding))
                        else:
                            await conn.execute("""
                                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                                VALUES ($1, $2, 1.0, $3, true)
                            """, domain_id, content_kn, meta_kn)
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить в knowledge_nodes: {e}")
                
                # 7. Также сохраняем в дебаты для истории - как было
                try:
                    await conn.execute("""
                        INSERT INTO expert_discussions (topic, consensus_summary, status)
                        VALUES ('Daily Strategic Board Meeting', $1, 'closed')
                    """, directive)
                except Exception as e:
                    print(f"⚠️ Не удалось сохранить в expert_discussions: {e}")
                
                print("✅ Strategic Directive issued and stored.")
                
                # 8. Публикация в Markdown для истории (Singularity 10.0: Transparency)
                try:
                    reports_dir = "/app/docs/board_reports"
                    # Если запуск локальный (не в Docker), используем относительный путь
                    if not os.path.exists("/.dockerenv"):
                        reports_dir = "docs/board_reports"
                    
                    os.makedirs(reports_dir, exist_ok=True)
                    
                    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
                    filename = f"DIRECTIVE_{date_str}.md"
                    filepath = os.path.join(reports_dir, filename)
                    
                    md_content = f"""# 🏛 СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА ДИРЕКТОРОВ
**Дата:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} UTC
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
            else:
                print("❌ Директива не получена или содержит ошибку. Сохранение пропущено.")
    
    except Exception as e:
        print(f"❌ Board meeting error: {e}")
        import traceback
        traceback.print_exc()
    print(f"[{datetime.now()}] Strategic Board Meeting finished.")

if __name__ == '__main__':
    asyncio.run(run_board_meeting())

