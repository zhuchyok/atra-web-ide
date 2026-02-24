# Инструкции по установке TA-Lib на сервере

## 🎯 Проблема

На сервере появляется предупреждение:

```
⚠️ talib не найден, но система продолжит работу
ℹ️ talib недоступен, используется fallback режим
```

Это означает, что библиотека `talib` (Technical Analysis Library) не установлена или не работает корректно.

## 🔧 Решение

### 1. Установка системных зависимостей

**Для Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install build-essential
sudo apt-get install wget
```

**Для CentOS/RHEL:**

```bash
sudo yum groupinstall "Development Tools"
sudo yum install wget
```

### 2. Установка TA-Lib

**Способ 1: Через pip (рекомендуется)**

```bash
# Переходим в директорию проекта
cd /root/atra

# Активируем виртуальное окружение
source .venv/bin/activate

# Устанавливаем TA-Lib
pip install TA-Lib
```

**Способ 2: Ручная установка (если pip не работает)**

```bash
# Скачиваем исходники TA-Lib
cd /tmp
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/

# Компилируем и устанавливаем
./configure --prefix=/usr/local
make
sudo make install

# Обновляем переменные окружения
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
echo 'export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH' >> ~/.bashrc

# Устанавливаем Python обертку
cd /root/atra
source .venv/bin/activate
pip install TA-Lib
```

### 3. Проверка установки

**Создайте тестовый скрипт:**

```bash
cat > test_talib.py << 'EOF'
import talib
import numpy as np

# Тестовые данные
data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)

# Тестируем простой индикатор
sma = talib.SMA(data, timeperiod=3)
print("TA-Lib работает корректно!")
print(f"SMA(3): {sma}")
EOF

# Запускаем тест
python test_talib.py
```

**Ожидаемый результат:**

```
TA-Lib работает корректно!
SMA(3): [nan nan 2. 3. 4. 5. 6. 7. 8. 9.]
```

### 4. Перезапуск сервиса

```bash
# Останавливаем сервис
sudo systemctl stop myproject.service

# Запускаем сервис
sudo systemctl start myproject.service

# Проверяем статус
sudo systemctl status myproject.service

# Проверяем логи
journalctl -u myproject.service -f
```

## 🔍 Диагностика проблем

### Если установка не работает:

**1. Проверьте системные зависимости:**

```bash
# Проверьте, что gcc установлен
gcc --version

# Проверьте, что make установлен
make --version
```

**2. Проверьте права доступа:**

```bash
# Убедитесь, что у пользователя есть права на установку
sudo -u root pip install TA-Lib
```

**3. Проверьте переменные окружения:**

```bash
echo $LD_LIBRARY_PATH
echo $PATH
```

**4. Альтернативная установка через conda:**

```bash
# Если pip не работает, попробуйте conda
conda install -c conda-forge ta-lib
```

### Если TA-Lib все еще не работает:

**1. Проверьте, что библиотека найдена:**

```bash
python -c "import talib; print('TA-Lib версия:', talib.__version__)"
```

**2. Проверьте системные библиотеки:**

```bash
ldconfig -p | grep ta-lib
```

**3. Переустановите с правами root:**

```bash
sudo pip install --force-reinstall TA-Lib
```

## 📊 Проверка работы

После установки TA-Lib в логах должно появиться:

```
✅ TA-Lib успешно загружен
✅ Технические индикаторы доступны
```

Вместо:

```
⚠️ talib не найден, но система продолжит работу
ℹ️ talib недоступен, используется fallback режим
```

## 🚀 Автоматическая установка

Создайте скрипт для автоматической установки:

```bash
cat > install_talib.sh << 'EOF'
#!/bin/bash

echo "🔧 Установка TA-Lib..."

# Обновляем систему
sudo apt-get update

# Устанавливаем системные зависимости
sudo apt-get install -y build-essential wget

# Скачиваем и компилируем TA-Lib
cd /tmp
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr/local
make
sudo make install

# Обновляем переменные окружения
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
echo 'export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH' >> ~/.bashrc

# Устанавливаем Python обертку
cd /root/atra
source .venv/bin/activate
pip install TA-Lib

echo "✅ TA-Lib установлен!"
EOF

chmod +x install_talib.sh
./install_talib.sh
```

## 📅 Дата создания

6 октября 2025

## ✅ Статус

- ⏳ Требуется установка TA-Lib на сервере
- ⏳ Требуется проверка работы
- ⏳ Требуется обновление зависимостей
