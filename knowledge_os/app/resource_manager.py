import asyncio
import os
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


@asynccontextmanager
async def acquire_resource_lock(lock_name: str, timeout: int = 300):
    """
    Context manager to ensure only one heavy process runs at a time.
    Uses Redis as a distributed lock. Falls back to no-op if Redis is unavailable.
    """
    # Пробуем подключиться к Redis, если не получается - работаем без блокировок
    rd = None
    lock_key = "lock:heavy_process"
    lock_token = f"{lock_name}:{uuid.uuid4()}"

    class LeaseHandle:
        def __init__(self, redis_client, key, token, name):
            self.redis_client = redis_client
            self.key = key
            self.token = token
            self.name = name
            self.lost = False
            self.released = False

        async def release(self):
            if self.released:
                return False
            self.released = True
            if not self.redis_client:
                return True
            released = await self.redis_client.eval(
                """
                if redis.call('get', KEYS[1]) == ARGV[1] then
                    return redis.call('del', KEYS[1])
                else
                    return 0
                end
                """,
                1,
                self.key,
                self.token,
            )
            if int(released or 0) == 1:
                print(f"🔓 Global resource lock RELEASED by '{self.name}'.")
                return True
            print(f"ℹ️ Global resource lock already rotated for '{self.name}'.")
            return False

    redis_urls = [
        os.getenv("REDIS_URL"),
        "redis://redis:6379",  # имя сервиса в knowledge_os compose
        "redis://knowledge_os_redis:6379",  # контейнер atra-web-ide
        "redis://knowledge_redis:6379",  # контейнер atra (отдельный проект)
        "redis://atra-redis:6379",
        "redis://localhost:6379",
    ]

    for url in redis_urls:
        if url:
            test_rd = None
            try:
                test_rd = await redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
                await asyncio.wait_for(test_rd.ping(), timeout=2)
                rd = test_rd
                break
            except Exception:
                if test_rd:
                    try:
                        await test_rd.close()
                    except Exception:
                        pass
                rd = None
                continue

    if not rd:
        # Redis недоступен - работаем без блокировок
        print(f"⚠️ Redis недоступен, работаем без блокировок для '{lock_name}'")
        yield LeaseHandle(None, lock_key, lock_token, lock_name)
        return

    print(f"⏳ Waiting for global resource lock for '{lock_name}'...")

    max_wait_time = int(os.getenv("HEAVY_PROCESS_LOCK_WAIT_SEC", "30"))
    wait_start = asyncio.get_event_loop().time()
    renew_task = None

    try:
        while True:
            # Проверяем таймаут ожидания
            elapsed = asyncio.get_event_loop().time() - wait_start
            if elapsed > max_wait_time:
                print(f"⏱️ Timeout waiting for lock ({max_wait_time}s), proceeding without lock...")
                yield LeaseHandle(None, lock_key, lock_token, lock_name)
                break

            # Try to set the lock. NX=True only sets if it doesn't exist.
            # Expiry ensures the lock is released if the process crashes.
            if await rd.set(lock_key, lock_token, nx=True, ex=timeout):
                print(f"🔒 Global resource lock ACQUIRED by '{lock_name}'.")
                lease = LeaseHandle(rd, lock_key, lock_token, lock_name)

                async def _renew_loop():
                    # Продлеваем lease только если lock всё ещё наш (owner-token check)
                    interval = max(5, min(20, timeout // 3))
                    while True:
                        await asyncio.sleep(interval)
                        renewed = await rd.eval(
                            """
                            if redis.call('get', KEYS[1]) == ARGV[1] then
                                return redis.call('expire', KEYS[1], tonumber(ARGV[2]))
                            else
                                return 0
                            end
                            """,
                            1,
                            lock_key,
                            lock_token,
                            str(timeout),
                        )
                        if int(renewed or 0) != 1:
                            print(f"⚠️ Global resource lock LOST by '{lock_name}'")
                            lease.lost = True
                            break

                renew_task = asyncio.create_task(_renew_loop())
                try:
                    yield lease
                    break
                finally:
                    if renew_task:
                        renew_task.cancel()
                        try:
                            await renew_task
                        except asyncio.CancelledError:
                            pass
                    await lease.release()
            else:
                # Ждем меньше времени и проверяем таймаут
                await asyncio.sleep(5)  # Уменьшено с 30 до 5 секунд
    finally:
        if rd:
            try:
                await rd.close()
            except Exception:
                pass
