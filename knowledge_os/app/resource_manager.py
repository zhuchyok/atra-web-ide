import asyncio
import redis.asyncio as redis
import os
from contextlib import asynccontextmanager

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

@asynccontextmanager
async def acquire_resource_lock(lock_name: str, timeout: int = 3600):
    """
    Context manager to ensure only one heavy process runs at a time.
    Uses Redis as a distributed lock. Falls back to no-op if Redis is unavailable.
    """
    # Пробуем подключиться к Redis, если не получается - работаем без блокировок
    rd = None
    redis_urls = [
        os.getenv('REDIS_URL'),
        'redis://redis:6379',              # имя сервиса в knowledge_os compose
        'redis://knowledge_os_redis:6379', # контейнер atra-web-ide
        'redis://knowledge_redis:6379',    # контейнер atra (отдельный проект)
        'redis://atra-redis:6379',
        'redis://localhost:6379',
    ]
    
    for url in redis_urls:
        if url:
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
        # Redis недоступен - работаем без блокировок (просто yield)
        print(f"⚠️ Redis недоступен, работаем без блокировок для '{lock_name}'")
        yield True
        return
    
    # Redis доступен - используем блокировки
    lock_key = f"lock:heavy_process"
    
    print(f"⏳ Waiting for global resource lock for '{lock_name}'...")
    
    max_wait_time = 60  # Максимум 60 секунд ожидания
    wait_start = asyncio.get_event_loop().time()
    
    try:
        while True:
            # Проверяем таймаут ожидания
            elapsed = asyncio.get_event_loop().time() - wait_start
            if elapsed > max_wait_time:
                print(f"⏱️ Timeout waiting for lock ({max_wait_time}s), proceeding without lock...")
                yield True
                break
            
            # Try to set the lock. NX=True only sets if it doesn't exist.
            # Expiry ensures the lock is released if the process crashes.
            if await rd.set(lock_key, lock_name, nx=True, ex=timeout):
                print(f"🔒 Global resource lock ACQUIRED by '{lock_name}'.")
                try:
                    yield True
                    break
                finally:
                    await rd.delete(lock_key)
                    print(f"🔓 Global resource lock RELEASED by '{lock_name}'.")
            else:
                current_owner = await rd.get(lock_key)
                # Ждем меньше времени и проверяем таймаут
                await asyncio.sleep(5)  # Уменьшено с 30 до 5 секунд
    finally:
        if rd:
            try:
                await rd.close()
            except Exception:
                pass

