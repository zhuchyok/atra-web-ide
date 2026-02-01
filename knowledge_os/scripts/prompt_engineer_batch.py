#!/usr/bin/env python3
"""
[KNOWLEDGE OS] Batch Prompt Engineer — улучшение system_prompt для существующих экспертов.

Правило: ТОЛЬКО УЛУЧШАТЬ, НИЧЕГО НЕ УДАЛЯТЬ.
Сохраняет всё, что эксперт уже умеет. Добавляет глубину, методологии, мировые практики.

Использование:
    python knowledge_os/scripts/prompt_engineer_batch.py [--dry-run] [--limit N] [--source db|seed]
    python knowledge_os/scripts/prompt_engineer_batch.py --output staging.json  # staging для MDM-ревью
    
    --dry-run   Показать что будет изменено, без записи в БД
    --limit N   Обработать только первые N экспертов с generic промптами
    --source    db (default) — эксперты из БД; seed — из seed_experts.json
    --output F  Записать улучшенные промпты в JSON для ревью (без записи в БД)
"""

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent
SEED_JSON = KNOWLEDGE_ROOT / "db" / "seed_experts.json"
sys.path.insert(0, str(KNOWLEDGE_ROOT / "app"))

# Generic-шаблон (sync_employees) — короткие промпты требуют улучшения
GENERIC_PATTERNS = [
    "Выполняйте задачи в рамках своей роли",
    "Согласуйте результат с контекстом проекта",
    "You are {name}, {role}",
]

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

# Зависимости (asyncpg) устанавливаются на этапе setup, не в рантайме (12-Factor).
ASYNCPG_SETUP_HINT = "Установите зависимости: bash knowledge_os/scripts/setup_knowledge_os.sh"
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

try:
    from ai_core import run_smart_agent_sync
except ImportError:
    def run_smart_agent_sync(prompt, **kwargs):
        return None


def _is_generic(system_prompt: str, min_len: int = 200) -> bool:
    """Промпт считается generic, если короткий или содержит типовые фразы."""
    if not system_prompt or len(system_prompt.strip()) < min_len:
        return True
    for pat in ["Выполняйте задачи в рамках", "Согласуйте результат с контекстом"]:
        if pat in system_prompt:
            return True
    return False


def _build_prompt_engineer_prompt(name: str, role: str, department: str, current_prompt: str) -> str:
    """Промпт для LLM (prompt engineer мирового уровня)."""
    return f"""Ты — ведущий Prompt Engineer мирового класса. Задача: создать system_prompt уровня ТОП-ЭКСПЕРТА В МИРЕ для ИИ-корпорации.

Эксперт: {name}, роль: {role}, отдел: {department}.
Текущий промпт (ОБЯЗАТЕЛЬНО СОХРАНИТЬ всё из него, ничего не удалять):
---
{current_prompt[:2000]}
---

Требования:
- Сохранить ВСЕ компетенции, стиль и особенности из текущего промпта. Не удалять, не сокращать.
- Дополнить до уровня мирового топ-эксперта: методологии (FAANG, McKinsey, IEEE, ISO — применимые к области), лучшие практики индустрии.
- Добавить 5–7 ключевых компетенций мирового уровня с конкретными примерами.
- Границы экспертизы (что входит, что делегировать).
- Стиль общения: конкретный, структурированный, экспертный.
- Формат ответа (по возможности).

Результат: только текст нового system_prompt (расширенный, без пояснений). Длина: существенно больше текущего, но без потери сути. Минимум 300 символов."""


def _load_from_seed():
    """Загрузка экспертов из seed_experts.json."""
    if not SEED_JSON.exists():
        return []
    with open(SEED_JSON, "r", encoding="utf-8") as f:
        seed = json.load(f)
    return [
        {
            "id": f"seed-{i}",
            "name": e["name"],
            "role": e.get("role", ""),
            "department": e.get("department", ""),
            "system_prompt": e.get("system_prompt", ""),
            "metadata": e.get("metadata", {}),
        }
        for i, e in enumerate(seed)
    ]


