# 📦 ИСПРАВЛЕНИЕ ЗАВИСИМОСТЕЙ НА СЕРВЕРЕ

## 🚨 Проблема

На сервере отсутствуют необходимые Python пакеты:

```
ModuleNotFoundError: No module named 'flask'
ModuleNotFoundError: No module named 'pandas'
```

## ✅ РЕШЕНИЕ

### **Вариант 1: Автоматическая установка (рекомендуется)**

1. **Скопируйте файл `install_dependencies.py`** на сервер
2. **Запустите установку:**
   ```bash
   python3 install_dependencies.py
   ```

### **Вариант 2: Установка через requirements.txt**

1. **Скопируйте файл `requirements.txt`** на сервер
2. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

### **Вариант 3: Ручная установка**

```bash
# Основные пакеты
pip install flask pandas numpy requests python-dotenv

# Дополнительные пакеты
pip install matplotlib seaborn plotly scipy scikit-learn

# Технические индикаторы (может потребовать системные зависимости)
pip install TA-Lib
```

---

## 🔧 УСТАНОВКА TA-Lib (если нужен)

TA-Lib может потребовать системные зависимости:

### **Ubuntu/Debian:**

```bash
sudo apt-get update
sudo apt-get install build-essential
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
pip install TA-Lib
```

### **CentOS/RHEL:**

```bash
sudo yum groupinstall "Development Tools"
sudo yum install wget
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
pip install TA-Lib
```

---

## 🧪 ПРОВЕРКА УСТАНОВКИ

После установки проверьте:

```bash
# Проверка основных пакетов
python3 -c "import flask; print('✅ Flask работает')"
python3 -c "import pandas; print('✅ Pandas работает')"
python3 -c "import requests; print('✅ Requests работает')"

# Проверка Dashboard
python3 -c "from web.dashboard import dashboard; print('✅ Dashboard импортируется')"
```

---

## 📋 ПОЛНАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ ИСПРАВЛЕНИЯ

```bash
# 1. Установка зависимостей
python3 install_dependencies.py

# 2. Исправление демо-режима
python3 quick_fix_server.py

# 3. Перезапуск системы
pkill -f "python.*main.py"
python3 main.py
```

---

## ⚡ БЫСТРЫЕ КОМАНДЫ

### **Установка только критических пакетов:**

```bash
pip install flask pandas numpy requests python-dotenv
```

### **Полная установка одной командой:**

```bash
python3 install_dependencies.py && python3 quick_fix_server.py && pkill -f "python.*main.py" && python3 main.py
```

---

## 🚨 ЕСЛИ НЕ ПОМОГЛО

### **Проверьте версию Python:**

```bash
python3 --version
# Должно быть Python 3.7 или выше
```

### **Обновите pip:**

```bash
python3 -m pip install --upgrade pip
```

### **Попробуйте установку с --user:**

```bash
pip install --user flask pandas numpy requests
```

### **Проверьте права доступа:**

```bash
# Если ошибки прав доступа
sudo pip install flask pandas numpy requests
```

---

## 📊 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

После установки зависимостей:

1. **Dashboard должен импортироваться без ошибок**
2. **Система должна запускаться без ModuleNotFoundError**
3. **Dashboard должен работать в полноценном режиме**

---

## 🎯 ЗАКЛЮЧЕНИЕ

**Проблема:** Отсутствуют Python пакеты на сервере  
**Решение:** Установить зависимости через pip  
**Результат:** Dashboard работает в полноценном режиме

---

**Дата:** 2025-10-05  
**Статус:** ✅ Готово к применению
