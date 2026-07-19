import asyncio
import json
import os
import subprocess
from datetime import datetime

import asyncpg
import httpx
from ai_core import run_smart_agent_async

# Секреты только из переменных окружения (мировая практика безопасности)
TG_TOKEN = os.getenv("TG_TOKEN", "")
ALLOWED_USER_ID = int(os.getenv("TG_ALLOWED_USER_ID", "0")) or 556251171
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
VECTOR_CORE_URL = "http://localhost:8001"


async def get_embedding(text: str) -> list:
    """Get embedding from VectorCore microservice."""
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{VECTOR_CORE_URL}/encode", json={"text": text}, timeout=30.0)
        response.raise_for_status()
        return response.json()["embedding"]


async def send_telegram_msg(chat_id, text):
    if not TG_TOKEN or not TG_TOKEN.strip():
        return  # Секрет не задан — не вызываем API (мировая практика)
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(
                url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10
            )
            if not res.is_success:
                await client.post(url, data={"chat_id": chat_id, "text": text}, timeout=10)
        except Exception as e:
            print(f"Ошибка TG: {e}")


async def get_expert_config(name):
    try:
        conn = await asyncpg.connect(DB_URL)
        row = await conn.fetchrow(
            "SELECT id, name, system_prompt, role, department FROM experts WHERE name ILIKE $1",
            name + "%",
        )
        await conn.close()
        return row
    except Exception as e:
        print(f"БД ошибка: {e}")
    return None


async def log_interaction(
    expert_id,
    query,
    response,
    knowledge_ids=None,
    knowledge_applied=None,
    trace=None,
    reasoning_trace=None,
):
    try:
        conn = await asyncpg.connect(DB_URL)

        # Интеллектуальная оценка стоимости
        prompt_tokens = len(query) // 4
        completion_tokens = len(response) // 4
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = (total_tokens / 1000) * 0.01

        metadata = {
            "source": "telegram",
            "knowledge_node_ids": knowledge_ids or [],
            "knowledge_applied": knowledge_applied or False,
            "trace": trace or [],
            "reasoning_trace": reasoning_trace,  # Store the reasoning trace for distillation
        }
        await conn.execute(
            """
            INSERT INTO interaction_logs (expert_id, user_query, assistant_response, metadata, token_usage, cost_usd)
            VALUES ($1, $2, $3, $4, $5, $6)
        """,
            expert_id,
            query,
            response,
            json.dumps(metadata),
            total_tokens,
            cost_usd,
        )

        if knowledge_ids:
            await conn.execute(
                "UPDATE knowledge_nodes SET usage_count = usage_count + 1 WHERE id = ANY($1)",
                knowledge_ids,
            )

        await conn.close()
    except Exception as e:
        print(f"Ошибка логирования: {e}")


async def create_corporate_task(creator_id, assignee_name, title, description):
    try:
        conn = await asyncpg.connect(DB_URL)
        assignee = await conn.fetchrow(
            "SELECT id FROM experts WHERE name ILIKE $1", assignee_name + "%"
        )
        if assignee:
            await conn.execute(
                """
                INSERT INTO tasks (creator_expert_id, assignee_expert_id, title, description, status)
                VALUES ($1, $2, $3, $4, 'pending')
                ON CONFLICT (title, COALESCE(project_context, 'default'::character varying))
                WHERE (status = ANY (ARRAY['pending'::text, 'in_progress'::text]))
                DO UPDATE SET updated_at = NOW()
            """,
                creator_id,
                assignee["id"],
                title,
                description,
            )
            await conn.close()
            return True
        await conn.close()
    except Exception as e:
        print(f"Ошибка создания задачи: {e}")
    return False


async def search_knowledge(query: str, domain: str = None, limit: int = 5):
    try:
        # Получение эмбеддинга через VectorCore
        embedding = await get_embedding(query)

        conn = await asyncpg.connect(DB_URL)

        sql = """
            SELECT k.id, k.content, k.confidence_score, d.name as domain_name,
                   (1 - (k.embedding <=> $1::vector)) as similarity
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.confidence_score > 0.3
        """
        params = [str(embedding)]

        if domain:
            sql += " AND d.name ILIKE $2"
            params.append(f"%{domain}%")

        sql += f" ORDER BY similarity DESC LIMIT ${len(params) + 1}"
        params.append(limit)

        results = await conn.fetch(sql, *params)

        await conn.close()

        if not results:
            return None, []

        knowledge_text = "\n".join(
            [
                f"[{r['domain_name']}] (сходство: {r['similarity']:.2f}): {r['content'][:200]}"
                for r in results
            ]
        )
        knowledge_ids = [r["id"] for r in results]
        return knowledge_text, knowledge_ids
    except Exception as e:
        print(f"Ошибка поиска знаний: {e}")
        return None, []


async def check_notifications():
    try:
        conn = await asyncpg.connect(DB_URL)
        rows = await conn.fetch(
            "SELECT id, message FROM notifications WHERE sent = FALSE ORDER BY created_at ASC"
        )
        for row in rows:
            await send_telegram_msg(ALLOWED_USER_ID, row["message"])
            await conn.execute("UPDATE notifications SET sent = TRUE WHERE id = $1", row["id"])
        await conn.close()
    except (asyncpg.PostgresError, ConnectionError, TimeoutError) as e:
        print(f"⚠️ Error checking notifications: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected error in check_notifications: {e}")


