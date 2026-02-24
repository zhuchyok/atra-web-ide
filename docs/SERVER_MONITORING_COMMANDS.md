# КОМАНДЫ МОНИТОРИНГА НА СЕРВЕРЕ

## 🚀 Запуск мониторинга на сервере:

### 1. **Быстрый мониторинг:**

```bash
# Перейти в директорию проекта
cd ~/atra

# Запустить мониторинг
./start_monitoring.sh
```

### 2. **Прямой запуск Python мониторинга:**

```bash
cd ~/atra
python3 terminal_monitor.py
```

### 3. **Мониторинг логов в реальном времени:**

```bash
# Основные логи
tail -f system_improved.log

# Все логи одновременно
tail -f *.log

# Логи с фильтром
tail -f system_improved.log | grep -E "(ERROR|WARNING|INFO)"
```

### 4. **Проверка статуса системы:**

```bash
# Процессы
ps aux | grep main.py

# Использование ресурсов
top -bn1 | head -20

# Дисковое пространство
df -h

# Память
free -h
```

### 5. **Мониторинг через systemd (если используется):**

```bash
# Статус сервиса
sudo systemctl status atra

# Логи сервиса
sudo journalctl -u atra -f

# Последние логи
sudo journalctl -u atra --since "1 hour ago"
```

### 6. **Мониторинг через PM2 (если используется):**

```bash
# Статус процессов
pm2 list

# Логи в реальном времени
pm2 logs

# Мониторинг ресурсов
pm2 monit
```

### 7. **Комбинированный мониторинг:**

```bash
# Создать скрипт полного мониторинга
cat > monitor_server.sh << 'EOF'
#!/bin/bash
while true; do
    clear
    echo "=== МОНИТОРИНГ СЕРВЕРА $(date) ==="
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

chmod +x monitor_server.sh
./monitor_server.sh
```

### 8. **Мониторинг в фоновом режиме:**

```bash
# Запустить мониторинг в фоне
nohup python3 terminal_monitor.py > monitoring.log 2>&1 &

# Проверить, что запустился
ps aux | grep terminal_monitor

# Посмотреть логи мониторинга
tail -f monitoring.log
```

### 9. **Удаленный мониторинг:**

```bash
# Если сервер удаленный, подключиться по SSH
ssh user@server_ip

# Запустить мониторинг
cd ~/atra
./start_monitoring.sh
```

### 10. **Мониторинг через tmux (рекомендуется):**

```bash
# Создать сессию tmux
tmux new-session -d -s monitoring

# Войти в сессию
tmux attach -t monitoring

# Запустить мониторинг
cd ~/atra
python3 terminal_monitor.py

# Отключиться (сессия продолжит работать)
# Нажать Ctrl+B, затем D

# Вернуться к сессии
tmux attach -t monitoring
```

## 🎯 **Рекомендуемая последовательность:**

1. **Подключиться к серверу:**

   ```bash
   ssh user@server_ip
   ```

2. **Перейти в директорию проекта:**

   ```bash
   cd ~/atra
   ```

3. **Запустить мониторинг:**

   ```bash
   ./start_monitoring.sh
   ```

4. **Для постоянного мониторинга использовать tmux:**
   ```bash
   tmux new-session -d -s monitoring 'cd ~/atra && python3 terminal_monitor.py'
   tmux attach -t monitoring
   ```

## ✅ **Проверка работы:**

- **Процессы:** `ps aux | grep main.py`
- **Логи:** `tail -f system_improved.log`
- **Ресурсы:** `top` или `htop`
- **Статус сервиса:** `sudo systemctl status atra` (если используется systemd)
