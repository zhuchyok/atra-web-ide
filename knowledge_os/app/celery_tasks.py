"""
[SINGULARITY 26.7] Celery Tasks - Background Job Processing

Виктория Б (Celery): Complex задачи выносятся в background workers
- Рекурсия решена: каждый worker - отдельный процесс
- Масштабируемость: добавляй workers -> больше throughput
- Webhook callback: клиент получает уведомление о завершении
"""

import os
import asyncio
from typing import Optional, Dict, Any
from celery import Celery
from celery.signals import worker_init

# Celery app - отдельный процесс, нет рекурсии!
app = Celery("victoria")

# Конфигурация из environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 min max
    task_soft_time_limit=240,  # 4 min soft
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
)


# Импорты AI_core только внутри tasks (отдельный процесс!)
def get_ai_core():
    """Lazy import - избегаем рекурсии при загрузке модуля"""
    from knowledge_os.app.ai_core import run_smart_agent_async

    return run_smart_agent_async


# ============================================================
# TASKS - Heavy Processing (отдельный процесс, нет рекурсии)
# ============================================================


@app.task(bind=True, name="victoria.run_code_generation", max_retries=2)
def run_code_generation(self, goal: str, **kwargs):
    """
    Heavy code generation task

    Этот код выполняется в отдельном Celery worker процессе.
    Нет рекурсии - каждый worker независимый.
    """
    try:
        run_smart_agent_async = get_ai_core()

        # Выполняем в event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            run_smart_agent_async(
                goal=goal,
                expert_name=kwargs.get("expert_name", "Виктория"),
                category=kwargs.get("category", "code"),
                is_vip=kwargs.get("is_vip", False),
                project_context=kwargs.get("project_context"),
            )
        )
        loop.close()

        return {
            "status": "success",
            "output": result.get("output", ""),
            "task_id": self.request.id,
        }

    except Exception as e:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        return {
            "status": "failed",
            "error": str(e),
            "task_id": self.request.id,
        }


@app.task(bind=True, name="victoria.run_analysis", max_retries=2)
def run_analysis(self, goal: str, context: Optional[Dict] = None, **kwargs):
    """
    Analysis task with full RAG pipeline

    Heavy задача с доступом к базе данных.
    Worker имеет отдельный стек - нет рекурсии.
    """
    try:
        from knowledge_os.app.ai_core import run_smart_agent_async

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Full RAG pipeline
        result = loop.run_until_complete(
            run_smart_agent_async(
                goal=goal,
                expert_name=kwargs.get("expert_name", "Аналитик"),
                category="analysis",
                project_context=kwargs.get("project_context", context),
            )
        )
        loop.close()

        return {
            "status": "success",
            "output": result.get("output", ""),
            "knowledge": result.get("knowledge", {}),
        }

    except Exception as e:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        return {"status": "failed", "error": str(e)}


@app.task(bind=True, name="victoria.run_research", max_retries=1)
def run_research(self, query: str, **kwargs):
    """
    Research task - deep research с множественными источниками
    """
    try:
        from knowledge_os.app.ai_core import run_smart_agent_async

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            run_smart_agent_async(
                goal=f"Проведи глубокое исследование: {query}",
                expert_name="Исследователь",
                category="research",
            )
        )
        loop.close()

        return {
            "status": "success",
            "output": result.get("output", ""),
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.task(name="victoria.health_check")
def health_check():
    """Проверка здоровья worker-а"""
    return {
        "status": "healthy",
        "worker": "celery-victoria",
    }


# ============================================================
# Fast Path - для простых задач (без очереди)
# ============================================================


def is_complex_task(goal: str) -> bool:
    """
    Определяет_complex задачу для постановки в очередь

    Returns True для задач которые нужно отправить в Celery
    """
    goal_lower = goal.lower()

    complex_keywords = [
        "код",
        "code",
        "напиши",
        "write",
        "создай",
        "create",
        "проект",
        "project",
        "архитектура",
        "architecture",
        "анализ",
        "analysis",
        "исследование",
        "research",
        "реализуй",
        "implement",
        "разработай",
        "develop",
        "спроектируй",
        "design",
    ]
    return any(kw in goal_lower for kw in complex_keywords)


async def offload_to_celery(goal: str, expert_name: str = "Виктория", category: str = None) -> str:
    """Async wrapper for Celery task queueing"""
    if is_complex_task(goal):
        task = queue_task.delay(goal, expert_name=expert_name, category=category)
        return task.id
    raise ValueError("Task not complex enough for Celery")


def queue_task(goal: str, **kwargs) -> Dict[str, Any]:
    """
    Постановка задачи в очередь

    Возвращает task_id для отслеживания
    """
    if is_complex_task(goal):
        task = run_code_generation.delay(goal, **kwargs)
        return {"queued": True, "task_id": task.id, "status_url": f"/api/tasks/{task.id}"}

    return {"queued": False}


# ============================================================
# Webhook Callback Helper
# ============================================================


async def notify_webhook(webhook_url: str, result: Dict):
    """Отправить результат на webhook"""
    if not webhook_url:
        return

    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            await session.post(webhook_url, json=result)
    except Exception as e:
        print(f"Webhook error: {e}")


# Celery beat schedule (если нужен periodic tasks)
@app.task(name="victoria.periodic.health")
def periodic_health():
    """Periodic health check"""
    return {"status": "ok", "timestamp": asyncio.time.time()}


if __name__ == "__main__":
    app.start()
