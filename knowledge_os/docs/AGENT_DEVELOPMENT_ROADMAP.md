# 🚀 План развития агентов на основе Day_1_v4

**Дата создания:** 2025-11-13  
**Статус:** 🟡 В разработке  
**Основа:** Документ `Day_1_v4 ru (1).pdf`

---

## 📋 Текущий статус

### ✅ Что уже реализовано:

1. **Think/Act/Observe цикл**
   - ✅ Единый трейс-лог `logs/agent_traces.log`
   - ✅ Инструментированы: `signal_live`, `auto_execution`, `risk_monitor`
   - ✅ Модуль `observability.tracing`

2. **Guidance System (Lessons Learned)**
   - ✅ `configs/guidance/<agent>.json` - хранение уроков
   - ✅ `configs/prompts/<agent>.yaml` - экспорт в YAML
   - ✅ `docs/guidance/<agent>.md` - документация
   - ✅ Автоматическое применение через `scripts/process_feedback.py`

3. **LM-Judge**
   - ✅ Rule-based judge в `observability/lm_judge.py`
   - ✅ Вердикты для сигналов, исполнения, защиты
   - ✅ Интеграция в Telegram сообщения

4. **Agent Identity**
   - ✅ `configs/agent_identity.json` - матрица прав
   - ✅ `observability.agent_identity` - контроль доступа
   - ✅ `docs/agent_identity_matrix.md` - документация

5. **Agent Gym**
   - ✅ Симуляции в `agent_gym/scenarios.py`
   - ✅ Конфигурация через JSON
   - ✅ Nightly runs с baseline сравнением

6. **Автоматический анализ сделок**
   - ✅ `observability.auto_analyzer` - анализ закрытых сделок
   - ✅ Генерация lessons из паттернов успеха/неудачи

---

## 🎯 Что нужно доработать (из Day_1_v4)

### 1. Централизованная система промптов

**Проблема:** Промпты разбросаны по коду, сложно аудировать и обновлять.

**Решение:**

- [ ] Создать `configs/agents/<agent>.yaml` для каждого агента
- [ ] Вынести все промпты из кода в YAML файлы
- [ ] Создать `observability/prompt_manager.py` для загрузки промптов
- [ ] Интегрировать загрузку промптов в агенты

**Структура YAML:**

```yaml
agent: signal_live
version: 1.0
description: "Генератор торговых сигналов"

system_prompt: |
  Ты - эксперт по алгоритмической торговле на криптовалютном рынке.
  Твоя задача - анализировать рыночные данные и генерировать точные торговые сигналы.

instructions:
  - "Анализируй индикаторы: RSI, MACD, EMA, Bollinger Bands"
  - "Проверяй BTC тренд перед генерацией сигнала"
  - "Используй AI оптимизатор для расчета TP/SL"

context_sources:
  - "trading.db:signals_log"
  - "trading.db:accepted_signals"
  - "ai_learning_data:trading_patterns.json"

tools:
  - "data_sources_manager"
  - "ai_integration"
  - "correlation_manager"

examples:
  - input: "RSI=45, MACD=бычий, BTC=бычий"
    output: "LONG сигнал с confidence=75%"
```

**Файлы для создания:**

- `configs/agents/signal_live.yaml`
- `configs/agents/auto_execution.yaml`
- `configs/agents/risk_monitor.yaml`
- `observability/prompt_manager.py`

---

### 2. Context Engineering (улучшение) ✅ **ВЫПОЛНЕНО**

**Проблема:** Агенты не всегда используют релевантный контекст.

**Решение:**

- [x] Создать `observability/context_engine.py` ✅
- [x] Реализовать умный выбор контекста на основе:
  - Текущей миссии агента ✅
  - Истории действий ✅
  - Релевантности данных ✅
- [x] Добавить кэширование контекста ✅
- [x] Интегрировать в существующие агенты ✅

**Функции:**

