import asyncio
import asyncpg
import os
import json

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def migrate():
    print("🚀 Начинаю миграцию: Deep Expert Specialization (Singularity 21.17)")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # 1. Добавляем колонки в таблицу experts
        print("📝 Обновляю таблицу experts...")
        await conn.execute("""
            ALTER TABLE experts
            ADD COLUMN IF NOT EXISTS specialization_level VARCHAR(20) DEFAULT 'PRO',
            ADD COLUMN IF NOT EXISTS rule_file VARCHAR(255),
            ADD COLUMN IF NOT EXISTS performance_score FLOAT DEFAULT 0.0,
            ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;
        """)

        # 2. Маппинг основных экспертов (Elite)
        elite_mapping = {
            "Виктория": {"level": "ELITE", "rule": None}, # Виктория - оркестратор
            "Игорь": {"level": "ELITE", "rule": "09_backend_developer.md"},
            "Дмитрий": {"level": "ELITE", "rule": "10_ml_engineer.md"},
            "Сергей": {"level": "ELITE", "rule": "03_devops_engineer.md"},
            "Анна": {"level": "ELITE", "rule": "08_qa_engineer.md"},
            "Максим": {"level": "ELITE", "rule": "14_financial_analyst.md"},
            "Елена": {"level": "ELITE", "rule": "11_sre_monitor.md"},
            "Алексей": {"level": "ELITE", "rule": "12_security_engineer.md"},
            "Павел": {"level": "ELITE", "rule": "01_quant_developer.md"},
            "Мария": {"level": "ELITE", "rule": "05_risk_manager.md"},
            "Роман": {"level": "ELITE", "rule": "04_data_engineer.md"},
            "Ольга": {"level": "ELITE", "rule": "07_system_architect.md"},
            "Татьяна": {"level": "ELITE", "rule": "13_technical_writer.md"},
            "Арина": {"level": "ELITE", "rule": "22_orchestrator.md"}
        }

        for name, data in elite_mapping.items():
            await conn.execute("""
                UPDATE experts
                SET specialization_level = $1, rule_file = $2
                WHERE name = $3
            """, data["level"], data["rule"], name)
            print(f"✅ Эксперт {name} переведен на уровень {data['level']}")

        # 3. Устанавливаем PRO уровень для остальных по умолчанию
        await conn.execute("""
            UPDATE experts
            SET specialization_level = 'PRO'
            WHERE specialization_level IS NULL
        """)

        print("✨ Миграция успешно завершена!")

    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate())
