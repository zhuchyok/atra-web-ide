# 🔍 АУДИТ ЖЁСТКО ЗАКОДИРОВАННЫХ СПИСКОВ ЭКСПЕРТОВ

**Дата аудита:** 2026-01-14  
**Проведён:** Артём (Performance Lead, Marketing)  
**Статус:** ⚠️ ТРЕБУЕТ ДЕЙСТВИЙ

---

## 📊 EXECUTIVE SUMMARY

| Метрика                          | Значение |
| -------------------------------- | -------- |
| Файлов с хардкодами              | 7        |
| Критических точек                | 12       |
| Уникальных экспертов в хардкодах | ~10      |
| Рекомендуемый рефакторинг        | 5 файлов |

---

## 🔴 НАЙДЕННЫЕ ХАРДКОДЫ

### 1. telegram_gateway.py (КРИТИЧНО)

**Файл:** `/root/knowledge_os/app/telegram_gateway.py`  
**Строки:** 293-296

```python
if lower_text.startswith('виктория'):
    target_name = 'Виктория'; user_text = user_text[8:].strip(', ').strip()
elif lower_text.startswith('владимир'):
    target_name = 'Владимир'; user_text = user_text[8:].strip(', ').strip()
```

**Проблема:** Только 2 эксперта доступны через Telegram, остальные игнорируются.

**Рекомендация:** Использовать динамический список из БД:

```python
async def get_expert_prefixes():
    experts = await get_available_experts()
    return {e['name'].lower(): e['name'] for e in experts}
```

---

### 2. telegram_simple.py (КРИТИЧНО)

**Файл:** `/root/knowledge_os/app/telegram_simple.py`  
**Строки:** 127-141, 187-200

```python
# Хардкод дефолта если БД пуста
expert = {
    'name': 'Виктория',
    'system_prompt': 'Вы Виктория, Главный Координатор...',
    ...
}
```

и парсинг имён (строки 187-200):

```python
if any(x in lower_text for x in ['виктория', 'вика']):
    target_name = 'Виктория'
elif any(x in lower_text for x in ['владимир', 'вова']):
    target_name = 'Владимир'
elif any(x in lower_text for x in ['дмитрий', 'дима']):
    target_name = 'Дмитрий'
elif any(x in lower_text for x in ['мария', 'маша']):
    target_name = 'Мария'
```

**Проблема:**

- Только 4 эксперта доступны
- Хардкод промпта может устареть
- Нет синхронизации с БД

---

### 3. expert_validator.py (ДОПУСТИМО)

**Файл:** `/root/knowledge_os/app/expert_validator.py`  
**Строки:** 65-81

```python
FALLBACK_EXPERTS: List[str] = [
    "Дмитрий",  # Engineer
    "Мария",    # Analyst
    "Максим",   # Developer
]

EXTENDED_FALLBACK_EXPERTS: List[str] = [
    "Дмитрий",
    "Мария",
    "Максим",
    "Сергей",
    "Елена",
]

COORDINATOR_NAMES: Set[str] = {"Виктория"}
```

**Статус:** ✅ ДОПУСТИМО - это резервный fallback при недоступности БД.
**Рекомендация:** Добавить автоматическую синхронизацию при старте.

---

### 4. swarm_orchestrator.py (ДОПУСТИМО)

**Файл:** `/root/knowledge_os/app/swarm_orchestrator.py`  
**Строка:** 46

```python
FALLBACK_EXPERTS = ["Дмитрий", "Мария", "Максим"]
```

**Статус:** ✅ ДОПУСТИМО - локальный fallback при неудачном импорте.

---

### 5. distillation_engine.py (ТРЕБУЕТ ВНИМАНИЯ)

**Файл:** `/root/knowledge_os/app/distillation_engine.py`  
**Строка:** 64

```python
WHERE (l.feedback_score >= $1 OR (e.name IN ('Виктория', 'Дмитрий', 'Мария') AND l.feedback_score IS NULL))
```

**Проблема:** При добавлении новых экспертов высокого уровня, их ответы не попадут в дистилляцию.

**Рекомендация:** Заменить на:

```python
WHERE (l.feedback_score >= $1
       OR (e.role IN ('Team Lead', 'Director', 'Senior Engineer')
           AND l.feedback_score IS NULL))
```

---

### 6. check_experts_count.py (ДОПУСТИМО)

**Файл:** `/root/knowledge_os/scripts/check_experts_count.py`  
**Строки:** 68-70, 92-97

