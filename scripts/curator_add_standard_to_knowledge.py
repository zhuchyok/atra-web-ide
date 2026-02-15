#!/usr/bin/env python3
"""
Добавить эталоны куратора в базу знаний (knowledge_nodes) для RAG.
Домен curator_standards. Без эмбеддинга — узлы находятся текстовым поиском (ILIKE).
Запуск: DATABASE_URL=... python3 scripts/curator_add_standard_to_knowledge.py
Обновить содержимое эталона status_project (после правки standards): --update-status
Если asyncpg не установлен: knowledge_os/.venv/bin/python scripts/curator_add_standard_to_knowledge.py
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOMAIN_NAME = "curator_standards"
SOURCE_REF = "curator_standard"
CONFIDENCE = 0.95

# Эталон 1: что ты умеешь
CAPABILITIES_PREFIX = "Вопрос: что ты умеешь? Ответ: "
# Эталон 2: приветствие (из standards/greeting.md)
GREETING_PREFIX = "Вопрос: привет Ответ: "
GREETING_ANSWER = "Привет! Я Виктория, Team Lead корпорации ATRA. Чем могу помочь?"

# Эталон 3: статус проекта (из standards/status_project.md)
STATUS_PREFIX = "Вопрос: какой статус проекта"
STATUS_ANSWER = (
    "Статус проекта смотрите в дашборде (Corporation Dashboard, порт 8501) и в списке задач Knowledge OS. "
    "Опираюсь на факты из MASTER_REFERENCE и задач, не придумываю сроки. "
    "Коротко: статус проекта — в дашборде (порт 8501) и в задачах Knowledge OS, детали в MASTER_REFERENCE."
)

# Эталон 4: список файлов (из standards/list_files.md)
LIST_FILES_PREFIX = "Вопрос: покажи список файлов"
LIST_FILES_ANSWER = "Для списка файлов в корне или в директории выполняю команду ls (через Veronica или инструменты). Результат — вывод команды или структурированный список."

# Эталон 5: одна строка кода (из standards/one_line_code.md)
ONE_LINE_CODE_PREFIX = "Вопрос: напиши одну строку кода на Python вывод текущей даты"
ONE_LINE_CODE_ANSWER = "```python\nfrom datetime import date\nprint(date.today())\n```"


async def ensure_domain(conn):
    domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", DOMAIN_NAME)
    if not domain_id:
        domain_id = await conn.fetchval(
            "INSERT INTO domains (name, description) VALUES ($1, $2) RETURNING id",
            DOMAIN_NAME,
            "Эталоны куратора для RAG",
        )
        print(f"Создан домен: {DOMAIN_NAME}")
    return domain_id


async def add_if_missing(conn, domain_id, content_prefix: str, content_full: str, standard_name: str):
    existing = await conn.fetchval(
        """SELECT id FROM knowledge_nodes
           WHERE domain_id = $1 AND content LIKE $2 LIMIT 1""",
        domain_id,
        content_prefix + "%",
    )
    if existing:
        print(f"Эталон «{standard_name}» уже есть (id={existing}). Пропуск.")
        return 0
    metadata = json.dumps({"source": SOURCE_REF, "standard": standard_name})
    node_id = await conn.fetchval(
        """INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, source_ref)
           VALUES ($1, $2, $3, $4, $5) RETURNING id""",
        domain_id,
        content_full,
        CONFIDENCE,
        metadata,
        SOURCE_REF,
    )
    print(f"Добавлен узел «{standard_name}» (id={node_id}).")
    return 1


async def update_status_project(conn, domain_id: int, content_status: str) -> int:
    """Обновить содержимое узла status_project (после правки standards/status_project.md)."""
    r = await conn.execute(
        """UPDATE knowledge_nodes
           SET content = $1
           WHERE domain_id = $2 AND metadata::jsonb->>'standard' = 'status_project'
           RETURNING id""",
        content_status,
        domain_id,
    )
    if r == "UPDATE 0":
        print("Узел status_project не найден, ничего не обновлено.")
        return 0
    print("Обновлён эталон «status_project» в RAG.")
    return 1


async def main():
    parser = argparse.ArgumentParser(description="Добавить эталоны куратора в knowledge_nodes (RAG).")
    parser.add_argument("--update-status", action="store_true", help="Обновить только содержимое эталона status_project в БД")
    args = parser.parse_args()

    try:
        import asyncpg
    except ImportError:
        print("Требуется asyncpg: pip install asyncpg")
        return 1

    cap_file = ROOT / "configs" / "victoria_capabilities.txt"
    if not cap_file.exists():
        print(f"Файл не найден: {cap_file}")
        return 1
    capabilities_text = cap_file.read_text(encoding="utf-8").strip()
    content_cap = CAPABILITIES_PREFIX + capabilities_text
    content_greeting = GREETING_PREFIX + GREETING_ANSWER
    content_status = "Вопрос: какой статус проекта? Ответ: " + STATUS_ANSWER
    content_list = "Вопрос: покажи список файлов в корне проекта Ответ: " + LIST_FILES_ANSWER
    content_code = "Вопрос: напиши одну строку кода на Python вывод текущей даты Ответ: " + ONE_LINE_CODE_ANSWER

    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        return 1

    try:
        domain_id = await ensure_domain(conn)
        if args.update_status:
            await update_status_project(conn, domain_id, content_status)
            print("Готово (только обновление status_project).")
            return 0
        added = 0
        added += await add_if_missing(conn, domain_id, CAPABILITIES_PREFIX, content_cap, "what_can_you_do")
        added += await add_if_missing(conn, domain_id, GREETING_PREFIX, content_greeting, "greeting")
        added += await add_if_missing(conn, domain_id, "Вопрос: какой статус проекта", content_status, "status_project")
        added += await add_if_missing(conn, domain_id, "Вопрос: покажи список файлов", content_list, "list_files")
        added += await add_if_missing(conn, domain_id, "Вопрос: напиши одну строку кода", content_code, "one_line_code")
        print(f"Готово. Добавлено узлов: {added}. RAG (ILIKE) находит по запросам из эталонов.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