```python
class ContextEngine:
    def select_context(self, agent: str, mission: str, history: List[Trace]) -> Dict:
        """Выбирает релевантный контекст для агента"""

    def enrich_context(self, base_context: Dict, additional_sources: List[str]) -> Dict:
        """Обогащает контекст дополнительными источниками"""

    def cache_context(self, key: str, context: Dict, ttl: int = 3600):
        """Кэширует контекст для повторного использования"""
```

---

### 3. Расширение Agent Ops ✅ **ВЫПОЛНЕНО**

**Проблема:** Недостаточно метрик и мониторинга для агентов.

**Решение:**

- [x] Создать Prometheus метрики для каждого агента ✅
  - `agent_missions_total` - общее количество миссий ✅
  - `agent_missions_success_total` - успешные миссии ✅
  - `agent_missions_failed_total` - неудачные миссии ✅
  - `agent_think_duration_seconds` - время на этап Think ✅
  - `agent_act_duration_seconds` - время на этап Act ✅
  - `agent_observe_duration_seconds` - время на этап Observe ✅
  - `agent_mission_duration_seconds` - общее время миссии ✅
  - `agent_guidance_applied` - количество примененных уроков ✅
  - `agent_prompt_loaded_total` - количество загрузок промптов ✅
  - `agent_context_selected_total` - количество выборов контекста ✅
- [ ] Создать Grafana дашборд для визуализации (следующий шаг)
- [ ] Добавить алерты на аномалии в поведении агентов (следующий шаг)
- [x] Интегрировать в `risk_monitor` ✅

**Метрики:**

```python
# observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge

agent_missions_total = Counter(
    'agent_missions_total',
    'Total number of agent missions',
    ['agent', 'mission', 'status']
)

agent_step_duration = Histogram(
    'agent_step_duration_seconds',
    'Duration of agent steps',
    ['agent', 'step']
)

agent_guidance_applied = Gauge(
    'agent_guidance_applied',
    'Number of guidance lessons applied',
    ['agent', 'issue']
)
```

---

### 4. Улучшение HITL (Human-in-the-Loop) ✅ **ВЫПОЛНЕНО**

**Проблема:** HITL feedback убран из Telegram, но нужен для обучения.

**Решение:**

- [x] Восстановить автоматический сбор feedback через анализ сделок ✅
- [x] Добавить неявный feedback (через анализ результатов) ✅
  - Если сделка прибыльная → позитивный feedback ✅
  - Если сделка убыточная → негативный feedback ✅
- [x] Создать `observability/implicit_feedback.py` ✅
- [x] Интегрировать в `FeedbackAggregator` и `process_feedback.py` ✅

**Логика:**

```python
class ImplicitFeedbackCollector:
    def collect_from_trade(self, trade: TradeResult) -> Feedback:
        """Собирает неявный feedback из результата сделки"""
        if trade.pnl > 0:
            return Feedback(
                type="positive",
                signal_key=trade.signal_key,
                reason="profitable_trade"
            )
        else:
            return Feedback(
                type="negative",
                signal_key=trade.signal_key,
                reason="unprofitable_trade"
            )
```

---

### 5. Многоагентная координация (L3-L4) ✅ **ВЫПОЛНЕНО**

**Проблема:** Агенты работают изолированно, нет координации.

**Решение:**

- [x] Создать `observability/agent_coordinator.py` ✅
- [x] Реализовать обмен контекстом между агентами ✅
  - `signal_live` → `auto_execution` (сигналы) ✅
  - `auto_execution` → `risk_monitor` (статус позиций) ✅
  - `risk_monitor` → `signal_live` (блокировки) ✅
- [x] Добавить shared memory для координации ✅
- [x] Реализовать event-driven архитектуру ✅

**Архитектура:**

