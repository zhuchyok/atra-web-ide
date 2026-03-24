import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone

import asyncpg

# Сингулярность 10.0: Импорты с поддержкой разных путей (Docker/Local)
try:
    from ai_core import run_smart_agent_async
    from redis_manager import redis_manager
    from services.knowledge_service import knowledge_service
except ImportError:
    try:
        from app.ai_core import run_smart_agent_async
        from app.redis_manager import redis_manager
        from app.services.knowledge_service import knowledge_service
    except ImportError:
        # Fallback для тестов или специфических окружений
        import sys

        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from ai_core import run_smart_agent_async
        from redis_manager import redis_manager
        from services.knowledge_service import knowledge_service

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ExpertWorker")

DB_URL = os.getenv("DATABASE_URL")
STREAM_NAME = "expert_tasks"
GROUP_NAME = "expert_workers"
CONSUMER_NAME = f"worker_{os.uname()[1]}"

# Глобальный пул соединений (Singularity 21.9: Один пул — один процесс)
_db_pool = None


async def get_db_pool():
    """Возвращает глобальный пул соединений с БД"""
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            DB_URL,
            min_size=1,
            max_size=10,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )
    return _db_pool


async def process_task(task_data: dict):
    """Выполняет задачу и сохраняет результат."""
    task_id = task_data["task_id"]
    expert_name = task_data["expert_name"]
    description = task_data["description"]

    logger.info(f"🛠️ [WORKER] Начало выполнения задачи {task_id} для {expert_name}")
    print(f"DEBUG_PRINT: task_data metadata: {task_data.get('metadata')}")

    try:
        # 1. Обновляем статус в БД и Redis
        # Сингулярность 10.0: Проверяем, является ли task_id валидным UUID перед запросом к БД
        is_valid_uuid = False
        try:
            import uuid

            uuid.UUID(str(task_id))
            is_valid_uuid = True
        except ValueError:
            logger.warning(f"⚠️ Task ID {task_id} is not a valid UUID, skipping DB update")

        # [SINGULARITY 21.9] Circuit Breaker: Глобальный таймаут на всю обработку задачи (15 минут)
        # Это предотвращает бесконечное зависание воркера при сбоях LLM/сетевых задержках
        TASK_TOTAL_TIMEOUT = float(os.getenv("WORKER_TASK_TOTAL_TIMEOUT", "900"))

        async with asyncio.timeout(TASK_TOTAL_TIMEOUT):
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                if is_valid_uuid:
                    await conn.execute(
                        "UPDATE tasks SET status = 'in_progress', updated_at = NOW() WHERE id = $1",
                        task_id,
                    )

                await redis_manager.update_task_status(
                    task_id, "in_progress", metadata={"expert": expert_name}
                )

                # 2. Выполняем через AI Core или ReAct Agent (Singularity 14.0)
                # ... (логика выбора агента) ...
                if task_data.get("metadata", {}).get("complex") or expert_name == "Виктория":
                    # ... (выполнение ReAct) ...
                    logger.info(f"🧠 [WORKER] Используем ReAct Agent для сложной задачи {task_id}")
                    try:
                        from react_agent import ReActAgent

                        model_hint = task_data.get("metadata", {}).get("model_hint")
                        print(f"DEBUG_PRINT: Initializing ReActAgent with model: {model_hint or 'victoria-wisdom-v3.5:latest'}")
                        agent = ReActAgent(agent_name=expert_name, model_name=model_hint or "victoria-wisdom-v3.5:latest")
                        print(f"DEBUG_PRINT: Calling agent.run() for task {task_id}")
                        report = await agent.run(goal=description)
                        print(f"DEBUG_PRINT: agent.run() finished for task {task_id}")
                        # [SINGULARITY 21.26] Fix: ReActAgent returns 'response', not 'result'
                        if isinstance(report, dict) and "response" in report:
                            report_text = report["response"]
                        else:
                            report_text = str(report.get("result") if isinstance(report, dict) else report)
                    except Exception as e:
                        logger.error(f"⚠️ Ошибка ReAct Agent, fallback на AI Core: {e}")
                        report = await run_smart_agent_async(
                            description,
                            expert_name=expert_name,
                            category=task_data.get("category", "general"),
                        )
                        report_text = str(report.get("result") if isinstance(report, dict) else report)
                else:
                    report = await run_smart_agent_async(
                        description,
                        expert_name=expert_name,
                        category=task_data.get("category", "general"),
                    )
                    report_text = str(report.get("result") if isinstance(report, dict) else report)

                # 3. Сохраняем результат
                if isinstance(report_text, dict):
                    report_text = json.dumps(report_text, ensure_ascii=False, indent=2)
                else:
                    report_text = str(report_text)

                if is_valid_uuid:
                    print(f"DEBUG_PRINT: Updating task {task_id} to completed in DB")
                    await conn.execute(
                        """
                        UPDATE tasks SET status = 'completed', result = $2, completed_at = NOW()
                        WHERE id = $1
                    """,
                        task_id,
                        report_text,
                    )

                await redis_manager.update_task_status(task_id, "completed", result=report_text)

                # Сингулярность 10.0: Снимаем блокировку идемпотентности
                await redis_manager.release_task_lock(task_id)

                # 4. Сохраняем инсайт в базу знаний
                await knowledge_service.save_insight(
                    report_text,
                    expert_name,
                    metadata={"task_id": task_id, "source": "worker_service"},
                )

                logger.info(f"✅ [WORKER] Задача {task_id} успешно завершена")

    except asyncio.TimeoutError:
        logger.error(
            f"⌛ [CIRCUIT BREAKER] Задача {task_id} прервана по таймауту ({TASK_TOTAL_TIMEOUT}с)"
        )
        error_msg = f"Task timed out after {TASK_TOTAL_TIMEOUT}s (Circuit Breaker)"
        await _handle_task_error(task_id, error_msg, is_valid_uuid)

    except Exception as e:
        logger.error(f"❌ [WORKER] Ошибка задачи {task_id}: {e}", exc_info=True)
        error_msg = str(e)
        await _handle_task_error(task_id, error_msg, is_valid_uuid)


