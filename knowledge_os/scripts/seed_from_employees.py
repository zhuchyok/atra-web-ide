import asyncio
import json
import os

import asyncpg


async def seed_experts():
    # Use the same default as other scripts or env
    db_url = os.getenv(
        "DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os"
    )

    # Path is relative to workspace root if run from there
    json_path = "configs/experts/employees.json"
    if not os.path.exists(json_path):
        # Try knowledge_os relative path
        json_path = "../configs/experts/employees.json"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    employees = data.get("employees", [])
    print(f"Found {len(employees)} employees in employees.json")

    conn = await asyncpg.connect(db_url)
    try:
        for emp in employees:
            name = emp["name"]
            role = emp["role"]
            dept = emp.get("department", "General")

            # Create a basic system prompt if missing
            system_prompt = f"You are {name}, {role} in the {dept} department."

            await conn.execute(
                """
                INSERT INTO experts (name, role, department, system_prompt)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (name) DO UPDATE
                SET role = EXCLUDED.role,
                    department = EXCLUDED.department;
            """,
                name,
                role,
                dept,
                system_prompt,
            )
            print(f"Seeded/Updated expert: {name}")

        print("Expert seeding completed successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_experts())
