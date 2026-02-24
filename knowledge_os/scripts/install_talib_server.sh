#!/bin/bash

echo "🔧 Установка TA-Lib на сервере..."
echo "=================================="

# Проверяем, что мы в правильной директории
if [ ! -f "main.py" ]; then
    echo "❌ Ошибка: Запустите скрипт из директории проекта"
    echo "   Текущая директория: $(pwd)"
    echo "   Ожидается файл: main.py"
    exit 1
fi

# Определяем тип системы
if [ -f /etc/debian_version ]; then
    DISTRO="debian"
    echo "📦 Обнаружена Debian/Ubuntu система"
elif [ -f /etc/redhat-release ]; then
    DISTRO="redhat"
    echo "📦 Обнаружена RedHat/CentOS система"
else
    DISTRO="unknown"
    echo "⚠️ Неизвестная система, пробуем Debian подход"
fi

# Функция для установки зависимостей
install_dependencies() {
    echo "📦 Установка системных зависимостей..."

    if [ "$DISTRO" = "debian" ]; then
        sudo apt-get update
        sudo apt-get install -y build-essential wget libffi-dev python3-dev
    elif [ "$DISTRO" = "redhat" ]; then
        sudo yum groupinstall -y "Development Tools"
        sudo yum install -y wget libffi-devel python3-devel
    else
        echo "⚠️ Неизвестная система, пробуем установить базовые зависимости"
        sudo apt-get update || true
        sudo apt-get install -y build-essential wget || true
    fi
}

# Функция для компиляции и установки TA-Lib
install_talib() {
    echo "📥 Скачивание и компиляция TA-Lib..."

    # Создаем временную директорию
    TEMP_DIR="/tmp/talib_install_$$"
    mkdir -p "$TEMP_DIR"
    cd "$TEMP_DIR"

    # Скачиваем TA-Lib
    echo "📥 Скачивание TA-Lib..."
    wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz

    if [ $? -ne 0 ]; then
        echo "❌ Ошибка скачивания TA-Lib"
        exit 1
    fi

    # Распаковываем
    echo "📦 Распаковка TA-Lib..."
    tar -xzf ta-lib-0.4.0-src.tar.gz
    cd ta-lib/

    # Компилируем
    echo "🔨 Компиляция TA-Lib..."
    ./configure --prefix=/usr/local

    if [ $? -ne 0 ]; then
        echo "❌ Ошибка конфигурации TA-Lib"
        exit 1
    fi

    make

    if [ $? -ne 0 ]; then
        echo "❌ Ошибка компиляции TA-Lib"
        exit 1
    fi

    # Устанавливаем
    echo "📦 Установка TA-Lib..."
    sudo make install

    if [ $? -ne 0 ]; then
        echo "❌ Ошибка установки TA-Lib"
        exit 1
    fi

    # Очищаем временную директорию
    cd /
    rm -rf "$TEMP_DIR"
}

# Функция для настройки переменных окружения
setup_environment() {
    echo "🌍 Настройка переменных окружения..."

    # Обновляем LD_LIBRARY_PATH
    export LD_LIBRARY_PATH="/usr/local/lib:$LD_LIBRARY_PATH"

    # Добавляем в .bashrc
    if ! grep -q "LD_LIBRARY_PATH=/usr/local/lib" ~/.bashrc; then
        echo 'export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
        echo "✅ LD_LIBRARY_PATH добавлен в ~/.bashrc"
    fi

    # Обновляем ldconfig
    echo "/usr/local/lib" | sudo tee /etc/ld.so.conf.d/talib.conf
    sudo ldconfig

    echo "✅ Переменные окружения настроены"
}

# Функция для установки Python обертки
install_python_wrapper() {
    echo "🐍 Установка Python обертки TA-Lib..."

    # Проверяем, есть ли виртуальное окружение
    if [ -d "venv" ]; then
        echo "🔧 Активируем виртуальное окружение..."
        source venv/bin/activate
    elif [ -d ".venv" ]; then
        echo "🔧 Активируем виртуальное окружение..."
        source .venv/bin/activate
    fi

    # Устанавливаем TA-Lib
    pip install TA-Lib

    if [ $? -ne 0 ]; then
        echo "❌ Ошибка установки Python обертки TA-Lib"
        echo "🔧 Пробуем установку с правами root..."
        sudo pip install TA-Lib
    fi
}

# Функция для проверки установки
verify_installation() {
    echo "🧪 Проверка установки TA-Lib..."

    # Проверяем системные библиотеки
    echo "📚 Проверка системных библиотек..."
    if ldconfig -p | grep -q ta-lib; then
        echo "✅ Системные библиотеки TA-Lib найдены"
    else
        echo "⚠️ Системные библиотеки TA-Lib не найдены"
    fi

    # Проверяем Python модуль
    echo "🐍 Проверка Python модуля..."
    python3 -c "
import talib
import numpy as np
print('✅ TA-Lib версия:', talib.__version__)

# Тестируем простой индикатор
data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
sma = talib.SMA(data, timeperiod=3)
print('✅ SMA тест пройден:', sma[-1])
"

    if [ $? -eq 0 ]; then
        echo "✅ TA-Lib успешно установлен и работает!"
        return 0
    else
        echo "❌ Ошибка проверки TA-Lib"
        return 1
    fi
}