async def _handle_task_error(task_id, error_msg, is_valid_uuid):
    """Вспомогательная функция для обработки ошибок задачи"""
    try:
        await redis_manager.update_task_status(task_id, "failed", result=error_msg)
        if is_valid_uuid:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'failed',
                        result = $2,
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('last_error', $3::text)
                    WHERE id = $1
                """,
                    task_id,
                    error_msg,
                    error_msg[:200],
                )
        await redis_manager.release_task_lock(task_id)
    except Exception as e:
        logger.error(f"⚠️ Не удалось сохранить ошибку в БД/Redis: {e}")


async def worker_loop():
    """Основной цикл воркера: слушает Redis Stream."""
    client = await redis_manager.get_client()

    # Создаем группу потребителей, если её нет
    try:
        await client.xgroup_create(f"stream:{STREAM_NAME}", GROUP_NAME, mkstream=True)
    except Exception:
        pass  # Группа уже существует

    # Запускаем систему самообучения корпорации (Singularity 14.0)
    try:
        from corporation_self_learning import get_corporation_learner

        learner = get_corporation_learner()
        # Запускаем в фоне (интервал 6 часов)
        asyncio.create_task(learner.start_continuous_learning(interval_hours=6))
        logger.info("🧠 [SINGULARITY 10.0] Collective Learning system started")
    except Exception as e:
        logger.warning(f"⚠️ [SINGULARITY 10.0] Could not start collective learning: {e}")

    logger.info(f"🚀 [WORKER] Воркер запущен. Слушаю поток {STREAM_NAME}...")

    while True:
        try:
            # Сингулярность 10.0: Сначала проверяем зависшие задачи других воркеров (Autoclaim)
            # Если задача висит более 5 минут (300000 мс), перехватываем её
            stale_messages = await redis_manager.autoclaim_tasks(
                STREAM_NAME, GROUP_NAME, CONSUMER_NAME, min_idle_time_ms=300000
            )

            # Читаем новые сообщения
            messages = await client.xreadgroup(
                GROUP_NAME, CONSUMER_NAME, {f"stream:{STREAM_NAME}": ">"}, count=1, block=5000
            )

            # Объединяем зависшие и новые сообщения
            all_messages = []
            if stale_messages:
                all_messages.append((f"stream:{STREAM_NAME}", stale_messages))
            if messages:
                all_messages.extend(messages)

            if not all_messages:
                continue

            for stream, msgs in all_messages:
                for msg_id, data in msgs:
                    try:
                        # Проверяем количество попыток (Dead Letter Queue logic)
                        # Если задача провалилась более 3 раз, помечаем как failed
                        info = await client.xpending_range(
                            f"stream:{STREAM_NAME}", GROUP_NAME, msg_id, msg_id, 1
                        )
                        if info and info[0]["times_delivered"] > 3:
                            logger.error(
                                f"💀 [DLQ] Задача {msg_id} превысила лимит попыток (3). Удаляем из очереди."
                            )
                            await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, msg_id)
                            continue

                        # Сингулярность 10.0: поддержка как JSON-строки, так и прямого словаря
                        raw_payload = data.get(b"payload") or data.get("payload")
                        if isinstance(raw_payload, (str, bytes)):
                            payload = json.loads(raw_payload)
                        else:
                            # Если данные уже в виде словаря (пришли не как JSON строка)
                            payload = {
                                k.decode() if isinstance(k, bytes) else k: v.decode()
                                if isinstance(v, bytes)
                                else v
                                for k, v in data.items()
                            }

                        await process_task(payload)
                        # Подтверждаем обработку
                        await client.xack(f"stream:{STREAM_NAME}", GROUP_NAME, msg_id)
                    except Exception as e:
                        logger.error(f"❌ [WORKER] Ошибка обработки сообщения {msg_id}: {e}")

        except Exception as e:
            logger.error(f"⚠️ [WORKER] Ошибка в цикле: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("🛑 [WORKER] Остановка по сигналу пользователя")
