# 🔧 BITGET TROUBLESHOOTING - ПОЧЕМУ НЕ ОТКРЫВАЕТ ПОЗИЦИИ

**Дата:** 2025-01-31

---

## 🔍 ДИАГНОСТИКА

### **ШАГ 1: Проверьте режим пользователя**

```
/mode
```

**Должно быть:**

```
🤖 Режим торговли: AUTO
🔐 Ключи Bitget: ✅ Подключены
```

**Если показывает MANUAL или ключи НЕ подключены:**

```
/connect_bitget <api_key> <secret> <passphrase>
/mode_set auto
```

---

### **ШАГ 2: Проверьте логи**

Ищите в логах строки:

```
🔍 [AUTO CHECK] user_id=<ваш_id>
🔍 [AUTO CHECK] <SYMBOL> режим: auto
🤖 [AUTO] <SYMBOL>: запуск автоисполнения для user <id>
🤖 [AUTO] <SYMBOL>: баланс=<баланс>, сумма=<сумма> USDT
```

**Если НЕТ этих строк:**

- Режим не auto
- user_id не передаётся
- Сигнал не дошёл до auto-исполнения

---

### **ШАГ 3: Проверьте ключи в БД**

Проверьте что ключи сохранены:

```python
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute("SELECT user_id, exchange_name, is_active FROM user_exchange_keys")
print(cursor.fetchall())
conn.close()
```

**Должно быть:**

```
[(your_user_id, 'bitget', 1)]
```

---

### **ШАГ 4: Проверьте доступность ccxt**

```python
import ccxt
print(ccxt.__version__)
```

**Если ошибка:**

```bash
pip install ccxt
```

---

### **ШАГ 5: Проверьте API ключи на Bitget**

Тестовый скрипт:

```python
import ccxt

bitget = ccxt.bitget({
    'apiKey': 'your_api_key',
    'secret': 'your_secret',
    'password': 'your_passphrase',
})

# Проверка баланса
try:
    balance = bitget.fetch_balance()
    print("✅ Подключение успешно!")
    print("Баланс:", balance['total'])
except Exception as e:
    print("❌ Ошибка:", e)
```

---

### **ШАГ 6: Детальное логирование**

Добавлено детальное логирование в `signal_live.py`:

```python
🔍 [AUTO CHECK] user_id=...
🔍 [AUTO CHECK] BTCUSDT режим: auto
🤖 [AUTO] BTCUSDT: запуск автоисполнения
🤖 [AUTO] BTCUSDT: баланс=1000.00, сумма=50.00 USDT
✅ [AUTO] BTCUSDT успешно открыт автоматически
```

Смотрите эти строки в логах!

---

## 🚨 ЧАСТЫЕ ПРОБЛЕМЫ

### **1. Режим Manual вместо Auto**

**Проблема:**

```
/mode показывает: 👤 MANUAL
```

**Решение:**

```
/mode_set auto
```

---

### **2. Ключи не подключены**

**Проблема:**

```
🔐 Ключи Bitget: ❌ Не подключены
```

**Решение:**

```
/connect_bitget <api_key> <secret> <passphrase>
```

---

### **3. ccxt не установлен**

**Проблема:**

```
Логи: "ccxt недоступен или ошибка инициализации"
```

**Решение:**

```bash
pip install ccxt
```

---

### **4. Неверные права API ключа**

**Проблема:**

```
Логи: "Bitget API error: insufficient permissions"
```

**Решение:**

- Пересоздайте API ключ на Bitget
- Убедитесь что включены Read + Trade
- Отключите Transfer и Withdraw

---

### **5. IP whitelist на Bitget**

**Проблема:**

```
Логи: "Bitget API error: IP not whitelisted"
```

**Решение:**

- Зайдите в Bitget API Management
- Измените IP whitelist на "All IPs" (для теста)
- Или добавьте ваш IP сервера

---

### **6. Недостаточный баланс**

**Проблема:**

```
Логи: "Bitget API error: insufficient balance"
```

**Решение:**

- Пополните баланс на Bitget
- Минимум: 50-100 USDT для тестов

---

## 📊 ЧТО ПРОВЕРИТЬ В ЛОГАХ

### **Успешное авто-исполнение:**

```
🔍 [AUTO CHECK] user_id=123456789
🔍 [AUTO CHECK] BTCUSDT режим: auto
🤖 [AUTO] BTCUSDT: запуск автоисполнения для user 123456789
🤖 [AUTO] BTCUSDT: баланс=1000.00, сумма=50.00 USDT
🔐 Ключи bitget для user 123456789 сохранены (зашифрованы)
✅ [AUTO] BTCUSDT успешно открыт автоматически
```

### **Проблема с режимом:**

```
🔍 [AUTO CHECK] user_id=123456789
🔍 [AUTO CHECK] BTCUSDT режим: manual  ← ПРОБЛЕМА!
👤 [MANUAL] BTCUSDT: пользователь в ручном режиме
```

**Решение:** `/mode_set auto`

### **Проблема с ключами:**

```
🤖 [AUTO] BTCUSDT: запуск автоисполнения
❌ Ошибка получения ключей bitget для 123456789  ← ПРОБЛЕМА!
```

**Решение:** `/connect_bitget ...`

---

## 🎯 БЫСТРАЯ ДИАГНОСТИКА

Выполните последовательно:

```
1. /mode
   Проверьте: AUTO + ключи подключены

2. Дождитесь сигнала

3. Смотрите логи:
   grep "AUTO" logs/atra.log

4. Если нет строк [AUTO] — режим не auto

5. Если есть [AUTO] но ошибки — проверьте ключи

6. Если есть [AUTO] и "успешно" — проверьте Bitget
```

---

## ✅ ПОСЛЕ ИСПРАВЛЕНИЯ

**Должны видеть:**

1. В логах: `✅ [AUTO] BTCUSDT успешно открыт`
2. В Bitget → Positions: открытая позиция
3. В боте → /positions: позиция отображается
4. Синхронизация каждые 3 мин

**ПРОВЕРЬТЕ ВСЕ ШАГИ ВЫШЕ!** 🎯
