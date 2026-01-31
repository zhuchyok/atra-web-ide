# 🚀 ДЕПЛОЙ LIGHTGBM НА СЕРВЕР

## 📋 ЧТО НУЖНО ПРИМЕНИТЬ

### Новые файлы:
1. ✅ `lightgbm_predictor.py` - основной модуль LightGBM
2. ✅ `lightgbm_auto_retrain.py` - автоматическое переобучение
3. ✅ `train_lightgbm_models.py` - скрипт обучения
4. ✅ `deploy_lightgbm.sh` - скрипт деплоя

### Измененные файлы:
1. ✅ `signal_live.py` - интеграция ML фильтра
2. ✅ `main.py` - запуск автоматического переобучения

---

## 🔧 ШАГИ ДЕПЛОЯ

### Вариант 1: Автоматический деплой (рекомендуется)

```bash
# 1. Закоммитить изменения
git add lightgbm_predictor.py lightgbm_auto_retrain.py train_lightgbm_models.py
git add signal_live.py main.py deploy_lightgbm.sh
git commit -m "feat: Добавлена LightGBM система для ML фильтрации сигналов"
git push origin insight

# 2. Запустить скрипт деплоя
./deploy_lightgbm.sh
```

### Вариант 2: Ручной деплой

```bash
# 1. Подключиться к серверу
ssh root@185.177.216.15

# 2. Обновить код
cd /root/atra
git fetch origin
git checkout insight
git pull origin insight

# 3. Установить зависимости
# Для Linux (Ubuntu/Debian):
apt-get update && apt-get install -y libomp-dev
python3 -m pip install lightgbm scikit-learn

# Для macOS на сервере:
brew install libomp
export LDFLAGS="-L/opt/homebrew/opt/libomp/lib"
export CPPFLAGS="-I/opt/homebrew/opt/libomp/include"
python3 -m pip install lightgbm scikit-learn

# 4. Обучить модели
python3 train_lightgbm_models.py

# 5. Перезапустить систему
pkill -f "python.*main.py"
nohup python3 main.py > main.log 2>&1 &
```

---

## ✅ ПРОВЕРКА ДЕПЛОЯ

### 1. Проверить логи при запуске:

```bash
tail -50 main.log | grep -i lightgbm
```

**Ожидаемый вывод:**
```
✅ LightGBM предсказатель доступен и модели загружены
✅ Автоматическое переобучение LightGBM запущено
  ⏰ Интервал проверки: каждые 168 часов (7 дней)
  📊 Минимум новых паттернов: 1000
```

### 2. Проверить наличие моделей:

```bash
ls -lh ai_learning_data/lightgbm_models/
```

**Должны быть файлы:**
- `classifier.txt`
- `regressor.txt`
- `metadata.json`

### 3. Проверить работу ML фильтра:

В логах при генерации сигналов должны появляться:
```
🤖 [ML PREDICTION] BTCUSDT BUY: success_prob=75.23%, expected_profit=2.45%, combined_score=1.842, recommendation=BUY
✅ [ML PASS] BTCUSDT LONG CLASSIC: ML фильтр пройден
```

---

## ⚠️ ВОЗМОЖНЫЕ ПРОБЛЕМЫ

### Проблема 1: libomp не найден

**Решение:**
```bash
# Ubuntu/Debian:
apt-get install libomp-dev

# macOS:
brew install libomp
export LDFLAGS="-L/opt/homebrew/opt/libomp/lib"
export CPPFLAGS="-I/opt/homebrew/opt/libomp/include"
```

### Проблема 2: Модели не обучены

**Решение:**
```bash
# Обучить вручную:
python3 train_lightgbm_models.py

# Проверить наличие данных:
python3 -c "import json; data=json.load(open('ai_learning_data/trading_patterns.json')); print(f'Паттернов: {len(data)}')"
```

### Проблема 3: LightGBM не импортируется

**Решение:**
```bash
# Переустановить:
python3 -m pip uninstall lightgbm -y
python3 -m pip install lightgbm

# Проверить:
python3 -c "import lightgbm; print('OK')"
```

---

## 📊 МОНИТОРИНГ ПОСЛЕ ДЕПЛОЯ

### Проверить статус автоматического переобучения:

```bash
tail -100 main.log | grep -i "переобучение\|retrain"
```

### Проверить работу ML фильтра:

```bash
tail -100 main.log | grep -i "ML PREDICTION\|ML PASS\|ML BLOCK"
```

### Проверить метрики моделей:

```bash
cat ai_learning_data/lightgbm_models/metadata.json | python3 -m json.tool
```

---

## 🎯 ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

После успешного деплоя:

1. ✅ LightGBM модели обучены и загружены
2. ✅ ML фильтр работает в signal_live.py
3. ✅ Автоматическое переобучение запущено
4. ✅ В логах появляются ML предсказания
5. ✅ Сигналы фильтруются по ML score

---

**Статус**: ✅ Готово к деплою
**Дата**: 2025-01-XX

