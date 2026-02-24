# Инструкция по обновлению сервера с исправлениями DCA

## 🎯 Проблема

На сервере не работают исправления расчета средней цены и TP уровней для DCA сигналов.

## 🔧 Исправления для применения

### 1. **signal_live.py**

- Убрать комиссию из расчета средней цены
- Уменьшить комиссию в TP уровнях (0.1% вместо 0.2%)

### 2. **telegram_utils.py**

- Исправить возврат функции `dca_calculate_next_qty_and_tp`

## 📋 Способы обновления сервера

### Способ 1: Автоматический скрипт (рекомендуется)

```bash
# Запустить скрипт обновления
python3 manual_dca_fix.py
```

### Способ 2: Bash скрипт

```bash
# Сделать скрипт исполняемым
chmod +x quick_server_update.sh

# Запустить обновление
./quick_server_update.sh
```

### Способ 3: Ручное обновление

#### 1. Создать резервную копию

```bash
# Создать директорию для бэкапа
mkdir -p server_backup_$(date +%Y%m%d_%H%M%S)

# Скопировать файлы
cp signal_live.py server_backup_*/
cp telegram_utils.py server_backup_*/
```

#### 2. Остановить сервер

```bash
# Найти процесс
ps aux | grep python | grep main.py

# Остановить сервер
pkill -f "python.*main.py"
```

#### 3. Применить исправления

**В signal_live.py найти и заменить:**

```python
# БЫЛО:
# Учитываем комиссию при расчете средней цены
commission_rate = 0.001  # 0.1% комиссия
# Комиссия учитывается только для новой позиции, не для всех
new_position_cost = new_qty * price
new_position_commission = new_position_cost * commission_rate
total_cost_with_commission = sum(q * p for q, p in zip(qtys, entry_prices)) + new_position_cost + new_position_commission
avg_price_new = total_cost_with_commission / total_qty

# СТАЛО:
# Расчет средней цены БЕЗ комиссии (комиссия учитывается только в TP)
total_cost = sum(q * p for q, p in zip(qtys, entry_prices)) + new_qty * price
avg_price_new = total_cost / total_qty
```

**В signal_live.py найти и заменить:**

```python
# БЫЛО:
fee_round_frac = 0.001  # 0.1% общая комиссия (уменьшено)

# СТАЛО:
fee_round_frac = 0.0005  # 0.05% общая комиссия (еще уменьшено)
```

**В telegram_utils.py найти и заменить:**

```python
# БЫЛО:
return 0, 0

# СТАЛО:
return 0, 0, 0
```

#### 4. Запустить сервер

```bash
# Запустить сервер в фоне
nohup python3 main.py > server.log 2>&1 &

# Проверить статус
ps aux | grep python | grep main.py
```

## 🔍 Проверка обновления

### 1. Проверить статус сервера

```bash
ps aux | grep python | grep main.py
```

### 2. Проверить логи

```bash
tail -f server.log
```

### 3. Проверить работу DCA

- Отправить тестовый DCA сигнал
- Проверить расчет средней цены
- Проверить TP уровни

## 🚨 В случае проблем

### Откат к резервной копии

```bash
# Остановить сервер
pkill -f "python.*main.py"

# Восстановить файлы из бэкапа
cp server_backup_*/signal_live.py ./
cp server_backup_*/telegram_utils.py ./

# Запустить сервер
nohup python3 main.py > server.log 2>&1 &
```

### Проверка изменений

```bash
# Проверить, что изменения применены
grep -n "Расчет средней цены БЕЗ комиссии" signal_live.py
grep -n "fee_round_frac = 0.0005" signal_live.py
grep -n "return 0, 0, 0" telegram_utils.py
```

## 📊 Ожидаемые результаты

После применения исправлений:

- ✅ Средняя цена рассчитывается без комиссии
- ✅ TP уровни рассчитываются с уменьшенной комиссией (0.1%)
- ✅ Расчеты стали более точными
- ✅ DCA сигналы работают корректно

## 📞 Поддержка

Если возникли проблемы:

1. Проверьте логи сервера: `tail -f server.log`
2. Проверьте статус процесса: `ps aux | grep python`
3. Восстановите из резервной копии
4. Обратитесь за помощью