```python
FALLBACK_EXPERTS = ["Дмитрий", "Мария", "Максим"]
COORDINATOR_NAMES = {"Виктория"}

KNOWN_EXPERT_NAMES = {
    'Виктория', 'Дмитрий', 'Игорь', 'Сергей', 'Анна', ...
}
```

**Статус:** ✅ ДОПУСТИМО - используется для сканирования, а не для бизнес-логики.
**Рекомендация:** Периодически обновлять KNOWN_EXPERT_NAMES из БД.

---

## ⚠️ РАСХОЖДЕНИЯ С БД

> **ВАЖНО:** Для точной верификации необходимо выполнить SQL запросы к БД.
> Список ниже может быть неполным.

### Потенциально отсутствующие в хардкодах:

- Эксперты, добавленные после последнего обновления кода
- Эксперты с нестандартными именами
- Новые директоры отделов

### Для верификации выполните:

```bash
cd /root/knowledge_os
python scripts/check_experts_count.py --verbose --no-confirm
```

---

## 📋 ПЛАН РЕФАКТОРИНГА

### Приоритет 1 (КРИТИЧНО):

#### telegram_gateway.py

```python
# БЫЛО:
if lower_text.startswith('виктория'): ...
elif lower_text.startswith('владимир'): ...

# СТАНЕТ:
expert_aliases = await get_expert_aliases_from_db()
# expert_aliases = {'виктория': 'Виктория', 'вика': 'Виктория', 'владимир': 'Владимир', ...}
for alias, name in expert_aliases.items():
    if lower_text.startswith(alias):
        target_name = name
        user_text = user_text[len(alias):].strip(', ').strip()
        break
```

#### telegram_simple.py

Аналогичный рефакторинг с кэшированием алиасов при старте.

### Приоритет 2 (ВАЖНО):

#### distillation_engine.py

Заменить хардкод имён на проверку ролей:

```python
WHERE (l.feedback_score >= $1
       OR (e.role ILIKE '%Lead%' OR e.role ILIKE '%Director%')
       AND l.feedback_score IS NULL)
```

### Приоритет 3 (НИЗКИЙ):

- Добавить в expert_validator.py автосинхронизацию fallback-списков
- Обновить KNOWN_EXPERT_NAMES в check_experts_count.py

---

## 🔧 СКРИПТЫ ВАЛИДАЦИИ

### Основной скрипт:

```bash
python /root/knowledge_os/scripts/check_experts_count.py --verbose
```

### Быстрая проверка SQL:

```sql
-- Количество экспертов
SELECT COUNT(*) FROM experts;

-- Список имён
SELECT name, role, department FROM experts ORDER BY name;

-- Проверка конкретных имён
SELECT name FROM experts WHERE name NOT IN ('Виктория', 'Дмитрий', 'Мария', 'Максим', 'Владимир');
```

### Новый скрипт быстрой валидации:

См. файл: `/root/knowledge_os/scripts/quick_validate_experts.py`

---

## 📝 ПРОЦЕСС ВЕРИФИКАЦИИ ДЛЯ БУДУЩИХ ПРОВЕРОК

### Регулярный аудит (рекомендуется 1 раз в месяц):

1. **Запуск check_experts_count.py:**

   ```bash
   python scripts/check_experts_count.py --verbose --no-confirm
   ```

2. **Проверка отчёта:**

   ```bash
   cat scripts/reports/experts_check_report.txt
   ```

3. **При обнаружении расхождений:**
   - Если эксперт есть в БД, но нет в хардкоде → добавить или рефакторить
   - Если эксперт есть в хардкоде, но нет в БД → удалить из кода или добавить в БД

### При добавлении нового эксперта в БД:

1. Добавить запись в таблицу experts
2. Если используется fallback → обновить FALLBACK_EXPERTS
3. Запустить валидацию
4. Проверить все telegram_gateway на поддержку нового имени

### CI/CD интеграция:

```yaml
# .github/workflows/experts_check.yml
- name: Validate Expert Lists
  run: python scripts/check_experts_count.py --no-confirm --sql-only
```

---

## ✅ ЧЕКЛИСТ ЗАВЕРШЕНИЯ РЕФАКТОРИНГА

- [ ] telegram_gateway.py - динамический парсинг имён
- [ ] telegram_simple.py - динамический парсинг имён
- [ ] distillation_engine.py - замена имён на роли
- [ ] expert_validator.py - автосинхронизация при старте
- [ ] CI/CD интеграция скрипта валидации
- [ ] Документация обновлена

---

**Автор отчёта:** Артём (Performance Lead)  
**Контакт для вопросов:** Запустите `python scripts/check_experts_count.py --help`
