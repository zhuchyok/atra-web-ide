# 🚀 План улучшения Victoria Agent

**Дата:** 2026-01-25  
**Статус:** 📋 **ПЛАН ПРЕДЛОЖЕНИЙ**

---

## 🎯 ТЕКУЩЕЕ СОСТОЯНИЕ

### ✅ Что уже работает:
- ✅ Отдельный Victoria-сервер (`victoria_server.py`)
- ✅ Оптимизация простых задач (пропуск planner)
- ✅ ELK логирование интегрировано
- ✅ Доступ к Ollama через `host.docker.internal:11434`
- ✅ Health checks и статус endpoints
- ✅ MCP интеграция для Cursor

### ⚠️ Области для улучшения:
1. **Интеграция с Knowledge OS** — не использует базу знаний экспертов
2. **Выбор экспертов** — не использует систему из 40+ экспертов
3. **Кэширование** — нет кэширования похожих задач
4. **Обработка ошибок** — базовая, без retry логики
5. **Метрики** — нет детальных метрик производительности
6. **Обучение** — не накапливает опыт из выполненных задач

---

## 💡 ПРЕДЛОЖЕНИЯ ПО УЛУЧШЕНИЮ

### 1. 🔗 ИНТЕГРАЦИЯ С KNOWLEDGE OS

**Проблема:** Victoria не использует базу знаний из Knowledge OS (50,926 знаний, 58 экспертов)

**Решение:**
```python
# Добавить в VictoriaAgent.__init__()
from knowledge_os.src.database.db import Database

class VictoriaAgent(BaseAgent):
    def __init__(self, name: str = "Виктория", model_name: str = None):
        # ... существующий код ...
        
        # Интеграция с Knowledge OS
        self.db = Database()
        self.expert_team = self._load_expert_team()  # Загрузить команду экспертов
        
    def _load_expert_team(self):
        """Загрузить команду экспертов из Knowledge OS"""
        experts = self.db.get_all_experts()
        return {expert.name: expert for expert in experts}
```

**Преимущества:**
- ✅ Доступ к 50,926 знаний из базы
- ✅ Использование опыта 58 экспертов
- ✅ RAG (Retrieval Augmented Generation) для контекста

---

### 2. 👥 АВТОМАТИЧЕСКИЙ ВЫБОР ЭКСПЕРТОВ

**Проблема:** Victoria не использует систему выбора экспертов для задач

**Решение:**
```python
async def select_expert_for_task(self, goal: str) -> Optional[str]:
    """Автоматически выбрать эксперта для задачи"""
    # Анализ задачи
    category = self._categorize_task(goal)
    
    # Поиск подходящего эксперта в Knowledge OS
    expert = self.db.find_expert_by_category(category)
    
    if expert:
        # Использовать знания эксперта в промпте
        expert_knowledge = self.db.get_expert_knowledge(expert.name)
        return expert.name, expert_knowledge
    
    return None, None

async def plan(self, goal: str):
    # Выбрать эксперта для задачи
    expert_name, expert_knowledge = await self.select_expert_for_task(goal)
    
    if expert_name:
        plan_prompt = f"""ТЫ — ВИКТОРИЯ, TEAM LEAD. 
        
ЭКСПЕРТ ДЛЯ ЗАДАЧИ: {expert_name}
ЗНАНИЯ ЭКСПЕРТА: {expert_knowledge[:500]}

ЗАДАЧА: {goal}
...
"""
    else:
        # Существующий промпт
        ...
```

**Преимущества:**
- ✅ Использование специализированных знаний экспертов
- ✅ Более точные решения для специфичных задач
- ✅ Автоматическое распределение задач

---

### 3. 💾 КЭШИРОВАНИЕ ПОХОЖИХ ЗАДАЧ

**Проблема:** Повторяющиеся задачи выполняются заново каждый раз

**Решение:**
```python
import hashlib
from functools import lru_cache

class VictoriaAgent(BaseAgent):
    def __init__(self, ...):
        # ... существующий код ...
        self.task_cache = {}  # Кэш выполненных задач
        
    def _task_hash(self, goal: str) -> str:
        """Хеш задачи для кэширования"""
        return hashlib.md5(goal.lower().strip().encode()).hexdigest()
    
    async def run(self, goal: str, max_steps: int = 30) -> str:
        # Проверка кэша
        task_hash = self._task_hash(goal)
        if task_hash in self.task_cache:
            logger.info(f"✅ Использован кэш для задачи: {goal[:50]}")
            return self.task_cache[task_hash]
        
        # Выполнение задачи
        result = await super().run(goal, max_steps)
        
        # Сохранение в кэш (только для успешных задач)
        if result and "ошибка" not in result.lower():
            self.task_cache[task_hash] = result
            # Сохранить в Knowledge OS для обучения
            self.db.save_task_result(goal, result)
        
        return result
```

