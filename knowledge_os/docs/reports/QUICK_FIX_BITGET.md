# ⚡ БЫСТРОЕ ИСПРАВЛЕНИЕ BITGET

**Проблема:** Старые ключи зашифрованы старым ключом и не расшифровываются.

**Решение:** Удалить старые ключи и переподключить заново.

---

## 🔧 ВАРИАНТ 1: Через Telegram (РЕКОМЕНДУЕТСЯ)

Бот может не отвечать на `/disconnect_bitget`. Тогда:

**Просто переподключите ключи заново:**

```
/connect_bitget <api_key> <secret> <passphrase>
```

Это перезапишет старые ключи новыми (зашифрованными правильным ключом).

Затем:

```
/mode_set auto
```

---

## 🔧 ВАРИАНТ 2: Через SQL напрямую

Если Вариант 1 не помог, выполните вручную:

```bash
cd /Users/zhuchyok/Documents/GITHUB/atra/atra

sqlite3 trading.db "DELETE FROM user_exchange_keys;"
sqlite3 trading.db "UPDATE user_settings SET trade_mode = 'manual';"
```

Затем в боте:

```
/connect_bitget <api_key> <secret> <passphrase>
/mode_set auto
```

---

## 🔧 ВАРИАНТ 3: Через Python скрипт

```bash
cd /Users/zhuchyok/Documents/GITHUB/atra/atra
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute("DELETE FROM user_exchange_keys")
print(f"Удалено {cursor.rowcount} ключей")
cursor.execute("UPDATE user_settings SET trade_mode = 'manual'")
conn.commit()
conn.close()
print("✅ Готово!")
EOF
```

---

## ✅ САМЫЙ ПРОСТОЙ СПОСОБ

**Попробуйте просто:**

1. В боте:

```
/connect_bitget <api_key> <secret> <passphrase>
```

Это перезапишет старые ключи (используется `INSERT OR REPLACE`).

2. Перезапустите бот:

```bash
python main.py
```

3. Проверьте логи — должно быть:

```
🔐 Ключ шифрования загружен из файла 'env'
✅ Шифрование ключей активировано
✅ Ключи bitget для user <id> сохранены (зашифрованы)
```

**БЕЗ:**

```
❌ Ошибка расшифрования
```

4. Активируйте auto:

```
/mode_set auto
```

**Готово!** 🚀

---

## 📋 ПРОВЕРКА

После всех шагов проверьте:

```
/mode
```

Должно показать:

```
🤖 Режим торговли: AUTO
🔐 Ключи Bitget: ✅ Подключены
```

**Дождитесь сигнала и проверьте логи!**
