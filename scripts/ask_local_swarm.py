import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone

print(f"DEBUG: SCRIPT START (PID: {os.getpid()})")
print(f"DEBUG: os.environ['REDIS_URL'] at start: {os.environ.get('REDIS_URL')}")

# [SINGULARITY 24.3] Устанавливаем REDIS_URL для локального запуска
# Если мы в Docker, используем имя сервиса. Если на хосте, используем localhost.
is_docker = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "").lower() == "true"
if is_docker:
    # ВАЖНО: В Docker используем REDIS_URL из окружения, если он есть
    os.environ["REDIS_URL"] = os.getenv("REDIS_URL", "redis://knowledge_os_redis:6379/0")
    print(f"DEBUG: Running in Docker, REDIS_URL={os.environ['REDIS_URL']}")
else:
    # [FIX] На хосте используем 6381, но только если мы НЕ в докере
    if not os.environ.get("REDIS_URL"):
        os.environ["REDIS_URL"] = "redis://localhost:6381/0"
    print(f"DEBUG: Running on Host, REDIS_URL={os.environ['REDIS_URL']}")

# Добавляем пути
base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ko_app_path = os.path.join(base_path, "knowledge_os/app")
if ko_app_path not in sys.path:
    sys.path.insert(0, ko_app_path)

# [SINGULARITY 24.3] ПРОВЕРКА: что в окружении ПЕРЕД импортом
print(f"DEBUG: REDIS_URL in environ BEFORE import: {os.environ.get('REDIS_URL')}")

import redis_manager as rm_module
# Принудительно сбрасываем и переинициализируем синглтон с новым URL
rm_module.RedisManager._instance = None
rm_module.redis_manager = rm_module.RedisManager(url=os.environ["REDIS_URL"])
rm_module.REDIS_URL = os.environ["REDIS_URL"]
print(f"DEBUG: redis_manager re-initialized with {os.environ['REDIS_URL']}")

from event_bus import get_event_bus, Event, EventType
from event_bus_redis_bridge import start_redis_bridge

