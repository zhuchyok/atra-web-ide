"""
ATRA Curator Findings → Knowledge Nodes
Читает последний отчёт куратора, извлекает ПРОБЛЕМА-строки и
сохраняет в PostgreSQL knowledge_nodes (с дедупликацией по SHA256).
Fallback: docs/curator_findings.jsonl если БД недоступна.
Сгенерировано: Victoria (victoria-wisdom-v3.5) via MLX — мозг спланировал.
"""
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
            content_hash = compute_sha256(problem)
            # Идемпотентность — пропускаем дубликаты по content_hash в metadata
            existing = await conn.fetchval(
                "SELECT 1 FROM knowledge_nodes WHERE metadata->>'content_hash' = $1",
                content_hash,
            )
            if existing:
                continue
            import json as _json  # noqa: PLC0415
            await conn.execute(
                """
                INSERT INTO knowledge_nodes
                    (content, source_ref, metadata, confidence_score, is_verified)
                VALUES ($1, $2, $3, $4, $5)
                """,
                problem,
                "curator",
                _json.dumps({
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


async def main() -> None:
    report_path = get_latest_report()
    if not report_path:
        print("Отчёты куратора не найдены в", REPORTS_DIR)
        return

    print(f"Читаю отчёт: {report_path.name}")
    problems = extract_problems(report_path)
    print(f"Найдено ПРОБЛЕМА-строк: {len(problems)}")

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


if __name__ == "__main__":
    asyncio.run(main())
