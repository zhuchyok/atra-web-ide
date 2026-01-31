# 🚀 Реализация улучшений Victoria Agent

**Дата:** 2026-01-25  
**Статус:** 📋 **ПЛАН РЕАЛИЗАЦИИ**

---

## 🎯 СТРАТЕГИЯ РЕАЛИЗАЦИИ

### Принцип: Постепенная интеграция с минимальными изменениями

**Подход:**
1. ✅ Сохранить существующую функциональность
2. ✅ Добавить новые возможности опционально (через env vars)
3. ✅ Обеспечить обратную совместимость
4. ✅ Тестировать каждый этап

---

## 📋 ЭТАП 1: ИНТЕГРАЦИЯ С KNOWLEDGE OS (Приоритет 1)

### Цель: Подключить Victoria к базе знаний (50,926 знаний, 58 экспертов)

### Шаг 1.1: Добавить зависимость от Knowledge OS Database

**Файл:** `src/agents/bridge/victoria_server.py`

```python
# Добавить в начало файла
import os
from typing import Optional

# Опциональная интеграция с Knowledge OS
USE_KNOWLEDGE_OS = os.getenv("USE_KNOWLEDGE_OS", "false").lower() == "true"

if USE_KNOWLEDGE_OS:
    try:
        # Пытаемся импортировать Database из knowledge_os
        import sys
        knowledge_os_paths = [
            "/app/app",  # Путь в контейнере
            os.path.join(os.path.dirname(__file__), "../../../knowledge_os/src/database"),
            os.path.join(os.path.dirname(__file__), "../../knowledge_os/src/database"),
        ]
        db_imported = False
        for db_path in knowledge_os_paths:
            if os.path.exists(os.path.join(db_path, "db.py")):
                if db_path not in sys.path:
                    sys.path.insert(0, db_path)
                try:
                    from db import Database
                    KNOWLEDGE_OS_AVAILABLE = True
                    db_imported = True
                    logger.info("✅ Knowledge OS Database доступна")
                    break
                except Exception as e:
                    logger.warning(f"Failed to import Database from {db_path}: {e}")
        if not db_imported:
            KNOWLEDGE_OS_AVAILABLE = False
            logger.warning("Knowledge OS Database не найдена, продолжаем без неё")
    except Exception as e:
        KNOWLEDGE_OS_AVAILABLE = False
        logger.warning(f"Failed to setup Knowledge OS: {e}")
else:
    KNOWLEDGE_OS_AVAILABLE = False
```

### Шаг 1.2: Инициализация Database в VictoriaAgent

```python
class VictoriaAgent(BaseAgent):
    def __init__(self, name: str = "Виктория", model_name: str = None):
        # ... существующий код ...
        
        # Интеграция с Knowledge OS (опционально)
        self.db = None
        self.expert_team = {}
        if USE_KNOWLEDGE_OS and KNOWLEDGE_OS_AVAILABLE:
            try:
                # Инициализация Database
                db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@atra-knowledge-os-db:5432/knowledge_os")
                self.db = Database(db_url=db_url)
                logger.info("✅ Knowledge OS Database подключена")
                
                # Загрузка команды экспертов (асинхронно, при первом использовании)
                self._expert_team_loaded = False
            except Exception as e:
                logger.error(f"❌ Ошибка подключения к Knowledge OS: {e}")
                self.db = None
```

### Шаг 1.3: Метод загрузки экспертов

```python
async def _load_expert_team(self):
    """Загрузить команду экспертов из Knowledge OS"""
    if not self.db or self._expert_team_loaded:
        return
    
    try:
        # Получить всех экспертов из базы
        experts = await self.db.get_all_experts()
        self.expert_team = {expert['name']: expert for expert in experts}
        self._expert_team_loaded = True
        logger.info(f"✅ Загружено {len(self.expert_team)} экспертов из Knowledge OS")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки экспертов: {e}")
        self.expert_team = {}
```

### Шаг 1.4: Метод поиска знаний (RAG)

