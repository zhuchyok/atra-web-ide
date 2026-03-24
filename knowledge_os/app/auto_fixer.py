import asyncio
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
PROJECT_ROOT = "/root/knowledge_os"


def run_cursor_agent(prompt: str):
    """Run cursor-agent CLI to generate code fixes."""
    try:
        env = os.environ.copy()
        result = subprocess.run(
            ["/root/.local/bin/cursor-agent", "--print", prompt],
            capture_output=True,
            text=True,
            check=True,
            timeout=1800,
            env=env,
        )
        return result.stdout
    except Exception as e:
        print(f"Error running cursor-agent for fixing: {e}")
        return None


def verify_syntax(file_path: str):
    """Verify python syntax using py_compile."""
    try:
        subprocess.run(["python3", "-m", "py_compile", file_path], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Syntax error in {file_path}: {e.stderr.decode()}")
        return False


async def apply_fix(task_id, file_name, instruction):
    print(f"🔧 Auto-Fixer: Attempting to fix {file_name} for task {task_id}...")

    file_path = os.path.join(PROJECT_ROOT, "app", file_name)
    if not os.path.exists(file_path):
        print(f"❌ File {file_path} not found.")
        return False

    # 1. Create backup
    bak_path = file_path + ".bak"
    shutil.copy2(file_path, bak_path)

    try:
        # 2. Read original content
        with open(file_path) as f:
            original_content = f.read()

        # 3. Generate fix using cursor-agent
        prompt = f"""
        ТЫ - ГЛАВНЫЙ PYTHON РАЗРАБОТЧИК.
        ЗАДАЧА: Исправь ошибку в файле {file_name} согласно инструкции.

        ИНСТРУКЦИЯ: {instruction}

        ТЕКУЩЕЕ СОДЕРЖИМОЕ ФАЙЛА:
        ```python
        {original_content}
        ```

        ОТВЕТЬ ТОЛЬКО ПОЛНЫМ ТЕКСТОМ ИСПРАВЛЕННОГО ФАЙЛА. НЕ ИСПОЛЬЗУЙ ЧАТ-ПОЯСНЕНИЯ.
        """

        new_content = run_cursor_agent(prompt)

        if not new_content or len(new_content) < 10:
            print("❌ Failed to generate new content.")
            return False

        # Clean up output (remove markdown fences if any)
        if "```python" in new_content:
            new_content = new_content.split("```python")[1].split("```")[0]
        elif "```" in new_content:
            new_content = new_content.split("```")[1].split("```")[0]

        # 4. Write new content
        with open(file_path, "w") as f:
            f.write(new_content.strip())

        # 5. Verify syntax
        if verify_syntax(file_path):
            print(f"✅ Fix applied and verified for {file_name}")
            return True
        else:
            print(f"🚨 Syntax error detected! Rolling back {file_name}...")
            shutil.copy2(bak_path, file_path)
            return False

    except Exception as e:
        print(f"❌ Error during fixing: {e}")
        shutil.copy2(bak_path, file_path)
        return False


async def run_auto_fixer_cycle():
    print("🚑 Starting Guarded Auto-Fixer cycle...")
    conn = await asyncpg.connect(DB_URL)

    # 1. Get pending auto-audit tasks
    tasks = await conn.fetch("""
        SELECT id, title, description, metadata
        FROM tasks
        WHERE status = 'pending'
        AND metadata->>'source' = 'code_auditor'
        ORDER BY created_at ASC LIMIT 3
    """)

    if not tasks:
        print("✅ No pending auto-audit tasks.")
        await conn.close()
        return

    for t in tasks:
        # Пытаемся вычленить имя файла из заголовка или описания
        # Обычно code_auditor пишет "Исправить X в файле Y.py"
        instruction = t["description"]

        # Упрощенный поиск файла (можно улучшить)
        target_file = None
        for word in t["title"].split() + t["description"].split():
            if word.endswith(".py"):
                target_file = word.strip(".,()")
                break

        if target_file:
            success = await apply_fix(t["id"], target_file, instruction)
            if success:
                await conn.execute(
                    "UPDATE tasks SET status = 'completed', metadata = metadata || '{\"fixed_at\": \"now()\"}'::jsonb WHERE id = $1",
                    t["id"],
                )
                await conn.execute(
                    """
                    INSERT INTO notifications (message, type)
                    VALUES ($1, 'system_alert')
                """,
                    f"💊 AUTO-FIX SUCCESS: Файл {target_file} исправлен автоматически.",
                )
            else:
                await conn.execute("UPDATE tasks SET status = 'failed' WHERE id = $1", t["id"])
        else:
            print(f"⚠️ Could not identify target file for task: {t['title']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(run_auto_fixer_cycle())
