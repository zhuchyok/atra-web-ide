"""
ATRA Curator Findings → Knowledge Nodes
Читает последний отчёт куратора, извлекает ПРОБЛЕМА-строки и
сохраняет в PostgreSQL knowledge_nodes (с дедупликацией по SHA256).
Fallback: docs/curator_findings.jsonl если БД недоступна.

Write-side guard (#66 residual): refuse/non-actionable text is NOT inserted.
Standards/docs ingest (ingest_docs_to_rag / curator_add_standard_to_knowledge) untouched.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "docs" / "curator_reports"
FALLBACK_FILE = ROOT / "docs" / "curator_findings.jsonl"
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Narrow refusal / Cognitive Code refuse markers (case-insensitive substring).
_REFUSAL_MARKERS = (
    "insufficient_context",
    "не могу приступить",
    "когнитивн",  # Когнитивный Код / кодекс
    "cognitive code",
    "blocked / awaiting context",
    "blocked / уточнение",
    "awaiting context",
    "уточнение необходимо",
    "status: blocked",
    "**статус:** blocked",
    "статус задачи: **unverified",
)

# Chatter that is not durable actionable knowledge.
_NON_ACTIONABLE_MARKERS = (
    "queued to worker",
    "### message:",
    "\nuser:",
    "\nassistant:",
    "system: добрый",
    "victoria уточняет",
    "нужно уточнение",
)

_POISON_TAG = "refusal_like"


def _body_after_goal(content: str) -> str:
    """Strip leading `[goal]` prefix used by extract_problems entries."""
    if content.startswith("[") and "]" in content[:160]:
        return content.split("]", 1)[1].strip()
    return content.strip()


def is_non_knowledge_finding(content: str) -> bool:
    """True → do not insert/update as knowledge (refusal or non-actionable).

    Keeps real ПРОБЛЕМА findings. Does not touch standards/docs writers.
    """
    if not content or not str(content).strip():
        return True
    text = str(content)
    lower = text.lower()
    if any(m in lower for m in _REFUSAL_MARKERS):
        return True
    body = _body_after_goal(text)
    body_l = body.lower()
    # Pure OK / nothing-found curator chatter is not durable knowledge.
    if body_l.startswith(("ок", "ok", "✅")) and "проблем" not in body_l:
        return True
    if any(m in body_l for m in _NON_ACTIONABLE_MARKERS):
        return True
    if body_l.startswith(("привет", "добрый")) and "проблем" not in body_l:
        return True
    return False


def get_latest_report() -> Path | None:
    """Возвращает путь к последнему отчёту куратора по mtime."""
    reports = sorted(
        REPORTS_DIR.glob("curator_*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    return reports[-1] if reports else None


def extract_problems(report_path: Path) -> list[str]:
    """Извлекает проблемы из отчёта куратора.

    Формат: results[].output_preview — строки НЕ начинающиеся с ОК.
    Также ищет явные маркеры ПРОБЛЕМА / НАЙДЕНО / ERROR в тексте.
    """
    problems = []
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for result in data.get("results", []):
            goal = result.get("goal", "")
            preview = result.get("output_preview", "")
            if not preview:
                continue
            # Проблема = не начинается с "ОК" и не пустой
            preview_upper = preview.strip().upper()
            is_ok = (
                preview_upper.startswith("ОК")
                or preview_upper.startswith("OK")
                or preview_upper.startswith("✅")
            )
            has_problem = (
                not is_ok
                or "ПРОБЛЕМ" in preview_upper
                or "НАЙДЕН" in preview_upper
                or "КРИТИЧ" in preview_upper
                or result.get("status") == "error"
            )
            if has_problem:
                entry = f"[{goal[:80]}] {preview.strip()}"
                problems.append(entry)

    except (json.JSONDecodeError, IOError):
        # Fallback: текстовый поиск
        with open(report_path, "r", encoding="utf-8") as f:
            for line in f:
                up = line.upper()
                if "ПРОБЛЕМА" in up or "НАЙДЕН" in up:
                    problems.append(line.strip())

    return problems


def compute_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def filter_actionable_problems(problems: list[str]) -> tuple[list[str], int]:
    """Drop refusal / non-actionable entries. Returns (kept, skipped)."""
    kept: list[str] = []
    skipped = 0
    for problem in problems:
        if is_non_knowledge_finding(problem):
            skipped += 1
            continue
        kept.append(problem)
    return kept, skipped


async def save_to_db(problems: list[str], report_name: str) -> int:
    """Сохраняет в PostgreSQL. Возвращает количество новых записей."""
    try:
        import asyncpg  # noqa: PLC0415
    except ImportError:
        raise RuntimeError("asyncpg не установлен")

    conn = await asyncpg.connect(DATABASE_URL, timeout=10)
    saved = 0
    try:
        for problem in problems:
            if is_non_knowledge_finding(problem):
                continue
            content_hash = compute_sha256(problem)
            # Идемпотентность — пропускаем дубликаты по content_hash в metadata
            existing = await conn.fetchval(
                "SELECT 1 FROM knowledge_nodes WHERE metadata->>'content_hash' = $1",
                content_hash,
            )
            if existing:
                continue
            await conn.execute(
                """
                INSERT INTO knowledge_nodes
                    (content, source_ref, metadata, confidence_score, is_verified)
                VALUES ($1, $2, $3, $4, $5)
                """,
                problem,
                "curator",
                json.dumps({
                    "content_hash": content_hash,
                    "node_type": "curator_finding",
                    "report": report_name,
                }),
                0.8,
                False,
            )
            saved += 1
    finally:
        await conn.close()
    return saved


def save_to_fallback(problems: list[str], report_name: str) -> int:
    """JSONL-fallback если БД недоступна. Возвращает количество новых записей."""
    FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Загружаем существующие хэши для дедупликации
    existing_hashes: set[str] = set()
    if FALLBACK_FILE.exists():
        with open(FALLBACK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    existing_hashes.add(entry.get("metadata", {}).get("content_hash", ""))
                except json.JSONDecodeError:
                    pass

    saved = 0
    with open(FALLBACK_FILE, "a", encoding="utf-8") as f:
        for problem in problems:
            if is_non_knowledge_finding(problem):
                continue
            content_hash = compute_sha256(problem)
            if content_hash in existing_hashes:
                continue
            entry = {
                "id": str(uuid.uuid4()),
                "content": problem,
                "node_type": "curator_finding",
                "source": "curator",
                "metadata": {"content_hash": content_hash, "report": report_name},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            existing_hashes.add(content_hash)
            saved += 1
    return saved


async def soft_tag_existing(*, apply: bool) -> dict[str, int]:
    """Dry-run (default) or soft-tag refusal-like curator_finding rows in metadata.

    Does NOT delete. Sets metadata.poison_tag = refusal_like.
    """
    try:
        import asyncpg  # noqa: PLC0415
    except ImportError:
        raise RuntimeError("asyncpg не установлен")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL не задан")

    conn = await asyncpg.connect(DATABASE_URL, timeout=10)
    try:
        rows = await conn.fetch(
            """
            SELECT id, content, metadata
            FROM knowledge_nodes
            WHERE COALESCE(metadata->>'node_type', '') = 'curator_finding'
            """
        )
        total = len(rows)
        candidates = 0
        already = 0
        updated = 0
        for row in rows:
            meta = row["metadata"]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            meta = dict(meta or {})
            if meta.get("poison_tag") == _POISON_TAG:
                already += 1
                continue
            if not is_non_knowledge_finding(row["content"] or ""):
                continue
            candidates += 1
            if not apply:
                continue
            meta["poison_tag"] = _POISON_TAG
            await conn.execute(
                "UPDATE knowledge_nodes SET metadata = $1::jsonb WHERE id = $2",
                json.dumps(meta),
                row["id"],
            )
            updated += 1
        return {
            "curator_finding_total": total,
            "soft_tag_candidates": candidates,
            "already_tagged": already,
            "updated": updated,
            "apply": int(apply),
        }
    finally:
        await conn.close()


async def main_async(args: argparse.Namespace) -> None:
    if args.soft_tag_existing:
        stats = await soft_tag_existing(apply=args.apply)
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"soft-tag {mode}: {stats}")
        return

    report_path = get_latest_report()
    if not report_path:
        print("Отчёты куратора не найдены в", REPORTS_DIR)
        return

    print(f"Читаю отчёт: {report_path.name}")
    problems = extract_problems(report_path)
    problems, skipped = filter_actionable_problems(problems)
    print(f"Найдено ПРОБЛЕМА-строк (actionable): {len(problems)} (skipped non-knowledge: {skipped})")

    if not problems:
        print("Проблем не найдено — нечего сохранять.")
        return

    saved = 0
    if DATABASE_URL:
        try:
            saved = await save_to_db(problems, report_path.name)
            print(f"✅ Сохранено в PostgreSQL: {saved} новых записей")
        except Exception as e:
            print(f"⚠️  БД недоступна ({e}), использую JSONL-fallback")
            saved = save_to_fallback(problems, report_path.name)
            print(f"✅ Сохранено в {FALLBACK_FILE}: {saved} новых записей")
    else:
        saved = save_to_fallback(problems, report_path.name)
        print(f"✅ DATABASE_URL не задан, сохранено в {FALLBACK_FILE}: {saved} новых записей")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Curator findings → knowledge_nodes")
    p.add_argument(
        "--soft-tag-existing",
        action="store_true",
        help="Dry-run count (or --apply) soft-tag refusal-like curator_finding rows",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="With --soft-tag-existing: write metadata.poison_tag (no delete)",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
