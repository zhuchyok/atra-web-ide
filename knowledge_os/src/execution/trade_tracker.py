#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль отслеживания реальных сделок для расчета метрик производительности
Интегрируется с auto_execution.py и telegram_handlers.py
"""

import logging
import sqlite3
from datetime import datetime
from typing import Dict, Optional, List, Any
import os

logger = logging.getLogger(__name__)


class TradeTracker:
    """Отслеживание и запись реальных сделок в БД"""
    
    def __init__(self, db_path: str = "trading.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Инициализация таблицы trades в БД"""
        try:
            schema_file = os.path.join(os.path.dirname(__file__), "database_schema_trades.sql")
            if os.path.exists(schema_file):
                with open(schema_file, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                # Выполняем только CREATE TABLE и индексы (игнорируем остальное если таблица уже существует)
                for statement in schema_sql.split(';'):
                    statement = statement.strip()
                    if statement and statement.upper().startswith(('CREATE TABLE', 'CREATE INDEX', 'CREATE VIEW', 'CREATE TRIGGER')):
                        try:
                            cursor.execute(statement)
                        except sqlite3.OperationalError as e:
                            if "already exists" not in str(e).lower():
                                logger.warning("Ошибка выполнения SQL: %s - %s", statement[:50], e)
                conn.commit()
                conn.close()
                logger.info("✅ Таблица trades инициализирована")
            else:
                # Создаем таблицу напрямую если файла нет
                self._create_trades_table()
        except Exception as e:
            logger.error("❌ Ошибка инициализации таблицы trades: %s", e)
            self._create_trades_table()
    
    def _create_trades_table(self):
        """Создание таблицы trades напрямую"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    entry_time DATETIME NOT NULL,
                    exit_time DATETIME NOT NULL,
                    duration_minutes REAL,
                    quantity REAL NOT NULL,
                    position_size_usdt REAL NOT NULL,
                    leverage REAL DEFAULT 1.0,
                    risk_percent REAL,
                    pnl_usd REAL NOT NULL,
                    pnl_percent REAL NOT NULL,
                    fees_usd REAL DEFAULT 0.0,
                    net_pnl_usd REAL NOT NULL,
                    exit_reason TEXT NOT NULL,
                    tp1_price REAL,
                    tp2_price REAL,
                    sl_price REAL,
                    tp1_hit BOOLEAN DEFAULT 0,
                    tp2_hit BOOLEAN DEFAULT 0,
                    sl_hit BOOLEAN DEFAULT 0,
                    signal_key TEXT,
                    user_id TEXT,
                    trade_mode TEXT DEFAULT 'futures',
                    filter_mode TEXT DEFAULT 'strict',
                    confidence REAL,
                    dca_count INTEGER DEFAULT 0,
                    max_drawdown_pct REAL DEFAULT 0.0,
                    max_profit_pct REAL DEFAULT 0.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Создаем индексы
            for index_sql in [
                "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)",
                "CREATE INDEX IF NOT EXISTS idx_trades_exit_time ON trades(exit_time)",
                "CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_trades_exit_reason ON trades(exit_reason)",
            ]:
                cursor.execute(index_sql)
            
            conn.commit()
            conn.close()
            logger.info("✅ Таблица trades создана")
        except Exception as e:
            logger.error("❌ Ошибка создания таблицы trades: %s", e)
    
    async def record_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        entry_time: datetime,
        exit_time: datetime,
        quantity: float,
        position_size_usdt: float,
        leverage: float = 1.0,
        risk_percent: Optional[float] = None,
        fees_usd: float = 0.0,
        exit_reason: str = 'MANUAL',
        tp1_price: Optional[float] = None,
        tp2_price: Optional[float] = None,
        sl_price: Optional[float] = None,
        signal_key: Optional[str] = None,
        user_id: Optional[str] = None,
        trade_mode: str = 'futures',
        filter_mode: str = 'strict',
        confidence: Optional[float] = None,
        dca_count: int = 0,
    ) -> Optional[int]:
        """
        Записывает закрытую сделку в БД
        
        Returns:
            ID созданной записи или None при ошибке
        """
        try:
            # Нормализуем direction
            direction = direction.upper()
            if direction == 'BUY':
                direction = 'LONG'
            elif direction == 'SELL':
                direction = 'SHORT'
            
            # Рассчитываем PnL
            if direction == 'LONG':
                pnl_usd = (exit_price - entry_price) * quantity
            else:  # SHORT
                pnl_usd = (entry_price - exit_price) * quantity
            
            pnl_percent = (pnl_usd / position_size_usdt) * 100 if position_size_usdt > 0 else 0
            net_pnl_usd = pnl_usd - fees_usd
            
            # Рассчитываем длительность
            duration_minutes = (exit_time - entry_time).total_seconds() / 60
            
            # Определяем какие TP/SL сработали
            tp1_hit = False
            tp2_hit = False
            sl_hit = False
            
            if exit_reason == 'TP1':
                tp1_hit = True
            elif exit_reason == 'TP2':
                tp2_hit = True
            elif exit_reason == 'SL':
                sl_hit = True
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO trades (
                    symbol, direction, entry_price, exit_price,
                    entry_time, exit_time, duration_minutes,
                    quantity, position_size_usdt, leverage, risk_percent,
                    pnl_usd, pnl_percent, fees_usd, net_pnl_usd,
                    exit_reason, tp1_price, tp2_price, sl_price,
                    tp1_hit, tp2_hit, sl_hit,
                    signal_key, user_id, trade_mode, filter_mode,
                    confidence, dca_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, direction, entry_price, exit_price,
                entry_time.isoformat(), exit_time.isoformat(), duration_minutes,
                quantity, position_size_usdt, leverage, risk_percent,
                pnl_usd, pnl_percent, fees_usd, net_pnl_usd,
                exit_reason, tp1_price, tp2_price, sl_price,
                tp1_hit, tp2_hit, sl_hit,
                signal_key, user_id, trade_mode, filter_mode,
                confidence, dca_count
            ))
            
            trade_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info("✅ Сделка записана: %s %s %s (ID: %d, PnL: %.2f USDT / %.2f%%)",
                       symbol, direction, exit_reason, trade_id, net_pnl_usd, pnl_percent)
            
            return trade_id
            
        except Exception as e:
            logger.error("❌ Ошибка записи сделки: %s", e, exc_info=True)
            return None
    
    def get_trades(
        self,
        user_id: Optional[str] = None,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Получает список сделок с фильтрацией
        
        Returns:
            Список словарей с данными сделок
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM trades WHERE 1=1"
            params = []
            
            if user_id:
                query += " AND user_id = ?"
                params.append(str(user_id))
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if start_date:
                query += " AND exit_time >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND exit_time <= ?"
                params.append(end_date.isoformat())
            
            query += " ORDER BY exit_time DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            trades = []
            for row in rows:
                trade = dict(row)
                # Конвертируем datetime строки обратно
                if trade.get('entry_time'):
                    trade['entry_time'] = datetime.fromisoformat(trade['entry_time'])
                if trade.get('exit_time'):
                    trade['exit_time'] = datetime.fromisoformat(trade['exit_time'])
                trades.append(trade)
            
            return trades
            
        except Exception as e:
            logger.error("❌ Ошибка получения сделок: %s", e)
            return []


# Singleton instance
_trade_tracker_instance = None

def get_trade_tracker(db_path: str = "trading.db") -> TradeTracker:
    """Получить экземпляр TradeTracker (singleton)"""
    global _trade_tracker_instance
    if _trade_tracker_instance is None:
        _trade_tracker_instance = TradeTracker(db_path)
    return _trade_tracker_instance
