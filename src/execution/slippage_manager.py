import sqlite3
import logging
import time
from typing import Dict, Optional, Any
from datetime import datetime
from src.core.exceptions import DatabaseQueryError, DatabaseError

logger = logging.getLogger(__name__)

class SlippageManager:
    """Менеджер компенсации проскальзывания"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SlippageManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.db_path = "trading.db"
        self._init_db()
        
        # Настройки порогов ликвидности (USD)
        self.high_liquidity_threshold = 100_000_000
        self.medium_liquidity_threshold = 10_000_000
        
        # Базовое проскальзывание
        self.high_liquidity_slippage = 0.0005      # 0.05%
        self.medium_liquidity_slippage = 0.001     # 0.1%
        self.low_liquidity_slippage = 0.002        # 0.2%
        self.very_low_liquidity_slippage = 0.005   # 0.5%
        
        # Параметры оптимизации
        self.limit_order_threshold = 0.0015        # 0.15% - порог для перехода на limit
        self.limit_price_offset = 0.0005           # 0.05% - отступ для limit цены
        self.compensation_threshold = 0.0015       # 0.15% - порог для компенсации размера
        self.max_compensation_pct = 0.1            # 10% - максимальная корректировка размера
        
        self._initialized = True
        logger.info("✅ SlippageManager инициализирован")

    def _init_db(self):
        """Инициализация таблицы в БД"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS slippage_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    expected_price REAL NOT NULL,
                    actual_price REAL NOT NULL,
                    slippage_pct REAL NOT NULL,
                    volume_24h REAL,
                    order_size_usd REAL,
                    volatility REAL,
                    order_id TEXT,
                    timestamp REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """)
                logger.info("✅ Таблица slippage_records инициализирована")
        except Exception as e:
            logger.error("❌ Ошибка инициализации БД SlippageManager: %s", e)

    def calculate_dynamic_slippage(self, 
                                 symbol: str, 
                                 volume_24h: Optional[float] = None,
                                 order_size_usd: Optional[float] = None,
                                 volatility: Optional[float] = None) -> float:
        """Рассчитывает ожидаемое динамическое проскальзывание"""
        
        # 1. Базовое проскальзывание на основе ликвидности
        if volume_24h is None or volume_24h <= 0:
            slippage = self.medium_liquidity_slippage
        elif volume_24h >= self.high_liquidity_threshold:
            slippage = self.high_liquidity_slippage
        elif volume_24h >= self.medium_liquidity_threshold:
            slippage = self.medium_liquidity_slippage
        else:
            slippage = self.low_liquidity_slippage
            
        # 2. Корректировка на основе размера ордера
        if order_size_usd and volume_24h and volume_24h > 0:
            # Если ордер > 0.01% от дневного объема, увеличиваем проскальзывание
            size_factor = (order_size_usd / volume_24h) * 1000
            if size_factor > 1:
                slippage *= (1 + min(size_factor, 5))
                
        # 3. Корректировка на основе волатильности
        if volatility and volatility > 0.02: # Если волатильность > 2%
            slippage *= (1 + (volatility * 10))
            
        return float(slippage)

    def record_slippage(self,
                       symbol: str,
                       side: str,
                       expected_price: float,
                       actual_price: float,
                       volume_24h: Optional[float] = None,
                       order_size_usd: Optional[float] = None,
                       volatility: Optional[float] = None,
                       order_id: Optional[str] = None):
        """Записывает реальное проскальзывание в БД"""
        try:
            if expected_price <= 0:
                return
                
            side = side.lower()
            if side == 'buy':
                slippage_pct = (actual_price - expected_price) / expected_price
            else:
                slippage_pct = (expected_price - actual_price) / expected_price
                
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                INSERT INTO slippage_records 
                (symbol, side, expected_price, actual_price, slippage_pct, 
                 volume_24h, order_size_usd, volatility, order_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (symbol, side, expected_price, actual_price, slippage_pct,
                      volume_24h, order_size_usd, volatility, order_id, time.time()))
                
            logger.debug("📊 Recorded slippage for %s: %.4f%%", symbol, slippage_pct * 100)
        except Exception as e:
            logger.error("❌ Ошибка записи проскальзывания: %s", e)

    def should_use_limit_order(self,
                             symbol: str,
                             side: str,
                             current_price: float,
                             volume_24h: Optional[float] = None,
                             order_size_usd: Optional[float] = None,
                             volatility: Optional[float] = None) -> Dict[str, Any]:
        """Определяет, стоит ли использовать limit ордер вместо market"""
        
        expected_slippage = self.calculate_dynamic_slippage(
            symbol, volume_24h, order_size_usd, volatility
        )
        
        # Получаем среднее реальное проскальзывание из БД
        avg_real_slippage = self._get_avg_slippage(symbol)
        
        # Итоговая оценка риска проскальзывания
        risk_score = max(expected_slippage, avg_real_slippage)
        
        use_limit = risk_score > self.limit_order_threshold
        
        limit_price = current_price
        if use_limit:
            if side.lower() == 'buy':
                limit_price = current_price * (1 + self.limit_price_offset)
            else:
                limit_price = current_price * (1 - self.limit_price_offset)
                
        return {
            'use_limit': use_limit,
            'limit_price': float(limit_price),
            'expected_slippage': float(expected_slippage),
            'potential_savings': float(risk_score * 100),
            'reason': "High expected slippage" if use_limit else "Normal liquidity"
        }

    def get_adjusted_position_size(self,
                                 symbol: str,
                                 base_position_size: float,
                                 volume_24h: Optional[float] = None) -> float:
        """Корректирует размер позиции для компенсации проскальзывания"""
        
        avg_slippage = self._get_avg_slippage(symbol)
        
        if avg_slippage > self.compensation_threshold:
            # Уменьшаем размер позиции, чтобы итоговый риск (с учетом проскальзывания) остался прежним
            reduction = min(avg_slippage, self.max_compensation_pct)
            adjusted_size = base_position_size * (1 - reduction)
            logger.info("📉 Reduced size for %s: %.2f -> %.2f (slippage: %.4f%%)",
                       symbol, base_position_size, adjusted_size, avg_slippage * 100)
            return float(adjusted_size)
            
        return float(base_position_size)

    def _get_avg_slippage(self, symbol: str, limit: int = 5) -> float:
        """Получает среднее проскальзывание за последние N сделок"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT slippage_pct FROM slippage_records WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                    (symbol, limit)
                )
                rows = cursor.fetchall()
                if not rows:
                    return 0.0
                return sum(row[0] for row in rows) / len(rows)
        except (sqlite3.Error, DatabaseQueryError, DatabaseError) as e:
            logging.debug("Ошибка получения среднего проскальзывания: %s", e)
            return 0.0

    def get_symbol_statistics(self, symbol: str) -> Dict[str, Any]:
        """Возвращает статистику проскальзывания по символу"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*), AVG(slippage_pct), MAX(slippage_pct)
                    FROM slippage_records WHERE symbol = ?
                """, (symbol,))
                row = cursor.fetchone()
                return {
                    'count': row[0] or 0,
                    'avg_slippage_pct': (row[1] or 0.0) * 100,
                    'max_slippage_pct': (row[2] or 0.0) * 100
                }
        except (sqlite3.Error, DatabaseQueryError, DatabaseError) as e:
            logging.debug("Ошибка получения статистики проскальзывания для %s: %s", symbol, e)
            return {'count': 0, 'avg_slippage_pct': 0.0, 'max_slippage_pct': 0.0}

    def should_wait_for_better_liquidity(self, symbol: str, current_volume: float) -> Dict[str, Any]:
        """Проверяет, стоит ли подождать лучшей ликвидности (H4.4)"""
        # Упрощенная реализация: если текущий объем сильно ниже среднего
        avg_vol = self._get_avg_volume(symbol)
        if avg_vol > 0 and current_volume < (avg_vol * 0.5):
            wait_time = min(120, (1 - current_volume/avg_vol) * 200) # до 2 мин
            return {
                'should_wait': True,
                'wait_time_sec': int(wait_time),
                'reason': f"Current volume ({current_volume:.0f}) is too low vs average ({avg_vol:.0f})"
            }
        return {'should_wait': False, 'wait_time_sec': 0}

    def _get_avg_volume(self, symbol: str) -> float:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT AVG(volume_24h) FROM slippage_records WHERE symbol = ?", (symbol,)
                )
                return cursor.fetchone()[0] or 0.0
        except (sqlite3.Error, DatabaseQueryError, DatabaseError) as e:
            logging.debug("Ошибка получения среднего объема для %s: %s", symbol, e)
            return 0.0

def get_slippage_manager() -> SlippageManager:
    """Возвращает экземпляр SlippageManager (Singleton)"""
    return SlippageManager()

