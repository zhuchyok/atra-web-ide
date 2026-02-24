# БЫСТРЫЕ КОМАНДЫ ДЛЯ СЕРВЕРА

## 🚀 Команды для копирования на сервер:

### 1. **Проверка статуса бота:**

```bash
# Проверить процессы
ps aux | grep main.py

# Проверить логи
tail -n 10 system_improved.log

# Проверить ресурсы
top -bn1 | head -20
```

### 2. **Мониторинг логов в реальном времени:**

```bash
# Основные логи
tail -f system_improved.log

# Все логи
tail -f *.log

# Логи с фильтром
tail -f system_improved.log | grep -E "(ERROR|WARNING|INFO)"
```

### 3. **Простой мониторинг (скопировать и запустить):**

```bash
# Создать файл мониторинга
cat > monitor.sh << 'EOF'
#!/bin/bash
while true; do
    clear
    echo "=== МОНИТОРИНГ $(date) ==="
    echo ""
    echo "🔄 Процессы main.py:"
    ps aux | grep main.py | grep -v grep
    echo ""
    echo "💻 Ресурсы:"
    echo "CPU: $(top -bn1 | grep 'Cpu(s)' | awk '{print $2}')"
    echo "RAM: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
    echo ""
    echo "📝 Последние логи:"
    tail -n 5 system_improved.log 2>/dev/null || echo "Лог не найден"
    echo ""
    echo "Обновление через 10 секунд... (Ctrl+C для выхода)"
    sleep 10
done
EOF

chmod +x monitor.sh
./monitor.sh
```

### 4. **Запуск бота (если не запущен):**

```bash
# Остановить старые процессы
pkill -f main.py

# Запустить бота
nohup python3 main.py > main.log 2>&1 &

# Проверить, что запустился
ps aux | grep main.py
```

### 5. **Перезапуск бота:**

```bash
# Остановить
pkill -f main.py

# Подождать
sleep 3

# Запустить
nohup python3 main.py > main.log 2>&1 &

# Проверить
ps aux | grep main.py
```

### 6. **Мониторинг через tmux:**

```bash
# Создать сессию
tmux new-session -d -s monitoring

# Войти в сессию
tmux attach -t monitoring

# Запустить мониторинг
tail -f system_improved.log

# Отключиться (Ctrl+B, затем D)
# Вернуться: tmux attach -t monitoring
```

### 7. **Быстрая проверка системы:**

```bash
echo "=== СТАТУС СИСТЕМЫ ==="
echo "Процессы:"
ps aux | grep main.py | grep -v grep
echo ""
echo "Логи:"
tail -n 3 system_improved.log 2>/dev/null || echo "Лог не найден"
echo ""
echo "Ресурсы:"
top -bn1 | head -5
```

### 8. **Мониторинг в фоне:**

```bash
# Запустить мониторинг в фоне
nohup bash -c 'while true; do echo "$(date): $(ps aux | grep main.py | grep -v grep | wc -l) процессов"; sleep 30; done' > monitor.log 2>&1 &

# Проверить логи мониторинга
tail -f monitor.log
```

## 🎯 **Рекомендуемая последовательность:**

1. **Подключиться к серверу:**

   ```bash
   ssh root@server_ip
   cd ~/atra
   ```

2. **Проверить статус:**

   ```bash
   ps aux | grep main.py
   ```

3. **Если бот не запущен:**

   ```bash
   nohup python3 main.py > main.log 2>&1 &
   ```

4. **Запустить мониторинг:**

   ```bash
   tail -f system_improved.log
   ```

5. **Для постоянного мониторинга:**
   ```bash
   tmux new-session -d -s monitoring 'tail -f system_improved.log'
   tmux attach -t monitoring
   ```

## ✅ **Проверка работы:**

- **Процессы:** `ps aux | grep main.py`
- **Логи:** `tail -f system_improved.log`
- **Ресурсы:** `top` или `htop`
- **Статус:** `systemctl status atra` (если используется systemd)
