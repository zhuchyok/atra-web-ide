# 📊 РУКОВОДСТВО ПО МОНИТОРИНГУ БЛОКИРОВОК СИГНАЛОВ

**Дата:** 2025-11-06  
**Статус:** Активное мониторинг

---

## 🚀 БЫСТРЫЙ СТАРТ

### 1. Запуск мониторинга в реальном времени:

```bash
./monitor_signal_blocks.sh
```

### 2. Анализ блокировок за последние 6 часов:

```bash
./analyze_signal_blocks.sh 6
```

### 3. Анализ за последние 12 часов:

```bash
./analyze_signal_blocks.sh 12
```

---

## 📊 ОТСЛЕЖИВАЕМЫЕ СОБЫТИЯ

### **Direction Check:**

- `✅ [DIRECTION CHECK]` - сигнал прошел проверку (3/4 или 4/4)
- `🚫 [DIRECTION CHECK]` - недостаточно подтверждений (1/4 или 2/4)

### **Quality Score:**

- `✅ [QUALITY PASS]` - Quality score >= 0.70, Confidence >= 0.60
- `🚫 [QUALITY BLOCK]` - Quality score < 0.70 или Confidence < 0.60

### **RSI Warning:**

- `🚫 [RSI FILTER]` - RSI в опасной зоне (BUY: RSI > 65, SELL: RSI < 35)

### **Volume Quality:**

- `🚫 [VOLUME BLOCK]` - Volume quality < 0.80 (манипуляции объемом)

### **False Breakout:**

- `🚫 [BREAKOUT BLOCK]` - False breakout обнаружен

### **MTF Confirmation:**

- `✅ [MTF PASS]` - MTF подтвержден на H4
- `🚫 [MTF BLOCK]` - MTF не подтвержден на H4

### **Send Signal:**

- `🚫 [SEND_SIGNAL BLOCK]` - сигнал заблокирован при отправке
- `✅ [PRODUCTION]` - сигнал успешно отправлен

### **No Signal:**

- `🚫 [NO SIGNAL]` - generate_signal вернул None

---

## 🔍 АНАЛИЗ БЛОКИРОВОК

### **Проверка текущих блокировок:**

```bash
# Все блокировки за последний час
tail -5000 bot.log | grep -E "BLOCK|NO SIGNAL" | tail -20

# Конкретный символ
tail -5000 bot.log | grep "SYMBOLUSDT" | grep -E "BLOCK|PASS|NO SIGNAL"

# Quality Score блокировки
tail -5000 bot.log | grep "QUALITY BLOCK"
```

### **Статистика по типам блокировок:**

```bash
# Direction Check
tail -5000 bot.log | grep -c "DIRECTION CHECK.*3/4"
tail -5000 bot.log | grep -c "DIRECTION CHECK.*2/4"

# Quality Score
tail -5000 bot.log | grep -c "QUALITY PASS"
tail -5000 bot.log | grep -c "QUALITY BLOCK"

# RSI Warning
tail -5000 bot.log | grep -c "RSI.*FILTER"

# Volume Quality
tail -5000 bot.log | grep -c "VOLUME BLOCK"

# False Breakout
tail -5000 bot.log | grep -c "BREAKOUT BLOCK"

# MTF Confirmation
tail -5000 bot.log | grep -c "MTF PASS"
tail -5000 bot.log | grep -c "MTF BLOCK"
```

---

## 📈 ИНТЕРПРЕТАЦИЯ РЕЗУЛЬТАТОВ

### **Нормальная ситуация:**

- Direction Check: 20-30% проходят (3/4)
- Quality Score: 50-70% проходят после Direction Check
- RSI Warning: блокирует 30-50% сигналов
- Финально отправлено: 5-15% от исходных сигналов

### **Проблемная ситуация:**

- Direction Check: < 10% проходят
- Quality Score: < 30% проходят
- Финально отправлено: 0 сигналов

### **Оптимизация:**

- Если Quality Score блокирует > 50% сигналов → анализировать компоненты
- Если RSI Warning блокирует > 70% сигналов → проверить рыночные условия
- Если MTF блокирует > 80% сигналов → проверить доступность данных H4

---

## 🎯 КЛЮЧЕВЫЕ ВОПРОСЫ ДЛЯ АНАЛИЗА

### **1. Почему Quality Score низкий?**

- Проверить компоненты: Data Quality, Trend Strength, Volume, Volatility, RSI
- Найти "слабые места" снижающие score

### **2. Где пропадают сигналы после Quality PASS?**

- Проверить Volume Quality, False Breakout, MTF Confirmation
- Проверить блокировки в send_signal

### **3. Можно ли оптимизировать без ослабления защиты?**

- Адаптивные веса по рыночному режиму
- Адаптивные пороги по рыночному режиму
- Улучшение компонентов Quality Score

---

## 📋 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

### **После сбора данных (2-3 часа):**

- ✅ Точное понимание где блокируются сигналы
- ✅ Статистика по каждому фильтру
- ✅ Топ-5 символов с блокировками
- ✅ Детальный анализ Quality Score

### **После анализа:**

- ✅ Оптимизация Quality Score компонентов
- ✅ Устранение узких мест в pipeline
- ✅ Увеличение количества качественных сигналов
- ✅ Сохранение всех защитных механизмов

---

## 🚀 СЛЕДУЮЩИЕ ШАГИ

1. ✅ Запустить мониторинг на 2-3 часа
2. ✅ Собрать статистику блокировок
3. ✅ Проанализировать Quality Score компоненты
4. ✅ Найти оптимизации без ослабления защиты
