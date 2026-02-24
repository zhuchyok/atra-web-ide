"""
Corporation Data Tool — универсальный инструмент для запросов к БД корпорации.
Victoria (или любой агент) может задать вопрос на естественном языке,
инструмент сформирует SQL и вернёт результат.

Это позволяет отвечать на ЛЮБЫЕ вопросы о корпорации без хардкода классификаторов.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Схема БД корпорации (для контекста модели)
DB_SCHEMA_CONTEXT = """
Схема базы данных корпорации Singularity 10.0:

1. experts (сотрудники/эксперты корпорации):
   - id (UUID), name (имя), role (роль), department (отдел)
   - system_prompt (промпт), performance_score (рейтинг), virtual_budget
   - is_active, created_at, updated_at

2. tasks (задачи):
   - id (UUID), title, description, status ('pending', 'in_progress', 'completed', 'cancelled')
   - priority, assignee_expert_id (FK → experts), creator_expert_id
   - created_at, updated_at, deadline, result

3. knowledge_nodes (узлы знаний):
   - id (UUID), domain_id (FK → domains), content (текст знания)
   - embedding (вектор), confidence_score, is_verified
   - usage_count, created_at, updated_at

4. domains (домены знаний):
   - id (UUID), name, description, created_at

5. interaction_logs (логи взаимодействий):
   - id, expert_id, query, response, feedback_score
   - created_at, tokens_used

6. okrs (OKR цели):
   - id, objective, key_results, progress, quarter, year

7. corporation_kpis (KPI метрики):
   - id, metric_name, current_value, target_value, updated_at

ВАЖНО: Генерируй ТОЛЬКО SELECT запросы (read-only). Никаких INSERT/UPDATE/DELETE.
"""


async def _generate_sql_from_question(question: str, llm_url: str) -> Optional[str]:
    """
    Генерирует SQL-запрос из вопроса на естественном языке.
    Использует LLM для понимания вопроса и формирования SQL.
    """
    prompt = f"""{DB_SCHEMA_CONTEXT}

Вопрос пользователя: «{question}»

Сгенерируй SQL SELECT запрос для PostgreSQL, который ответит на этот вопрос.
Правила:
1. Только SELECT (никаких INSERT/UPDATE/DELETE)
2. Используй COUNT(*), SUM(), AVG() для агрегации
3. Для подсчёта записей: SELECT COUNT(*) FROM table_name
4. Ограничивай LIMIT 100 если возвращаешь строки
5. Используй русские названия колонок если они есть