```python
async def _get_knowledge_context(self, goal: str, limit: int = 5) -> str:
    """Получить релевантные знания из Knowledge OS"""
    if not self.db:
        return ""
    
    try:
        # Поиск знаний по задаче
        knowledge_nodes = await self.db.search_knowledge(
            query=goal,
            limit=limit
        )
        
        if knowledge_nodes:
            context = "\n--- РЕЛЕВАНТНЫЕ ЗНАНИЯ ИЗ БАЗЫ ---\n"
            for node in knowledge_nodes:
                context += f"- {node.get('content', '')[:200]}...\n"
            return context
    except Exception as e:
        logger.warning(f"Ошибка поиска знаний: {e}")
    
    return ""
```

### Шаг 1.5: Использование знаний в планировании

```python
async def plan(self, goal: str):
    # Получить контекст из базы знаний
    knowledge_context = ""
    if USE_KNOWLEDGE_OS and self.db:
        knowledge_context = await self._get_knowledge_context(goal)
    
    plan_prompt = f"""ТЫ — ТЕХНИЧЕСКИЙ ДИРЕКТОР ATRA. Составь ПРОСТОЙ план.

{knowledge_context}

ЗАДАЧА: {goal}

КРИТИЧЕСКИ ВАЖНО:
- План должен быть МАКСИМАЛЬНО ПРОСТЫМ (1 шаг для простых задач)
- НЕ добавляй дополнительные требования
- Выполняй ТОЧНО то что просят, ничего лишнего

ПЛАН (только 1-2 шага, максимально просто):"""
    
    return await self.planner.ask(plan_prompt, raw_response=True)
```

---

## 📋 ЭТАП 2: АВТОМАТИЧЕСКИЙ ВЫБОР ЭКСПЕРТОВ (Приоритет 2)

### Шаг 2.1: Категоризация задач

```python
def _categorize_task(self, goal: str) -> str:
    """Определить категорию задачи для выбора эксперта"""
    goal_lower = goal.lower()
    
    # Категории и ключевые слова
    categories = {
        "backend": ["api", "сервер", "база данных", "postgresql", "sql", "docker"],
        "frontend": ["интерфейс", "ui", "ux", "веб", "браузер", "react", "vue"],
        "ml": ["модель", "обучение", "нейросеть", "ml", "ai", "машинное обучение"],
        "devops": ["развертывание", "deploy", "ci/cd", "мониторинг", "grafana", "prometheus"],
        "security": ["безопасность", "security", "уязвимость", "аудит"],
        "database": ["база данных", "миграция", "схема", "индекс"],
        "performance": ["производительность", "оптимизация", "скорость", "latency"],
    }
    
    for category, keywords in categories.items():
        if any(keyword in goal_lower for keyword in keywords):
            return category
    
    return "general"  # По умолчанию
```

### Шаг 2.2: Выбор эксперта для задачи

```python
async def select_expert_for_task(self, goal: str) -> tuple[Optional[str], Optional[dict]]:
    """Автоматически выбрать эксперта для задачи"""
    if not self.db or not USE_KNOWLEDGE_OS:
        return None, None
    
    try:
        # Загрузить экспертов если еще не загружены
        if not self._expert_team_loaded:
            await self._load_expert_team()
        
        # Определить категорию задачи
        category = self._categorize_task(goal)
        
        # Маппинг категорий на роли экспертов
        category_to_role = {
            "backend": "Backend Developer",
            "frontend": "Frontend Developer",
            "ml": "ML Engineer",
            "devops": "DevOps Engineer",
            "security": "Security Engineer",
            "database": "Database Engineer",
            "performance": "Performance Engineer",
            "general": "Team Lead"
        }
        
        target_role = category_to_role.get(category, "Team Lead")
        
        # Найти эксперта по роли
        for expert_name, expert_data in self.expert_team.items():
            if expert_data.get('role') == target_role:
                # Получить знания эксперта
                expert_knowledge = await self.db.get_expert_knowledge(expert_name)
                logger.info(f"✅ Выбран эксперт: {expert_name} ({target_role}) для задачи: {goal[:50]}")
                return expert_name, expert_knowledge
        
        # Если не найден, вернуть None
        return None, None
        
    except Exception as e:
        logger.error(f"❌ Ошибка выбора эксперта: {e}")
        return None, None
```

