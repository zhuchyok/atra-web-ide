# 🔧 ПАТЧИ ДЛЯ РЕФАКТОРИНГА ХАРДКОДОВ ЭКСПЕРТОВ

## ⚠️ ВАЖНО: Перед применением патчей

1. Сделайте бэкап файлов
2. Проверьте, что БД доступна и содержит экспертов
3. Запустите тесты после применения

---

## PATCH 1: telegram_gateway.py (строки 272-305)

### Текущий код (ПРОБЛЕМА):

```python
async def telegram_bridge():
    # ...
    for update in data.get('result', []):
        # ...
        lower_text = user_text.lower()
        if lower_text.startswith('виктория'):
            target_name = 'Виктория'; user_text = user_text[8:].strip(', ').strip()
        elif lower_text.startswith('владимир'):
            target_name = 'Владимир'; user_text = user_text[8:].strip(', ').strip()
```

### Предлагаемый код (РЕШЕНИЕ):

```python
# Добавить импорт в начало файла:
from expert_aliases import get_alias_manager, extract_expert_from_message

async def telegram_bridge():
    print(f"[{datetime.now()}] Telegram шлюз v4.7 (Dynamic Experts) запущен...")
    offset = 0

    # Инициализируем менеджер алиасов при старте
    alias_manager = await get_alias_manager()

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            try:
                # ... existing code ...

                for update in data.get('result', []):
                    offset = update['update_id'] + 1
                    msg = update.get('message')
                    if msg:
                        user_id = msg.get('from', {}).get('id')
                        user_text = msg.get('text', '')
                        chat_id = msg['chat']['id']

                        # НОВЫЙ КОД: Динамическое определение эксперта
                        target_name, user_text = await extract_expert_from_message(
                            user_text,
                            default_expert='Виктория'
                        )

                        asyncio.create_task(handle_message(target_name, user_text, chat_id, user_id))

                # Периодически обновляем кэш алиасов (раз в 30 мин автоматически)
                await alias_manager.load_aliases()
                await check_notifications()
            except Exception as e:
                await asyncio.sleep(5)
            await asyncio.sleep(0.1)
```

---

## PATCH 2: telegram_simple.py (строки 184-206)

### Текущий код (ПРОБЛЕМА):

```python
# Определение эксперта по ключевым словам
if any(x in lower_text for x in ['виктория', 'вика']):
    target_name = 'Виктория'
    user_text = user_text.replace('Виктория', '').replace('Вика', '').strip(', ').strip()
elif any(x in lower_text for x in ['владимир', 'вова']):
    target_name = 'Владимир'
    # ... и т.д. для каждого эксперта
```

### Предлагаемый код (РЕШЕНИЕ):

```python
# Добавить импорт в начало файла:
from expert_aliases import extract_expert_from_message

# В telegram_bridge(), вместо блока if/elif:

# Определение эксперта через динамический менеджер алиасов
target_name, user_text = await extract_expert_from_message(
    user_text,
    default_expert='Виктория'
)

# Обработка запроса в отдельной задаче
asyncio.create_task(handle_message(target_name, user_text, chat_id, user_id))
```

---

## PATCH 3: distillation_engine.py (строка 64)

### Текущий код (ПРОБЛЕМА):

```python
WHERE (l.feedback_score >= $1 OR (e.name IN ('Виктория', 'Дмитрий', 'Мария') AND l.feedback_score IS NULL))
```

### Предлагаемый код (РЕШЕНИЕ):

```python
# Вариант A: Фильтр по ролям (рекомендуется)
WHERE (
    l.feedback_score >= $1
    OR (
        (e.role ILIKE '%Lead%' OR e.role ILIKE '%Director%' OR e.role ILIKE '%Senior%')
        AND l.feedback_score IS NULL
    )
)

# Вариант B: Динамический список из конфига
# В начале класса:
SENIOR_ROLES = ['Team Lead', 'Director', 'Senior Engineer', 'Manager']

# В запросе:
WHERE (
    l.feedback_score >= $1
    OR (e.role = ANY($3::text[]) AND l.feedback_score IS NULL)
)
# И передать SENIOR_ROLES как параметр
```

---

## PATCH 4: telegram_simple.py fallback (строки 134-141)

### Текущий код (ПРОБЛЕМА):

```python
# Хардкод дефолта если БД пуста
expert = {
    'name': 'Виктория',
    'system_prompt': 'Вы Виктория, Главный Координатор торговой системы ATRA...',
    'role': 'Team Lead',
    'id': 0
}
```

### Предлагаемый код (РЕШЕНИЕ):

```python
# Добавить импорт:
from expert_validator import get_validated_fallback_experts

# В handle_message():
if not expert:
    logger.warning(f"Эксперт {target_name} не найден в БД")

    # Пробуем Викторию
    expert = await get_expert_config('Виктория')

    if not expert:
        # Используем валидированный fallback с предупреждением
        logger.error("БД недоступна, используется FALLBACK")

        # Импортируем дефолтный промпт из конфига (не хардкодим!)
        from config import DEFAULT_COORDINATOR_CONFIG
        expert = DEFAULT_COORDINATOR_CONFIG
```

И создать `config.py`:

```python
# /root/knowledge_os/app/config.py
DEFAULT_COORDINATOR_CONFIG = {
    'name': 'Виктория',
    'system_prompt': (
        'Вы Виктория, Главный Координатор торговой системы ATRA. '
        'Отвечайте лаконично и по делу. '
        'При невозможности ответить — делегируйте соответствующему эксперту.'
    ),
    'role': 'Team Lead',
    'department': 'Management',
    'id': 0
}
```

---

## 📋 ПОРЯДОК ПРИМЕНЕНИЯ ПАТЧЕЙ

1. **Создать expert_aliases.py** ✅ (уже создан)

2. **Обновить telegram_gateway.py**:
   - Добавить импорт `from expert_aliases import ...`
   - Заменить блок if/elif на вызов `extract_expert_from_message()`
   - Тест: `python telegram_gateway.py` (без запуска, проверить импорты)

3. **Обновить telegram_simple.py**:
   - Аналогичные изменения
   - Тест: проверить подключение к боту

4. **Обновить distillation_engine.py**:
   - Заменить хардкод имён на фильтр по ролям
   - Тест: `python distillation_engine.py`

5. **Запустить валидацию**:
   ```bash
   python scripts/quick_validate_experts.py
   ```

---

## ⚠️ ПРИМЕЧАНИЕ О НЕОПРЕДЕЛЁННОСТИ

> **Список хардкодов может быть неполным!**
>
> Проведённый аудит покрывает основные файлы, но в кодовой базе
> могут существовать другие места с хардкодами экспертов.
>
> Рекомендуется:
>
> 1. Регулярно запускать `check_experts_count.py`
> 2. При добавлении экспертов в БД — проверять все gateway-файлы
> 3. Использовать `expert_aliases.py` для новых интеграций

---

**Автор патчей:** Артём (Performance Lead)
**Дата:** 2026-01-14
