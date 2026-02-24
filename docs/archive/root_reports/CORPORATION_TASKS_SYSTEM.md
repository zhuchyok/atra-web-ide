# 📋 СИСТЕМА ЗАДАЧ КОРПОРАЦИИ ATRA

**Дата:** 2026-01-26  
**Статус:** ✅ **ПОЛНАЯ СИСТЕМА РАБОТАЕТ**

---

## 🎯 ОБЗОР

Корпорация ATRA имеет полноценную систему управления задачами:

- ✅ **Создание задач** - из разных источников
- ✅ **Обсуждение задач** - через дебаты экспертов
- ✅ **Обработка задач** - через Smart Worker
- ✅ **Закрытие задач** - автоматическое и ручное

---

## 📊 ТЕКУЩАЯ СТАТИСТИКА

### Статусы задач:

- **Pending:** 14,311+ задач (84.70%)
- **Completed:** 2,533+ задачи (14.92%)
- **In Progress:** 61 задача (0.36%)
- **Failed:** 3 задачи (0.02%)

### Производительность:

- **Скорость обработки:** ~3.4 задачи/минуту
- **Создано за 5 минут:** 5 задач (Enhanced Orchestrator)
- **Завершено за час:** 206 задач

---

## ✅ СОЗДАНИЕ ЗАДАЧ

### Источники задач:

#### 1. **Enhanced Orchestrator** ✅

- **Частота:** Каждые 5 минут
- **Функции:**
  - Распределяет задачи по экспертам
  - Балансирует нагрузку
  - Создает задачи для "голодных" доменов
- **Файл:** `knowledge_os/app/enhanced_orchestrator.py`

#### 2. **Curiosity Engine** ✅

- **Частота:** Каждые 6 часов
- **Функции:**
  - Находит "голодные" домены
  - Создает исследовательские задачи
  - Автономный рекрутинг экспертов
- **Файл:** `knowledge_os/app/curiosity_engine.py`

#### 3. **Debate Processor** ✅

- **Триггер:** После дебатов экспертов
- **Условие:** consensus_score >= 0.5
- **Функции:**
  - Создает задачи из консенсуса экспертов
  - Приоритизирует на основе consensus_score
  - Назначает эксперта для внедрения
- **Файл:** `knowledge_os/app/debate_processor.py`
- **Метод:** `create_task_from_debate()`

#### 4. **Nightly Learner** ✅

- **Частота:** Ежедневно в 6:00 MSK
- **Функции:**
  - Обучение на основе опыта
  - Обновление экспертов
  - Эволюция знаний
- **Файл:** `knowledge_os/app/nightly_learner.py`

#### 5. **Пользователи** ✅

- **Через API:** REST API endpoints
- **Через Telegram:** Telegram Gateway
- **Файл:** `knowledge_os/app/telegram_gateway.py`
- **Метод:** `create_corporate_task()`

### Структура задачи в БД:

```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, in_progress, completed, failed, cancelled
    priority VARCHAR(20) DEFAULT 'medium',  -- urgent, high, medium, low
    assignee_expert_id UUID REFERENCES experts(id),
    creator_expert_id UUID REFERENCES experts(id),
    domain_id UUID REFERENCES domains(id),
    metadata JSONB DEFAULT '{}',
    result TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    estimated_duration_minutes INTEGER,
    actual_duration_minutes INTEGER
);
```

---

## 💬 ОБСУЖДЕНИЕ ЗАДАЧ

### Система дебатов экспертов:

#### 1. **Expert Council** ✅

- **Механизм:** Обсуждение между экспертами
- **Участники:** 2-3 эксперта из разных департаментов
- **Файл:** `knowledge_os/app/nightly_learner.py`
- **Метод:** `run_expert_council()`

#### 2. **Debate Processor** ✅

- **Анализ консенсуса:** consensus_score (0-1)
- **Приоритеты:**
  - urgent: >= 0.9
  - high: >= 0.75
  - medium: >= 0.6
  - low: >= 0.4
- **Создание задач:** При consensus_score >= 0.5
- **Файл:** `knowledge_os/app/debate_processor.py`
- **Методы:**
  - `analyze_debate_consensus()` - анализ консенсуса
  - `create_task_from_debate()` - создание задачи
  - `prioritize_knowledge_from_debate()` - приоритизация знаний

#### 3. **Expert Council Discussion** ✅ (НОВОЕ)

- **Механизм:** Обсуждение новых практик с 58 экспертами
- **Файл:** `knowledge_os/app/expert_council_discussion.py`
- **Методы:**
  - `conduct_discussion()` - проведение обсуждения
  - `generate_hypotheses()` - генерация гипотез
  - `save_hypotheses()` - сохранение гипотез

### Процесс обсуждения:

1. **Инициация дебата:**
   - Nightly Learner создает дебат при новом знании
   - Выбирает 2 случайных эксперта из других департаментов

2. **Обсуждение:**
   - Каждый эксперт дает свою оценку
   - Формируется consensus_summary

3. **Анализ:**
   - Debate Processor анализирует консенсус
   - Вычисляет consensus_score
   - Определяет приоритет

4. **Создание задачи:**
   - Если consensus_score >= 0.5 → создается задача
   - Назначается эксперт для внедрения
   - Приоритет на основе consensus_score

---

## ⚙️ ОБРАБОТКА ЗАДАЧ

### Smart Worker (автономный обработчик):

#### 1. **Smart Worker Autonomous** ✅

