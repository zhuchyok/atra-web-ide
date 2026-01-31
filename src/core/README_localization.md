# Система локализации ATRA

Многоязычная поддержка для торгового бота ATRA с поддержкой русского и английского языков.

## 🏗️ Архитектура

```
src/core/
├── localization.py      # Основная система локализации
├── config.py           # Конфигурация языков
└── README_localization.md  # Эта документация

locales/
├── en.json             # Английские переводы
└── ru.json             # Русские переводы
```

## 🚀 Быстрый старт

### Базовое использование

```python
from src.core.localization import gettext

# Получение текста на русском (по умолчанию)
text = gettext('welcome')
print(text)  # "Добро пожаловать в торгового бота ATRA!"

# Получение текста на английском
text_en = gettext('welcome', 'en')
print(text_en)  # "Welcome to ATRA Trading Bot!"

# С параметрами
price_text = gettext('entry_price', 'ru', price=45000.50)
print(price_text)  # "Цена входа: 45000.50"
```

### Интеграция с Telegram

```python
from src.telegram.formatters import SignalFormatter
from src.core.localization import gettext

formatter = SignalFormatter()

# Сигнал с языком
signal_data = {
    'signal': 'LONG',
    'symbol': 'BTC',
    'language': 'en'  # Английский
}

message = formatter.format_signal_message(signal_data)
# Сообщение будет на английском
```

## 📝 Структура переводов

### Файлы переводов

- **locales/ru.json** - Русские переводы (основной язык)
- **locales/en.json** - Английские переводы (вспомогательный)

### Пример структуры JSON

```json
{
  "welcome": "Добро пожаловать в торгового бота ATRA!",
  "help": "Доступные команды:\n/start - Запустить бота\n/help - Показать эту справку",
  "signal_long": "Сигнал LONG",
  "signal_short": "Сигнал SHORT",
  "entry_price": "Цена входа",
  "take_profit": "Тейк профит",
  "stop_loss": "Стоп лосс"
}
```

## 🔧 API

### Основные функции

#### `gettext(key, language=None, **kwargs)`
Получение переведенного текста.

```python
# Простой текст
text = gettext('welcome')

# С языком
text = gettext('welcome', 'en')

# С параметрами
text = gettext('error_message', 'ru', error_code=404)
```

#### `set_language(user_id, language)`
Установка языка для пользователя.

```python
set_language(123456789, 'en')  # Английский для пользователя
```

#### `get_supported_languages()`
Получение списка поддерживаемых языков.

```python
languages = get_supported_languages()
# ['ru', 'en']
```

### Классы

#### `Localizer`
Основной класс для управления переводами.

```python
from src.core.localization import Localizer, LocalizationConfig

config = LocalizationConfig(default_language='ru')
localizer = Localizer(config)

text = localizer.get_text('welcome', 'ru')
```

## 🛠️ Добавление новых переводов

### 1. Обновление JSON файлов

Добавьте новый ключ в оба файла:

**locales/ru.json:**
```json
{
  "new_feature": "Новая функция"
}
```

**locales/en.json:**
```json
{
  "new_feature": "New Feature"
}
```

### 2. Использование в коде

```python
# В Python коде
new_text = gettext('new_feature', 'ru')

# В Telegram сообщениях
message = f"🔥 {gettext('new_feature')} активирована!"
```

### 3. Проверка переводов

```python
from src.core.localization import localizer

# Проверка валидности переводов
validation = localizer.validate_translations()
print(f"Missing keys: {validation['missing_keys']}")
print(f"Extra keys: {validation['extra_keys']}")
```

## 🎯 Поддерживаемые языки

| Код | Язык | Статус | Переводов |
|-----|------|--------|-----------|
| ru | Русский | ✅ Полный | 79+ |
| en | English | ✅ Полный | 79+ |

## 🔄 Fallback стратегия

1. **Основной язык**: ru (русский)
2. **Fallback**: en (английский)
3. **Если ключ не найден**: возвращается сам ключ

```python
# ru -> en -> key
text = gettext('missing_key', 'ru')
# Вернет 'missing_key' если перевод не найден
```

## 📊 Статистика

### Текущие метрики

- **Поддерживаемые языки**: 2
- **Ключей переводов**: 79+
- **Категории**:
  - UI элементы: 25%
  - Сигналы: 20%
  - Ошибки: 15%
  - Настройки: 40%

### Валидация переводов

```python
validation = localizer.validate_translations()
print(f"Языков с ошибками: {validation['summary']['languages_with_missing']}")
print(f"Общее кол-во ключей: {validation['summary']['base_keys_count']}")
```

## 🚨 Обработка ошибок

### Отсутствующие файлы
```python
WARNING: Translation file not found: en.json
INFO: Using fallback translations
```

### Поврежденные JSON
```python
ERROR: Error parsing translation file ru.json
WARNING: Using empty translations for ru
```

### Отсутствующие ключи
```python
WARNING: Translation not found for key 'missing_key' in language 'ru'
INFO: Returning key as fallback
```

## 📝 Лучшие практики

### 1. Использование в коде
```python
# ✅ Хорошо
text = gettext('welcome')

# ❌ Плохо
text = "Добро пожаловать"  # hardcoded текст
```

### 2. Ключи переводов
```python
# ✅ Хорошо - описательные ключи
"signal_strength": "Сила сигнала"
"entry_price": "Цена входа"

# ❌ Плохо - технические ключи
"sig_str": "Сила сигнала"
"price": "Цена входа"
```

### 3. Плейсхолдеры
```python
# В JSON
"price_message": "Цена: {price} USDT"

# В коде
text = gettext('price_message', 'ru', price=45000.50)
```

## 🔧 Конфигурация

### Настройки в config.py

```python
# Языковые настройки
DEFAULT_LANGUAGE = "ru"  # Язык по умолчанию
SUPPORTED_LANGUAGES = ["ru", "en"]  # Поддерживаемые языки
```

### Пользовательские настройки

```python
# В базе данных или конфигурации
user_languages = {
    123456789: 'en',  # Пользователь с английским
    987654321: 'ru'   # Пользователь с русским
}
```

## 📚 Примеры

### Telegram бот

```python
def get_help_message(user_id):
    language = get_user_language(user_id)
    return gettext('help', language)

def send_signal_message(chat_id, signal_data):
    language = signal_data.get('language', 'ru')
    message = format_signal(signal_data, language)
    bot.send_message(chat_id, message)
```

### Dashboard

```python
def render_dashboard(user_id):
    language = get_user_language(user_id)
    title = gettext('dashboard_title', language)
    return render_template('dashboard.html',
                         title=title,
                         language=language)
```

---

*Система локализации ATRA v1.0*
*Дата создания: 22 августа 2024 г.*
