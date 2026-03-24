"""
[KNOWLEDGE OS] Expert Generator Engine.
Autonomous Recruitment: Designing and hiring AI experts for specific domains.
Part of the ATRA Singularity framework.
"""

import asyncio
import getpass
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

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

# Sync trigger for employees.json
try:
    from knowledge_os.app.employees_sync_daemon import trigger_employees_sync

    SYNC_TRIGGER_AVAILABLE = True
except ImportError:
    trigger_employees_sync = None
    SYNC_TRIGGER_AVAILABLE = False

# Local project imports with fallback
try:
    from ai_core import run_smart_agent_sync
except ImportError:

    def run_smart_agent_sync(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_sync."""
        return None


logger = logging.getLogger(__name__)

USER_NAME = getpass.getuser()
DEFAULT_DB_URL = (
    os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:6432/knowledge_os"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

DB_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# Путь к autonomous_candidates.json для MDM-ревью
_AUTONOMOUS_CANDIDATES_PATHS = [
    Path(__file__).resolve().parent.parent.parent
    / "configs"
    / "experts"
    / "autonomous_candidates.json",
    Path(__file__).resolve().parent.parent / "configs" / "experts" / "autonomous_candidates.json",
    Path(os.getenv("AUTONOMOUS_CANDIDATES_JSON", "")),
]


def _append_autonomous_candidate(
    expert_id,
    name: str,
    role: str,
    department: str,
    system_prompt: str = "",
) -> None:
    """Добавить кандидата в autonomous_candidates.json для MDM-ревью (добавление в employees.json)."""
    path = next(
        (p for p in _AUTONOMOUS_CANDIDATES_PATHS if p and str(p) and str(p) not in (".", "")), None
    )
    if not path or not path.parent.exists():
        return
    try:
        data = {"candidates": [], "updated": datetime.now(timezone.utc).isoformat()}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        entry = {
            "expert_id": str(expert_id),
            "name": name,
            "role": role,
            "department": department,
            "system_prompt_preview": (system_prompt[:300] + "...")
            if len(system_prompt) > 300
            else system_prompt,
            "hired_at": datetime.now(timezone.utc).isoformat(),
        }
        data.setdefault("candidates", []).append(entry)
        data["updated"] = datetime.now(timezone.utc).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("📋 Добавлен кандидат в %s для MDM-ревью", path.name)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.debug("Could not append to autonomous_candidates.json: %s", e)


def run_cursor_agent(prompt: str):
    """Run cursor-agent CLI through smart core."""
    return run_smart_agent_sync(prompt, expert_name="HR-Director", category="recruitment")


async def recruit_expert(domain_name: str):
    """
    Autonomous Recruitment: Designing expert for domain.
    1. Analyzes best practices.
    2. Generates name, role, and system prompt.
    3. Persists expert to database.
    """
    if not ASYNCPG_AVAILABLE:
        logger.error("❌ asyncpg is not installed. Recruitment is disabled.")
        return

    logger.info("🕵️ Autonomous Recruitment: Designing expert for domain '%s'...", domain_name)
    conn = await asyncpg.connect(DB_URL)

    # 1. Анализируем лучшие мировые практики для этой роли (промпт мирового уровня)
    recruitment_prompt = f"""
    Ты — ведущий Prompt Engineer мирового класса. Создай эксперта уровня ТОП-1 В МИРЕ для ИИ-корпорации.

    ОБЛАСТЬ: {domain_name}

    ЗАДАЧА:
    1. Придумай имя (в стиле компании: Марк, София и т.п.).
    2. Определи роль (каноничный формат: Legal Counsel, Data Analyst, Backend Developer, QA Engineer, Risk Manager, Trading Strategy Developer и т.п.).
    3. Разработай system_prompt уровня мирового топ-эксперта. ОБЯЗАТЕЛЬНО включи:
       - Методологии (FAANG, McKinsey, IEEE, ISO — применимые к области)
       - Стиль общения: конкретный, структурированный, экспертный
       - 5–7 ключевых компетенций с конкретными примерами
       - Границы экспертизы (что входит, что делегировать)
       - Формат ответа (по возможности)
       - Лучшие практики индустрии
    Референс: структура промптов топ-экспертов (Анна QA, Павел Trading, Игорь Backend) — чёткая специализация, Reuse First, структурированный ответ.

    Длина system_prompt: минимум 200 символов, желательно 400+.

    ВЕРНИ ТОЛЬКО JSON (без пояснений):
    {{
        "name": "Имя",
        "role": "Роль",
        "system_prompt": "Текст промпта мирового уровня",
        "department": "{domain_name}"
    }}
    """

    output = run_cursor_agent(recruitment_prompt)

    if output:
        try:
            # More robust JSON extraction
            json_match = re.search(r"(\{[\s\S]*\})", output)
            if json_match:
                clean_json = json_match.group(1)
            else:
                clean_json = output.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0]
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0]

            # Handle potential unescaped newlines in the system_prompt or other strings
            try:
                data = json.loads(clean_json)
            except json.JSONDecodeError:
                # Try to escape newlines manually in values
                fixed_json = re.sub(
                    r'(?<=: ")([\s\S]*?)(?=",)',
                    lambda m: m.group(1).replace("\n", "\\n"),
                    clean_json,
                )
                data = json.loads(fixed_json)

            # Валидация: system_prompt минимум 200 символов (мирового уровня)
            sp = data.get("system_prompt", "") or ""
            if len(sp) < 200:
                logger.warning(
                    "⚠️ system_prompt слишком короткий (%d символов), дополняем инструкцией", len(sp)
                )
                data["system_prompt"] = (
                    sp + "\n\n[Дополнительно: применяй методологии FAANG/McKinsey/IEEE. "
                    "5–7 ключевых компетенций. Границы экспертизы. Структурированный ответ.]"
                )

            # 2. Получаем/создаём domain_id (для INSERT в experts и knowledge_nodes)
            domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", domain_name)
            if not domain_id:
                domain_id = await conn.fetchval(
                    "INSERT INTO domains (name) VALUES ($1) RETURNING id", domain_name
                )

            # 3. Нанимаем эксперта (вставляем в базу с domain_id)
            expert_id = await conn.fetchval(
                """
                INSERT INTO experts (name, role, system_prompt, department, metadata, domain_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (name) DO NOTHING
                RETURNING id
            """,
                data["name"],
                data["role"],
                data["system_prompt"],
                data["department"],
                json.dumps(
                    {"hired_at": datetime.now(timezone.utc).isoformat(), "is_autonomous": True}
                ),
                domain_id,
            )

            if expert_id:
                logger.info(
                    "✅ Hired new expert: %s as %s in %s",
                    data["name"],
                    data["role"],
                    data["department"],
                )

                # 4. Post-hire: notifications (для Telegram/дашборда)
                try:
                    await conn.execute(
                        """
                        INSERT INTO notifications (message, sent)
                        VALUES ($1, FALSE)
                    """,
                        f"expert_hired:{expert_id}:{data['name']}:{data['role']}:{data['department']}",
                    )
                except Exception as nf_exc:  # pylint: disable=broad-exception-caught
                    logger.warning("Could not write to notifications: %s", nf_exc)

                # 5. Post-hire: Redis knowledge_stream (для Victoria, workers)
                if REDIS_AVAILABLE and REDIS_URL:
                    try:
                        rd = await redis.from_url(REDIS_URL, decode_responses=True)
                        await rd.xadd(
                            "knowledge_stream",
                            {
                                "type": "expert_hired",
                                "expert_id": str(expert_id),
                                "name": str(data["name"]),
                                "role": str(data["role"]),
                                "department": str(data["department"]),
                            },
                        )
                        await rd.aclose()
                    except Exception as rd_exc:  # pylint: disable=broad-exception-caught
                        logger.warning("Could not publish to Redis: %s", rd_exc)

                # 6. MDM: запись в autonomous_candidates.json для ревью (добавление в employees.json)
                _append_autonomous_candidate(
                    expert_id=expert_id,
                    name=data["name"],
                    role=data["role"],
                    department=data["department"],
                    system_prompt=data.get("system_prompt", "")[:500],
                )

                # 7. Создаем приветственное знание (по возможности с embedding — VERIFICATION §5)
                welcome_msg = (
                    f"👋 ПРИВЕТСТВИЕ: Я {data['name']}, ваш новый эксперт в области {domain_name}. "
                    "Моя цель - довести наши компетенции в этой сфере до абсолютного максимума."
                )
                meta_kn = json.dumps({"type": "recruitment_event", "expert_name": data["name"]})
                embedding = None
                try:
                    from semantic_cache import get_embedding

                    embedding = await get_embedding(welcome_msg[:8000])
                except Exception:
                    pass
                if embedding is not None:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                        VALUES ($1, $2, 1.0, $3, TRUE, $4::vector)
                    """,
                        domain_id,
                        welcome_msg,
                        meta_kn,
                        str(embedding),
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                        VALUES ($1, $2, 1.0, $3, TRUE)
                    """,
                        domain_id,
                        welcome_msg,
                        meta_kn,
                    )

                # 8. Синхронизация employees.json (автоматически добавит нового эксперта)
                if SYNC_TRIGGER_AVAILABLE and trigger_employees_sync:
                    try:
                        await trigger_employees_sync(f"hired:{data['name']}")
                    except Exception as sync_exc:  # pylint: disable=broad-exception-caught
                        logger.debug("Sync trigger skipped: %s", sync_exc)
            else:
                logger.warning("⚠️ Expert %s already exists.", data["name"])

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("❌ Error parsing recruitment output: %s", exc)

    await conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(recruit_expert(sys.argv[1]))
    else:
        print("Usage: python expert_generator.py <domain_name>")
