#!/usr/bin/env python3
"""
Импорт узлов знаний из atra backups.
Источники: ~/Documents/dev/atra/backups/knowledge_os_*.sql.gz

БЕЗОПАСНОСТЬ:
- Только INSERT, никакого DDL (CREATE/ALTER/DROP/TRUNCATE)
- Вставляем только в колонки, которые есть в целевой таблице
- domain_id, embedding не трогаем (другая схема/FK)
- DRY_RUN=1 — только показать, что будет импортировано
"""
import asyncio
import gzip
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Пути к дампам atra (можно переопределить через ATRA_BACKUP_PATH)
ATRA_BACKUPS = Path(os.getenv("ATRA_BACKUP_PATH", str(Path.home() / "Documents" / "dev" / "atra" / "backups")))
DUMP_PATTERNS = [
    "knowledge_os_20260122_214735.sql.gz",  # 21 MB
    "knowledge_os_20260120_125507.sql.gz",  # 19 MB
]

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


def find_best_dump() -> Path | None:
    """Найти самый свежий дамп knowledge_os."""
    # Прямой путь из env
    direct = os.getenv("KNOWLEDGE_DUMP_PATH")
    if direct and Path(direct).exists():
        return Path(direct)
    candidates = []
    base = Path(ATRA_BACKUPS) if isinstance(ATRA_BACKUPS, str) else ATRA_BACKUPS
    for p in base.glob("knowledge_os_*.sql.gz"):
        if "remote" not in p.name and p.stat().st_size > 1_000_000:
            candidates.append((p.stat().st_mtime, p))
    # Также проверяем kn_dump.sql.gz (при копировании в /tmp)
    for p in base.glob("kn_dump.sql.gz"):
        if p.stat().st_size > 1_000_000:
            candidates.append((p.stat().st_mtime, p))
    return max(candidates)[1] if candidates else None


def extract_knowledge_nodes_from_dump(path: Path) -> list[dict]:
    """Извлечь строки knowledge_nodes из pg_dump (COPY format)."""
    nodes = []
    in_copy = False
    columns = None

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("COPY public.knowledge_nodes "):
                in_copy = True
                # Парсим заголовок: COPY public.knowledge_nodes (col1, col2, ...) FROM stdin;
                m = re.search(r"\((.*?)\)", line)
                columns = [c.strip() for c in m.group(1).split(",")] if m else []
                continue
            if in_copy:
                if line.strip() == r"\.":
                    break
                # Табуляция между колонками
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 3 and columns:
                    row = dict(zip(columns, parts))
                    nodes.append(row)
    return nodes


async def import_nodes(nodes: list[dict]) -> int:
    """
    Импорт в knowledge_postgres.
    ВАЖНО: вставляем ТОЛЬКО в колонки, которые есть в целевой таблице.
    Никакого DDL — не меняем схему, не трогаем существующие данные.
    """
    try:
        import asyncpg
    except ImportError:
        print("pip install asyncpg")
        return 0

    conn = await asyncpg.connect(DB_URL)

    # Получаем реальный список колонок целевой таблицы
    cols = await conn.fetch("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'knowledge_nodes' AND table_schema = 'public'
        ORDER BY ordinal_position
    """)
    target_columns = {r["column_name"] for r in cols}
    print(f"   Колонки в целевой таблице: {sorted(target_columns)}")

    # Только колонки, которые есть в целевой таблице.
    # Не трогаем: id, domain_id (FK), embedding (разная размерность).
    insert_cols = [c for c in ["content", "metadata", "confidence_score", "is_verified", "usage_count", "source_ref", "created_at"] if c in target_columns]

    if "content" not in insert_cols:
        print("❌ Колонка content обязательна — прерываем")
        await conn.close()
        return 0

    def _val(v, default=None):
        if v is None or v == "\\N" or v == "":
            return default
        return v

    dry_run = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
    if dry_run:
        would_insert = sum(1 for r in nodes if (_val(r.get("content"), "") or ""))
        print(f"   ⚠️ DRY_RUN — будет импортировано ~{would_insert} узлов")
        await conn.close()
        return 0

    inserted = 0
    skipped = 0

    for r in nodes:
        try:
            content = _val(r.get("content"), "") or ""
            if not content:
                continue
            metadata = _val(r.get("metadata"), "{}")
            if isinstance(metadata, str) and not metadata.startswith("{"):
                metadata = "{}"
            conf = float(_val(r.get("confidence_score"), "0.5") or 0.5)
            verified = str(_val(r.get("is_verified"), "f")).lower() in ("t", "true", "1")
            usage = int(_val(r.get("usage_count"), "0") or 0)
            source_ref = _val(r.get("source_ref"))
            created_at = _val(r.get("created_at"))

            # Собираем только существующие колонки
            cols_sql = []
            vals = []
            for col in ["content", "metadata", "confidence_score", "is_verified", "usage_count", "source_ref", "created_at"]:
                if col not in insert_cols:
                    continue
                if col == "content":
                    vals.append(content)
                elif col == "metadata":
                    vals.append(metadata)
                elif col == "confidence_score":
                    vals.append(conf)
                elif col == "is_verified":
                    vals.append(verified)
                elif col == "usage_count":
                    vals.append(usage)
                elif col == "source_ref":
                    vals.append(source_ref)
                elif col == "created_at":
                    try:
                        dt = datetime.fromisoformat(created_at.replace("+00", "+00:00")) if created_at else None
                    except Exception:
                        dt = None
                    vals.append(dt)
                cols_sql.append(col)

            # created_at NULL → NOW() через COALESCE
            ph = []
            for i, c in enumerate(cols_sql):
                n = i + 1
                if c == "created_at":
                    ph.append(f"COALESCE(${n}::timestamptz, NOW())")
                elif c == "metadata":
                    ph.append(f"${n}::jsonb")
                else:
                    ph.append(f"${n}")

            sql = f"INSERT INTO knowledge_nodes ({', '.join(cols_sql)}) VALUES ({', '.join(ph)})"
            await conn.execute(sql, *vals)
            inserted += 1
            if inserted % 1000 == 0:
                print(f"   ... {inserted}")
        except Exception as e:
            skipped += 1
            if "duplicate" not in str(e).lower() and "violates" not in str(e).lower():
                print(f"   ⚠️ {e}")

    total = await conn.fetchval("SELECT COUNT(*) FROM knowledge_nodes")
    await conn.close()
    print(f"Импортировано: {inserted}, пропущено: {skipped}, всего в БД: {total}")
    return inserted


async def main():
    dump = find_best_dump()
    if not dump:
        print("❌ Дамп не найден. Проверьте:", ATRA_BACKUPS)
        return 1

    print(f"📂 Дамп: {dump} ({dump.stat().st_size / 1e6:.1f} MB)")
    print("📥 Извлечение узлов...")
    nodes = extract_knowledge_nodes_from_dump(dump)
    print(f"   Найдено: {len(nodes)} узлов")

    if not nodes:
        print("❌ Узлы не найдены")
        return 1

    print("💾 Импорт в БД...")
    await import_nodes(nodes)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