**Преимущества:**
- ✅ Мгновенные ответы на повторяющиеся задачи
- ✅ Экономия ресурсов (модели, время)
- ✅ Накопление опыта в базе знаний

---

### 4. 🔄 УЛУЧШЕННАЯ ОБРАБОТКА ОШИБОК И RETRY

**Проблема:** Базовая обработка ошибок, нет retry логики

**Решение:**
```python
from src.core.retry import RetryManager, RetryConfig

class VictoriaAgent(BaseAgent):
    def __init__(self, ...):
        # ... существующий код ...
        
        # Retry manager для надежности
        retry_config = RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            retryable_exceptions=(httpx.RequestError, asyncio.TimeoutError)
        )
        self.retry_manager = RetryManager(config=retry_config)
    
    async def step(self, prompt: str):
        """Выполнить шаг с retry логикой"""
        async def _execute_step():
            context_memory = self.memory[-10:] if len(self.memory) > 10 else self.memory
            return await self.executor.ask(prompt, history=context_memory)
        
        try:
            return await self.retry_manager.execute_async(_execute_step)
        except Exception as e:
            logger.error(f"❌ Ошибка после retry: {e}")
            # Fallback на более простую модель
            return await self._fallback_execution(prompt)
    
    async def _fallback_execution(self, prompt: str):
        """Fallback на более простую модель"""
        fallback_executor = OllamaExecutor(
            model="phi4",  # Более легкая модель
            base_url=_ollama_base_url()
        )
        return await fallback_executor.ask(prompt)
```

**Преимущества:**
- ✅ Автоматические retry при временных ошибках
- ✅ Fallback на альтернативные модели
- ✅ Повышенная надежность системы

---

### 5. 📊 МЕТРИКИ И МОНИТОРИНГ

**Проблема:** Нет детальных метрик производительности

**Решение:**
```python
import time
from typing import Dict, List

class VictoriaAgent(BaseAgent):
    def __init__(self, ...):
        # ... существующий код ...
        self.metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "avg_execution_time": 0.0,
            "cache_hits": 0,
            "expert_selections": {}
        }
    
    async def run(self, goal: str, max_steps: int = 30) -> str:
        start_time = time.time()
        
        try:
            result = await super().run(goal, max_steps)
            
            # Метрики
            execution_time = time.time() - start_time
            self.metrics["tasks_completed"] += 1
            self.metrics["avg_execution_time"] = (
                (self.metrics["avg_execution_time"] * (self.metrics["tasks_completed"] - 1) + execution_time) 
                / self.metrics["tasks_completed"]
            )
            
            # Экспорт метрик в Prometheus
            self._export_metrics(execution_time, "success")
            
            return result
        except Exception as e:
            self.metrics["tasks_failed"] += 1
            self._export_metrics(time.time() - start_time, "error")
            raise
    
    def _export_metrics(self, execution_time: float, status: str):
        """Экспорт метрик в Prometheus"""
        # Использовать существующий metrics_exporter
        from knowledge_os.app.metrics_exporter import get_metrics_exporter
        exporter = get_metrics_exporter()
        exporter.record_victoria_task(
            execution_time=execution_time,
            status=status
        )
```

**Преимущества:**
- ✅ Детальная аналитика производительности
- ✅ Интеграция с Prometheus/Grafana
- ✅ Выявление узких мест

---

### 6. 🧠 ОБУЧЕНИЕ И АДАПТАЦИЯ

**Проблема:** Victoria не накапливает опыт из выполненных задач

**Решение:**
```python
async def run(self, goal: str, max_steps: int = 30) -> str:
    # ... выполнение задачи ...
    
    # После успешного выполнения
    if result and "ошибка" not in result.lower():
        # Сохранить в Knowledge OS
        await self._learn_from_task(goal, result)
    
    return result

async def _learn_from_task(self, goal: str, result: str):
    """Обучение на основе выполненной задачи"""
    # Извлечь знания из результата
    knowledge = {
        "task": goal,
        "solution": result,
        "timestamp": datetime.now(timezone.utc),
        "expert": "Виктория"
    }
    
    # Сохранить в Knowledge OS
    self.db.add_knowledge_node(
        domain="victoria_tasks",
        knowledge=knowledge,
        source="victoria_agent"
    )
    
    # Обновить базу знаний эксперта
    self.db.update_expert_knowledge("Виктория", knowledge)
```

**Преимущества:**
- ✅ Постоянное улучшение на основе опыта
- ✅ Накопление знаний в базе
- ✅ Адаптация к новым задачам

---

### 7. 🎯 ИНТЕГРАЦИЯ С SINGULARITY КОМПОНЕНТАМИ

