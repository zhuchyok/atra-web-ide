#!/bin/bash

echo "🔧 Установка TA-Lib на сервере..."

# Проверяем, что мы в правильной директории
if [ ! -f "main.py" ]; then
    echo "❌ Ошибка: Запустите скрипт из директории проекта /root/atra"
    exit 1
fi

# Обновляем систему
echo "📦 Обновление системы..."
sudo apt-get update

# Устанавливаем системные зависимости
echo "🔧 Установка системных зависимостей..."
sudo apt-get install -y build-essential wget

# Скачиваем и компилируем TA-Lib
echo "📥 Скачивание TA-Lib..."
cd /tmp
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/

echo "🔨 Компиляция TA-Lib..."
./configure --prefix=/usr/local
make
sudo make install

# Обновляем переменные окружения
echo "🌍 Обновление переменных окружения..."
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
echo 'export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH' >> ~/.bashrc

# Устанавливаем Python обертку
echo "🐍 Установка Python обертки..."
cd /root/atra
source .venv/bin/activate
pip install TA-Lib

# Проверяем установку
echo "🧪 Проверка установки..."
python -c "import talib; print('✅ TA-Lib версия:', talib.__version__)"

if [ $? -eq 0 ]; then
    echo "✅ TA-Lib успешно установлен!"
    echo "🔄 Перезапустите сервис: sudo systemctl restart myproject.service"
else
    echo "❌ Ошибка установки TA-Lib"
    exit 1
fi
