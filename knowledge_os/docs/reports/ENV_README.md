# .env файл для ATRA Trading Bot

## 🚀 Быстрый старт

1. **Скопируйте env файл:**

   ```bash
   cp env .env
   ```

2. **Отредактируйте .env файл:**

   ```bash
   nano .env
   ```

3. **Укажите обязательные переменные:**
   - `TELEGRAM_TOKEN` - токен продакшен бота
   - `TELEGRAM_TOKEN_DEV` - токен dev бота
   - `TELEGRAM_CHAT_IDS` - ID чатов через запятую

4. **Запустите бота:**
   ```bash
   python main.py
   ```

## 🔑 Уже настроенные API ключи

В файле уже указаны реальные ключи из config.py:

- ✅ `CRYPTOPANIC_API_KEY=390212cf54403e087e19347f4f3e4a2f4459c79c`
- ✅ `NEWSDATA_API_KEY=pub_9259f5b0818a4d40baabae05a908af4f`

## 📝 Что нужно указать

### Обязательные:

- `TELEGRAM_TOKEN` - токен основного бота
- `TELEGRAM_TOKEN_DEV` - токен для разработки
- `TELEGRAM_CHAT_IDS` - ID чатов (через запятую)

### Опциональные:

- `TRADINGVIEW_API_KEY` - для TradingView
- `ETHERSCAN_API_KEY` - для Ethereum Explorer
- `BSCSCAN_API_KEY` - для BSC Explorer
- `POLYGONSCAN_API_KEY` - для Polygon Explorer
- `ARBISCAN_API_KEY` - для Arbitrum Explorer

## ⚙️ Настройки окружения

- `ATRA_ENV=dev` - режим разработки
- `ATRA_ENV=prod` - продакшен режим

В dev режиме используется `TELEGRAM_TOKEN_DEV`, в prod - `TELEGRAM_TOKEN`.

## 🔐 Безопасность

- ✅ .env файл уже в .gitignore
- ✅ Не коммитьте .env файл в git
- ✅ Храните токены в безопасном месте

## 🎯 Готово!

После настройки токенов бот готов к работе!
