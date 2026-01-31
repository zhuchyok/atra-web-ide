#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💰 Мониторинг прибыльности системы - Елена (Monitor) + Максим (Data Analyst)

Постоянное отслеживание:
- Win Rate
- Средний убыток vs средняя прибыль
- Соотношение убытков к прибыли
- Проблемные символы
- Автоматические алерты при ухудшении показателей
"""

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from collections import defaultdict
from decimal import Decimal

logger = logging.getLogger(__name__)


class ProfitabilityMonitor:
    """
    Мониторинг прибыльности торговой системы
    
    Ответственный: Елена (Monitor) - постоянное отслеживание показателей
    Аналитик: Максим (Data Analyst) - анализ данных и метрики
    """
    
    def __init__(self, db_path: str = "trading.db"):
        self.db_path = db_path
        self.monitoring_interval = 3600  # Проверка каждый час
        self.alert_thresholds = {
            'min_win_rate': 0.40,  # Минимальный Win Rate 40%
            'max_loss_profit_ratio': 3.0,  # Максимальное соотношение убытков к прибыли 3:1
            'max_avg_loss': -1.5,  # Максимальный средний убыток -1.5 USDT
            'min_avg_profit': 0.3,  # Минимальная средняя прибыль 0.3 USDT
        }
        self.is_running = False
        
    async def start_monitoring(self):
        """Запуск постоянного мониторинга"""
        self.is_running = True
        logger.info("💰 [Елена] Запуск мониторинга прибыльности системы")
        
        while self.is_running:
            try:
                await self.check_profitability_metrics()
                await asyncio.sleep(self.monitoring_interval)
            except Exception as e:
                logger.error(f"❌ [Елена] Ошибка мониторинга: {e}", exc_info=True)
                await asyncio.sleep(60)  # Короткая пауза при ошибке
    
    def stop_monitoring(self):
        """Остановка мониторинга"""
        self.is_running = False
        logger.info("💰 [Елена] Остановка мониторинга прибыльности")
    
    async def check_profitability_metrics(self) -> Dict[str, Any]:
        """
        Проверка показателей прибыльности за последние 24 часа
        
        Ответственный: Елена (Monitor) + Максим (Data Analyst)
        """
        try:
            # Получаем данные из БД
            metrics = await self._calculate_metrics_24h()
            
            # 🆕 АНАЛИЗ ВРЕМЕНИ - Максим (Data Analyst): Обновление худших периодов
            # 🔧 ИСПРАВЛЕНО: Улучшенная обработка и автоматическое включение блокировки
            try:
                from src.analysis.time_analysis import get_time_analysis
                time_analysis = get_time_analysis(self.db_path)
                time_analysis_result = time_analysis.analyze_win_rate_by_time(days=30)
                
                if 'error' in time_analysis_result:
                    # Нет данных - это нормально для новой системы
                    if time_analysis_result.get('total_trades', 0) == 0:
                        logger.debug(f"📊 [Максим] Анализ времени: {time_analysis_result.get('message', 'Нет данных')}")
                    else:
                        logger.warning(f"⚠️ [Максим] Ошибка анализа времени: {time_analysis_result.get('error')}")
                else:
                    # Данные есть - логируем результаты
                    total_trades = time_analysis_result.get('total_trades', 0)
                    worst_hours = time_analysis_result.get('worst_hours', [])
                    worst_weekdays = time_analysis_result.get('worst_weekdays', [])
                    enable_blocking = time_analysis_result.get('enable_blocking', False)
                    
                    logger.info(
                        f"📊 [Максим] Анализ времени: {total_trades} сделок, "
                        f"блокировка={'включена' if enable_blocking else 'отключена'}, "
                        f"худшие часы: {sorted(worst_hours) if worst_hours else 'нет'}, "
                        f"худшие дни: {sorted(worst_weekdays) if worst_weekdays else 'нет'}"
                    )
                    
                    if 'recommendations' in time_analysis_result:
                        for rec in time_analysis_result['recommendations']:
                            logger.info(f"📊 [Максим] {rec}")
            except Exception as e:
                logger.debug(f"Ошибка анализа времени: {e}")
            
            # Проверяем пороги
            alerts = self._check_thresholds(metrics)
            
            # Логируем результаты
            self._log_metrics(metrics, alerts)
            
            # Отправляем алерты при необходимости
            if alerts:
                await self._send_alerts(alerts, metrics)
            
            # Сохраняем метрики
            await self._save_metrics(metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ [Елена] Ошибка проверки метрик: {e}", exc_info=True)
            return {}
    
    async def _calculate_metrics_24h(self) -> Dict[str, Any]:
        """
        Расчёт метрик за последние 24 часа
        
        Аналитик: Максим (Data Analyst)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Время 24 часа назад
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            
            # Получаем закрытые сделки из signals_log
            query = """
                SELECT 
                    symbol,
                    side,
                    entry_price,
                    exit_price,
                    net_profit,
                    result,
                    created_at,
                    exit_time
                FROM signals_log
                WHERE exit_time IS NOT NULL
                  AND exit_time >= ?
                  AND result IS NOT NULL
                ORDER BY exit_time DESC
            """
            
            cursor.execute(query, (since.isoformat(),))
            rows = cursor.fetchall()
            
            if not rows:
                logger.info("📊 [Максим] Нет закрытых сделок за последние 24 часа")
                return {
                    'total_trades': 0,
                    'winners': 0,
                    'losers': 0,
                    'win_rate': 0.0,
                    'total_pnl': 0.0,
                    'avg_profit': 0.0,
                    'avg_loss': 0.0,
                    'loss_profit_ratio': 0.0,
                    'problematic_symbols': []
                }
            
            # Анализируем сделки
            winners = []
            losers = []
            symbol_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'pnl': 0.0})
            
            for row in rows:
                pnl = float(row['net_profit'] or 0)
                symbol = row['symbol']
                
                if pnl > 0:
                    winners.append(pnl)
                    symbol_stats[symbol]['wins'] += 1
                    symbol_stats[symbol]['pnl'] += pnl
                else:
                    losers.append(pnl)
                    symbol_stats[symbol]['losses'] += 1
                    symbol_stats[symbol]['pnl'] += pnl
            
            total_trades = len(rows)
            win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0.0
            total_pnl = sum(winners) + sum(losers)
            avg_profit = (sum(winners) / len(winners)) if winners else 0.0
            avg_loss = (sum(losers) / len(losers)) if losers else 0.0
            
            # Соотношение убытков к прибыли
            total_profit = sum(winners) if winners else 0.0
            total_loss = abs(sum(losers)) if losers else 0.0
            loss_profit_ratio = (total_loss / total_profit) if total_profit > 0 else 0.0
            
            # Проблемные символы (Win Rate < 30% или убытки > 5 USDT)
            problematic_symbols = []
            for symbol, stats in symbol_stats.items():
                symbol_trades = stats['wins'] + stats['losses']
                if symbol_trades > 0:
                    symbol_wr = (stats['wins'] / symbol_trades * 100)
                    if symbol_wr < 30 or stats['pnl'] < -5.0:
                        problematic_symbols.append({
                            'symbol': symbol,
                            'win_rate': symbol_wr,
                            'pnl': stats['pnl'],
                            'trades': symbol_trades
                        })
            
            conn.close()
            
            return {
                'total_trades': total_trades,
                'winners': len(winners),
                'losers': len(losers),
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_profit': avg_profit,
                'avg_loss': avg_loss,
                'loss_profit_ratio': loss_profit_ratio,
                'total_profit': total_profit,
                'total_loss': total_loss,
                'problematic_symbols': problematic_symbols,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ [Максим] Ошибка расчёта метрик: {e}", exc_info=True)
            return {}
    
    def _check_thresholds(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Проверка порогов и генерация алертов
        
        Ответственный: Елена (Monitor)
        """
        alerts = []
        
        if not metrics or metrics.get('total_trades', 0) == 0:
            return alerts
        
        # Проверка Win Rate
        win_rate = metrics.get('win_rate', 0.0)
        if win_rate < (self.alert_thresholds['min_win_rate'] * 100):
            alerts.append({
                'type': 'LOW_WIN_RATE',
                'severity': 'HIGH',
                'message': f"⚠️ КРИТИЧНО: Win Rate {win_rate:.1f}% ниже порога {self.alert_thresholds['min_win_rate']*100:.0f}%",
                'value': win_rate,
                'threshold': self.alert_thresholds['min_win_rate'] * 100
            })
        
        # Проверка соотношения убытков к прибыли
        loss_profit_ratio = metrics.get('loss_profit_ratio', 0.0)
        if loss_profit_ratio > self.alert_thresholds['max_loss_profit_ratio']:
            alerts.append({
                'type': 'HIGH_LOSS_PROFIT_RATIO',
                'severity': 'HIGH',
                'message': f"⚠️ КРИТИЧНО: Соотношение убытков к прибыли {loss_profit_ratio:.1f}:1 превышает порог {self.alert_thresholds['max_loss_profit_ratio']:.1f}:1",
                'value': loss_profit_ratio,
                'threshold': self.alert_thresholds['max_loss_profit_ratio']
            })
        
        # Проверка среднего убытка
        avg_loss = metrics.get('avg_loss', 0.0)
        if avg_loss < self.alert_thresholds['max_avg_loss']:
            alerts.append({
                'type': 'HIGH_AVG_LOSS',
                'severity': 'MEDIUM',
                'message': f"⚠️ Средний убыток {avg_loss:.2f} USDT превышает порог {self.alert_thresholds['max_avg_loss']:.2f} USDT",
                'value': avg_loss,
                'threshold': self.alert_thresholds['max_avg_loss']
            })
        
        # Проверка средней прибыли
        avg_profit = metrics.get('avg_profit', 0.0)
        if avg_profit < self.alert_thresholds['min_avg_profit']:
            alerts.append({
                'type': 'LOW_AVG_PROFIT',
                'severity': 'MEDIUM',
                'message': f"⚠️ Средняя прибыль {avg_profit:.2f} USDT ниже порога {self.alert_thresholds['min_avg_profit']:.2f} USDT",
                'value': avg_profit,
                'threshold': self.alert_thresholds['min_avg_profit']
            })
        
        # Проверка проблемных символов
        problematic_symbols = metrics.get('problematic_symbols', [])
        if problematic_symbols:
            alerts.append({
                'type': 'PROBLEMATIC_SYMBOLS',
                'severity': 'MEDIUM',
                'message': f"⚠️ Обнаружено {len(problematic_symbols)} проблемных символов",
                'symbols': problematic_symbols
            })
        
        return alerts
    
    def _log_metrics(self, metrics: Dict[str, Any], alerts: List[Dict[str, Any]]):
        """
        Логирование метрик
        
        Ответственный: Елена (Monitor)
        """
        if not metrics:
            return
        
        logger.info("=" * 80)
        logger.info("💰 [Елена] ОТЧЁТ О ПРИБЫЛЬНОСТИ ЗА 24 ЧАСА")
        logger.info("=" * 80)
        logger.info(f"📊 Всего сделок: {metrics.get('total_trades', 0)}")
        logger.info(f"✅ Прибыльных: {metrics.get('winners', 0)}")
        logger.info(f"❌ Убыточных: {metrics.get('losers', 0)}")
        logger.info(f"📈 Win Rate: {metrics.get('win_rate', 0.0):.1f}%")
        logger.info(f"💰 Общий PnL: {metrics.get('total_pnl', 0.0):.2f} USDT")
        logger.info(f"📊 Средняя прибыль: {metrics.get('avg_profit', 0.0):.2f} USDT")
        logger.info(f"📊 Средний убыток: {metrics.get('avg_loss', 0.0):.2f} USDT")
        logger.info(f"📊 Соотношение убытков к прибыли: {metrics.get('loss_profit_ratio', 0.0):.1f}:1")
        
        if alerts:
            logger.warning("⚠️ [Елена] ОБНАРУЖЕНЫ ПРОБЛЕМЫ:")
            for alert in alerts:
                logger.warning(f"  {alert['message']}")
        else:
            logger.info("✅ [Елена] Все показатели в норме")
        
        logger.info("=" * 80)
    
    async def _send_alerts(self, alerts: List[Dict[str, Any]], metrics: Dict[str, Any]):
        """
        Отправка алертов
        
        Ответственный: Елена (Monitor)
        """
        try:
            # Отправка в Telegram (если доступно)
            try:
                from src.telegram.bot import send_admin_message
                
                for alert in alerts:
                    if alert['severity'] == 'HIGH':
                        message = f"🚨 [Елена] КРИТИЧЕСКИЙ АЛЕРТ\n\n{alert['message']}\n\n"
                        message += f"📊 Текущие показатели:\n"
                        message += f"Win Rate: {metrics.get('win_rate', 0.0):.1f}%\n"
                        message += f"Общий PnL: {metrics.get('total_pnl', 0.0):.2f} USDT\n"
                        message += f"Соотношение убытков к прибыли: {metrics.get('loss_profit_ratio', 0.0):.1f}:1"
                        
                        await send_admin_message(message)
            except ImportError:
                logger.debug("Telegram bot недоступен для отправки алертов")
            
        except Exception as e:
            logger.error(f"❌ [Елена] Ошибка отправки алертов: {e}")
    
    async def _save_metrics(self, metrics: Dict[str, Any]):
        """
        Сохранение метрик в БД для истории
        
        Ответственный: Максим (Data Analyst)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Создаём таблицу если не существует
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profitability_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_trades INTEGER,
                    winners INTEGER,
                    losers INTEGER,
                    win_rate REAL,
                    total_pnl REAL,
                    avg_profit REAL,
                    avg_loss REAL,
                    loss_profit_ratio REAL,
                    total_profit REAL,
                    total_loss REAL,
                    alerts_count INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Сохраняем метрики
            cursor.execute("""
                INSERT INTO profitability_metrics (
                    timestamp, total_trades, winners, losers, win_rate,
                    total_pnl, avg_profit, avg_loss, loss_profit_ratio,
                    total_profit, total_loss, alerts_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.get('timestamp'),
                metrics.get('total_trades', 0),
                metrics.get('winners', 0),
                metrics.get('losers', 0),
                metrics.get('win_rate', 0.0),
                metrics.get('total_pnl', 0.0),
                metrics.get('avg_profit', 0.0),
                metrics.get('avg_loss', 0.0),
                metrics.get('loss_profit_ratio', 0.0),
                metrics.get('total_profit', 0.0),
                metrics.get('total_loss', 0.0),
                len(metrics.get('problematic_symbols', []))
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ [Максим] Ошибка сохранения метрик: {e}")
    
    async def get_daily_report(self) -> Dict[str, Any]:
        """
        Получение ежедневного отчёта
        
        Ответственный: Максим (Data Analyst)
        """
        try:
            metrics = await self._calculate_metrics_24h()
            alerts = self._check_thresholds(metrics)
            
            return {
                'metrics': metrics,
                'alerts': alerts,
                'status': 'OK' if not alerts else 'WARNING',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"❌ [Максим] Ошибка генерации отчёта: {e}")
            return {}


# Singleton instance
_profitability_monitor_instance: Optional[ProfitabilityMonitor] = None


def get_profitability_monitor(db_path: str = "trading.db") -> ProfitabilityMonitor:
    """Получить экземпляр монитора прибыльности"""
    global _profitability_monitor_instance
    if _profitability_monitor_instance is None:
        _profitability_monitor_instance = ProfitabilityMonitor(db_path)
    return _profitability_monitor_instance