async def ask_local_swarm(query: str):

    print("DEBUG: Starting EventBus...")
    bus = get_event_bus()
    await bus.start()
    
    print("DEBUG: Starting Redis Bridge...")
    bridge = await start_redis_bridge(bus)
    
    # [SINGULARITY 24.3] DEBUG: Проверим, какой RedisManager использует мост
    print(f"DEBUG: RedisManager URL in bridge instance: {bridge.redis_manager.url}")
    
    # [SINGULARITY 24.3] ПРОВЕРКА: может ли мост реально подключиться к Redis?
    try:
        client = await bridge.redis_manager.get_client()
        await client.ping()
        print(f"✅ [DEBUG] Redis connection verified to {bridge.redis_manager.url}")
    except Exception as e:
        print(f"❌ [DEBUG] Redis connection failed to {bridge.redis_manager.url}: {e}")

    print("DEBUG: Initializing dialogue...")
    dialogue_id = str(uuid.uuid4())

    # [SINGULARITY 24.3] Fix 5: Очистка устаревших задач и ghost-групп перед тестом
    try:
        client = await bridge.redis_manager.get_client()
        # 1. Удаляем и пересоздаём группу expert_workers - самый чистый способ сбросить pending
        try:
            await client.xgroup_destroy("stream:expert_tasks", "expert_workers")
        except Exception:
            pass
        try:
            await client.xgroup_create("stream:expert_tasks", "expert_workers", id="$", mkstream=True)
        except Exception:
            await client.xgroup_setid("stream:expert_tasks", "expert_workers", "$")
        # 2. Очищаем stream:expert_tasks (все задачи)
        await client.xtrim("stream:expert_tasks", maxlen=0)
        # 3. Удаляем ghost consumer groups из event_bus_stream (оставляем только lag=0)
        try:
            all_groups = await client.xinfo_groups("stream:event_bus_stream")
            for grp in all_groups:
                g_name = grp["name"].decode() if isinstance(grp["name"], bytes) else grp["name"]
                consumers = grp.get("consumers", 0)
                # Удаляем только пустые группы (не текущую активную)
                if consumers == 0 and g_name != bridge.group_name:
                    try:
                        await client.xgroup_destroy("stream:event_bus_stream", g_name)
                    except Exception:
                        pass
        except Exception as ge:
            print(f"DEBUG: Ghost group cleanup: {ge}")
        print(f"✅ [CLEANUP] Streams purged, consumer groups reset")
    except Exception as ce:
        print(f"⚠️ [CLEANUP] Could not purge streams: {ce}")

    # [SINGULARITY 24.3] Устанавливаем флаг активного диалога — воркеры пропустят не-диалоговые задачи
    try:
        client = await bridge.redis_manager.get_client()
        await client.set("dialogue_active", "1", ex=600)  # TTL 10 минут
        print(f"✅ [CLEANUP] dialogue_active flag set (600s TTL)")
    except Exception as flag_err:
        print(f"⚠️ [CLEANUP] Could not set dialogue_active: {flag_err}")

    print(f"\n🚀 [SINGULARITY 24.3] Инициализация Живого Чата...")
    print(f"📝 Запрос: {query}")
    print(f"🆔 ID Диалога: {dialogue_id}")
    print("-" * 50)

    # Состояние для отслеживания ответов
    responses_received = set()
    consensus_event = asyncio.Event()
    final_result = None

    async def handle_expert_thought(event: Event):
        data = event.payload
        if data.get("dialogue_id") == dialogue_id:
            expert = data.get("expert_name")
            thought = data.get("thought")
            print(f"💭 [{expert}] размышляет: {thought}")

    async def handle_expert_response(event: Event):
        data = event.payload
        if data.get("dialogue_id") == dialogue_id:
            expert = data.get("expert_name")
            response = data.get("response")
            if expert not in responses_received:
                responses_received.add(expert)
                print(f"\n📥 [ОТВЕТ] {expert}:")
                print(f"{response}")
                print("-" * 30)

    async def handle_consensus(event: Event):
        nonlocal final_result
        data = event.payload
        if data.get("dialogue_id") == dialogue_id:
            final_result = data
            consensus_event.set()

    # Подписка на события
    bus.subscribe(EventType.EXPERT_THOUGHT, handle_expert_thought)
    bus.subscribe(EventType.EXPERT_RESPONSE, handle_expert_response)
    bus.subscribe(EventType.DIALOGUE_CONSENSUS, handle_consensus)

    # Публикация запроса
    event = Event(
        event_id=str(uuid.uuid4()),
        event_type=EventType.DIALOGUE_REQUEST,
        payload={"query": query, "dialogue_id": dialogue_id},
        source="cursor_bridge"
    )
    
    print(f"DEBUG: Publishing event {event.event_id} via local bus...")
    await bus.publish(event)

    print("⏳ Ожидание ответов экспертов...")
    
    try:
        # Ждем консенсуса с таймаутом
        await asyncio.wait_for(consensus_event.wait(), timeout=300)
        
        if final_result:
            print("\n" + "=" * 50)
            print("🤝 [ИТОГОВЫЙ КОНСЕНСУС РОЯ]")
            print(f"📊 Score: {final_result.get('consensus_score', 0):.2f} | Согласие: {final_result.get('agreement_level', 0):.2f}")
            print("-" * 50)
            print(final_result.get("final_answer"))
            print("=" * 50 + "\n")
            
    except asyncio.TimeoutError:
        print("\n⚠️ Таймаут ожидания консенсуса. Возможно, эксперты еще работают.")
    finally:
        await bridge.stop()
        await bus.stop()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python scripts/ask_local_swarm.py \"ваш вопрос\"")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    asyncio.run(ask_local_swarm(query))