- **Режим:** Автономная обработка
- **Файл:** `knowledge_os/app/smart_worker_autonomous.py`
- **Функции:**
  - Берет задачи со статусом 'pending'
  - Обновляет статус на 'in_progress'
  - Обрабатывает через эксперта
  - Обновляет статус на 'completed' или 'failed'

#### 2. **Smart Worker v3.0** ✅

- **Режим:** Параллельная обработка
- **Скорость:** ~3.4 задачи/минуту
- **Файл:** `knowledge_os/app/smart_worker_v3.py`

#### 3. **Smart Worker v4.0 (PARALLEL)** ✅

- **Режим:** Параллельная обработка (10 задач одновременно)
- **Скорость:** ~30 задач/минуту (10x ускорение)
- **Файл:** `knowledge_os/app/smart_worker_v3_1.py`

### Процесс обработки:

1. **Выбор задачи:**

   ```sql
   SELECT * FROM tasks
   WHERE status = 'pending'
   ORDER BY priority DESC, created_at ASC
   LIMIT 10
   ```

2. **Обновление статуса:**

   ```sql
   UPDATE tasks
   SET status = 'in_progress',
       started_at = NOW(),
       updated_at = NOW()
   WHERE id = $1
   ```

3. **Обработка:**
   - Получает конфигурацию эксперта
   - Формирует промпт с задачей
   - Вызывает агента через `run_smart_agent_async()`
   - Таймаут: 5 минут

4. **Завершение:**
   - Сохраняет результат
   - Обновляет статус на 'completed' или 'failed'
   - Записывает `completed_at` и `actual_duration_minutes`

---

## ✅ ЗАКРЫТИЕ ЗАДАЧ

### Автоматическое закрытие:

#### 1. **При успешной обработке** ✅

```python
# В smart_worker_autonomous.py
await pool.execute("""
    UPDATE tasks
    SET status = 'completed',
        result = $2,
        completed_at = NOW(),
        actual_duration_minutes = EXTRACT(EPOCH FROM (NOW() - started_at)) / 60,
        updated_at = NOW()
    WHERE id = $1
""", task_id, report)
```

#### 2. **При ошибке** ✅

```python
await pool.execute("""
    UPDATE tasks
    SET status = 'failed',
        result = $2,
        updated_at = NOW()
    WHERE id = $1
""", task_id, error_message)
```

#### 3. **Через Task Prioritizer** ✅

- **Файл:** `knowledge_os/app/task_prioritizer.py`
- **Метод:** `complete_task(task_id, success=True)`
- **Функции:**
  - Обновляет статус на COMPLETED или FAILED
  - Уменьшает нагрузку агента
  - Обновляет в БД

### Ручное закрытие:

#### Через API:

```python
# Обновление статуса задачи
UPDATE tasks
SET status = 'completed',
    completed_at = NOW()
WHERE id = $1
```

#### Через Telegram:

- Команды для управления задачами
- Статус обновляется через Telegram Gateway

---

## 📊 МЕТРИКИ И СТАТИСТИКА

### Текущие метрики:

- **Всего задач:** 16,908+
- **Pending:** 14,311 (84.70%)
- **Completed:** 2,533 (14.92%)
- **In Progress:** 61 (0.36%)
- **Failed:** 3 (0.02%)

### Производительность:

- **Скорость обработки:** ~3.4 задачи/минуту
- **Скорость создания:** ~5 задач/5 минут
- **Баланс:** Создание > Обработка (накапливаются задачи)

### Проблемы:

- ⚠️ **Накопление задач:** 84.70% в pending
- ⚠️ **Низкая скорость обработки:** 3.4/минуту vs создание
- ⚠️ **Недостаточно workers:** Нужно больше параллельных обработчиков

---

## 🔧 РЕКОМЕНДАЦИИ

### 1. Увеличить количество workers

- Запустить больше экземпляров Smart Worker
- Использовать Smart Worker v4.0 (PARALLEL) - 10x ускорение

### 2. Оптимизировать приоритизацию

- Фокусироваться на urgent и high приоритетах
- Отложить low приоритеты

### 3. Улучшить баланс

- Снизить скорость создания задач
- Или увеличить скорость обработки

### 4. Автоматическая архивация

- Архивировать старые completed задачи
- Очищать failed задачи после анализа

---

## 📝 ДОКУМЕНТАЦИЯ

### Основные файлы:

- `knowledge_os/app/debate_processor.py` - обработка дебатов и создание задач
- `knowledge_os/app/smart_worker_autonomous.py` - автономная обработка задач
- `knowledge_os/app/enhanced_orchestrator.py` - оркестрация и создание задач
- `knowledge_os/app/task_prioritizer.py` - приоритизация и закрытие задач
- `knowledge_os/app/expert_council_discussion.py` - обсуждение с экспертами

### Документы:

- `docs/mac-studio/TASKS_ANALYSIS.md` - анализ задач
- `docs/mac-studio/CORPORATION_WORK_STATUS.md` - статус работы корпорации

---

## ✅ ИТОГИ

**Система задач корпорации ATRA полностью функциональна:**

- ✅ **Создание:** 5 источников задач работают
- ✅ **Обсуждение:** Дебаты экспертов → консенсус → задачи
- ✅ **Обработка:** Smart Worker обрабатывает задачи
- ✅ **Закрытие:** Автоматическое и ручное закрытие работает

**Требуется оптимизация:**

- ⚠️ Увеличить скорость обработки
- ⚠️ Улучшить баланс создание/обработка
- ⚠️ Оптимизировать приоритизацию

---

_Документ создан: 2026-01-26_