Верни ТОЛЬКО SQL запрос без пояснений, без markdown, без ```sql```:"""

    try:
        from app.network_resilience import safe_http_request

        is_mlx = "11435" in llm_url
        if is_mlx:
            payload = {
                "category": "coding",
                "prompt": prompt,
                "stream": False,
                "max_tokens": 300,
                "temperature": 0.1,
            }
        else:
            payload = {
                "model": "qwen2.5-coder:32b",  # Лучшая для SQL
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 300, "temperature": 0.1},
            }
        resp = await safe_http_request(
            f"{llm_url}/api/generate", method="POST", timeout=30, json=payload
        )
        if resp is None or resp.status_code != 200:
            return None
        data = resp.json()
        sql = (data.get("response") or data.get("text") or "").strip()
        # Очистка от markdown
        sql = sql.replace("```sql", "").replace("```", "").strip()
        # Проверка безопасности
        sql_upper = sql.upper()
        if any(
            kw in sql_upper
            for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE"]
        ):
            logger.warning(f"⚠️ Попытка выполнить опасный SQL: {sql[:100]}")
            return None
        if not sql_upper.startswith("SELECT"):
            logger.warning(f"⚠️ SQL не начинается с SELECT: {sql[:100]}")
            return None
        return sql
    except Exception as e:
        logger.error(f"Ошибка генерации SQL: {e}")
        return None


async def _execute_sql(sql: str) -> Dict[str, Any]:
    """Выполняет SQL запрос и возвращает результат."""
    try:
        import asyncpg

        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
        conn = await asyncpg.connect(db_url, timeout=5.0)
        try:
            rows = await conn.fetch(sql)
            if not rows:
                return {"success": True, "data": [], "count": 0}
            # Конвертируем Record в dict
            result = [dict(r) for r in rows]
            return {"success": True, "data": result, "count": len(result)}
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Ошибка выполнения SQL: {e}")
        return {"success": False, "error": str(e)}


async def _format_answer(question: str, sql_result: Dict[str, Any], llm_url: str) -> str:
    """Форматирует ответ на естественном языке на основе данных из БД."""
    if not sql_result.get("success"):
        return f"Не удалось получить данные: {sql_result.get('error', 'неизвестная ошибка')}"

    data = sql_result.get("data", [])
    if not data:
        return "По вашему запросу данных не найдено."

    # Если простой COUNT — НЕ отдаём в LLM! Модель может подменить число (галлюцинация).
    # Отвечаем напрямую, без LLM-формулирования.
    if len(data) == 1 and len(data[0]) == 1:
        key = list(data[0].keys())[0]
        value = data[0][key]
        if isinstance(value, (int, float)):
            # Простой шаблон по смыслу вопроса — без LLM
            q = question.lower()
            if any(w in q for w in ["сотрудник", "эксперт", "employee", "людей", "команда"]):
                return f"В корпорации {value} сотрудников (экспертов)."
            if any(w in q for w in ["узл", "знани", "knowledge", "node"]):
                return f"В базе знаний корпорации {value} узлов знаний."
            if any(w in q for w in ["задач", "task"]):
                # Сингулярность 10.0: Для статуса проекта добавляем контекст дашборда
                is_status_project = "статус" in q and (
                    "проект" in q or "задач" in q or "дашборд" in q
                )
                answer = f"В корпорации {value} задач."
                if is_status_project:
                    answer += "\n\n💡 Статус проекта также доступен в дашборде (порт 8501), смотрите список задач Knowledge OS. Детали в MASTER_REFERENCE."
                return answer
            return f"Результат: {value}"

    # Для таблиц — форматируем
    q = question.lower()
    is_status_project = "статус" in q and ("проект" in q or "задач" in q or "дашборд" in q)

    if len(data) <= 10:
        lines = []
        for i, row in enumerate(data, 1):
            line = ", ".join(f"{k}: {v}" for k, v in row.items())
            lines.append(f"{i}. {line}")
        answer = "Результаты:\n" + "\n".join(lines)
    else:
        answer = f"Найдено {len(data)} записей. Показаны первые 10:\n" + "\n".join(
            f"{i}. " + ", ".join(f"{k}: {v}" for k, v in row.items())
            for i, row in enumerate(data[:10], 1)
        )

    if is_status_project:
        answer += "\n\n💡 Статус проекта также доступен в дашборде (порт 8501), смотрите список задач Knowledge OS. Детали в MASTER_REFERENCE."

    return answer


async def query_corporation_data(question: str) -> Dict[str, Any]:
    """
    Главная функция — отвечает на любой вопрос о данных корпорации.

    Args:
        question: Вопрос на естественном языке (рус/англ)

    Returns:
        Dict с ключами: answer (ответ), sql (SQL запрос), raw_data (сырые данные)
    """
    logger.info(f"📊 [CORP DATA TOOL] Вопрос: {question[:100]}...")

    # Запрос о показателях Mac Studio (память, CPU) — не SQL, а системные метрики
    if is_system_metrics_question(question):
        sys_result = await query_system_metrics()
        return {
            "answer": sys_result.get("answer", ""),
            "sql": None,
            "raw_data": None,
            "count": None,
            "success": sys_result.get("success", False),
        }

    # Определяем URL для LLM
    is_docker = (
        os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
    )
    if is_docker:
        mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    else:
        mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Пробуем MLX, потом Ollama
    llm_urls = [url for url in [mlx_url, ollama_url] if url and url.lower() != "disabled"]

    sql = None
    for llm_url in llm_urls:
        sql = await _generate_sql_from_question(question, llm_url)
        if sql:
            logger.info(f"✅ SQL сгенерирован через {llm_url}: {sql[:100]}...")
            break

    if not sql:
        return {
            "answer": "Не удалось понять вопрос и сформировать запрос к базе данных.",
            "sql": None,
            "raw_data": None,
            "success": False,
        }

    # Выполняем SQL
    result = await _execute_sql(sql)

    if not result.get("success"):
        return {
            "answer": f"Ошибка при выполнении запроса: {result.get('error')}",
            "sql": sql,
            "raw_data": None,
            "success": False,
        }

    # Форматируем ответ
    answer = await _format_answer(question, result, llm_urls[0])

    # Добавляем источник данных (откуда взято)
    if sql:
        answer_with_source = f"{answer}\n\n_Источник: `{sql}`_"
    else:
        answer_with_source = answer

    return {
        "answer": answer_with_source,
        "sql": sql,
        "raw_data": result.get("data"),
        "count": result.get("count"),
        "success": True,
    }


def _extract_latest_user_message(goal: str) -> str:
    """
    Извлекает последнее сообщение пользователя из goal с историей чата.
    Victoria может получить goal вида:
    «Предыдущий диалог:
    Пользователь: сколько сотрудников?
    Ассистент: В корпорации 120 сотрудников.
    Пользователь: подтверди количество»

    Для data-вопросов используем ТОЛЬКО последнее сообщение пользователя,
    чтобы не передавать в Text-to-SQL ошибочные числа из истории.
    """
    if not goal:
        return goal
    markers = ["Пользователь:", "User:", "пользователь:"]
    for marker in markers:
        if marker in goal:
            parts = goal.split(marker)
            last_part = (parts[-1] or "").strip()
            if last_part and len(last_part) > 2:
                return last_part
    return goal


def is_system_metrics_question(question: str) -> bool:
    """Запрос о показателях Mac Studio / системы: память, CPU, мониторинг."""
    q = question.lower()
    return any(
        kw in q
        for kw in [
            "макстудио",
            "mac studio",
            "показател",
            "мониторинг",
            "память",
            "памяти",
            "cpu",
            "процессор",
            "диск",
            "memory",
            "систем",
            "ресурс",
        ]
    )


async def query_system_metrics() -> Dict[str, Any]:
    """
    Сбор показателей Mac Studio: CPU, память, диск, MLX.
    """
    result = {"success": False, "answer": "", "source": "system"}
    try:
        sys_text = ""
        try:
            from app.enhanced_monitor import get_system_metrics

            sys_m = await get_system_metrics()
            cpu = sys_m.get("cpu", {})
            ram = sys_m.get("ram", {})
            disk = sys_m.get("disk", {})
            sys_text = (
                f"**Система (Mac Studio):**\n"
                f"- CPU: {cpu.get('percent', 0)}% ({cpu.get('count', '?')} ядер)\n"
                f"- Память: {ram.get('used_gb', 0)} / {ram.get('total_gb', 0)} ГБ ({ram.get('percent', 0)}%)\n"
                f"- Диск: {disk.get('used_gb', 0)} / {disk.get('total_gb', 0)} ГБ ({disk.get('percent', 0)}%)\n"
            )
        except Exception:
            try:
                import psutil

                cpu = psutil.cpu_percent(interval=0.5)
                ram = psutil.virtual_memory()
                sys_text = f"**Система:** CPU {cpu}%, Память {ram.percent}% ({ram.used / (1024**3):.1f} / {ram.total / (1024**3):.1f} ГБ)\n"
            except Exception:
                pass

        mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")
        if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() == "true":
            mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
        mlx_text = ""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{mlx_url}/health")
                if r.status_code == 200:
                    d = r.json()
                    mem = d.get("memory", {})
                    mlx_text = (
                        f"\n**MLX API Server:** {d.get('status', '?')}\n"
                        f"- Память: {mem.get('used_percent', 0)}%, "
                        f"свободно {mem.get('available_gb', 0)} ГБ из {mem.get('total_gb', 0)} ГБ\n"
                        f"- Моделей в кэше: {d.get('models_cached', 0)}\n"
                    )
                else:
                    mlx_text = "\n**MLX API Server:** недоступен\n"
        except Exception:
            mlx_text = "\n**MLX API Server:** недоступен\n"

        answer = (sys_text or "Системные метрики недоступны.") + mlx_text
        result["success"] = True
        result["answer"] = answer
    except Exception as e:
        logger.error(f"query_system_metrics: {e}")
        result["answer"] = f"Ошибка сбора метрик: {e}"
    return result


def is_data_question(question: str) -> bool:
    """
    Определяет, является ли вопрос запросом данных о корпорации.
    Используется для маршрутизации в Victoria.
    Использует регулярные выражения для точного поиска слов (избегает ложных срабатываний типа 'отрефактори' -> 'кто').
    """
    import re

    q = question.lower()

    def has_word(text, words):
        for w in words:
            # Поиск слова с границами (начало строки, пробел, пунктуация)
            if re.search(rf"\b{re.escape(w)}", text):
                return True
        return False

    # ПРИОРИТЕТ 1: Глаголы действия всегда указывают на задачу, а не на вопрос о данных
    action_verbs = [
        "создай",
        "создать",
        "напиши",
        "написать",
        "сделай",
        "сделать",
        "удали",
        "удалить",
        "исправь",
        "исправить",
        "отрефактори",
        "отрефакторить",
        "добавь",
        "добавить",
        "запусти",
        "запустить",
        "проверь",
        "проверить",
        "выполни",
        "выполнить",
        "поручи",
        "поручить",
        "прикажи",
        "приказать",
        "начинается",
        "заканчивается",
        "проходит",
        "идет",
    ]
    logger.info(f"DEBUG is_data_question: q='{q}' action_verbs_match={has_word(q, action_verbs)}")
    if has_word(q, action_verbs):
        return False

    # ПРИОРИТЕТ 1.1: Специфические фразы-исключения (не данные)
    if any(p in q for p in ["во сколько", "когда будет", "когда начинается"]):
        return False

    # ПРИОРИТЕТ 2: Запрос о показателях Mac Studio (память, CPU, мониторинг)
    if is_system_metrics_question(question):
        return True

    # ПРИОРИТЕТ 3: Если спрашивают про корпорацию — всегда через Text-to-SQL (БД)
    corp_keywords = ["корпораци", "corporation", "компани", "отдел", "department"]
    if has_word(q, corp_keywords):
        return True

    data_keywords = [
        "сколько",
        "количество",
        "число",
        "count",
        "how many",
        "список",
        "покажи",
        "выведи",
        "show",
        "list",
        "статистика",
        "метрик",
        "статус",
        "stats",
        "кто",
        "какие",
        "какой",
        "what",
        "which",
        "who",
        "топ",
        "лучш",
        "худш",
        "top",
        "best",
        "worst",
        "последн",
        "recent",
        "latest",
        "новы",
        "всего",
        "total",
        "sum",
        "итого",
        "средн",
        "average",
        "avg",
        "подтверди",
        "повтори",
        "напомни",
    ]
    entity_keywords = [
        "сотрудник",
        "эксперт",
        "expert",
        "employee",
        "задач",
        "task",
        "задани",
        "знани",
        "knowledge",
        "узл",
        "node",
        "домен",
        "domain",
        "област",
        "kpi",
        "okr",
        "цел",
        "goal",
        "бюджет",
        "budget",
        "рейтинг",
        "score",
        "лог",
        "log",
        "взаимодейств",
        "interaction",
    ]

    has_data_kw = has_word(q, data_keywords)
    has_entity_kw = has_word(q, entity_keywords)

    # Дополнительная защита: если вопрос слишком длинный, это скорее всего сложная задача, а не простой запрос данных
    if len(q) > 300:
        return False

    return has_data_kw and has_entity_kw


# Тест
if __name__ == "__main__":

    async def test():
        questions = [
            "сколько сотрудников в корпорации?",
            "сколько узлов знаний?",
            "какие отделы есть?",
            "топ-5 экспертов по рейтингу",
            "сколько задач в статусе pending?",
        ]
        for q in questions:
            print(f"\n❓ {q}")
            result = await query_corporation_data(q)
            print(f"📊 SQL: {result.get('sql')}")
            print(f"✅ Ответ: {result.get('answer')}")

    asyncio.run(test())
