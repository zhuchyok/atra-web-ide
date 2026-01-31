# 📋 ИНСТРУКЦИИ ПО ДЕПЛОЮ: Компенсация проскальзывания

## 🚀 ДЕПЛОЙ НА СЕРВЕР

### Вариант 1: Использование скрипта (рекомендуется)

```bash
# На сервере выполните:
cd /root/atra
bash <(curl -s https://raw.githubusercontent.com/your-repo/atra/insight/scripts/deploy_slippage_to_server.sh)
```

Или скопируйте скрипт на сервер и выполните:
```bash
scp scripts/deploy_slippage_to_server.sh root@185.177.216.15:/root/
ssh root@185.177.216.15 "bash /root/deploy_slippage_to_server.sh"
```

### Вариант 2: Ручной деплой

```bash
# 1. Подключитесь к серверу
ssh root@185.177.216.15

# 2. Перейдите в директорию проекта
cd /root/atra

# 3. Обновите код
git pull

# 4. Проверьте синтаксис
python3 -m py_compile slippage_manager.py order_manager.py signal_live.py

# 5. Проверьте импорты
python3 -c "from slippage_manager import get_slippage_manager; sm = get_slippage_manager(); print('✅ SlippageManager работает')"

# 6. Перезапустите сервис
systemctl restart signal_live

# 7. Проверьте статус
systemctl status signal_live

# 8. Проверьте логи
journalctl -u signal_live -n 100 --no-pager | grep -i slippage
```

## ✅ ПРОВЕРКА РАБОТОСПОСОБНОСТИ

### 1. Проверка импортов
```bash
python3 -c "from slippage_manager import get_slippage_manager; print('OK')"
```

### 2. Проверка создания SlippageManager
```bash
python3 -c "from slippage_manager import get_slippage_manager; sm = get_slippage_manager(); print('✅ SlippageManager:', type(sm).__name__)"
```

### 3. Проверка методов
```bash
python3 -c "
from slippage_manager import get_slippage_manager
sm = get_slippage_manager()
print('✅ calculate_dynamic_slippage:', hasattr(sm, 'calculate_dynamic_slippage'))
print('✅ should_use_limit_order:', hasattr(sm, 'should_use_limit_order'))
print('✅ get_adjusted_position_size:', hasattr(sm, 'get_adjusted_position_size'))
"
```

### 4. Проверка логов сервиса
```bash
# Общие логи
journalctl -u signal_live -n 50 --no-pager

# Фильтр по slippage
journalctl -u signal_live -n 100 --no-pager | grep -i slippage

# Фильтр по ошибкам
journalctl -u signal_live -n 100 --no-pager | grep -i error
```

### 5. Проверка статуса сервиса
```bash
systemctl status signal_live
```

## 🔍 ЧТО ПРОВЕРЯТЬ В ЛОГАХ

### Успешная инициализация:
```
✅ SlippageManager инициализирован
✅ Таблица slippage_records инициализирована
```

### Использование компенсации:
```
💰 [SLIPPAGE COMPENSATION] SYMBOL: размер скорректирован X → Y USDT
```

### Использование limit ордеров:
```
🎯 [ORDER OPTIMIZATION] SYMBOL: используем LIMIT ордер @ PRICE
```

### Ошибки (не должны появляться):
```
❌ Ошибка инициализации БД проскальзывания
❌ Ошибка расчета динамического проскальзывания
```

## 🛠️ УСТРАНЕНИЕ ПРОБЛЕМ

### Проблема: SlippageManager не импортируется
```bash
# Проверьте наличие файла
ls -la /root/atra/slippage_manager.py

# Проверьте синтаксис
python3 -m py_compile slippage_manager.py
```

### Проблема: Ошибка БД
```bash
# Проверьте права на файл БД
ls -la /root/atra/trading.db

# Если нужно, создайте БД вручную
python3 -c "from slippage_manager import get_slippage_manager; get_slippage_manager()"
```

### Проблема: Сервис не запускается
```bash
# Проверьте логи
journalctl -u signal_live -n 100 --no-pager

# Проверьте конфигурацию
systemctl cat signal_live
```

## 📊 МОНИТОРИНГ

После деплоя следите за:
1. Логами компенсации проскальзывания
2. Использованием limit ордеров
3. Записями в БД `slippage_records`
4. Отсутствием ошибок

## ✅ КРИТЕРИИ УСПЕШНОГО ДЕПЛОЯ

- ✅ Сервис запущен без ошибок
- ✅ SlippageManager инициализирован
- ✅ Нет ошибок в логах
- ✅ Компенсация применяется (видно в логах)
- ✅ БД `slippage_records` создана

