# 📊 ЛОГИКА ОТБОРА МОНЕТ В БОТЕ ATRA

## 🎯 ОБЩАЯ СХЕМА

Бот использует **двухуровневую систему отбора монет**:

### **УРОВЕНЬ 1: Источник монет**

#### **Вариант A: Фиксированный портфель (если `AUTO_FETCH_COINS=False`)**

- Используется список `COINS` из `config.py` (20 монет)
- Это оптимальный портфель, подобранный по результатам бэктестов
- Пример: `["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", ...]`

#### **Вариант B: Автоматический подбор (если `AUTO_FETCH_COINS=True`)** ⭐ **ТЕКУЩИЙ РЕЖИМ**

- Получает монеты из API Binance
- Вызывает `get_filtered_top_usdt_pairs_fast(top_n=500, final_limit=200)`
- **Итог:** до 200 монет из топ-500 по объему

---

## 📈 КРИТЕРИИ ОТБОРА (Автоматический режим)

### **1. Объем торговли (24h)**

- **Минимальный порог:** `30,000,000 USDT` (30 миллионов) ⚠️ **СНИЖЕНО с 50M**
- Источник: `RISK_FILTERS.get("min_volume_24h", 30_000_000)`
- Фильтрация: только монеты с объемом > 30M USDT

### **2. Сортировка по объему**

- Монеты сортируются по `quoteVolume` (объем в USDT) по убыванию
- Берется топ-500 монет для дальнейшей фильтрации

### **3. Whitelist/Blacklist (капитализация)**

- Используется модуль `market_cap.py` и `market_cap_blacklist.py`
- **Whitelist:** монеты с капитализацией > 100M USD (из `RISK_FILTERS["min_market_cap"]`)
- **Blacklist:** монеты из черного списка (исключаются)
- **Приоритет:** используется **только whitelist** (если монета в whitelist - она проходит)
- **Минимальная капитализация:** 100,000,000 USD (100 миллионов)

### **4. Фильтрация стейблкоинов**

- Исключаются: `USDCUSDT`, `TUSDUSDT`, `FDUSDUSDT`, `USDPUSDT`, `AEURUSDT`, `CUSDUSDT`
- Полный список: `STABLECOIN_SYMBOLS` в `config.py`

### **5. Фильтрация дублей**

- Исключаются символы типа `CAKEUSDTUSDT`, `USDEUSDTUSDT`
- Проверка: `s.count('USDT') == 1` (только одно вхождение USDT)
- Проверка: `s.endswith('USDT')` и `not s.endswith('USDTUSDT')`

### **6. Финальный лимит**

- После всех фильтров остается до **200 монет** (`final_limit=200`)
- Это максимальное количество монет для анализа

---

## 🔍 ДЕТАЛЬНАЯ ЛОГИКА

### **Функция: `get_filtered_top_usdt_pairs_fast(top_n=500, final_limit=200)`**

```python
# 1. Получаем топ-500 монет по объему с Binance
top_pairs = await get_top_usdt_pairs_by_volume(limit=500)

# 2. Фильтруем по:
#    - Минимальный объем: > 50M USDT
#    - Whitelist (капитализация)
#    - Исключаем стейблкоины
#    - Исключаем дубли

# 3. Возвращаем до 200 монет
return filtered_symbols[:200]
```

### **Функция: `get_top_usdt_pairs_by_volume(limit=500)`**

```python
# 1. Получаем все тикеры с Binance через CCXT
tickers = exchange.fetch_tickers()

# 2. Фильтруем USDT пары
usdt_pairs = {s: t for s, t in tickers.items() if s.endswith("/USDT")}

# 3. Фильтруем по объему (> 50M USDT)
filtered_pairs = {
    s: t for s, t in usdt_pairs.items()
    if t.get("quoteVolume") and t["quoteVolume"] > 50_000_000
}

# 4. Сортируем по объему (по убыванию)
sorted_pairs = sorted(filtered_pairs.values(),
                     key=lambda x: x["quoteVolume"],
                     reverse=True)

# 5. Берем топ-N и применяем whitelist
top_pairs = [pair["symbol"].replace("/", "")
             for pair in sorted_pairs[:limit * 2]]
whitelisted_pairs = [s for s in top_pairs if s in whitelisted_symbols]

# 6. Возвращаем топ-N из whitelist
return whitelisted_pairs[:limit]
```

---

## 📊 ТЕКУЩИЕ НАСТРОЙКИ

### **На сервере:**

- `AUTO_FETCH_COINS = True` (автоматический подбор)
- `top_n = 500` (берем топ-500 по объему)
- `final_limit = 200` (финальный лимит - 200 монет)
- `min_volume_24h = 30,000,000 USDT` (минимальный объем) ⚠️ **СНИЖЕНО**
- `min_market_cap = 100,000,000 USD` (минимальная капитализация)

### **Результат:**

- Бот анализирует **до 200 монет** из **топ-500 по объему**
- Все монеты имеют объем > 50M USDT
- Все монеты в whitelist (высокая капитализация)
- Исключены стейблкоины и дубли

---

## 🎯 ОТВЕТ НА ВОПРОС

**Вопрос:** "а монеты как отбираются? по объему и капитализации и из топ 200?"

**Ответ:**

1. ✅ **По объему:** Да, сортируются по 24h объему (USDT), минимум 50M USDT
2. ✅ **По капитализации:** Да, через whitelist (только монеты с высокой капитализацией)
3. ⚠️ **Из топ-200:** Не совсем - берется **топ-500 по объему**, затем фильтруется до **200 монет** по whitelist и другим критериям

**Итог:** Бот отбирает **до 200 монет** из **топ-500 по объему** с фильтрацией по:

- Объему (> 30M USDT) ⚠️ **СНИЖЕНО с 50M**
- Капитализации (> 100M USD, whitelist)
- Исключению стейблкоинов и дублей

---

**Дата:** 2025-12-01  
**Файлы:**

- `signal_live.py` (функция `get_symbols()`)
- `src/strategies/pair_filtering.py` (функции `get_filtered_top_usdt_pairs_fast()`, `get_top_usdt_pairs_by_volume()`)
- `market_cap.py` (whitelist/blacklist)
- `config.py` (настройки `AUTO_FETCH_COINS`, `COINS`, `RISK_FILTERS`)
