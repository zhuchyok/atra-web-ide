"""
[SINGULARITY 26.8] Subprocess Runner - Bypass Recursion

Виктория subprocess: запускает сложные задачи в отдельном процессе
- Нет рекурсии: отдельный Python процесс
- Простой деплой: не нужен Celery broker
- Fast: asyncio.create_subprocess_exec
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional


async def run_in_subprocess(
    prompt: str, expert_name: str = "Виктория", category: Optional[str] = None, timeout: int = 120
) -> Dict[str, Any]:
    """
    Запускает задачу в отдельном процессе - обходит recursion limit
    """
    # Создаём временный скрипт
    script_content = f"""
import asyncio
import json
import os
import sys
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/knowledge_os/app")

async def main():
    try:
        from ai_core import run_smart_agent_async
        result = await run_smart_agent_async(
            goal="{prompt}",
            expert_name="{expert_name}",
            category="{category or "general"}"
        )
        output = result.get("output", str(result))[:5000] if result else ""
        print(json.dumps({{"status": "success", "output": output}}))
    except Exception as e:
        print(json.dumps({{"status": "error", "output": str(e)[:500]}}))

if __name__ == "__main__":
    asyncio.run(main())
"""

    # Пишем скрипт
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(script_content)
        script_path = f.name

    try:
        # Запускаем в subprocess
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONPATH": "/app:/app/knowledge_os/app"},
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {"status": "timeout", "output": f"Task exceeded {timeout}s"}

        # Читаем результат
        if stdout:
            try:
                return json.loads(stdout.decode())
            except json.JSONDecodeError:
                return {"status": "success", "output": stdout.decode()[:5000]}

        if stderr:
            return {"status": "error", "output": stderr.decode()[:500]}

        return {"status": "empty", "output": "No output"}

    finally:
        # cleanup
        Path(script_path).unlink(missing_ok=True)


async def is_complex_task(prompt: str) -> bool:
    """Determines if task needs subprocess"""
    complex_keywords = [
        "код",
        "code",
        "писать",
        "write",
        "создай",
        "create",
        "анализ",
        "analysis",
        "исследование",
        "research",
        "реализуй",
        "implement",
        "архитектура",
        "architecture",
    ]
    return len(prompt) > 50 and any(kw in prompt.lower() for kw in complex_keywords)
