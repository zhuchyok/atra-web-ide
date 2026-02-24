import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def seed_database():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ОШИБКА: DATABASE_URL не установлен.")
        return

    try:
        conn = await asyncpg.connect(db_url)
        print("✅ Подключение к БД успешно.")

        # Читаем SQL файлы
        seed_files = ["knowledge_os/db/seed_experts.sql", "knowledge_os/db/seed_knowledge.sql"]

        for file_path in seed_files:
            if os.path.exists(file_path):
                print(f"📖 Загрузка {file_path}...")
                with open(file_path, encoding="utf-8") as f:
                    sql = f.read()
                    await conn.execute(sql)
                print(f"✅ Файл {file_path} успешно выполнен.")
            else:
                print(f"⚠️ Файл {file_path} не найден.")

        await conn.close()
        print("\n🎉 Заполнение базы данных завершено!")

    except Exception as e:
        print(f"❌ ОШИБКА при заполнении: {e}")


if __name__ == "__main__":
    asyncio.run(seed_database())
