# 🚀 Краткое руководство: Система агентов

## 📋 Что работает автоматически

### 1. **Централизованные промпты**

- ✅ Промпты загружаются автоматически при запуске агентов
- ✅ Файлы: `configs/agents/signal_live.yaml`, `auto_execution.yaml`, `risk_monitor.yaml`
- ✅ Ничего делать не нужно — работает само

### 2. **Context Engineering**

- ✅ Автоматически выбирает релевантный контекст для каждого агента
- ✅ Кэширует результаты для оптимизации
- ✅ Работает прозрачно в фоне

### 3. **Agent Ops (метрики)**

- ✅ Метрики собираются автоматически
- ✅ Экспорт в Prometheus: `metrics/agent_metrics.prom`
- ✅ Запуск: `python3 scripts/export_agent_metrics.py`

### 4. **Неявный feedback**

- ✅ Автоматически собирается из результатов сделок
- ✅ Конвертируется в lessons для обучения
- ✅ Запуск: `python3 scripts/process_feedback.py --apply-guidance`

### 5. **Многоагентная координация**

- ✅ Работает автоматически через EventBus
- ✅ Агенты обмениваются контекстом через SharedMemory
- ✅ Ничего делать не нужно

### 6. **Self-Evolving System**

- ✅ Анализирует производительность агентов
- ✅ Генерирует улучшения промптов
- ✅ Запуск: `python3 scripts/evolve_prompts.py --apply`

---

## 🛠️ Ручное управление

### Просмотр lessons learned:

```bash
# Просмотр всех уроков
cat configs/guidance/signal_live.json
cat configs/guidance/auto_execution.json
cat configs/guidance/risk_monitor.json
```

### Обработка feedback:

```bash
# Собрать feedback и применить lessons
python3 scripts/process_feedback.py --apply-guidance

# С выводом в консоль
python3 scripts/process_feedback.py --print
```

### Эволюция промптов:

```bash
# Анализ всех агентов (без применения)
python3 scripts/evolve_prompts.py

# Эволюция конкретного агента
python3 scripts/evolve_prompts.py --agent signal_live

# Применить эволюцию автоматически
python3 scripts/evolve_prompts.py --apply

# С минимальным приростом 10%
python3 scripts/evolve_prompts.py --apply --min-gain 0.10
```

### Экспорт метрик:

```bash
# Экспорт метрик агентов в Prometheus формат
python3 scripts/export_agent_metrics.py
```

---

## 📊 Где смотреть результаты

### 1. **Lessons learned:**

- `configs/guidance/<agent>.json` - JSON формат
- `docs/guidance/<agent>.md` - Markdown формат

### 2. **Метрики:**

- `metrics/agent_metrics.prom` - Prometheus формат
- `logs/agent_traces.log` - Трассировка агентов

### 3. **Эволюция промптов:**

- `cache/evolution/<agent>/variant_*.json` - Варианты промптов
- `configs/agents/<agent>.yaml.backup_*` - Резервные копии

### 4. **Неявный feedback:**

- `observability/implicit_feedback.json` - Собранный feedback

---

## 🔄 Рекомендуемый workflow

### Ежедневно:

```bash
# 1. Собрать feedback из сделок
python3 scripts/process_feedback.py --apply-guidance

# 2. Экспортировать метрики
python3 scripts/export_agent_metrics.py
```

### Еженедельно:

```bash
# Эволюция промптов (с применением)
python3 scripts/evolve_prompts.py --apply --min-gain 0.10
```

---

## ⚙️ Настройка

### Пороги эволюции:

- Минимальный прирост: `--min-gain 0.05` (5% по умолчанию)
- Минимум уроков: 3 (в коде `evolution_engine.py`)

### Промпты агентов:

- Редактировать: `configs/agents/<agent>.yaml`
- После изменений перезапустить агента

---

## 📝 Важно

1. **Все работает автоматически** - агенты сами загружают промпты, выбирают контекст, координируются
2. **Ручной запуск нужен только для:**
   - Обработки feedback (`process_feedback.py`)
   - Эволюции промптов (`evolve_prompts.py`)
   - Экспорта метрик (`export_agent_metrics.py`)
3. **Резервные копии** создаются автоматически перед применением эволюции

---

**См. также:**

- [AGENT_DEVELOPMENT_SUMMARY.md](./AGENT_DEVELOPMENT_SUMMARY.md) - полный отчет
- [AGENT_DEVELOPMENT_ROADMAP.md](./AGENT_DEVELOPMENT_ROADMAP.md) - детали реализации
