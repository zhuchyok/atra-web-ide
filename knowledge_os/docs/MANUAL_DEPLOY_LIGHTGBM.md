# 🚀 РУЧНОЙ ДЕПЛОЙ LIGHTGBM НА СЕРВЕР

## ⚠️ ПРОБЛЕМА С АВТОМАТИЧЕСКИМ ДЕПЛОЕМ

Автоматический деплой через SSH не работает без интерактивной сессии.
**Нужно выполнить команды вручную на сервере.**

---

## 📋 ИНСТРУКЦИЯ ДЛЯ РУЧНОГО ДЕПЛОЯ

### Шаг 1: Подключиться к серверу

```bash
ssh root@185.177.216.15
# Ввести пароль: u44Ww9NmtQj,XG
```

### Шаг 2: Обновить код

```bash
cd /root/atra
git fetch origin
git checkout insight
git pull origin insight
```

**Если git push не прошел и изменений нет на сервере:**

- Нужно сначала отправить изменения локально через GitHub UI или другой способ
- Или использовать альтернативный способ (см. ниже)

### Шаг 3: Установить зависимости

```bash
# Для Linux (Ubuntu/Debian):
apt-get update
apt-get install -y libomp-dev
python3 -m pip install lightgbm scikit-learn

# Проверить установку:
python3 -c "import lightgbm; print('✅ LightGBM установлен')"
```

### Шаг 4: Обучить модели

```bash
# Перейти в директорию проекта
cd /root/atra

# Обучить модели
python3 train_lightgbm_models.py
```

**Ожидаемый результат:**

```
✅ Классификатор обучен: ROC-AUC=1.0000, Accuracy=99.72%
✅ Регрессор обучен: MAE=0.0521%, R²=0.9639
✅ Модели сохранены
```

### Шаг 5: Перезапустить систему

```bash
# Остановить текущий процесс
pkill -f "python.*main.py"
sleep 2

# Запустить заново
nohup python3 main.py > main.log 2>&1 &

# Проверить статус
ps aux | grep "python.*main.py" | grep -v grep
```

### Шаг 6: Проверить работу

```bash
# Проверить логи LightGBM
tail -50 main.log | grep -i lightgbm

# Должно быть:
# ✅ LightGBM предсказатель доступен и модели загружены
# ✅ Автоматическое переобучение LightGBM запущено

# Проверить наличие моделей
ls -lh ai_learning_data/lightgbm_models/

# Должны быть файлы:
# - classifier.txt
# - regressor.txt
# - metadata.json
```

---

## 🔄 АЛЬТЕРНАТИВНЫЙ СПОСОБ (если git pull не работает)

### Если изменения не попали на сервер через git:

**Вариант 1: Скопировать файлы напрямую**

На локальной машине:

```bash
# Создать архив с файлами
tar -czf lightgbm_files.tar.gz \
  lightgbm_predictor.py \
  lightgbm_auto_retrain.py \
  train_lightgbm_models.py \
  deploy_lightgbm.sh

# Отправить на сервер (потребуется пароль)
scp lightgbm_files.tar.gz root@185.177.216.15:/root/atra/
```

На сервере:

```bash
cd /root/atra
tar -xzf lightgbm_files.tar.gz
rm lightgbm_files.tar.gz

# Теперь установить зависимости и обучить (Шаги 3-6 выше)
```

**Вариант 2: Создать файлы вручную на сервере**

Используйте содержимое файлов из локальной версии проекта.

---

## ✅ ЧЕКЛИСТ ПРОВЕРКИ

После деплоя проверить:

- [ ] Код обновлен (`git pull` выполнен)
- [ ] LightGBM установлен (`python3 -c "import lightgbm"`)
- [ ] Модели обучены (`ls ai_learning_data/lightgbm_models/`)
- [ ] Система перезапущена (`ps aux | grep main.py`)
- [ ] В логах есть сообщения LightGBM (`tail main.log | grep LightGBM`)
- [ ] ML фильтр работает (есть логи `ML PREDICTION`)

---

## 📊 ОЖИДАЕМЫЕ ЛОГИ

После успешного деплоя в `main.log` должно быть:

```
✅ LightGBM предсказатель доступен и модели загружены
✅ Автоматическое переобучение LightGBM запущено
  ⏰ Интервал проверки: каждые 168 часов (7 дней)
  📊 Минимум новых паттернов: 1000
```

При генерации сигналов:

```
🤖 [ML PREDICTION] BTCUSDT BUY: success_prob=75.23%, expected_profit=2.45%, combined_score=1.842, recommendation=BUY
✅ [ML PASS] BTCUSDT LONG CLASSIC: ML фильтр пройден
```

---

**Статус**: ⚠️ Требуется ручной деплой
**Дата**: 2025-01-XX