async def handle_message(target_name, user_text, chat_id, user_id):
    if user_id != ALLOWED_USER_ID:
        return
    if not target_name:
        target_name = "Виктория"
    expert = await get_expert_config(target_name)
    if not expert:
        await send_telegram_msg(chat_id, f"❌ Эксперт {target_name} не найден в штате.")
        return

    print(f"[{datetime.now()}] Запрос к {expert['name']}: {user_text}")
    trace = []

    # 1. Поиск знаний
    domain_hint = expert.get("department")
    relevant_knowledge, knowledge_ids = await search_knowledge(user_text, domain_hint, limit=5)
    trace.append({"step": "knowledge_search", "query": user_text, "found_nodes": knowledge_ids})

    # 2. Логика Иерархической Оркестрации для Викторияии
    orchestration_output = ""
    if expert["name"] == "Виктория" and len(user_text) > 30:
        # Виктория теперь делегирует Директорам отделов
        analysis_prompt = f"""
        Вы Виктория, Главный Координатор холдинга. Запрос от владельца: {user_text}

        Определите, какой Директор отдела должен взять это в работу:
        - Дмитрий (CTO, отдел ML/Технологии)
        - Мария (Риск-менеджер, отдел Risk)
        - Максим (Аналитик, отдел Strategy/Data)
        - Яна (Креативный директор, отдел Creative)

        Верните JSON:
        {{
            "delegate_to": "Имя Директора",
            "task_title": "Заголовок задачи",
            "instructions": "Что именно Директор должен сделать"
        }}
        Если вопрос не требует делегирования, верните "НЕТ".
        """
        orchestration_cmd = await run_smart_agent_async(
            analysis_prompt, expert_name=expert["name"], category="orchestration"
        )
        trace.append({"step": "hierarchical_delegation", "result": orchestration_cmd})

        if orchestration_cmd and "НЕТ" not in orchestration_cmd.upper():
            try:
                # Парсинг решения Викторияии
                data_str = orchestration_cmd.strip()
                if "```" in data_str:
                    data_str = data_str.split("```")[1].replace("json", "").strip()
                decision = json.loads(data_str)

                director = await get_expert_config(decision["delegate_to"])
                if director:
                    # Директор готовит экспертную справку
                    director_prompt = f"{director['system_prompt']}\nВАЖНОЕ ЗАДАНИЕ ОТ ВИКТОРИИ: {decision['instructions']}\nКОНТЕКСТ: {user_text}"
                    director_opinion = await run_smart_agent_async(
                        director_prompt, expert_name=director["name"]
                    )
                    orchestration_output += f"\n\n🏛 *Директива {director['name']} ({director['department']}):*\n{director_opinion}"

                    # Создаем задачу для контроля
                    await create_corporate_task(
                        expert["id"],
                        director["name"],
                        decision["task_title"],
                        decision["instructions"],
                    )
                    trace.append({"step": "director_report_received", "director": director["name"]})
            except Exception as e:
                print(f"Hierarchical error: {e}")

    knowledge_context = f"\n\n📚 ЗНАНИЯ:\n{relevant_knowledge}" if relevant_knowledge else ""
    full_prompt = f"""{expert["system_prompt"]}\nРоль: {expert["role"]}\n{f"ВХОДНЫЕ ДАННЫЕ: {orchestration_output}" if orchestration_output else ""}\n{knowledge_context}\nЗапрос: {user_text}"""

    # Singularity v3.0: Request Reasoning Trace (CoT)
    result = await run_smart_agent_async(full_prompt, expert_name=expert["name"], require_cot=True)

    if isinstance(result, dict):
        response_text = result["response"]
        reasoning_trace = result["reasoning_trace"]
    else:
        response_text = result
        reasoning_trace = ""

    icon = "👩‍💼" if "Викт" in expert["name"] else "💼"
    await send_telegram_msg(
        chat_id, f"{icon} *{expert['name']}:*\n\n{response_text}{orchestration_output}"
    )
    await log_interaction(
        expert["id"], user_text, response_text, knowledge_ids, True, trace, reasoning_trace
    )


async def telegram_bridge():
    if not TG_TOKEN or not TG_TOKEN.strip():
        print(
            "⚠️ TG_TOKEN не задан (переменная окружения TG_TOKEN). Telegram шлюз не будет опрашивать API."
        )
        while True:
            await asyncio.sleep(3600)  # Не падать, просто ждать
    print(f"[{datetime.now()}] Telegram шлюз v4.6 (VectorCore Optimized) запущен...")
    offset = 0

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            try:
                url = (
                    f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates?offset={offset}&timeout=20"
                )
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("ok"):
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1
                            msg = update.get("message")
                            if msg:
                                user_id = msg.get("from", {}).get("id")
                                user_text = msg.get("text", "")
                                chat_id = msg["chat"]["id"]
                                target_name = None
                                lower_text = user_text.lower()
                                if lower_text.startswith("виктория"):
                                    target_name = "Виктория"
                                    user_text = user_text[8:].strip(", ").strip()
                                elif lower_text.startswith("владимир"):
                                    target_name = "Владимир"
                                    user_text = user_text[8:].strip(", ").strip()
                                asyncio.create_task(
                                    handle_message(target_name, user_text, chat_id, user_id)
                                )
                await check_notifications()
            except Exception as e:
                await asyncio.sleep(5)
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    try:
        asyncio.run(telegram_bridge())
    except KeyboardInterrupt:
        print("🛑 Telegram bridge stopped by user")
    except Exception as e:
        print(f"❌ Fatal error in telegram_bridge: {e}")
        raise
