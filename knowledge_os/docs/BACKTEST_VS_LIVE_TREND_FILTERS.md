# 🔍 РАЗНИЦА МЕЖДУ БЭКТЕСТОМ И LIVE: ФИЛЬТРЫ BTC/ETH/SOL

**Дата:** 17.11.2025

---

## ❓ ВОПРОС

**Проверяются ли в бэктесте все три тренда (BTC, ETH, SOL) или только тот, к которому коррелирует монета?**

---

## 📊 ОТВЕТ: ЕСТЬ РАЗНИЦА!

### **В БЭКТЕСТЕ** (`scripts/run_advanced_backtest.py`)

**Логика:**

1. ✅ **BTC тренд** - проверяется **ВСЕГДА** (обязательно)
2. ⚠️ **ETH тренд** - проверяется **если данные доступны** (опционально)
3. ⚠️ **SOL тренд** - проверяется **если данные доступны** (опционально)

**Код:**

```python
# 1. BTC тренд (обязательно)
btc_trend = self.check_btc_trend(btc_df, row.name)
if btc_trend is not None:
    if (direction == "LONG" and btc_trend) or (direction == "SHORT" and not btc_trend):
        confidence += 15
    else:
        return None  # Блокируем

# 2. ETH тренд (опционально)
eth_df = getattr(self, 'eth_df', None)
if eth_df is not None and not eth_df.empty:
    eth_trend = self.check_eth_trend(eth_df, row.name)
    if eth_trend is not None:
        if (direction == "LONG" and eth_trend) or (direction == "SHORT" and not eth_trend):
            confidence += 10
        else:
            return None  # Блокируем

# 3. SOL тренд (опционально)
sol_df = getattr(self, 'sol_df', None)
if sol_df is not None and not sol_df.empty:
    sol_trend = self.check_sol_trend(sol_df, row.name)
    if sol_trend is not None:
        if (direction == "LONG" and sol_trend) or (direction == "SHORT" and not sol_trend):
            confidence += 10
        else:
            return None  # Блокируем
```

**Важно:**

- Если ETH или SOL данные **не загружены** → проверка **пропускается**
- Если ETH или SOL данные **загружены** → проверка **обязательна**

---

### **В LIVE СИСТЕМЕ** (`signal_live.py`)

**Логика:**

1. ✅ **BTC тренд** - проверяется **ВСЕГДА**
2. ✅ **ETH тренд** - проверяется **ВСЕГДА**
3. ✅ **SOL тренд** - проверяется **ВСЕГДА**

**Код:**

```python
async def check_all_trend_alignments(symbol: str, signal_type: str) -> bool:
    """Проверяет соответствие сигнала трендам BTC, ETH и SOL"""

    # Проверка BTC (всегда активна)
    if not await check_btc_alignment(symbol, signal_type):
        return False

    # Проверка ETH (всегда активна)
    if not await check_eth_alignment(symbol, signal_type):
        return False

    # Проверка SOL (всегда активна)
    if not await check_sol_alignment(symbol, signal_type):
        return False

    return True
```

**Важно:**

- Все три проверки **обязательны**
- Если хотя бы одна блокирует → сигнал **не генерируется**

---

## 🎯 КОРРЕЛЯЦИОННЫЕ ГРУППЫ

**Корреляционные группы (BTC_HIGH, ETH_HIGH, SOL_HIGH) НЕ влияют на проверку трендов!**

**Группы используются только для:**

- Лимитов на одновременные сигналы (макс. 2 сигнала в BTC_HIGH)
- Кулдаунов между сигналами в одной группе
- Статистики и отчетов

**НО НЕ для фильтрации трендов!**

**Пример:**

- `BONKUSDT` → группа `SOL_HIGH` (корреляция к SOL = 0.85)
- Но проверяются **ВСЕ ТРИ** тренда: BTC, ETH, SOL
- Не только SOL!

---

## ⚠️ ПРОБЛЕМА: НЕСООТВЕТСТВИЕ

**В бэктесте:**

- ETH и SOL проверяются **опционально** (если данные загружены)
- Если данные не загружены → проверка пропускается

**В live:**

- ETH и SOL проверяются **всегда**
- Если данные недоступны → возвращается `True` (пропускается, но логика другая)

**Результат:**

- Бэктест может показать **больше сигналов**, чем в live
- Потому что в бэктесте ETH/SOL могут не проверяться

---

## ✅ РЕКОМЕНДАЦИЯ

**Для точного соответствия бэктеста и live:**

1. **В бэктесте загружать данные ETH и SOL всегда:**

   ```python
   # В run_advanced_backtest.py
   eth_df = await loader.fetch_ohlcv("ETHUSDT", interval="1h", days=days)
   sol_df = await loader.fetch_ohlcv("SOLUSDT", interval="1h", days=days)
   ```

2. **Или изменить логику бэктеста:**
   - Сделать проверку ETH/SOL обязательной (как в live)
   - Если данные недоступны → блокировать сигнал (как в live)

3. **Или изменить логику live:**
   - Сделать проверку ETH/SOL опциональной (как в бэктесте)
   - Но это **не рекомендуется**, так как снижает качество фильтрации

---

## 📋 ИТОГ

| Аспект                 | Бэктест        | Live           |
| ---------------------- | -------------- | -------------- |
| **BTC тренд**          | ✅ Обязательно | ✅ Обязательно |
| **ETH тренд**          | ⚠️ Опционально | ✅ Обязательно |
| **SOL тренд**          | ⚠️ Опционально | ✅ Обязательно |
| **Корреляция влияет?** | ❌ Нет         | ❌ Нет         |

**Вывод:**

- В бэктесте проверяются **все три тренда**, но ETH/SOL **опционально**
- В live проверяются **все три тренда**, **всегда**
- Корреляционные группы **не влияют** на проверку трендов
- Есть **несоответствие** между бэктестом и live