# Функция для создания fallback режима
create_fallback() {
    echo "🔧 Создание fallback режима..."

    # Создаем улучшенный talib_wrapper.py
    cat > talib_wrapper.py << 'EOF'
#!/usr/bin/env python3
"""
Универсальный wrapper для talib с автоматическим fallback
"""

import sys
import os
import site
import warnings

# Подавляем предупреждения talib
warnings.filterwarnings("ignore", category=UserWarning, module="talib")

def get_talib():
    """Получает talib модуль с автоматическим fallback"""

    # Сначала пробуем стандартный импорт
    try:
        import talib
        print("✅ talib успешно загружен")
        return talib
    except ImportError:
        pass

    # Если не получилось, ищем talib в различных местах
    possible_paths = [
        # Стандартные пути Python
        "/usr/local/lib/python3.9/site-packages",
        "/usr/local/lib/python3.10/site-packages",
        "/usr/local/lib/python3.11/site-packages",
        "/usr/local/lib/python3.12/site-packages",
        "/usr/lib/python3.9/site-packages",
        "/usr/lib/python3.10/site-packages",
        "/usr/lib/python3.11/site-packages",
        "/usr/lib/python3.12/site-packages",
        # Пользовательские пути
        os.path.expanduser("~/.local/lib/python3.9/site-packages"),
        os.path.expanduser("~/.local/lib/python3.10/site-packages"),
        os.path.expanduser("~/.local/lib/python3.11/site-packages"),
        os.path.expanduser("~/.local/lib/python3.12/site-packages"),
        # Виртуальные окружения
        os.path.join(os.getcwd(), "venv", "lib", "python3.9", "site-packages"),
        os.path.join(os.getcwd(), "venv", "lib", "python3.10", "site-packages"),
        os.path.join(os.getcwd(), "venv", "lib", "python3.11", "site-packages"),
        os.path.join(os.getcwd(), "venv", "lib", "python3.12", "site-packages"),
    ]

    # Добавляем пути к sys.path
    for path in possible_paths:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)

    # Пробуем импортировать talib после добавления путей
    try:
        import talib
        print("✅ talib найден в дополнительных путях")
        return talib
    except ImportError:
        pass

    # Последняя попытка - ищем через site-packages
    try:
        for site_dir in site.getsitepackages():
            talib_path = os.path.join(site_dir, "talib")
            if os.path.exists(talib_path):
                sys.path.insert(0, site_dir)
                try:
                    import talib
                    print(f"✅ talib найден в {site_dir}")
                    return talib
                except ImportError:
                    continue
    except (OSError, ImportError, RuntimeError):
        pass

    # Если talib не найден, используем fallback
    print("⚠️ talib не найден, используется fallback режим")
    return None

# Глобальная переменная для talib
_talib = get_talib()

# Создаем fallback функции если talib недоступен
if _talib is None:
    print("🔧 Создание fallback функций для talib...")

    # Создаем заглушки для основных функций talib
    class TalibFallback:
        """Fallback класс для talib функций"""

        @staticmethod
        def SMA(data, timeperiod=30):
            """Простая скользящая средняя"""
            import pandas as pd
            return pd.Series(data).rolling(window=timeperiod).mean().values

        @staticmethod
        def EMA(data, timeperiod=30):
            """Экспоненциальная скользящая средняя"""
            import pandas as pd
            return pd.Series(data).ewm(span=timeperiod).mean().values

        @staticmethod
        def RSI(data, timeperiod=14):
            """RSI индикатор"""
            import pandas as pd
            delta = pd.Series(data).diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=timeperiod).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=timeperiod).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.values

        @staticmethod
        def BBANDS(data, timeperiod=20, nbdevup=2, nbdevdn=2):
            """Полосы Боллинджера"""
            import pandas as pd
            series = pd.Series(data)
            middle = series.rolling(window=timeperiod).mean()
            std = series.rolling(window=timeperiod).std()
            upper = middle + (std * nbdevup)
            lower = middle - (std * nbdevdn)
            return upper.values, middle.values, lower.values

        @staticmethod
        def ATR(high, low, close, timeperiod=14):
            """Average True Range"""
            import pandas as pd
            high_series = pd.Series(high)
            low_series = pd.Series(low)
            close_series = pd.Series(close)

            tr1 = high_series - low_series
            tr2 = abs(high_series - close_series.shift(1))
            tr3 = abs(low_series - close_series.shift(1))

            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=timeperiod).mean()
            return atr.values

    # Заменяем talib на fallback
    _talib = TalibFallback()
    print("✅ Fallback режим активирован")

# Экспортируем talib или fallback
if _talib is not None:
    # Экспортируем все функции talib
    globals().update(_talib.__dict__)
EOF

    echo "✅ Создан улучшенный talib_wrapper.py"
}

# Главная функция
main() {
    echo "🚀 Начинаем установку TA-Lib на сервере..."

    # 1. Устанавливаем зависимости
    install_dependencies

    # 2. Компилируем и устанавливаем TA-Lib
    install_talib

    # 3. Настраиваем переменные окружения
    setup_environment

    # 4. Устанавливаем Python обертку
    install_python_wrapper

    # 5. Проверяем установку
    if verify_installation; then
        echo "🎉 TA-Lib успешно установлен!"
        echo "🔄 Перезапустите сервис: sudo systemctl restart atra.service"
    else
        echo "⚠️ TA-Lib не установлен, создаем fallback режим..."
        create_fallback
        echo "✅ Fallback режим создан, система будет работать без talib"
    fi

    echo ""
    echo "📋 Следующие шаги:"
    echo "1. Перезапустите сервис: sudo systemctl restart atra.service"
    echo "2. Проверьте логи: journalctl -u atra.service -f"
    echo "3. Проверьте работу: python3 -c \"from talib_wrapper import get_talib; print('talib доступен:', get_talib() is not None)\""
}

# Запускаем главную функцию
main "$@"
