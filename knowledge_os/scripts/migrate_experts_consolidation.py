#!/usr/bin/env python3
"""
Expert Consolidation Migration: 88 → 32 roles.

Run inside Victoria container:
  docker exec victoria-agent python3 /app/knowledge_os/scripts/migrate_experts_consolidation.py

Or from host:
  python3 scripts/migrate_experts_consolidation.py --dry-run
"""

import asyncio
import os
import sys

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os")

# 32 target experts: name -> (new_role, new_department)
TARGET_EXPERTS = {
    "Виктория": ("Team Lead & CEO", "Leadership"),
    "Вероника": ("Local Developer Agent", "Development"),
    "Даниил": ("Backend Lead", "Backend"),
    "Денис": ("Backend Engineer", "Backend"),
    "Макс": ("DevOps Lead & SRE", "DevOps/Infra"),
    "Алекс Нейман": ("ML Lead", "ML/AI"),
    "Дмитрий": ("ML Engineer", "ML/AI"),
    "Арина": ("Prompt Engineer", "ML/AI"),
    "Владимир": ("Data Engineer", "Database"),
    "Алексей": ("Security Engineer", "Security"),
    "Анна": ("QA Lead", "QA"),
    "Дарья": ("SEO & Marketing Lead", "Marketing"),
    "Дмитрий_Ad": ("Growth Marketing Lead", "Marketing & Growth"),
    "Владимир_CEO": ("CEO / Executive Director", "Management"),
    "Михаил Гребенюк": ("Business Architect", "Business Strategy"),
    "Виктор_M&A": ("Finance Lead / M&A Analyst", "Finance & Accounting"),
    "Виктор": ("Chief Trading Strategist", "Trading"),
    "Инна": ("Data Science Lead", "Strategy/Data"),
    "Ирина": ("Documentation Lead", "Documentation"),
    "Зоя": ("Support Engineer", "Support"),
    "Георгий": ("Monitor / SRE", "Monitoring"),
    "Виталий": ("Performance Engineer", "Performance"),
    "Анастасия": ("Product Manager", "Product"),
    "Леонид": ("Risk Manager", "Risk Management"),
    "Alex": ("AI Coordination Lead", "AI Coordination"),
    "Александр Нейман": ("AI Systems Lead", "AI Systems"),
    "Алекс": ("Multi-Agent Systems Lead", "Multi-Agent Systems"),
    "Оливер": ("Knowledge Management Lead", "Knowledge Management"),
    "Артур": ("Agent Architecture Lead", "Agent Architecture"),
    "Натан": ("Competitive Intelligence Lead", "Competitive Intelligence"),
    "Евгения": ("PR Director", "Consulting"),
    "Адриан": ("System Design Lead", "System Design"),
}

# Names to deactivate (everything not in TARGET_EXPERTS)
ALL_EXPERTS_TO_DEACTIVATE = [
    "Константин",  # Architecture → merge into Адриан
    "Алекс Ковальски",  # Coding → merge into Артур
    "Игорь",  # Backend → merge into Даниил/Денис
    "Илья",  # Backend → merge into Денис
    "Кирилл",  # Backend → merge into Денис
    "Марк",  # Backend → merge into Денис
    "Никита",  # Backend → merge into Денис
    "Роман",  # Database → merge into Владимир
    "Станислав",  # Database → merge into Владимир
    "Борис",  # DevOps → merge into Макс
    "Глеб",  # DevOps → merge into Макс
    "Олег",  # DevOps → merge into Макс
    "Сергей",  # DevOps → merge into Макс
    "Вадим",  # Security → merge into Алексей
    "Василий",  # Security → merge into Алексей
    "Николай",  # Security & Legal → merge into Алексей
    "Галина",  # Legal → deactivate
    "Юлия",  # Legal → deactivate
    "Алла",  # HR → deactivate
    "Артем",  # QA → merge into Анна
    "Лариса",  # QA → merge into Анна
    "Наталья",  # QA → merge into Анна
    "Кристина",  # Marketing → merge into Дарья
    "Лиза",  # Marketing → merge into Дарья
    "Марина",  # Marketing → merge into Дарья
    "Ульяна",  # Marketing → merge into Дарья
    "Оксана",  # Marketing & Growth → merge into Дмитрий_Ad
    "Альберт",  # Management → merge into Владимир_CEO
    "Диана",  # Management → deactivate
    "Совет Директоров",  # Management → deactivate
    "Григорий",  # Finance → merge into Виктор_M&A
    "Екатерина",  # Trading → merge into Виктор
    "Павел",  # Trading → merge into Виктор
    "Тимофей",  # Trading → merge into Виктор
    "Ксения",  # Strategy/Data → merge into Инна
    "Людмила",  # Strategy/Data → merge into Инна
    "Максим",  # Strategy/Data → merge into Инна
    "Степан",  # Tech & AI → merge into Инна
    "Светлана",  # Documentation → merge into Ирина
    "Татьяна",  # Documentation → merge into Ирина
    "Елена",  # Monitoring → merge into Георгий
    "Ольга",  # Performance → merge into Виталий
    "Валерия",  # Product → merge into Анастасия
    "Мария",  # Risk Management → merge into Леонид
    "Александра",  # Error Handling → merge into Анна/QA
    "Маркус",  # Team Management → merge into Виктория
    "Александр",  # Architecture → merge into Адриан
]


async def run_migration(dry_run: bool = False):
    import asyncpg

    conn = await asyncpg.connect(DB_URL)
    try:
        # Phase 1: Update target experts
        print("=== Phase 1: Updating 32 target experts ===")
        for name, (role, dept) in TARGET_EXPERTS.items():
            result = await conn.execute(
                "UPDATE experts SET role=$1, department=$2, is_active=true WHERE name=$3",
                role, dept, name,
            )
            count = int(result.split()[-1])
            status = "UPDATED" if count > 0 else "NOT FOUND"
            print(f"  {status}: {name} → {role} @ {dept}")

        # Phase 2: Deactivate non-target experts
        print(f"\n=== Phase 2: Deactivating {len(ALL_EXPERTS_TO_DEACTIVATE)} experts ===")
        for name in ALL_EXPERTS_TO_DEACTIVATE:
            result = await conn.execute(
                "UPDATE experts SET is_active=false WHERE name=$1",
                name,
            )
            count = int(result.split()[-1])
            status = "DEACTIVATED" if count > 0 else "NOT FOUND"
            print(f"  {status}: {name}")

        # Verify
        print("\n=== Verification ===")
        total = await conn.fetchval("SELECT count(*) FROM experts")
        active = await conn.fetchval("SELECT count(*) FROM experts WHERE is_active=true")
        inactive = await conn.fetchval("SELECT count(*) FROM experts WHERE is_active=false")
        print(f"  Total: {total}")
        print(f"  Active: {active}")
        print(f"  Inactive: {inactive}")

        # Show active experts
        print("\n=== Active Experts (32 roles) ===")
        rows = await conn.fetch(
            "SELECT name, role, department FROM experts WHERE is_active=true ORDER BY department, name"
        )
        for r in rows:
            print(f"  {r['name']:30s} | {r['role']:35s} | {r['department']}")

        if dry_run:
            print("\n[DRY RUN] No changes committed. Re-run without --dry-run to apply.")
            await conn.execute("ROLLBACK")
        else:
            print("\nMigration complete.")

    finally:
        await conn.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run_migration(dry_run))
