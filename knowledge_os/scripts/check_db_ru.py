import asyncio
import os

import asyncpg
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()


async def check_database():
    print("🔍 Проверка подключения к базе данных Knowledge OS...")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ОШИБКА: Переменная окружения DATABASE_URL не установлена.")
        return

    try:
        conn = await asyncpg.connect(db_url)
        print("✅ Подключение успешно установлено.")

        # Проверка таблиц
        tables = ["experts", "domains", "knowledge_nodes", "interaction_logs"]
        print("\n📊 Проверка таблиц:")

        for table in tables:
            try:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                print(f"  - {table}: {count} записей")
            except Exception as e:
                print(f"  - {table}: ❌ ОШИБКА (возможно, таблица не существует): {e}")

        # Проверка расширения vector
        try:
            vector_exists = await conn.fetchval(
                "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
            )
            if vector_exists:
                print("\n✅ Расширение 'vector' установлено.")
            else:
                print("\n⚠️ ВНИМАНИЕ: Расширение 'vector' НЕ обнаружено.")
        except Exception:
            print("\n⚠️ Не удалось проверить расширения.")

        await conn.close()

    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА подключения: {e}")


if __name__ == "__main__":
    asyncio.run(check_database())
