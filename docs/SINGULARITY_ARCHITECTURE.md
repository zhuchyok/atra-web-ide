# SINGULARITY ARCHITECTURE v3.0+
## Полное описание архитектуры ИИ-Корпорации ATRA

> Изучено с сервера 46.149.66.170 (Knowledge OS)

---

## 🧠 ОБЩАЯ АРХИТЕКТУРА

```
┌─────────────────────────────────────────────────────────────────┐
│                    SINGULARITY CORE v3.0                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ AI CORE     │    │ ORCHESTRATOR│    │ KNOWLEDGE   │         │
│  │ (Routing)   │◄──►│ (Scheduling)│◄──►│ GRAPH       │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ LOCAL LLM   │    │ CURIOSITY   │    │ DISTILLATION│         │
│  │ (L1 Router) │    │ ENGINE      │    │ ENGINE      │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ CLOUD LLM   │    │ EXPERT      │    │ META        │         │
│  │ (L2 Fallback)   │ GENERATOR   │    │ ARCHITECT   │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 ОСНОВНЫЕ КОМПОНЕНТЫ

### 1. AI CORE (`ai_core.py`)
**Центральный модуль координации AI агентов**

```python
# Функции:
- Semantic Caching (кэширование по эмбеддингам)
- RAG (Retrieval Augmented Generation)
- Hybrid Intelligence (Local + Cloud)
- Quality Assurance
- Anomaly Detection
- Circuit Breakers
```

**Ключевые методы:**
- `run_smart_agent_async()` — умный роутинг запросов
- `_get_knowledge_context()` — RAG из базы знаний
- `_run_cloud_agent_async()` — fallback в облако

---

### 2. ORCHESTRATOR (`orchestrator.py`)
**Singularity Orchestrator v3.0 — Hierarchical + Associative**

**Фазы работы:**

#### Фаза 1: АССОЦИАТИВНЫЙ МОЗГ
```python
# Cross-Domain Linking
- Находит новые знания за последние 6 часов
- Случайно выбирает знание из ДРУГОГО домена
- Генерирует "Synthetic Hypothesis" на стыке знаний
- Публикует в Redis Stream для реакции других агентов
```

#### Фаза 2: ДВИГАТЕЛЬ ЛЮБОПЫТСТВА
```python
# Curiosity Engine
- Ищет "интеллектуальные пустыни" (домены < 50 знаний)
- Автоматически рекрутирует экспертов если нет
- Создаёт исследовательские задачи
```

---

### 3. CURIOSITY ENGINE (`curiosity_engine.py`)
**Сканирование рабочего пространства на пробелы в знаниях**

```python
class CuriosityEngine:
    async def scan_for_gaps():
        # 1. Сканирует Python файлы
        # 2. Извлекает imports и TODOs
        # 3. Сравнивает с knowledge_nodes
        # 4. Создаёт исследовательские задачи
```

---

### 4. EXPERT GENERATOR (`expert_generator.py`)
**Автономный рекрутинг экспертов**

```python
async def recruit_expert(domain_name: str):
    # 1. Анализирует лучшие мировые практики
    # 2. Генерирует: имя, роль, system_prompt
    # 3. Сохраняет в БД experts
    # 4. Создаёт приветственное знание
```

**Пример генерации:**
```json
{
  "name": "Натан",
  "role": "Director of Competitive Intelligence",
  "system_prompt": "Ты — Натан, Director of Competitive Intelligence...",
  "department": "Marketing & Growth"
}
```

---

### 5. SWARM ORCHESTRATOR (`swarm_orchestrator.py`)
**War-Room для критических решений**

```python
class SwarmOrchestrator:
    async def get_war_room_experts(limit=5):
        # Выбирает экспертов: Engineers, Managers, Analysts
        # Fallback: Дмитрий, Мария, Максим
    
    async def handle_critical_failures():
        # Координирует несколько экспертов для консенсуса
```

---

### 6. INTELLIGENCE CONSENSUS (`intelligence_consensus.py`)
**Консенсус Local + Cloud моделей**

```python
class IntelligenceConsensus:
    async def get_consensus(prompt, expert_name):
        # 1. Запускает Local (L1) модель
        # 2. Запускает Cloud (L2) модель
        # 3. Сравнивает ответы
        # 4. Генерирует финальный ответ
```

---

### 7. META ARCHITECT (`meta_architect.py`)
**Автономный самовосстановитель кода**

```python
class MetaArchitect:
    async def self_repair_cycle():
        # 1. Находит задачи типа "🚨 АВТО-РЕМОНТ"
        # 2. Анализирует ошибку
        # 3. Читает файл
        # 4. Генерирует исправление
        # 5. Применяет патч
```

---

### 8. KNOWLEDGE GRAPH (`knowledge_graph.py`)
**Граф связей между знаниями**

```python
class LinkType(Enum):
    DEPENDS_ON = "depends_on"      # Зависит от
    CONTRADICTS = "contradicts"    # Противоречит
    ENHANCES = "enhances"          # Улучшает
    RELATED_TO = "related_to"      # Связано с
    SUPERSEDES = "supersedes"      # Заменяет
    PART_OF = "part_of"            # Является частью
