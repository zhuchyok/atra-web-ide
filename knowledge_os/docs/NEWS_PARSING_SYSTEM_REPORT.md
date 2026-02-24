# 📰 СИСТЕМА ПАРСИНГА НОВОСТЕЙ

## 🎯 ОБЗОР СИСТЕМЫ

У вас реализована комплексная система парсинга новостей с **9 источниками** топ криптовалютных сайтов и RSS-лент. Система работает асинхронно и включает кэширование, дедупликацию и фильтрацию новостей.

## 📡 ИСТОЧНИКИ НОВОСТЕЙ

### 1. **CoinGecko** (API)

- **Функция:** `get_coingecko_news(symbol)`
- **Тип:** Синхронный API запрос
- **Данные:** Описание монеты, последние обновления
- **Особенности:** Проверка на негативные ключевые слова

### 2. **TradingView** (RSS)

- **Функция:** `get_tradingview_news(symbol)`
- **Тип:** Асинхронный RSS парсинг
- **URL:** `https://www.tradingview.com/feed/`
- **Данные:** Новости криптовалютного рынка

### 3. **CryptoPanic** (API)

- **Функция:** `get_cryptopanic_news(symbol)`
- **Тип:** Асинхронный API запрос
- **API Key:** `390212cf54403e087e19347f4f3e4a2f4459c79c`
- **Данные:** Агрегированные новости криптовалют

### 4. **NewsData.io** (API)

- **Функция:** `get_newsdata_news(symbol)`
- **Тип:** Асинхронный API запрос
- **API Key:** `pub_9259f5b0818a4d40baabae05a908af4f`
- **Данные:** Новости из различных источников

### 5. **CoinDesk** (RSS)

- **Функция:** `get_coindesk_news(symbol)`
- **Тип:** Асинхронный RSS парсинг
- **Данные:** Новости из CoinDesk

### 6. **Bitcoin.com** (RSS)

- **Функция:** `get_bitcoincom_news(symbol)`
- **Тип:** Асинхронный RSS парсинг
- **Данные:** Новости Bitcoin и криптовалют

### 7. **CryptoSlate** (RSS)

- **Функция:** `get_cryptoslate_news(symbol)`
- **Тип:** Асинхронный RSS парсинг
- **Данные:** Новости криптовалютного рынка

### 8. **Cointelegraph** (RSS)

- **Функция:** `get_cointelegraph_news(symbol)`
- **Тип:** Асинхронный RSS парсинг
- **Данные:** Новости из Cointelegraph

### 9. **AMBCrypto** (RSS)

- **Функция:** `get_ambcrypto_news(symbol)`
- **Тип:** Асинхронный RSS парсинг
- **Данные:** Новости криптовалют

## 🔧 ОСНОВНЫЕ ФУНКЦИИ

### `get_news_multi_source(symbol)`

**Главная функция** для получения новостей из всех источников:

- Запускает все источники асинхронно
- Дедуплицирует новости
- Кэширует результаты
- Обрабатывает ошибки с fallback

### `deduplicate_news(news_sources)`

Объединяет и удаляет дубликаты новостей из разных источников.

### `is_negative_news(symbol)` / `is_positive_news(symbol)`

Анализируют новости на позитивность/негативность для фильтрации сигналов.

## ⚙️ КОНФИГУРАЦИЯ

### API Ключи

```python
CRYPTOPANIC_API_KEY = "390212cf54403e087e19347f4f3e4a2f4459c79c"
NEWSDATA_API_KEY = "pub_9259f5b0818a4d40baabae05a908af4f"
```

### Настройки времени

```python
NEWS_SETTINGS = {
    "freshness_hours": 2,        # Свежесть новостей
    "negative_block_hours": 2,   # Блокировка по негативным
    "positive_cache_hours": 1,   # Кэш позитивных новостей
    "block_short_on_positive_news": True,
}
```

### Режимы фильтрации

