# 🎯 План оптимизации дашборда Intelligence Command Center

**Совместный анализ:** Victoria (Team Lead), Ольга (Performance Engineer), Анастасия (Product Analyst), опыт DASHBOARD_FIX_EXPLAINED и ADDITIONAL_PERFORMANCE_OPTIMIZATIONS

**Проблема:** Дашборд потребляет ~11.5 ГБ памяти (Streamlit на порту 8501)

**Дата:** 2026-01-31

---

## 📋 Диагностика (Victoria + Ольга)

### 1. **Streamlit cache — главный потребитель**

- `@st.cache_data(ttl=60)` и `@st.cache_data(ttl=15)` без `max_entries`
- ~50+ уникальных вызовов `fetch_data` с разными параметрами (дни, домен, статус)
- Streamlit известен проблемой: кэш растёт без ограничений

### 2. **Тяжёлые данные в запросах** (Ольга)

- `knowledge_nodes.content` — до 50–100 КБ на строку
- `experts.system_prompt` — 1–5 КБ × 58 экспертов ≈ 170 КБ
- Запросы attacks, scout_reports, db_nodes грузят полный `content` без `LEFT(content, N)`

### 3. **Рендер всех вкладок** (Анастасия)

- При каждом взаимодействии Streamlit перезапускает скрипт
- Данные для **всех** вкладок вычисляются, а не только для активной

### 4. **Опыт DASHBOARD_FIX_EXPLAINED**

- READONLY для чтения, пул соединений
- Избегать частых переподключений к БД

---

## ✅ Рекомендации (приоритет)

### Фаза 1 — Быстрые wins (1–2 часа)

| #   | Изменение                                       | Файл   | Эффект                 |
| --- | ----------------------------------------------- | ------ | ---------------------- |
| 1   | `max_entries=100` в `st.cache_data`             | app.py | Ограничение роста кэша |
| 2   | `LEFT(k.content, 500)` в запросах с content     | app.py | −80% объёма на content |
| 3   | Не грузить `system_prompt` в списке экспертов   | app.py | −170 КБ на вызов       |
| 4   | `LEFT(content, 300)` для attacks, scout_reports | app.py | −90% на этих выборках  |

### Фаза 2 — Архитектура (полдня)

| #   | Изменение                                                    | Эффект                             |
| --- | ------------------------------------------------------------ | ---------------------------------- |
| 5   | Ленивая загрузка вкладок (`st.fragment` или условный рендер) | Данные только для активной вкладки |
| 6   | Вынести `system_prompt` в expander «Подробнее»               | Загрузка по клику                  |
| 7   | Периодический перезапуск дашборда (cron каждые 6ч)           | Сброс накопленной памяти           |

### Фаза 3 — Долгосрочно

| #   | Изменение                                | Эффект                                              |
| --- | ---------------------------------------- | --------------------------------------------------- |
| 8   | Отдельный API для агрегатов (FastAPI)    | Streamlit только рендерит, не держит тяжёлые данные |
| 9   | Persist cache на диск (`persist="disk"`) | Меньше RAM, но Streamlit всё равно грузит в память  |
| 10  | Миграция на React + lightweight charts   | Полный контроль над памятью                         |

---

## 📐 Конкретные SQL-изменения

```sql
-- Было (attacks):
SELECT content, expert_consensus->>'adversarial_attack' as attack, ...

-- Стало:
SELECT LEFT(content, 300) as content, expert_consensus->>'adversarial_attack' as attack, ...
```

```sql
-- Было (db_nodes для графа):
SELECT k.id, k.content, d.name as domain ...

-- Стало:
SELECT k.id, LEFT(k.content, 100) as content, d.name as domain ...
```

```sql
-- Было (experts список):
SELECT name, role, department, system_prompt, performance_score ...

-- Стало (без system_prompt для списка):
SELECT name, role, department, performance_score ...
-- system_prompt грузить только в expander по клику
```

---

## 📐 Изменения в коде (cache)

```python
# Было:
@st.cache_data(ttl=60)
def fetch_data(query, params=None, cache_key=None):

# Стало:
@st.cache_data(ttl=60, max_entries=100)
def fetch_data(query, params=None, cache_key=None):
```

---

## 🚀 Ожидаемый эффект

| Метрика        | До       | После Фазы 1                        |
| -------------- | -------- | ----------------------------------- |
| Память         | ~11.5 ГБ | ~2–4 ГБ                             |
| Время загрузки | —        | −30% за счёт меньшего объёма данных |

---

## 📚 Ссылки

- `knowledge_os/docs/DASHBOARD_FIX_EXPLAINED.md` — опыт с SQLite дашбордом
- `knowledge_os/docs/ADDITIONAL_PERFORMANCE_OPTIMIZATIONS_PLAN.md` — общий план
- `knowledge_os/scripts/PERFORMANCE_BOTTLENECKS_ANALYSIS.md` — lru_cache, кэширование