```python
class AgentCoordinator:
    def __init__(self):
        self.shared_memory = SharedMemory()
        self.event_bus = EventBus()

    def register_agent(self, agent: str, capabilities: List[str]):
        """Регистрирует агента и его возможности"""

    def coordinate(self, event: Event) -> List[Action]:
        """Координирует действия агентов на основе события"""
```

---

### 6. Self-Evolving System (L4) ✅ **ВЫПОЛНЕНО**

**Проблема:** Система не может самостоятельно эволюционировать.

**Решение:**

- [x] Создать `observability/evolution_engine.py` ✅
- [x] Реализовать автоматическое улучшение промптов ✅
  - Анализ эффективности текущих промптов ✅
  - Генерация вариантов улучшений ✅
  - Оценка и сравнение вариантов ✅
  - Применение лучших вариантов ✅
- [x] Интегрировать с Guidance System ✅
- [ ] A/B тестирование новых промптов (готово к расширению)

**Процесс:**

```python
class EvolutionEngine:
    def evolve_prompt(self, agent: str, current_prompt: str) -> str:
        """Эволюционирует промпт на основе lessons learned"""
        lessons = get_guidance(agent)
        improved = self.generate_variants(current_prompt, lessons)
        best = self.test_variants(improved)
        return best
```

---

## 📅 План реализации

### Фаза 1: Централизация промптов (1-2 дня)

1. Создать `configs/agents/` структуру
2. Вынести промпты из кода в YAML
3. Создать `prompt_manager.py`
4. Интегрировать в агенты

### Фаза 2: Context Engineering (2-3 дня)

1. Создать `context_engine.py`
2. Реализовать умный выбор контекста
3. Добавить кэширование
4. Интегрировать в агенты

### Фаза 3: Agent Ops расширение (2-3 дня)

1. Создать Prometheus метрики
2. Настроить Grafana дашборд
3. Добавить алерты
4. Интегрировать в мониторинг

### Фаза 4: HITL улучшение (1-2 дня)

1. Создать `implicit_feedback.py`
2. Интегрировать в `auto_analyzer.py`
3. Обновить `feedback.py` для обработки неявного feedback

### Фаза 5: Многоагентная координация (3-4 дня)

1. Создать `agent_coordinator.py`
2. Реализовать shared memory
3. Реализовать event bus
4. Интегрировать координацию

### Фаза 6: Self-Evolving System (4-5 дней)

1. Создать `evolution_engine.py`
2. Реализовать генерацию вариантов промптов
3. Реализовать A/B тестирование
4. Интегрировать с Guidance System

---

## 🎯 Критерии успеха

### Фаза 1:

- ✅ Все промпты вынесены в YAML
- ✅ Агенты загружают промпты через `prompt_manager`
- ✅ Нет hardcoded промптов в коде

### Фаза 2:

- ✅ Агенты используют релевантный контекст
- ✅ Кэширование работает
- ✅ Улучшение качества решений на 10%+

### Фаза 3:

- ✅ Все метрики в Prometheus
- ✅ Дашборд в Grafana
- ✅ Алерты работают

### Фаза 4:

- ✅ Неявный feedback собирается автоматически
- ✅ Lessons генерируются из feedback
- ✅ Улучшение accuracy на 5%+

### Фаза 5:

- ✅ Агенты координируются
- ✅ Shared memory работает
- ✅ Event bus функционирует

### Фаза 6:

- ✅ Промпты эволюционируют автоматически
- ✅ A/B тестирование работает
- ✅ Улучшение производительности на 15%+

---

## 📚 Ссылки

- [Day_1_v4 ru (1).pdf](<../docs/Day_1_v4%20ru%20(1).pdf>) - исходный документ
- [agents_inventory.md](./agents_inventory.md) - текущий реестр агентов
- [agent_identity_matrix.md](./agent_identity_matrix.md) - матрица прав
- [AGENT_GYM_GUIDE.md](./AGENT_GYM_GUIDE.md) - руководство по симуляциям

---

**Следующий шаг:** Начать с Фазы 1 - централизация промптов.