### Шаг 2.3: Использование эксперта в планировании

```python
async def plan(self, goal: str):
    # Выбрать эксперта для задачи
    expert_name = None
    expert_knowledge = None
    if USE_KNOWLEDGE_OS and self.db:
        expert_name, expert_knowledge = await self.select_expert_for_task(goal)
    
    # Получить контекст из базы знаний
    knowledge_context = ""
    if USE_KNOWLEDGE_OS and self.db:
        knowledge_context = await self._get_knowledge_context(goal)
    
    # Формировать промпт с учетом эксперта
    if expert_name and expert_knowledge:
        plan_prompt = f"""ТЫ — ВИКТОРИЯ, TEAM LEAD КОРПОРАЦИИ ATRA.

ЭКСПЕРТ ДЛЯ ЗАДАЧИ: {expert_name}
ЗНАНИЯ ЭКСПЕРТА:
{expert_knowledge.get('system_prompt', '')[:500]}...

{knowledge_context}

ЗАДАЧА: {goal}

Составь ПРОСТОЙ план (1-2 шага, максимально просто):"""
    else:
        # Существующий промпт без эксперта
        plan_prompt = f"""ТЫ — ТЕХНИЧЕСКИЙ ДИРЕКТОР ATRA. Составь ПРОСТОЙ план.

{knowledge_context}

ЗАДАЧА: {goal}

КРИТИЧЕСКИ ВАЖНО:
- План должен быть МАКСИМАЛЬНО ПРОСТЫМ (1 шаг для простых задач)
- НЕ добавляй дополнительные требования
- Выполняй ТОЧНО то что просят, ничего лишнего

ПЛАН (только 1-2 шага, максимально просто):"""
    
    return await self.planner.ask(plan_prompt, raw_response=True)
```

---

## 📋 ЭТАП 3: КЭШИРОВАНИЕ (Приоритет 3)

### Шаг 3.1: Добавить кэш задач

```python
import hashlib
from datetime import datetime, timedelta

class VictoriaAgent(BaseAgent):
    def __init__(self, name: str = "Виктория", model_name: str = None):
        # ... существующий код ...
        
        # Кэш выполненных задач
        self.task_cache = {}
        self.cache_ttl = timedelta(hours=24)  # TTL кэша
        self.use_cache = os.getenv("VICTORIA_USE_CACHE", "true").lower() == "true"
```

### Шаг 3.2: Методы работы с кэшем

```python
def _task_hash(self, goal: str) -> str:
    """Хеш задачи для кэширования"""
    # Нормализация: убрать лишние пробелы, привести к нижнему регистру
    normalized = " ".join(goal.lower().strip().split())
    return hashlib.md5(normalized.encode()).hexdigest()

def _get_cached_result(self, goal: str) -> Optional[str]:
    """Получить результат из кэша"""
    if not self.use_cache:
        return None
    
    task_hash = self._task_hash(goal)
    if task_hash in self.task_cache:
        cached_data = self.task_cache[task_hash]
        # Проверить TTL
        if datetime.now() - cached_data['timestamp'] < self.cache_ttl:
            logger.info(f"✅ Использован кэш для задачи: {goal[:50]}")
            return cached_data['result']
        else:
            # Удалить устаревший кэш
            del self.task_cache[task_hash]
    
    return None

def _save_to_cache(self, goal: str, result: str):
    """Сохранить результат в кэш"""
    if not self.use_cache:
        return
    
    task_hash = self._task_hash(goal)
    # Сохранять только успешные результаты
    if result and "ошибка" not in result.lower() and "error" not in result.lower():
        self.task_cache[task_hash] = {
            'result': result,
            'timestamp': datetime.now()
        }
        logger.debug(f"💾 Сохранено в кэш: {goal[:50]}")
```

### Шаг 3.3: Использование кэша в run()

