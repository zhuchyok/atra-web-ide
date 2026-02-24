# 🔍 РУКОВОДСТВО ПО МОНИТОРИНГУ СИГНАЛОВ

**Дата обновления:** 2025-11-05  
**Статус:** Детальное логирование активировано

---

## 📊 Что логируется

### 1. Этапы генерации сигнала (SHORT Alt-2)

#### Quality & Confidence проверки:

```
📊 [QUALITY CHECK] SYMBOL SHORT Alt-2: Quality=X.XXX (min=0.75), Confidence=X.XXX (min=0.70)
🚫 [QUALITY BLOCK] SYMBOL SHORT Alt-2: Quality score X.XXX < 0.75
🚫 [CONFIDENCE BLOCK] SYMBOL SHORT Alt-2: Pattern confidence X.XXX < 0.70
✅ [QUALITY PASS] SYMBOL SHORT Alt-2: Quality X.XXX >= 0.75, Confidence X.XXX >= 0.70
```

#### Volume Quality проверка:

```
📊 [VOLUME QUALITY] SYMBOL SHORT: Volume quality=X.XXX (min=0.80)
🚫 [VOLUME BLOCK] SYMBOL SHORT: Volume quality X.XXX < 0.80
✅ [VOLUME PASS] SYMBOL SHORT: Volume quality X.XXX >= 0.80
```

#### MTF Confirmation проверка:

```
📊 [MTF CHECK] SYMBOL SHORT: Проверка MTF Confirmation на H4...
🚫 [MTF BLOCK] SYMBOL SHORT: MTF Confirmation не пройден: ОПИСАНИЕ ОШИБКИ
✅ [MTF PASS] SYMBOL SHORT: MTF Confirmation пройден (H4)
⚠️ [MTF ERROR] Ошибка MTF Confirmation для SYMBOL: ОПИСАНИЕ ОШИБКИ
```

#### Успешная генерация:

```
✅ [SIGNAL GENERATED] SYMBOL SHORT Alt-2: Сигнал успешно сгенерирован! Quality=X.XXX, Confidence=X.XXX
```

---

### 2. Этапы обработки сигнала

#### Обработка пользователя:

```
🔍 [PROCESS] SYMBOL: Генерация сигнала для пользователя USER_ID (mode=futures/spot)
✅ [SIGNAL GENERATED] SYMBOL: Сигнал SELL @ X.XXXXXXXX сгенерирован для пользователя USER_ID
📤 [SEND START] SYMBOL: Начало отправки сигнала SELL для пользователя USER_ID
```

#### Результат отправки:

```
✅ [SEND SUCCESS] Сигнал SELL для SYMBOL отправлен пользователю USER_ID
⚠️ [SEND FAILED] Сигнал SELL для SYMBOL НЕ отправлен пользователю USER_ID (send_signal вернул False)
🚫 [NO SIGNAL] SYMBOL: generate_signal вернул None для пользователя USER_ID
```

---

### 3. Блокировки в send_signal()

#### Начало функции:

```
📨 [SEND_SIGNAL START] SYMBOL SELL @ X.XXXXXXXX для пользователя USER_ID (mode=futures/spot)
```

#### Блокировки:

```
🚫 [SEND_SIGNAL BLOCK] SYMBOL SELL: Сигнал уже был отправлен ранее
🚫 [SEND_SIGNAL BLOCK] SYMBOL SELL: Корреляционный риск заблокирован - ПРИЧИНА
🚫 [SEND_SIGNAL BLOCK] SYMBOL SELL: Portfolio risk заблокирован - ПРИЧИНА
```

#### Успешная отправка:

```
✅ [SEND_SIGNAL SUCCESS] SYMBOL SELL: Сигнал успешно отправлен пользователю USER_ID
```

#### Ошибки:

```
❌ [SEND_SIGNAL ERROR] КРИТИЧЕСКАЯ ОШИБКА в send_signal для SYMBOL SELL: ОПИСАНИЕ ОШИБКИ
```

---

## 🔍 Как искать проблемы

### 1. Поиск блокировок SHORT сигналов:

```bash
tail -10000 bot.log | grep -E '\[QUALITY BLOCK\]|\[CONFIDENCE BLOCK\]|\[VOLUME BLOCK\]|\[MTF BLOCK\]|\[SEND_SIGNAL BLOCK\]' | tail -20
```

### 2. Поиск успешных генераций:

```bash
tail -10000 bot.log | grep -E '\[SIGNAL GENERATED\]|\[QUALITY PASS\]|\[MTF PASS\]' | tail -20
```

### 3. Поиск всех этапов для конкретного символа:

```bash
tail -10000 bot.log | grep -E 'SYMBOL.*SHORT|SYMBOL.*SELL' | tail -30
```

### 4. Мониторинг в реальном времени:

```bash
tail -f bot.log | grep -E 'SHORT|SELL|QUALITY|CONFIDENCE|MTF|SEND_SIGNAL'
```

---

## 📋 Типичные причины блокировки

### 1. Quality Score < 0.75

- **Причина:** Низкое качество сигнала (недостаточно подтверждений индикаторов)
- **Решение:** Проверить RSI, MACD, ADX, Volume Ratio

### 2. Pattern Confidence < 0.70

- **Причина:** Низкая надежность паттерна
- **Решение:** Проверить силу тренда, качество данных

### 3. Volume Quality < 0.80

- **Причина:** Обнаружены манипуляции объемом
- **Решение:** Проверить объемы на бирже

### 4. MTF Confirmation не пройден

- **Причина:** Сигнал не подтвержден на H4 таймфрейме
- **Решение:** Проверить доступность данных H4, логику подтверждения

### 5. Корреляционный риск

- **Причина:** Слишком много сигналов в одной группе корреляции
- **Решение:** Проверить активные позиции пользователя

### 6. Portfolio risk

- **Причина:** Превышен лимит позиций или риска
- **Решение:** Проверить настройки портфеля

---

## ✅ Следующие шаги

1. **Мониторить логи** в реальном времени при следующем SHORT сигнале
2. **Идентифицировать** точное место блокировки
3. **Проанализировать** причину блокировки
4. **Применить исправление** если необходимо

---

## 📊 Текущие пороги для SHORT сигналов

- **Quality Score:** ≥ 0.75 (выше, чем для LONG: 0.70)
- **Pattern Confidence:** ≥ 0.70 (выше, чем для LONG: 0.60)
- **Volume Quality:** ≥ 0.80 (для SHORT Alt-2)
- **MTF Confirmation:** Обязательно для SHORT Alt-2
