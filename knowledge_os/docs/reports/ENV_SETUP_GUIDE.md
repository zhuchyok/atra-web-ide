# Руководство по настройке .env файлов

## 📋 Обзор

Проект ATRA использует переменные окружения для конфигурации. Созданы три файла:

- `env.example` - шаблон со всеми переменными
- `env.dev` - настройки для разработки
- `env.prod` - настройки для продакшена

## 🚀 Быстрый старт

### 1. Скопируйте нужный файл как .env

**Для разработки:**

```bash
cp env.dev .env
```

**Для продакшена:**

```bash
cp env.prod .env
```

### 2. Отредактируйте .env файл

Замените все значения `your_*_here` на реальные:

```bash
# Telegram токены
TELEGRAM_TOKEN=1234567890:ABCDEFghijklmnopQRSTUVwxyz
TELEGRAM_TOKEN_DEV=9876543210:ZYXWVUTSRQPONMLKJIHGFEDCBA

# API ключи
CRYPTOPANIC_API_KEY=your_real_api_key_here
TRADINGVIEW_API_KEY=your_real_api_key_here
NEWSDATA_API_KEY=your_real_api_key_here

# Blockchain explorers
ETHERSCAN_API_KEY=your_real_api_key_here
BSCSCAN_API_KEY=your_real_api_key_here
```

## 🔧 Основные переменные

### Обязательные для работы:

1. **TELEGRAM_TOKEN** (prod) или **TELEGRAM_TOKEN_DEV** (dev)
2. **TELEGRAM_CHAT_IDS** - ID чатов для уведомлений
3. **ATRA_ENV** - окружение (dev/prod)

### Опциональные (для расширенного функционала):

- API ключи для новостей (CryptoPanic, TradingView, NewsData)
- Blockchain explorer API ключи (Etherscan, BSCScan, etc.)

## 📊 Различия между dev и prod

### DEV (env.dev):

- Быстрые интервалы обновления
- Короткие кулдауны
- Включены алерты
- Меньшие пороги
- Отдельная база данных (`trading_dev.db`)

### PROD (env.prod):

- Стабильные интервалы
- Длинные кулдауны
- Отключены алерты
- Высокие пороги
- Основная база данных (`trading.db`)

## 🔐 Безопасность

### ⚠️ ВАЖНО:

- Никогда не коммитьте .env файлы в git
- Храните API ключи в безопасном месте
- Используйте разные токены для dev и prod

### .gitignore уже настроен:

```
.env
.env.*
```

## 🛠️ Получение API ключей

### Telegram Bot:

1. Напишите @BotFather в Telegram
2. Создайте нового бота: `/newbot`
3. Скопируйте полученный токен

### CryptoPanic:

1. Зарегистрируйтесь на https://cryptopanic.com/
2. Перейдите в API settings
3. Создайте новый API ключ

### TradingView:

1. Зарегистрируйтесь на https://tradingview.com/
2. Перейдите в настройки профиля
3. Создайте API ключ

### Blockchain Explorers:

- **Etherscan**: https://etherscan.io/apis
- **BSCScan**: https://bscscan.com/apis
- **PolygonScan**: https://polygonscan.com/apis
- **Arbiscan**: https://arbiscan.io/apis

## 🔄 Переключение окружений

### Для разработки:

```bash
cp env.dev .env
python main.py
```

### Для продакшена:

```bash
cp env.prod .env
python main.py
```

### Или установите переменную напрямую:

```bash
ATRA_ENV=dev python main.py
ATRA_ENV=prod python main.py
```

## 📝 Кастомизация

### Изменение настроек:

Отредактируйте соответствующий env файл (dev/prod) или создайте свой .env

### Добавление новых переменных:

1. Добавьте в config.py: `NEW_VAR = os.getenv("NEW_VAR", "default_value")`
2. Добавьте в env.example и соответствующие env файлы
3. Обновите документацию

## 🚨 Troubleshooting

### Проблема: "TELEGRAM_TOKEN not found"

**Решение:** Убедитесь, что в .env файле указан правильный токен

### Проблема: "Database connection failed"

**Решение:** Проверьте путь к базе данных в DATABASE

### Проблема: "API key invalid"

**Решение:** Проверьте правильность API ключей

### Проблема: "Chat ID not found"

**Решение:** Убедитесь, что TELEGRAM_CHAT_IDS содержит правильные ID

## 📚 Дополнительная информация

- Все переменные имеют значения по умолчанию в config.py
- Boolean переменные принимают: "true", "1", "yes" (регистр не важен)
- Числовые переменные автоматически конвертируются
- Строковые переменные используются как есть

---

## 🎯 Готово!

После настройки .env файла проект готов к запуску:

```bash
python main.py
```

Удачной торговли! 🚀
