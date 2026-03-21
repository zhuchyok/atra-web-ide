#!/usr/bin/env python3
"""
ingest_docs_to_rag.py — загрузка ключевых документов проекта в knowledge_nodes (RAG).

Чанкует .md файлы по секциям (## заголовки), сохраняет в PostgreSQL.
Дубли пропускаются (WHERE NOT EXISTS по source_ref + первые 100 символов контента).

Запуск:
  DATABASE_URL=postgresql://admin:... knowledge_os/.venv/bin/python scripts/ingest_docs_to_rag.py
  DATABASE_URL=... python3 scripts/ingest_docs_to_rag.py --dry-run   # только показать что будет загружено
  DATABASE_URL=... python3 scripts/ingest_docs_to_rag.py --file docs/MASTER_REFERENCE.md  # один файл
"""
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHUNK_SIZE = 800        # символов на чанк (мягкий предел)
MIN_CHUNK = 80          # минимальный размер чанка (короче — пропускаем)
CONFIDENCE = 0.90

# Ключевые документы (приоритет — от важного к второстепенному)
PRIORITY_DOCS = [
    "docs/MASTER_REFERENCE.md",
    "docs/CHANGES_FROM_OTHER_CHATS.md",
    "docs/ARCHITECTURE_FULL.md",
    "VICTORIA.md",
    "VERONICA.md",
    "docs/SETKI21_SITE_DEPLOY_VDS.md",
    "docs/MAC_STUDIO_LOAD_AND_VICTORIA.md",
    "docs/VERIFICATION_CHECKLIST_OPTIMIZATIONS.md",
    "docs/AUTONOMY_OFFLINE_READINESS.md",
    "docs/PORT_REGISTRY.md",
    "docs/CURATOR_RUNBOOK.md",
    "docs/VICTORIA_CURATOR_PLAN.md",
    "docs/VICTORIA_TASK_FORMULATION.md",
    "docs/TEAM_PERSONALITIES.md",
    "docs/COGNITIVE_CODE.md",
    "docs/PRINCIPLE_EXPERTS_FIRST.md",
    "docs/ORCHESTRATION_CANARY.md",
    "docs/VERONICA_REAL_ROLE.md",
    "docs/OPENWEBUI_RAG_SETUP.md",
    ".cursorrules",
]

# Документы которые НЕ загружаем (слишком большие или неинформативные)
SKIP_PATTERNS = [
    "CHANGES_FROM_OTHER_CHATS",  # загружаем явно, но только последние 5000 символов
    "package-lock",
    "*.pyc",
    ".git",
    "node_modules",
]


def chunk_markdown(text: str, source: str, max_size: int = CHUNK_SIZE) -> list[dict]:
    """Разбить markdown на чанки по заголовкам ## / ###."""
    chunks = []
    # Разбиваем по заголовкам h2/h3
    parts = re.split(r"(?=^#{1,3} )", text, flags=re.MULTILINE)

    for part in parts:
        part = part.strip()
        if len(part) < MIN_CHUNK:
            continue

        if len(part) <= max_size:
            chunks.append({"content": part, "source": source})
        else:
            # Большой блок — делим на подчанки по параграфам
            paragraphs = re.split(r"\n{2,}", part)
            current = ""
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                if len(current) + len(para) + 2 > max_size and current:
                    chunks.append({"content": current.strip(), "source": source})
                    current = para
                else:
                    current = (current + "\n\n" + para).strip() if current else para
            if current and len(current) >= MIN_CHUNK:
                chunks.append({"content": current.strip(), "source": source})

    return chunks


def collect_docs(files: list[str] | None = None) -> list[dict]:
    """Собрать чанки из всех приоритетных документов."""
    all_chunks = []
    targets = files or PRIORITY_DOCS

    for rel_path in targets:
        path = ROOT / rel_path
        if not path.exists():
            print(f"  ⚠️  Не найден: {rel_path}")
            continue

        text = path.read_text(encoding="utf-8", errors="replace")

        # CHANGES_FROM_OTHER_CHATS — берём только последние 6000 символов (самое актуальное)
        if "CHANGES_FROM_OTHER_CHATS" in rel_path:
            text = text[:6000]

        source_ref = f"doc:{path.name}"
        chunks = chunk_markdown(text, source_ref)
        print(f"  📄 {rel_path}: {len(chunks)} чанков ({len(text)} символов)")
        all_chunks.extend(chunks)

    return all_chunks


async def ingest(chunks: list[dict], db_url: str, dry_run: bool = False) -> int:
    """Сохранить чанки в knowledge_nodes (без дублей)."""
    try:
        import asyncpg
    except ImportError:
        print("Требуется asyncpg: knowledge_os/.venv/bin/python scripts/ingest_docs_to_rag.py")
        return 0

    if dry_run:
        print(f"\n[DRY RUN] Было бы вставлено: {len(chunks)} чанков")
        for c in chunks[:5]:
            print(f"  {c['source']}: {c['content'][:80]}...")
        return 0

    conn = await asyncpg.connect(db_url)
    inserted = 0
    skipped = 0

    try:
        for chunk in chunks:
            content = chunk["content"]
            source_ref = chunk["source"]
            meta = json.dumps({"source": "ingest_docs_to_rag", "file": source_ref})

            # Проверяем дубль по source_ref + начало контента
            exists = await conn.fetchval(
                """SELECT id FROM knowledge_nodes
                   WHERE source_ref = $1 AND left(content, 100) = left($2, 100)
                   LIMIT 1""",
                source_ref, content,
            )
            if exists:
                skipped += 1
                continue

            await conn.execute(
                """INSERT INTO knowledge_nodes (content, source_ref, confidence_score, metadata)
                   VALUES ($1, $2, $3, $4::jsonb)""",
                content, source_ref, CONFIDENCE, meta,
            )
            inserted += 1

    finally:
        await conn.close()

    return inserted


async def main() -> None:
    ap = argparse.ArgumentParser(description="Загрузить ключевые доки в RAG (knowledge_nodes)")
    ap.add_argument("--dry-run", action="store_true", help="Показать что будет загружено, не сохранять")
    ap.add_argument("--file", default="", help="Загрузить только один файл (путь от корня репо)")
    ap.add_argument("--all-docs", action="store_true", help="Загрузить все .md из docs/ (376 файлов)")
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL", "")
    if not db_url and not args.dry_run:
        print("❌ Нужен DATABASE_URL. Пример:")
        print("   DATABASE_URL=postgresql://admin:<password>@localhost:5432/knowledge_os python3 scripts/ingest_docs_to_rag.py")
        sys.exit(1)

    print("📚 Сбор документов...")

    if args.file:
        files = [args.file]
    elif args.all_docs:
        files = [str(p.relative_to(ROOT)) for p in (ROOT / "docs").glob("**/*.md")]
        files += [str(p.relative_to(ROOT)) for p in ROOT.glob("*.md")]
        print(f"  Найдено {len(files)} .md файлов")
    else:
        files = None  # приоритетный список

    chunks = collect_docs(files)
    print(f"\nВсего чанков: {len(chunks)}")

    if not chunks:
        print("Нечего загружать.")
        return

    print("\n💾 Сохранение в PostgreSQL...")
    inserted = await ingest(chunks, db_url, dry_run=args.dry_run)

    if not args.dry_run:
        print(f"\n✅ Загружено: {inserted} новых чанков")
        if inserted < len(chunks):
            print(f"   Пропущено (дубли): {len(chunks) - inserted}")


if __name__ == "__main__":
    asyncio.run(main())