**Проблема:** Victoria не использует компоненты Singularity (AI Core, Orchestrator, Curiosity Engine)

**Решение:**
```python
from knowledge_os.app.ai_core import run_smart_agent_async
from knowledge_os.app.curiosity_engine import CuriosityEngine

class VictoriaAgent(BaseAgent):
    def __init__(self, ...):
        # ... существующий код ...
        
        # Интеграция с Singularity
        self.curiosity_engine = CuriosityEngine()
        self.use_singularity = os.getenv("USE_SINGULARITY", "true").lower() == "true"
    
    async def run(self, goal: str, max_steps: int = 30) -> str:
        if self.use_singularity:
            # Использовать AI Core для интеллектуального роутинга
            result = await run_smart_agent_async(
                prompt=goal,
                expert_name="Виктория",
                category=self._categorize_task(goal),
                require_cot=True,  # Chain of Thought
                is_critical=True
            )
            return result
        else:
            # Существующий код
            return await super().run(goal, max_steps)
    
    async def scan_for_gaps(self):
        """Использовать Curiosity Engine для поиска пробелов в знаниях"""
        gaps = await self.curiosity_engine.scan_for_gaps()
        if gaps:
            logger.info(f"🔍 Найдены пробелы в знаниях: {len(gaps)}")
            # Создать исследовательские задачи
            for gap in gaps:
                await self._create_research_task(gap)
```

**Преимущества:**
- ✅ Использование всей мощи Singularity
- ✅ Интеллектуальный роутинг через AI Core
- ✅ Автоматическое исследование пробелов

---

### 8. 🔀 СТРИМИНГ ОТВЕТОВ

**Проблема:** Нет стриминга для длинных задач

**Решение:**
```python
from fastapi.responses import StreamingResponse

@app.post("/run/stream")
async def run_task_stream(request: TaskRequest):
    """Стриминг выполнения задачи"""
    async def generate():
        async for chunk in agent.run_stream(request.goal, max_steps=request.max_steps):
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

async def run_stream(self, goal: str, max_steps: int = 30):
    """Стриминг выполнения задачи"""
    # ... планирование ...
    
    # Стриминг выполнения
    async for step_result in self.executor.ask_stream(enhanced, history=self.memory):
        yield step_result
```

**Преимущества:**
- ✅ Мгновенная обратная связь для пользователя
- ✅ Лучший UX для длинных задач
- ✅ Возможность прервать выполнение

---

## 📋 ПРИОРИТИЗАЦИЯ УЛУЧШЕНИЙ

### 🔴 Критичные (высокий приоритет):
1. **Интеграция с Knowledge OS** — доступ к базе знаний
2. **Автоматический выбор экспертов** — использование команды
3. **Кэширование** — экономия ресурсов

### 🟡 Важные (средний приоритет):
4. **Улучшенная обработка ошибок** — надежность
5. **Метрики и мониторинг** — аналитика
6. **Стриминг ответов** — UX

### 🟢 Продвинутые (низкий приоритет):
7. **Обучение и адаптация** — накопление опыта
8. **Интеграция с Singularity** — использование всех компонентов

---

## 🎯 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

### Производительность:
- ✅ Ускорение ответов на 30-50% (кэширование)
- ✅ Повышение точности на 20-40% (эксперты)
- ✅ Снижение ошибок на 50-70% (retry логика)

### Функциональность:
- ✅ Доступ к 50,926 знаний
- ✅ Использование 40+ экспертов
- ✅ Автоматическое обучение

### Надежность:
- ✅ Автоматические retry
- ✅ Fallback механизмы
- ✅ Детальный мониторинг

---

## ✅ ПЛАН РЕАЛИЗАЦИИ

### Этап 1: Базовая интеграция (1-2 дня)
- [ ] Интеграция с Knowledge OS Database
- [ ] Загрузка команды экспертов
- [ ] Базовое кэширование

### Этап 2: Интеллектуальные функции (2-3 дня)
- [ ] Автоматический выбор экспертов
- [ ] Интеграция с AI Core
- [ ] Улучшенная обработка ошибок

### Этап 3: Мониторинг и оптимизация (1-2 дня)
- [ ] Метрики и экспорт в Prometheus
- [ ] Стриминг ответов
- [ ] Обучение и адаптация

---

## 📝 ИТОГ

**Victoria может стать значительно мощнее:**
- ✅ Использование всей базы знаний корпорации
- ✅ Автоматический выбор экспертов для задач
- ✅ Кэширование и оптимизация
- ✅ Надежность и мониторинг
- ✅ Постоянное обучение

**Следующий шаг:** Начать с интеграции Knowledge OS и выбора экспертов — это даст максимальный эффект!

---

*План создан 2026-01-25*
