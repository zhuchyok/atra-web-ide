# 🚀 РУЧНОЙ ЗАПУСК БОТА

Терминал не показывает вывод команд. Выполните вручную:

---

## СПОСОБ 1: Через скрипт

```bash
cd /Users/zhuchyok/Documents/GITHUB/atra/atra
chmod +x restart_bot.sh
./restart_bot.sh
```

---

## СПОСОБ 2: Команды по отдельности

```bash
cd /Users/zhuchyok/Documents/GITHUB/atra/atra

# 1. Остановите процессы
pkill -9 -f "python.*main.py"

# 2. Очистите БД
sqlite3 trading.db "DELETE FROM user_exchange_keys; DELETE FROM user_settings;"

# 3. Активируйте venv
source venv/bin/activate

# 4. Запустите бот
python main.py
```

---

## ПРОВЕРКА ЗАПУСКА

Должны увидеть:

```
🔐 Ключ шифрования загружен из файла 'env'
✅ Шифрование ключей активировано
✅ Telegram бот успешно запущен
```

**БЕЗ:**

```
❌ Ошибка расшифрования
```

---

## ПОСЛЕ ЗАПУСКА

В Telegram:

```
/start
```

Если ответил — готово к подключению ключей:

```
/connect_bitget bg_1539f9c919af347de1d72ef821cfd4d5 4b520626324237087d7795768603fbaddc2cd8bf50cbd1977170a067c970a838 Bik36745618OS

/mode_set auto

/mode
```

**Готово!** 🚀
