import asyncio
import json
import os
import subprocess
from datetime import datetime, timezone

try:
    import asyncpg
except ImportError:
    asyncpg = None  # модуль загрузится; get_pool() вернёт None при вызове


async def get_pool():
    if asyncpg is None:
        return None
    return await asyncpg.create_pool(
        os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os"),
        min_size=1,
        max_size=5,
    )


def run_cursor_agent(prompt: str):
    """Run cursor-agent CLI to process a prompt and return output."""
    try:
        result = subprocess.run(
            ["/root/.local/bin/cursor-agent", "--print", prompt],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except Exception as e:
        print(f"Error running cursor-agent for evaluation: {e}")
        return None


async def evaluate_knowledge(limit: int = 50):
    """
    Обработка необработанных узлов знаний через LM Judge.

    Args:
        limit: Количество узлов для обработки за один запуск (по умолчанию 50)
    """
    print(f"⚖️ Starting LM Judge (Evaluator) cycle (limit: {limit})...")
    pool = await get_pool()
    if pool is None:
        print("⚠️ asyncpg не установлен — установите: pip install asyncpg")
        return

    async with pool.acquire() as conn:
        # 1. Находим узлы, требующие верификации
        nodes = await conn.fetch(
            """
            SELECT id, content, metadata
            FROM knowledge_nodes
            WHERE is_verified = FALSE
            ORDER BY created_at ASC LIMIT $1
        """,
            limit,
        )

        if not nodes:
            print("✅ No unverified nodes found.")
            await pool.close()
            return

        for node in nodes:
            print(f"🧐 Evaluating node {node['id']}...")

            prompt = f"""
            Ты - Главный Судья Знаний (LM Judge). Проведи критический анализ следующего утверждения/информации:

            ЗНАНИЕ: {node["content"]}

            ЗАДАЧА:
            Оцени знание по 3 критериям (0-10):
            1. Достоверность (насколько это похоже на правду).
            2. Актуальность (не устарело ли это на 2025-2026 год).
            3. Полезность (насколько это ценно для корпорации).

            Верни JSON объект:
            {{
                "score": 0.0-1.0,
                "report": {{
                    "veracity": 0-10,
                    "relevance": 0-10,
                    "utility": 0-10,
                    "critique": "Краткая критика"
                }}
            }}
            Верни ТОЛЬКО JSON.
            """

            output = run_cursor_agent(prompt)

            if output:
                try:
                    # Очистка вывода
                    clean_json = output.strip()
                    if "```json" in clean_json:
                        clean_json = clean_json.split("```json")[1].split("```")[0]
                    elif "```" in clean_json:
                        clean_json = clean_json.split("```")[1].split("```")[0]

                    result = json.loads(clean_json)

                    await conn.execute(
                        """
                        UPDATE knowledge_nodes
                        SET confidence_score = $1,
                            quality_report = $2,
                            is_verified = TRUE
                        WHERE id = $3
                    """,
                        result["score"],
                        json.dumps(result["report"]),
                        node["id"],
                    )

                    print(f"✅ Node {node['id']} verified. Score: {result['score']}")

                except json.JSONDecodeError as e:
                    print(f"❌ Error parsing JSON for node {node['id']}: {e}")
                    print(f"   Output preview: {output[:200]}")
                except Exception as e:
                    print(f"❌ Error processing node {node['id']}: {e}")
            else:
                print(f"⚠️ No output from cursor-agent for node {node['id']}")

    await pool.close()


if __name__ == "__main__":
    import sys

    # Можно передать лимит через аргумент командной строки
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    asyncio.run(evaluate_knowledge(limit=limit))
