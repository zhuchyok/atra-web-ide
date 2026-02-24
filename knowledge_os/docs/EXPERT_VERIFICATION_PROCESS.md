# 📋 ПРОЦЕСС ВЕРИФИКАЦИИ СПИСКОВ ЭКСПЕРТОВ

## Обзор

Этот документ описывает процесс проверки соответствия жёстко закодированных списков экспертов актуальным данным в базе данных.

---

## 🔄 Регулярная верификация (рекомендуется 1 раз в месяц)

### Шаг 1: Быстрая проверка

```bash
cd /root/knowledge_os
python scripts/quick_validate_experts.py
```

**Ожидаемый результат:**

- ✅ ВАЛИДАЦИЯ ПРОЙДЕНА — все хардкоды актуальны
- ❌ ВАЛИДАЦИЯ НЕ ПРОЙДЕНА — требуется исправление

### Шаг 2: Полный аудит (при обнаружении проблем)

```bash
python scripts/check_experts_count.py --verbose --no-confirm
```

**Вывод включает:**

- SQL результаты (`SELECT COUNT(*)`, `SELECT name`)
- Сканирование кодовой базы
- Детальный отчёт о расхождениях
- Рекомендации по исправлению

### Шаг 3: Просмотр отчёта

```bash
cat scripts/reports/experts_check_report.txt
```

---

## 🆕 При добавлении нового эксперта в БД

### 1. Добавление записи в БД

```sql
INSERT INTO experts (name, role, department, system_prompt)
VALUES ('Новый Эксперт', 'Role Title', 'Department', 'System prompt...');
```

### 2. Проверка fallback-списков

Если новый эксперт критически важен (Lead, Director):

**Файл:** `/root/knowledge_os/app/expert_validator.py`

```python
# Добавить в EXTENDED_FALLBACK_EXPERTS (если необходимо)
EXTENDED_FALLBACK_EXPERTS: List[str] = [
    "Дмитрий",
    "Мария",
    "Максим",
    "Сергей",
    "Елена",
    "НовыйЭксперт",  # <-- добавить
]
```

### 3. Обновление алиасов (опционально)

**Файл:** `/root/knowledge_os/app/expert_aliases.py`

```python
# Добавить стандартные сокращения
STANDARD_DIMINUTIVES: Dict[str, List[str]] = {
    # ...
    'НовыйЭксперт': ['ник', 'никнейм'],  # <-- добавить
}
```

### 4. Запуск валидации

```bash
python scripts/quick_validate_experts.py
```

### 5. Перезапуск Telegram gateway (если работает)

```bash
# Graceful restart
pkill -f telegram_gateway.py
python /root/knowledge_os/app/telegram_gateway.py &
```

---

## 🔍 SQL Запросы для ручной проверки

### Количество экспертов

```sql
SELECT COUNT(*) FROM experts;
```

### Список всех экспертов

```sql
SELECT name, role, department FROM experts ORDER BY name;
```

### Проверка конкретного эксперта

```sql
SELECT * FROM experts WHERE name = 'Виктория';
```

### Эксперты, добавленные за последний месяц

```sql
SELECT name, role, created_at
FROM experts
WHERE created_at > NOW() - INTERVAL '30 days'
ORDER BY created_at DESC;
```

### Эксперты с определёнными ролями (для distillation)

```sql
SELECT name, role FROM experts
WHERE role ILIKE '%Lead%'
   OR role ILIKE '%Director%'
   OR role ILIKE '%Senior%';
```

---

## 🚨 Что делать при обнаружении расхождений

### Сценарий A: Эксперт есть в БД, но нет в хардкоде

**Диагноз:** Telegram gateway не сможет маршрутизировать запросы к этому эксперту.

**Решение:**

1. Если используется `expert_aliases.py` — кэш обновится автоматически
2. Если используется старый код — добавить в соответствующий блок if/elif
3. Рекомендация: провести рефакторинг на динамическую загрузку

### Сценарий B: Эксперт есть в хардкоде, но нет в БД

**Диагноз:** Критическая ошибка! Код ссылается на несуществующего эксперта.

**Решение:**

1. Добавить эксперта в БД
2. ИЛИ удалить из хардкода (если эксперт больше не нужен)

```sql
-- Добавление
INSERT INTO experts (name, role, system_prompt)
VALUES ('ИмяЭксперта', 'Role', 'Prompt');

-- Проверка
SELECT * FROM experts WHERE name = 'ИмяЭксперта';
```

### Сценарий C: Fallback-список неполный

**Диагноз:** При недоступности БД система будет работать с ограниченным набором экспертов.

**Решение:**

1. Обновить `EXTENDED_FALLBACK_EXPERTS` в `expert_validator.py`
2. Добавить комментарий с датой обновления

---

## 📊 Метрики для мониторинга

| Метрика                   | Целевое значение     | Как проверить                              |
| ------------------------- | -------------------- | ------------------------------------------ |
| Экспертов в БД            | >= кол-во в fallback | `SELECT COUNT(*) FROM experts`             |
| Хардкодов в коде          | Минимум              | `grep -r "FALLBACK_EXPERTS" app/`          |
| Время последней валидации | < 30 дней            | `cat scripts/reports/quick_validation.txt` |

---

## 🔗 Связанные файлы

| Файл                                | Назначение                       |
| ----------------------------------- | -------------------------------- |
| `scripts/check_experts_count.py`    | Полный аудит                     |
| `scripts/quick_validate_experts.py` | Быстрая проверка                 |
| `app/expert_validator.py`           | Централизованные fallback-списки |
| `app/expert_aliases.py`             | Динамический менеджер алиасов    |
| `scripts/reports/`                  | Отчёты проверок                  |
| `scripts/patches/`                  | Патчи для рефакторинга           |

---

## ⏰ Рекомендуемое расписание

| Действие              | Частота              | Команда                                           |
| --------------------- | -------------------- | ------------------------------------------------- |
| Быстрая валидация     | Еженедельно          | `python scripts/quick_validate_experts.py`        |
| Полный аудит          | Ежемесячно           | `python scripts/check_experts_count.py --verbose` |
| Проверка после деплоя | После каждого деплоя | `python scripts/quick_validate_experts.py`        |

---

**Документ создан:** 2026-01-14  
**Автор:** Артём (Performance Lead, Marketing)  
**Версия:** 1.0
