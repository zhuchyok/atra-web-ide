# ⚡ БЫСТРЫЙ ГАЙД ПО СЕРВЕРУ

## 🔗 ПОДКЛЮЧЕНИЕ:

```bash
ssh root@185.177.216.15
```

**Пароль:** `u44Ww9NmtQj,XG`

---

## 🚀 САМАЯ БЫСТРАЯ ПРОВЕРКА:

После подключения выполните **ОДНУ** команду:

```bash
cd /root/atra && ps aux | grep main.py | grep -v grep | wc -l && tail -3 system_improved.log && grep -c "callback_build" system_improved.log
```

**Результат:**

- Строка 1: **1** = бот работает ✅ | **0** = не запущен ❌ | **>1** = дубликаты ⚠️
- Строка 2-4: последние логи
- Строка 5: количество отправленных сигналов

---

## 🔧 БЫСТРОЕ ИСПРАВЛЕНИЕ:

### Если бот НЕ работает:

```bash
cd /root/atra && pkill -9 -f main.py && rm -f *.lock && export ATRA_ENV=prod && nohup python3 main.py > server.log 2>&1 & && sleep 3 && ps aux | grep main.py | grep -v grep
```

### Если есть дубликаты:

```bash
cd /root/atra && pkill -9 -f main.py && sleep 2 && rm -f *.lock && nohup python3 main.py > server.log 2>&1 & && sleep 3 && ps aux | grep main.py | grep -v grep
```

---

## 📊 МОНИТОРИНГ:

### Смотреть логи:

```bash
tail -f system_improved.log
```

### Смотреть только сигналы:

```bash
tail -f system_improved.log | grep callback_build
```

### Проверить активность:

```bash
python3 -c "import sqlite3; conn = sqlite3.connect('trading.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM telemetry_cycles WHERE datetime(ts) >= datetime(\"now\", \"-1 hours\")'); print(f'Циклов за час: {cursor.fetchone()[0]}'); conn.close()"
```

---

## ✅ КРИТЕРИИ НОРМАЛЬНОЙ РАБОТЫ:

- [ ] Процессов main.py: **ровно 1**
- [ ] Циклов за час: **> 0**
- [ ] Ошибок в логах: **минимум**
- [ ] Telegram polling: **запущен**
- [ ] Сигналы отправляются: **callback_build появляются**

---

## 🎯 ЧАСТЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ:

| Проблема                 | Команда исправления                                           |
| ------------------------ | ------------------------------------------------------------- |
| Бот не запущен           | `nohup python3 main.py > server.log 2>&1 &`                   |
| Множественные экземпляры | `pkill -9 -f main.py && rm -f *.lock`                         |
| Telegram не работает     | Проверить `grep "ERROR.*telegram" server.log`                 |
| Нет сигналов             | Проверить `grep "callback_build" system_improved.log \| tail` |
| Циклов = 0               | Полный перезапуск (см. выше)                                  |

---

## 📞 БЫСТРАЯ ПОМОЩЬ:

Если непонятно что делать - выполните:

```bash
cd /root/atra
./diagnose_server.sh
```

Это даст полную диагностику и подскажет что делать!