async def main(dry_run: bool = False, limit: int = 0, source: str = "db", output_file: str = ""):
    """Главный цикл: загрузка экспертов, улучшение промптов, запись."""
    if source == "db":
        if not ASYNCPG_AVAILABLE:
            print("❌ asyncpg не установлен.", ASYNCPG_SETUP_HINT)
            return
        conn = await asyncpg.connect(DB_URL)
        rows = await conn.fetch(
            "SELECT id, name, role, department, system_prompt FROM experts ORDER BY name"
        )
        await conn.close()
        rows = [dict(r) for r in rows]
    else:
        rows = _load_from_seed()

    to_improve = [
        r for r in rows
        if _is_generic(r.get("system_prompt") or "")
    ]
    if limit:
        to_improve = to_improve[:limit]

    print(f"📊 Всего экспертов: {len(rows)}, с generic промптами: {len(to_improve)}")
    if not to_improve:
        print("✅ Все промпты уже на хорошем уровне.")
        return

    if dry_run:
        print("🔍 DRY-RUN: будут обработаны:")
        for r in to_improve[:10]:
            print(f"   - {r['name']} ({r['role']}, len={len(r.get('system_prompt') or '')})")
        if len(to_improve) > 10:
            print(f"   ... и ещё {len(to_improve) - 10}")
        return

    updated = 0
    for row in to_improve:
        name = row["name"]
        role = row["role"] or ""
        department = row["department"] or ""
        current = row.get("system_prompt") or ""
        print(f"\n🔄 Обработка: {name}...")

        prompt = _build_prompt_engineer_prompt(name, role, department, current)
        output = run_smart_agent_sync(prompt, expert_name="HR-Director", category="recruitment")
        if not output or len(output.strip()) < 100:
            print(f"   ⚠️ LLM не вернул улучшенный промпт")
            continue

        # Очистка: убрать markdown, лишнее
        new_prompt = output.strip()
        if "```" in new_prompt:
            m = re.search(r"```(?:\w*)\s*([\s\S]*?)```", new_prompt)
            if m:
                new_prompt = m.group(1).strip()
        new_prompt = new_prompt[:15000]  # лимит

        if len(new_prompt) < len(current):
            print(f"   ⚠️ Новый промпт короче текущего, пропуск (сохраняем старое)")
            continue

        # Проверка: ключевые фразы из старого должны быть в новом (если были)
        key_phrases = [p for p in current.split() if len(p) > 5][:5]
        if key_phrases and not any(p in new_prompt for p in key_phrases):
            print(f"   ⚠️ Новый промпт потерял контекст, пропуск")
            continue

        if output_file:
            # Staging: записать в JSON для MDM-ревью
            staging = []
            if Path(output_file).exists():
                with open(output_file, "r", encoding="utf-8") as f:
                    staging = json.load(f)
            staging.append({
                "name": name,
                "role": role,
                "department": department,
                "old_len": len(current),
                "new_len": len(new_prompt),
                "system_prompt": new_prompt,
            })
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(staging, f, ensure_ascii=False, indent=2)
            updated += 1
            print(f"   ✅ Добавлен в staging (len: {len(current)} → {len(new_prompt)})")
        elif source == "db" and ASYNCPG_AVAILABLE:
            # Запись в БД
            try:
                conn = await asyncpg.connect(DB_URL)
                await conn.execute(
                    "UPDATE experts SET system_prompt = $1 WHERE id = $2",
                    new_prompt,
                    row["id"],
                )
                await conn.close()
                updated += 1
                print(f"   ✅ Обновлён в БД (len: {len(current)} → {len(new_prompt)})")
            except Exception as e:
                print(f"   ❌ Ошибка БД: {e}")
        elif source == "seed":
            # Обновить seed_experts.json
            try:
                with open(SEED_JSON, "r", encoding="utf-8") as f:
                    seed = json.load(f)
                for e in seed:
                    if e["name"] == name:
                        e["system_prompt"] = new_prompt
                        break
                with open(SEED_JSON, "w", encoding="utf-8") as f:
                    json.dump(seed, f, ensure_ascii=False, indent=2)
                updated += 1
                print(f"   ✅ Обновлён в seed (len: {len(current)} → {len(new_prompt)})")
            except Exception as e:
                print(f"   ❌ Ошибка seed: {e}")

    print(f"\n✅ Готово. Обновлено: {updated}/{len(to_improve)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Без записи в БД")
    parser.add_argument("--limit", type=int, default=0, help="Макс. число экспертов")
    parser.add_argument("--source", choices=["db", "seed"], default="db", help="Источник: db или seed")
    parser.add_argument("--output", default="", help="Записать в JSON для MDM-ревью (staging)")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit, source=args.source, output_file=args.output))
