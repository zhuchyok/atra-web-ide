#!/usr/bin/env python3
"""
Регистрация проекта в реестре корпорации (таблица projects).
После регистрации Victoria и Veronica принимают запросы с project_context=<slug>.

Использование:
  python scripts/register_project.py <slug> <name> [--description "описание"] [--workspace-path /path]
  или из knowledge_os: python scripts/register_project.py my-app "My App"

Требуется DATABASE_URL (или по умолчанию postgresql://admin:secret@localhost:5432/knowledge_os).
"""
import argparse
import asyncio
import os
import re
import sys


def _norm_slug(s: str) -> str:
    return (s or "").strip().lower()


def _validate_slug(slug: str) -> None:
    if not slug:
        raise SystemExit("slug is required")
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", slug):
        raise SystemExit("slug must be lowercase alphanumeric, hyphens/underscores allowed")


async def register(slug: str, name: str, description: str | None, workspace_path: str | None) -> None:
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    try:
        import asyncpg
    except ImportError:
        print("Install asyncpg: pip install asyncpg", file=sys.stderr)
        raise SystemExit(1)
    conn = await asyncpg.connect(db_url, timeout=10)
    try:
        await conn.execute(
            """
            INSERT INTO projects (slug, name, description, workspace_path, is_active)
            VALUES ($1, $2, $3, $4, true)
            ON CONFLICT (slug) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                workspace_path = EXCLUDED.workspace_path,
                updated_at = CURRENT_TIMESTAMP
            """,
            slug,
            (name or slug)[:500],
            (description or "")[:5000] if description else None,
            (workspace_path or f"/workspace/{slug}")[:1000],
        )
        print(f"OK: project '{slug}' registered. Restart Victoria/Veronica to pick up (or wait for cache TTL).")
    finally:
        await conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Register a project in the corporation registry (projects table)")
    ap.add_argument("slug", help="Project slug (e.g. my-app, atra-web-ide)")
    ap.add_argument("name", help="Display name")
    ap.add_argument("--description", "-d", default=None, help="Optional description")
    ap.add_argument("--workspace-path", "-w", default=None, help="Optional workspace path (default: /workspace/<slug>)")
    args = ap.parse_args()
    slug = _norm_slug(args.slug)
    _validate_slug(slug)
    asyncio.run(register(slug, args.name, args.description, args.workspace_path))


if __name__ == "__main__":
    main()
