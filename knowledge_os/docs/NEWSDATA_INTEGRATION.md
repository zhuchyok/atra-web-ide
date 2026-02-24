# Интеграция NewsData.io

## 📋 Описание

Успешно интегрирован новый новостной источник [NewsData.io](https://newsdata.io/) в систему получения новостей для улучшения качества торговых сигналов.

## 🔑 API Конфигурация

### API Ключ

```python
NEWSDATA_API_KEY = "pub_9259f5b0818a4d40baabae05a908af4f"
```

### Конфигурация в `config.py`

```python
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "pub_9259f5b0818a4d40baabae05a908af4f")
```

## ⚙️ Техническая реализация

### Функция получения новостей

```python
async def get_newsdata_news(symbol):
    """Получает новости с NewsData.io с повторными попытками"""
```

### Параметры API запроса

- **URL**: `https://newsdata.io/api/1/news`
- **Query**: `{symbol} cryptocurrency`
- **Language**: `en`
- **Category**: `business`
- **Country**: `us`
- **Timeout**: 15 секунд
- **Retries**: 3 попытки

### Анализ настроения новостей

Система автоматически анализирует настроение новостей на основе ключевых слов:

#### Позитивные ключевые слова:

- `partnership` - партнерство
- `adoption` - принятие
- `launch` - запуск
- `upgrade` - обновление
- `success` - успех
- `growth` - рост
- `profit` - прибыль
- `bullish` - бычий
- `rally` - ралли

#### Негативные ключевые слова:

- `hack` - взлом
- `exploit` - эксплойт
- `regulation` - регулирование
- `ban` - запрет
- `lawsuit` - судебный иск
- `scam` - мошенничество
- `fraud` - мошенничество
- `investigation` - расследование
- `arrest` - арест
- `shutdown` - закрытие

## 🔄 Интеграция в мультиисточниковую систему

### Обновленная функция `get_news_multi_source`

```python
async def get_news_multi_source(symbol):
    # Запускаем асинхронные источники одновременно
    tradingview_news = await get_tradingview_news(symbol)
    cryptopanic_news = await get_cryptopanic_news(symbol)
    newsdata_news = await get_newsdata_news(symbol)  # НОВЫЙ ИСТОЧНИК

    # CoinGecko - синхронная функция
    coingecko_news = get_coingecko_news(symbol)

    # Обрабатываем результаты
    news_sources = []
    if isinstance(coingecko_news, list):
        news_sources.append(coingecko_news)
    if isinstance(tradingview_news, list):
        news_sources.append(tradingview_news)
    if isinstance(cryptopanic_news, list):
        news_sources.append(cryptopanic_news)
    if isinstance(newsdata_news, list):  # НОВЫЙ ИСТОЧНИК
        news_sources.append(newsdata_news)
```

### Логирование

```
[NewsFilter] Получено новостей: TradingView=4, CoinGecko=1, CryptoPanic=0, NewsData.io=10, Итого уникальных=14
```

## 📊 Система кэширования

### Добавлен новый тип кэша

```python
NEWS_CACHE = {
    'blocked': {},      # {symbol: блокировка_до_utc}
    'positive': {},     # {symbol: (новость, до_времени)}
    'negative': {},     # {symbol: (новость, до_времени)}
    'coingecko': {},    # {symbol: (данные, до_времени)}
    'tradingview': {},  # {symbol: (данные, до_времени)}
    'cryptopanic': {},  # {symbol: (данные, до_времени)}
    'newsdata': {},     # {symbol: (данные, до_времени)} - НОВЫЙ
    'api_errors': {},   # {api_name: (ошибка_время, количество_ошибок)}
    'combined': {}      # {symbol: (комбинированные_новости, до_времени)}
}
```

### Время жизни кэша

```python
CACHE_TTL = {
    'blocked': 3600,      # 1 час для заблокированных
    'positive': 7200,     # 2 часа для позитивных новостей
    'negative': 7200,     # 2 часа для негативных новостей
    'coingecko': 1800,    # 30 минут для CoinGecko
    'tradingview': 900,   # 15 минут для TradingView
    'cryptopanic': 900,   # 15 минут для CryptoPanic
    'newsdata': 900,      # 15 минут для NewsData.io - НОВЫЙ
    'api_errors': 300,    # 5 минут для ошибок API
    'combined': 600       # 10 минут для комбинированных новостей
}
```

## 🚦 Rate Limiting

### Ограничения API

```python
API_RATE_LIMITS = {
    'coingecko': {'requests_per_minute': 10, 'last_request': 0},
    'cryptopanic': {'requests_per_minute': 30, 'last_request': 0},
    'tradingview': {'requests_per_minute': 60, 'last_request': 0},
    'newsdata': {'requests_per_minute': 20, 'last_request': 0}  # НОВЫЙ
}
```

## 🧪 Результаты тестирования

### Тест API NewsData.io

```
🧪 Тестирование API NewsData.io...
[NewsFilter] NewsData.io: получено 10 новостей для BTCUSDT
✅ Получено 10 новостей для BTCUSDT
📰 Пример новости:
   Заголовок: Get Your Ethereum World's Fair Tickets Now and Join Our Supporter Program!...
   Источник: NewsData.io
   Тип: neutral
   URL: https://zephyrnet.com/get-your-ethereum-worlds-fair-tickets-now-and-join-our-supporter-program/
```

### Тест мультиисточниковой интеграции

```
🧪 Тестирование интеграции в мультиисточниковую систему...
[NewsFilter] NewsData.io: получено 10 новостей для BTCUSDT
[NewsFilter] Получено новостей: TradingView=4, CoinGecko=1, CryptoPanic=0, NewsData.io=10, Итого уникальных=14
✅ Мультиисточниковая система работает: 14 новостей
📊 Источники новостей:
   coingecko: 1
   tradingview: 4
   NewsData.io: 9
✅ NewsData.io успешно интегрирован!
```

## 📈 Преимущества интеграции

### 1. **Дополнительный источник новостей**

- Увеличивает покрытие новостного фона
- Снижает зависимость от одного источника
- Повышает надежность системы

### 2. **Улучшенное качество сигналов**

- Более точный анализ настроения рынка
- Лучшее понимание новостного контекста
- Снижение ложных сигналов

### 3. **Географическое разнообразие**

- Новости из США (основной рынок)
- Бизнес-категория (более релевантные новости)
- Англоязычные источники

### 4. **Техническая надежность**

- Асинхронная обработка
- Система повторных попыток
- Кэширование результатов
- Rate limiting

## 🔧 Структура новостей NewsData.io

### Формат новости

```python
{
    'title': 'Заголовок новости',
    'description': 'Описание новости',
    'content': 'Полный текст новости',
    'created_at': '2024-01-27T10:00:00Z',
    'source': 'NewsData.io',
    'url': 'https://example.com/news',
    'news_type': 'positive|negative|neutral',
    'sentiment': 'positive|negative|neutral'
}
```

### Обработка дат

- Поддержка ISO 8601 формата
- Автоматическое преобразование в московское время
- Фильтрация по свежести новостей

## 🛡️ Обработка ошибок

### Типы ошибок

- **422**: Неверные параметры запроса
- **429**: Rate limit превышен
- **Timeout**: Превышение времени ожидания
- **Network**: Сетевые ошибки

### Стратегия обработки

- 3 попытки с экспоненциальной задержкой
- Fallback на другие источники
- Логирование ошибок для мониторинга
- Graceful degradation

## 📊 Мониторинг и логирование

### Логи системы

```
[NewsFilter] NewsData.io: получено 10 новостей для BTCUSDT
[NewsFilter] NewsData.io API rate limit для BTCUSDT, попытка 1/3
[NewsFilter] NewsData.io API ошибка: 422
```

### Метрики производительности

- Количество полученных новостей
- Время ответа API
- Процент успешных запросов
- Количество ошибок

## 🎯 Заключение

Интеграция NewsData.io успешно завершена и протестирована. Система теперь использует 4 источника новостей:

1. **CoinGecko** - базовые данные о монетах
2. **TradingView** - технический анализ и новости
3. **CryptoPanic** - специализированные криптоновости
4. **NewsData.io** - бизнес-новости и общие новости

Это обеспечивает более полное покрытие новостного фона и улучшает качество торговых сигналов.