```python
NEWS_FILTER_MODES = {
    "conservative": {
        "enable_negative_news": True,    # Блокировать по негативным
        "enable_positive_news": True,    # Генерировать LONG по позитивным
        "block_short_on_positive": True, # Блокировать SHORT при позитивных
    },
    "aggressive": {
        "enable_negative_news": False,   # НЕ блокировать по негативным
        "enable_positive_news": True,    # Генерировать LONG по позитивным
        "block_short_on_positive": False, # НЕ блокировать SHORT при позитивных
    }
}
```

## 🎯 КЛЮЧЕВЫЕ СЛОВА

### Негативные ключевые слова (21 слово)

- `hack`, `exploit`, `regulation`, `ban`, `lawsuit`
- `SEC`, `CFTC`, `liquidation`, `delist`, `scam`
- `fraud`, `investigation`, `arrest`, `shutdown`
- `outage`, `fork`, `upgrade`, `halving`, `ETF`
- `approval`, `rejection`

### Позитивные ключевые слова (30 слов)

- `partnership`, `adoption`, `integration`, `launch`
- `release`, `upgrade`, `update`, `innovation`
- `growth`, `expansion`, `investment`, `funding`
- `success`, `milestone`, `achievement`, `breakthrough`
- `development`, `technology`, `solution`, `platform`
- `ecosystem`, `community`, `governance`, `staking`
- `yield`, `rewards`, `airdrop`, `burn`, `buyback`
- `dividend`

## 🔄 ПРОЦЕСС РАБОТЫ

### 1. Запрос новостей

```python
news_list = await get_news_multi_source("BTCUSDT")
```

### 2. Асинхронный сбор

- Все 9 источников запускаются одновременно
- Каждый источник обрабатывается независимо
- Ошибки одного источника не влияют на другие

### 3. Дедупликация

- Новости объединяются из всех источников
- Удаляются дубликаты по заголовку и содержанию
- Сохраняется источник и время публикации

### 4. Кэширование

- Результаты кэшируются на 1 час
- Устаревшие данные автоматически очищаются
- Повторные запросы используют кэш

### 5. Фильтрация сигналов

- Анализ новостей на позитивность/негативность
- Блокировка сигналов по негативным новостям
- Усиление сигналов по позитивным новостям

## 📊 СТАТИСТИКА И ЛОГИРОВАНИЕ

Система выводит подробную статистику:

```
[NewsFilter] Получено новостей: TradingView=5, CoinGecko=2, CryptoPanic=8,
NewsData.io=3, CoinDesk=4, Bitcoin.com=2, CryptoSlate=3, Cointelegraph=6,
AMBCrypto=2, Итого уникальных=15
```

## 🎯 ИСПОЛЬЗОВАНИЕ В СИГНАЛАХ

### В функции `check_and_send_signals`:

1. **Проверка негативных новостей** - блокировка SHORT сигналов
2. **Проверка позитивных новостей** - усиление LONG сигналов
3. **Учет режима фильтрации** пользователя (conservative/aggressive)

### Пример логики:

```python
# Проверяем, не блокируется ли SHORT сигнал позитивными новостями
if signal_type == "SHORT" and positive_news_flag and mode_settings['block_short_on_positive']:
    print(f"[DEBUG] SHORT сигнал заблокирован позитивными новостями")
    signal_type = None  # Отменяем сигнал

# Проверяем новостное усиление для сигнала
if signal_type == "LONG" and positive_news_flag and mode_settings['enable_positive_news']:
    has_news_enhancement = True
    print(f"[DEBUG] LONG сигнал усилен позитивными новостями")
```

## 🔧 ТЕКУЩИЙ СТАТУС

- **NEWS_FILTER_ACTIVE = False** - новостные фильтры отключены
- Все источники настроены и готовы к работе
- Кэширование и дедупликация работают
- Система готова к включению

## 💡 РЕКОМЕНДАЦИИ

1. **Включить новостные фильтры** - изменить `NEWS_FILTER_ACTIVE = True`
2. **Мониторить API лимиты** - особенно для CryptoPanic и NewsData.io
3. **Проверить RSS источники** - убедиться в доступности
4. **Настроить ключевые слова** - добавить специфичные для вашей стратегии

Система парсинга новостей полностью функциональна и готова к использованию!
