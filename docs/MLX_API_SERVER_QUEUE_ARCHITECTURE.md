# Архитектура очередей для MLX API Server

## Текущая проблема

1. **MLX API Server** имеет лимит `_max_concurrent_requests = 5`
2. **Чат с Викторией** обращается к MLX через Victoria API (порт 8010)
3. **Task Distribution** обращается к MLX напрямую через ReActAgent
4. **НЕТ очереди** - при превышении лимита возвращается 503
5. **НЕТ приоритизации** - чат и Task Distribution конкурируют на равных

## Анализ запросов

### Чат с Викторией
- Путь: `Frontend → Backend API → Victoria API (8010) → MLX API Server (11435)`
- Приоритет: **ВЫСОКИЙ** (пользователь ждет ответа)
- Тип: интерактивный, требует быстрого ответа

### Task Distribution
- Путь: `Victoria → Task Distribution → ReActAgent → MLX API Server (11435)`
- Приоритет: **СРЕДНИЙ** (может подождать)
- Тип: фоновый, может выполняться асинхронно

## Решение: Очередь с приоритетами

### Вариант 1: Очередь в MLX API Server (рекомендуется)

```python
import asyncio
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

class RequestPriority(Enum):
    HIGH = 1      # Чат с Викторией
    MEDIUM = 2    # Task Distribution
    LOW = 3       # Фоновые задачи

@dataclass
class QueuedRequest:
    request_id: str
    priority: RequestPriority
    callback: callable
    created_at: datetime
    timeout: float = 300.0  # 5 минут

class MLXRequestQueue:
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.active_requests = 0
        self.queue = asyncio.PriorityQueue()
        self._lock = asyncio.Lock()
    
    async def add_request(
        self,
        request_id: str,
        priority: RequestPriority,
        callback: callable,
        timeout: float = 300.0
    ):
        """Добавить запрос в очередь"""
        queued = QueuedRequest(
            request_id=request_id,
            priority=priority,
            callback=callback,
            created_at=datetime.now(),
            timeout=timeout
        )
        await self.queue.put((priority.value, queued))
        await self._process_queue()
    
    async def _process_queue(self):
        """Обработать очередь"""
        while self.active_requests < self.max_concurrent:
            try:
                priority, request = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                break
            
            # Проверяем таймаут
            if (datetime.now() - request.created_at).total_seconds() > request.timeout:
                logger.warning(f"⚠️ Запрос {request.request_id} истек по таймауту")
                continue
            
            # Выполняем запрос
            self.active_requests += 1
            asyncio.create_task(self._execute_request(request))
    
    async def _execute_request(self, request: QueuedRequest):
        """Выполнить запрос"""
        try:
            await request.callback()
        finally:
            self.active_requests -= 1
            await self._process_queue()  # Обрабатываем следующий запрос
```

### Вариант 2: Отдельные очереди для чата и Task Distribution

```python
class RequestRouter:
    def __init__(self):
        self.chat_queue = asyncio.Queue()  # Приоритетная очередь
        self.task_queue = asyncio.Queue()  # Фоновая очередь
        self.max_chat_concurrent = 3  # Резервируем для чата
        self.max_task_concurrent = 2  # Для Task Distribution
    
    async def route_request(self, request_type: str, callback: callable):
        if request_type == "chat":
            await self.chat_queue.put(callback)
        else:
            await self.task_queue.put(callback)
        
        await self._process_queues()
```

### Вариант 3: Увеличить лимит + добавить очередь ожидания

```python
# Увеличить лимит
_max_concurrent_requests = 10  # Вместо 5

# Добавить очередь ожидания
_waiting_queue = asyncio.Queue(maxsize=50)  # Максимум 50 ожидающих

async def handle_request_with_queue(request):
    if _active_requests >= _max_concurrent_requests:
        # Добавляем в очередь ожидания
        await _waiting_queue.put(request)
        return {"status": "queued", "position": _waiting_queue.qsize()}
    else:
        # Выполняем сразу
        return await execute_request(request)
```

## Рекомендация

**Вариант 1** (очередь с приоритетами) - лучший выбор:
- ✅ Чат получает приоритет
- ✅ Task Distribution не блокирует чат
- ✅ Автоматическая обработка очереди
- ✅ Таймауты для защиты от зависших запросов

## Вопрос: Чат с Викторией в очереди?

**Текущее состояние:** НЕТ очереди
- Чат идет напрямую к MLX API Server
- При превышении лимита (5 запросов) получает 503
- Task Distribution конкурирует с чатом на равных

**После реализации:** ДА, но с приоритетом
- Чат попадает в очередь с приоритетом HIGH
- Обрабатывается первым при освобождении слота
- Task Distribution ждет, если все слоты заняты чатом

## План реализации

1. ✅ Создать `MLXRequestQueue` с приоритетами
2. ✅ Интегрировать в MLX API Server
3. ✅ Добавить параметр `priority` в запросы
4. ✅ Victoria API передает `priority=HIGH` для чатов
5. ✅ Task Distribution передает `priority=MEDIUM`
6. ✅ Тестирование