```python
async def run(self, goal: str, max_steps: int = 30) -> str:
    # Проверка кэша
    cached_result = self._get_cached_result(goal)
    if cached_result:
        return cached_result
    
    # Простые задачи не требуют планирования
    simple_tasks = ["скажи", "привет", "покажи файлы", "выведи список", "список файлов"]
    goal_lower = goal.lower()
    
    if any(task in goal_lower for task in simple_tasks) and len(goal.split()) <= 10:
        enhanced = f"ВЫПОЛНИ ЗАДАЧУ: {goal}\n\nВАЖНО: Выполняй ТОЧНО то что просят, ничего лишнего!"
    else:
        raw_plan = await self.plan(goal)
        enhanced = f"ТВОЙ ПЛАН:\n{raw_plan}\n\nПРИСТУПАЙ К ВЫПОЛНЕНИЮ: {goal}"
    
    result = await super().run(enhanced, max_steps)
    
    # Сохранить в кэш
    self._save_to_cache(goal, result)
    
    # Сохранить в Knowledge OS для обучения (если включено)
    if USE_KNOWLEDGE_OS and self.db and result:
        await self._learn_from_task(goal, result)
    
    return result
```

---

## 📋 ЭТАП 4: ОБУЧЕНИЕ И АДАПТАЦИЯ

### Шаг 4.1: Метод обучения на основе задач

```python
async def _learn_from_task(self, goal: str, result: str):
    """Обучение на основе выполненной задачи"""
    if not self.db:
        return
    
    try:
        from datetime import datetime, timezone
        
        # Извлечь знания из результата
        knowledge = {
            "task": goal,
            "solution": result[:1000],  # Ограничить длину
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "expert": "Виктория",
            "domain": "victoria_tasks"
        }
        
        # Сохранить в Knowledge OS
        await self.db.add_knowledge_node(
            domain="victoria_tasks",
            content=result[:500],
            metadata=knowledge,
            source="victoria_agent"
        )
        
        logger.debug(f"📚 Сохранено знание из задачи: {goal[:50]}")
        
    except Exception as e:
        logger.warning(f"Ошибка сохранения знания: {e}")
```

---

## 🔧 КОНФИГУРАЦИЯ

### Environment Variables

```bash
# Включить интеграцию с Knowledge OS
USE_KNOWLEDGE_OS=true

# URL базы данных Knowledge OS
DATABASE_URL=postgresql://admin:secret@atra-knowledge-os-db:5432/knowledge_os

# Использовать кэширование
VICTORIA_USE_CACHE=true

# Модель для Victoria
VICTORIA_MODEL=qwen2.5-coder:32b

# Модель для planner
VICTORIA_PLANNER_MODEL=phi3.5:3.8b
```

### docker-compose.yml

```yaml
victoria-agent:
  # ... существующие настройки ...
  environment:
    # ... существующие env vars ...
    - USE_KNOWLEDGE_OS: "true"
    - DATABASE_URL: postgresql://admin:secret@atra-knowledge-os-db:5432/knowledge_os
    - VICTORIA_USE_CACHE: "true"
```

---

## ✅ ПЛАН ТЕСТИРОВАНИЯ

### Тест 1: Интеграция Knowledge OS
```bash
# Проверить подключение
curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "покажи список экспертов"}'
```

### Тест 2: Выбор эксперта
```bash
# Задача для backend эксперта
curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "создай API endpoint для получения данных"}'
```

### Тест 3: Кэширование
```bash
# Первый запрос
curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "скажи привет"}'

# Второй запрос (должен использовать кэш)
curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "скажи привет"}'
```

---

## 📊 МЕТРИКИ УСПЕХА

### После реализации:
- ✅ Victoria использует базу знаний (50,926 знаний)
- ✅ Автоматический выбор экспертов работает
- ✅ Кэширование ускоряет повторяющиеся задачи на 30-50%
- ✅ Знания сохраняются в Knowledge OS

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

1. **Реализовать Этап 1** (Интеграция Knowledge OS) — 1-2 часа
2. **Протестировать** подключение и поиск знаний
3. **Реализовать Этап 2** (Выбор экспертов) — 1-2 часа
4. **Реализовать Этап 3** (Кэширование) — 30 минут
5. **Протестировать** все этапы вместе

---

*План реализации создан 2026-01-25*
