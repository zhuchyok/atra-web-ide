# АУДИТ БАЗЫ ДАННЫХ И СТАТИСТИКИ

## 📊 Анализ системы хранения данных

### Основные компоненты:

#### 1. **Структура базы данных:**
- **`trading.db`** - SQLite база данных
- **Автоматические бэкапы** в папку `backups/`
- **7 основных таблиц** для разных типов данных

#### 2. **Таблицы базы данных:**
- **`fees`** - Комиссии бирж
- **`quotes`** - Котировки
- **`arbitrage_events`** - Арбитражные события
- **`pairs`** - Торговые пары
- **`manual_trades`** - Ручные сделки
- **`active_signals`** - Активные сигналы
- **`signals`** - Сигналы

#### 3. **Система бэкапов:**
- **Автоматические бэкапы** при каждом изменении
- **Хранение в папке `backups/`**
- **Откат изменений** при необходимости

### 🔧 Анализ структуры таблиц:

#### **Таблица signals:**
```sql
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,                    -- Время
    exchange TEXT,              -- Биржа
    symbol TEXT,                -- Символ
    rsi REAL,                   -- RSI
    ema_fast REAL,              -- Быстрая EMA
    ema_slow REAL,              -- Медленная EMA
    price REAL                  -- Цена
)
```
- **Плюсы**: Простая структура
- **Минусы**: Мало данных о сигналах (нет side, TP, SL, результатов)

#### **Таблица manual_trades:**
```sql
CREATE TABLE IF NOT EXISTS manual_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    symbol TEXT,
    buy_exchange TEXT,
    sell_exchange TEXT,
    buy_price REAL,
    sell_price REAL,
    amount REAL,
    notified_profit REAL,
    notified_profit_pct REAL,
    withdraw_fee REAL,
    final_profit REAL,
    final_profit_pct REAL,
    status TEXT,
    real_buy_price REAL,
    real_sell_price REAL,
    real_amount REAL,
    real_profit REAL,
    real_profit_pct REAL,
    trade_completed INTEGER DEFAULT 0
)
```
- **Плюсы**: Детальная информация о сделках
- **Минусы**: Слишком много полей, дублирование данных

#### **Таблица active_signals:**
```sql
CREATE TABLE IF NOT EXISTS active_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_key TEXT UNIQUE,
    status TEXT,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP
)
```
- **Плюсы**: Предотвращает дублирование сигналов
- **Минусы**: Минимальная информация

### 🚨 Выявленные проблемы:

#### **Проблема 1: Неполная информация о сигналах**
- **Таблица signals** хранит только базовые данные (RSI, EMA, цена)
- **Отсутствует информация о:**
  - Стороне сделки (LONG/SHORT)
  - Уровнях TP/SL
  - Результатах выполнения
  - DCA параметрах
  - Фильтрах, которые сработали

#### **Проблема 2: Отсутствие таблицы пользователей**
- **Нет централизованного хранения** настроек пользователей
- **Настройки хранятся** в `user_data.json`
- **Проблема синхронизации** между файлом и базой

#### **Проблема 3: Дублирование данных в manual_trades**
- **calculated_profit** vs **real_profit**
- **calculated_profit_pct** vs **real_profit_pct**
- **notified_profit** vs **final_profit**
- **Усложняет понимание** какая прибыль реальная

#### **Проблема 4: Отсутствие индексов**
- **Нет индексов** для быстрого поиска
- **Полные сканирования** при запросах
- **Плохие производительность** при росте данных

#### **Проблема 5: Отсутствие статистики выполнения сигналов**
- **Нет таблицы** для хранения результатов сигналов
- **Невозможно проанализировать** эффективность
- **Отсутствует история** принятых/отклоненных сигналов

#### **Проблема 6: Примитивная система бэкапов**
- **Бэкап при каждом commit** - избыточно
- **Нет ротации бэкапов** - место на диске
- **Нет проверки целостности** бэкапов

### 🔧 Рекомендации по улучшению:

#### **1. Расширение таблицы signals:**
```sql
CREATE TABLE IF NOT EXISTS enhanced_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP,
    symbol TEXT,
    side TEXT,                          -- LONG/SHORT
    entry_price REAL,
    tp1_price REAL,
    tp2_price REAL,
    sl_price REAL,
    risk_pct REAL,                      -- Процент риска
    leverage REAL,                      -- Плечо
    filter_mode TEXT,                   -- Режим фильтрации
    btc_trend_status BOOLEAN,           -- Статус BTC тренда
    news_impact TEXT,                   -- Влияние новостей
    whale_impact TEXT,                  -- Влияние китов
    anomaly_score REAL,                 -- Сила аномалии
    user_id TEXT,                       -- ID пользователя
    status TEXT,                        -- PENDING/ACCEPTED/REJECTED
    result TEXT,                        -- TP1/TP2/SL/TIMEOUT
    exit_price REAL,                    -- Цена выхода
    profit REAL,                        -- Прибыль
    profit_pct REAL,                    -- Прибыль в %
    exit_ts DATETIME,                   -- Время выхода
    dca_count INTEGER DEFAULT 0,        -- Количество DCA
    INDEX idx_symbol (symbol),
    INDEX idx_user (user_id),
    INDEX idx_status (status),
    INDEX idx_ts (ts)
);
```