```

---

### 9. DISTILLATION ENGINE (`distillation_engine.py`)
**Knowledge Distillation — обучение локальных моделей**

```python
class KnowledgeDistiller:
    async def collect_high_quality_samples(days=7):
        # 1. Собирает успешные взаимодействия
        # 2. Собирает завершённые задачи экспертов
        # 3. Сохраняет в distillation_dataset.jsonl
        # 4. Используется для fine-tuning локальных моделей
```

---

### 10. SMART WORKER (`worker.py`)
**Автономный исполнитель задач**

```python
async def process_task(task):
    # 1. Берёт pending задачу
    # 2. Обновляет статус на in_progress
    # 3. Выполняет работу (эксперт)
    # 4. Сохраняет результат
    # 5. Логирует в knowledge_nodes
```

---

## 📊 БАЗА ДАННЫХ (PostgreSQL)

### Основные таблицы (26):

| Таблица | Назначение |
|---------|------------|
| `experts` | 58 экспертов с ролями и промптами |
| `knowledge_nodes` | 50,926 узлов знаний с эмбеддингами |
| `domains` | 35 доменов знаний |
| `tasks` | Задачи для экспертов |
| `interaction_logs` | Логи взаимодействий |
| `knowledge_links` | Связи между узлами |
| `semantic_ai_cache` | Семантический кэш |
| `expert_learning_logs` | Логи обучения экспертов |

---

## 🔄 ЖИЗНЕННЫЙ ЦИКЛ КОРПОРАЦИИ

### 1. Утренний цикл
```
06:00 → ORCHESTRATOR запускается
     → Собирает новые знания за 6 часов
     → Создаёт Cross-Domain гипотезы
     → Ищет интеллектуальные пустыни
     → Рекрутирует новых экспертов
     → Создаёт исследовательские задачи
```

### 2. Рабочий день
```
WORKER непрерывно:
     → Берёт pending задачи
     → Назначает экспертам
     → Выполняет исследования
     → Сохраняет результаты в knowledge_nodes
```

### 3. Ночной цикл
```
02:00 → DISTILLATION ENGINE
     → Собирает качественные ответы
     → Формирует датасет для обучения
     → Готовит fine-tuning локальных моделей
```

---

## 🌐 ROUTING STRATEGY

```
Запрос пользователя
        │
        ▼
┌───────────────────┐
│ SEMANTIC CACHE    │ ─── HIT ──► Возврат из кэша
└───────────────────┘
        │ MISS
        ▼
┌───────────────────┐
│ LOCAL ROUTER (L1) │ ─── Категории: coding, reasoning, fast
└───────────────────┘
        │
   ┌────┴────┐
   │         │
   ▼         ▼
┌─────┐   ┌─────┐
│ MLX │   │Ollama│  (Local LLMs)
└─────┘   └─────┘
        │
        │ FAIL / CRITICAL
        ▼
┌───────────────────┐
│ CLOUD (L2)        │ ─── Cursor Agent / OpenAI
└───────────────────┘
        │
        │ is_critical=True
        ▼
┌───────────────────┐
│ CONSENSUS         │ ─── Local + Cloud сравнение
└───────────────────┘
```

---

## 🛡️ БЕЗОПАСНОСТЬ И КАЧЕСТВО

### Circuit Breakers
- Защита от каскадных отказов
- Автоматическое переключение на fallback

### Quality Assurance
- Проверка ответов перед отправкой
- Детекция аномалий

### Self-Healing
- MetaArchitect автоматически исправляет ошибки
- Логирование и мониторинг

---

## 📁 ФАЙЛЫ СИСТЕМЫ

| Файл | Описание |
|------|----------|
| `ai_core.py` | Центральный модуль координации |
| `orchestrator.py` | Singularity Orchestrator v3.0 |
| `enhanced_orchestrator.py` | Расширенный оркестратор |
| `curiosity_engine.py` | Поиск пробелов в знаниях |
| `expert_generator.py` | Автономный рекрутинг |
| `swarm_orchestrator.py` | War-Room консенсус |
| `intelligence_consensus.py` | Local + Cloud консенсус |
| `meta_architect.py` | Самовосстановление кода |
| `knowledge_graph.py` | Граф знаний |
| `distillation_engine.py` | Knowledge Distillation |
| `worker.py` | Smart Worker |
| `local_router.py` | Роутер локальных моделей |
| `semantic_cache.py` | Семантический кэш |

---

## 🚀 ЗАПУСК

```bash
# Orchestrator (каждые 6 часов)
python knowledge_os/app/orchestrator.py

# Worker (постоянно)
python knowledge_os/app/worker.py

# Curiosity Engine (по расписанию)
python knowledge_os/app/curiosity_engine.py

# MCP Server
python knowledge_os/app/main.py
```

---

*Документация создана на основе анализа сервера 46.149.66.170 (Knowledge OS)*
*Дата: 25.01.2026*