#### **2. Создание таблицы пользователей:**
```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE,
    username TEXT,
    language TEXT DEFAULT 'ru',
    risk_tolerance TEXT DEFAULT 'moderate',
    filter_mode TEXT DEFAULT 'balanced',
    trade_mode TEXT DEFAULT 'spot',
    leverage REAL DEFAULT 1.0,
    deposit REAL DEFAULT 10000,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_active (is_active)
);
```

#### **3. Таблица статистики сигналов:**
```sql
CREATE TABLE IF NOT EXISTS signal_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE,
    total_signals INTEGER,
    accepted_signals INTEGER,
    rejected_signals INTEGER,
    profitable_signals INTEGER,
    losing_signals INTEGER,
    avg_profit REAL,
    avg_loss REAL,
    win_rate REAL,
    avg_holding_time INTEGER,           -- В минутах
    avg_dca_count REAL,
    by_symbol JSON,                     -- Статистика по символам
    by_filter JSON,                     -- Статистика по фильтрам
    INDEX idx_date (date)
);
```

#### **4. Улучшенная система бэкапов:**
```python
class BackupManager:
    def __init__(self, db_path, backup_dir="backups", max_backups=10):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.max_backups = max_backups

    def create_backup(self, force=False):
        """Создать бэкап с ротацией"""
        if not force and not self._should_backup():
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"trading_{timestamp}.db")

        shutil.copy2(self.db_path, backup_path)
        self._rotate_backups()

    def _should_backup(self):
        """Проверить необходимость бэкапа"""
        # Логика: бэкап каждые 100 изменений или каждый час
        pass

    def _rotate_backups(self):
        """Удалить старые бэкапы"""
        backups = sorted([
            f for f in os.listdir(self.backup_dir)
            if f.startswith("trading_") and f.endswith(".db")
        ])

        while len(backups) > self.max_backups:
            oldest = backups.pop(0)
            os.remove(os.path.join(self.backup_dir, oldest))
```

#### **5. Система аналитики:**
```python
class SignalAnalytics:
    def __init__(self, db):
        self.db = db

    def get_signal_performance(self, user_id=None, symbol=None, date_from=None, date_to=None):
        """Получить статистику выполнения сигналов"""
        query = """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN result IN ('TP1', 'TP2') THEN 1 ELSE 0 END) as profitable,
            AVG(CASE WHEN profit > 0 THEN profit ELSE NULL END) as avg_profit,
            AVG(CASE WHEN profit <= 0 THEN profit ELSE NULL END) as avg_loss,
            AVG(dca_count) as avg_dca
        FROM enhanced_signals
        WHERE status = 'ACCEPTED'
        AND exit_price IS NOT NULL
        """
        params = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if date_from:
            query += " AND ts >= ?"
            params.append(date_from)
        if date_to:
            query += " AND ts <= ?"
            params.append(date_to)

        return self.db.cursor.execute(query, params).fetchone()

    def get_filter_effectiveness(self):
        """Эффективность фильтров"""
        query = """
        SELECT
            filter_mode,
            COUNT(*) as signals,
            AVG(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as win_rate
        FROM enhanced_signals
        WHERE status = 'ACCEPTED'
        GROUP BY filter_mode
        """
        return self.db.cursor.execute(query).fetchall()
```

### 📋 План улучшений:

#### **Фаза 1: Реструктуризация таблиц**
1. Создать `enhanced_signals` таблицу с полными данными
2. Создать таблицу пользователей
3. Добавить индексы для производительности

#### **Фаза 2: Система аналитики**
1. Создать таблицу статистики сигналов
2. Добавить методы для анализа эффективности
3. Реализовать отчеты по фильтрам

#### **Фаза 3: Улучшение бэкапов**
1. Реализовать умную систему бэкапов
2. Добавить ротацию и проверку целостности
3. Оптимизировать использование места

#### **Фаза 4: Миграция данных**
1. Написать скрипт миграции из старых таблиц
2. Провести валидацию после миграции
3. Активировать новую структуру

### 🎯 Приоритеты:

#### **Высокий приоритет:**
1. Создать расширенную таблицу сигналов
2. Добавить таблицу пользователей
3. Создать систему аналитики сигналов

#### **Средний приоритет:**
1. Улучшить систему бэкапов
2. Добавить индексы для производительности
3. Реализовать миграцию данных

#### **Низкий приоритет:**
1. Добавить расширенную статистику
2. Реализовать dashboard для аналитики
3. Автоматизировать очистку старых данных

---

*Аудит базы данных завершен. Система имеет базовую функциональность, но требует значительных улучшений для надежного хранения и анализа данных.*
