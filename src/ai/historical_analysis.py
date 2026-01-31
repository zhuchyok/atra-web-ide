#!/usr/bin/env python3
"""
📊 АНАЛИЗ ИСТОРИЧЕСКИХ ДАННЫХ ДЛЯ ОБУЧЕНИЯ ИИ
Анализ всех сигналов и сделок из логов и базы данных
"""

import asyncio
import logging
import json
import sqlite3
import os
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, List, Any, Optional

# Импорты
AI_MODULES_AVAILABLE = False
try:
    from src.ai.learning import AILearningSystem, TradingPattern
    from src.ai.integration import AIIntegration
    AI_MODULES_AVAILABLE = True
except ImportError as e:
    logging.warning("Не удалось импортировать модули ИИ: %s", e)
    AILearningSystem = None
    TradingPattern = None
    AIIntegration = None

logger = logging.getLogger(__name__)

class HistoricalDataAnalyzer:
    """Анализатор исторических данных для обучения ИИ"""
    
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HistoricalDataAnalyzer, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Предотвращаем повторную инициализацию
        if HistoricalDataAnalyzer._initialized:
            return
        HistoricalDataAnalyzer._initialized = True
        self.db_path = "trading.db"
        self.log_files = [
            "trading_log.json",
            "user_data.json"
        ]
        # Исключаем тестовые данные ИИ системы
        try:
            from src.config.patterns import get_patterns_file_path, get_learning_metrics_path, get_optimized_parameters_path
        except ImportError:
            try:
                from src.config.patterns import get_patterns_file_path
            except ImportError:
                from patterns_config import get_patterns_file_path, get_learning_metrics_path, get_optimized_parameters_path
        self.excluded_files = [
            get_patterns_file_path("main"),
            get_learning_metrics_path(),
            get_optimized_parameters_path()
        ]

        # Инициализируем ИИ компоненты только если они доступны
        if AI_MODULES_AVAILABLE:
            try:
                # Используем singleton registry для получения единственного экземпляра
                try:
                    from src.ai.singleton import get_ai_learning_system
                    self.ai_learning = get_ai_learning_system()
                    logger.info("✅ Используем singleton экземпляр ИИ системы в историческом анализе")
                except (ImportError, AttributeError) as e:
                    logger.warning("⚠️ Singleton registry недоступен в историческом анализе, создаем новый экземпляр: %s", e)
                    self.ai_learning = AILearningSystem()
                self.ai_integration = AIIntegration()
                logger.info("📊 Анализатор исторических данных инициализирован с ИИ поддержкой")
            except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                logger.warning("⚠️ Ошибка инициализации ИИ компонентов: %s", e)
                self.ai_learning = None
                self.ai_integration = None
        else:
            self.ai_learning = None
            self.ai_integration = None
            logger.info("📊 Анализатор исторических данных инициализирован без ИИ поддержки")

    async def analyze_all_historical_data(self) -> Dict[str, Any]:
        """Анализирует все исторические данные"""
        logger.info("🔍 Начинаем анализ всех исторических данных...")

        analysis_results = {
            "timestamp": get_utc_now().isoformat(),
            "database_analysis": {},
            "log_files_analysis": {},
            "patterns_learned": 0,
            "total_signals": 0,
            "profitable_signals": 0,
            "loss_signals": 0,
            "recommendations": []
        }

        try:
            # 1. Анализ базы данных
            db_analysis = await self._analyze_database()
            analysis_results["database_analysis"] = db_analysis
            analysis_results["patterns_learned"] += db_analysis.get("patterns_learned", 0)

            # 2. Анализ файлов логов
            for log_file in self.log_files:
                if os.path.exists(log_file):
                    # Проверяем, не является ли файл тестовыми данными ИИ
                    if any(excluded in log_file for excluded in self.excluded_files):
                        logger.info("⚠️ Пропускаем тестовые данные ИИ: %s", log_file)
                        continue

                    log_analysis = await self._analyze_log_file(log_file)
                    analysis_results["log_files_analysis"][log_file] = log_analysis
                    analysis_results["patterns_learned"] += log_analysis.get("patterns_learned", 0)

            # 2.1. Специальный анализ файла с паттернами ИИ
            try:
                from src.config.patterns import get_patterns_file_path
            except ImportError:
                from patterns_config import get_patterns_file_path
            patterns_file = get_patterns_file_path("main")
            if os.path.exists(patterns_file):
                logger.info("🤖 Анализируем файл с паттернами ИИ: %s", patterns_file)
                patterns_analysis = await self._analyze_ai_patterns_file(patterns_file)
                analysis_results["log_files_analysis"][patterns_file] = patterns_analysis
                analysis_results["patterns_learned"] += patterns_analysis.get("patterns_learned", 0)

            # 3. Общий анализ результатов
            # Анализируем данные из таблицы signals_log
            db_analysis = analysis_results.get("database_analysis", {})
            tables = db_analysis.get("tables", {})
            signals_log_data = tables.get("signals_log", {})

            if signals_log_data and signals_log_data.get("total_signals", 0) > 0:
                # Есть данные в signals_log
                analysis_results["total_signals"] = signals_log_data.get("total_signals", 0)
                analysis_results["profitable_signals"] = signals_log_data.get("profitable_signals", 0)
                analysis_results["loss_signals"] = signals_log_data.get("loss_signals", 0)

                # Генерируем рекомендации на основе реальных данных
                recommendations = self._generate_recommendations_from_analysis(analysis_results)
                analysis_results["recommendations"] = recommendations
            else:
                # Нет данных в signals_log
                analysis_results["total_signals"] = 0
                analysis_results["profitable_signals"] = 0
                analysis_results["loss_signals"] = 0
                analysis_results["recommendations"] = [
                    "⚠️ В таблице signals_log нет торговых сигналов для анализа",
                    "📊 Рекомендуется проверить, сохраняются ли сигналы в базу данных",
                    "🔧 Возможно, система работает только с файлами, а не с базой данных"
                ]

            logger.info("✅ Анализ завершен: %d паттернов изучено", analysis_results['patterns_learned'])
            return analysis_results

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа исторических данных: %s", e)
            return {"error": str(e)}

    async def _analyze_database(self) -> Dict[str, Any]:
        """Анализирует данные из базы данных"""
        try:
            if not os.path.exists(self.db_path):
                return {"error": "База данных не найдена"}

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            analysis = {
                "timestamp": get_utc_now().isoformat(),
                "tables": {},
                "patterns_learned": 0,
                "total_records": 0
            }

            # Получаем список таблиц
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            for table_name, in tables:
                try:
                    # Анализируем каждую таблицу
                    table_analysis = await self._analyze_table(cursor, table_name)
                    analysis["tables"][table_name] = table_analysis
                    analysis["patterns_learned"] += table_analysis.get("patterns_learned", 0)
                    analysis["total_records"] += table_analysis.get("total_records", 0)

                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                    logger.error("❌ Ошибка анализа таблицы %s: %s", table_name, e)

            conn.close()
            return analysis

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа базы данных: %s", e)
            return {"error": str(e)}

    async def _analyze_table(self, cursor, table_name: str) -> Dict[str, Any]:
        """Анализирует конкретную таблицу"""
        try:
            # Получаем структуру таблицы
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()

            # Получаем количество записей
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            total_records = cursor.fetchone()[0]

            analysis = {
                "table_name": table_name,
                "columns": [col[1] for col in columns],
                "total_records": total_records,
                "patterns_learned": 0
            }

            # Анализируем данные в зависимости от типа таблицы
            if table_name == "signals_log":
                # Основная таблица с торговыми сигналами
                analysis.update(await self._analyze_signals_log_table(cursor, table_name))
            elif "signal" in table_name.lower() and table_name != "signals_log":
                analysis.update(await self._analyze_signals_table(cursor, table_name))
            elif "trade" in table_name.lower() or "position" in table_name.lower():
                analysis.update(await self._analyze_trades_table(cursor, table_name))
            elif "user" in table_name.lower():
                analysis.update(await self._analyze_users_table(cursor, table_name))

            return analysis

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа таблицы %s: %s", table_name, e)
            return {"error": str(e)}

    async def _analyze_signals_log_table(self, cursor, table_name: str) -> Dict[str, Any]:
        """Анализирует таблицу signals_log (основная таблица с торговыми сигналами)"""
        try:
            # Получаем все сигналы из signals_log
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT 1000;")
            signals = cursor.fetchall()

            patterns_learned = 0
            profitable_signals = 0
            loss_signals = 0
            total_signals = len(signals)

            for signal in signals:
                try:
                    # Создаем паттерн из данных сигнала (только если ИИ доступен)
                    if self.ai_learning:
                        pattern = await self._create_pattern_from_signals_log(signal)
                        if pattern and hasattr(self.ai_learning, 'add_pattern'):
                            try:
                                self.ai_learning.add_pattern(pattern)
                                patterns_learned += 1

                                if pattern.result == "WIN":
                                    profitable_signals += 1
                                elif pattern.result == "LOSS":
                                    loss_signals += 1
                            except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                                logger.warning("⚠️ Ошибка добавления паттерна из signals_log: %s", e)

                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                    logger.error("❌ Ошибка создания паттерна из signals_log: %s", e)

            return {
                "type": "signals_log",
                "patterns_learned": patterns_learned,
                "total_signals": total_signals,
                "profitable_signals": profitable_signals,
                "loss_signals": loss_signals,
                "analysis": f"Проанализировано {total_signals} сигналов из основной таблицы"
            }

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа таблицы signals_log: %s", e)
            return {"error": str(e)}

    async def _analyze_signals_table(self, cursor, table_name: str) -> Dict[str, Any]:
        """Анализирует таблицу сигналов"""
        try:
            # Проверяем структуру таблицы
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]

            # Определяем колонку для сортировки
            order_column = "ts" if "ts" in column_names else "id" if "id" in column_names else column_names[0] if column_names else "id"

            # Получаем все сигналы
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY {order_column} DESC LIMIT 1000;")
            signals = cursor.fetchall()

            patterns_learned = 0

            for signal in signals:
                try:
                    # Создаем паттерн из данных сигнала (только если ИИ доступен)
                    if self.ai_learning:
                        pattern = await self._create_pattern_from_signal(signal)
                        if pattern and hasattr(self.ai_learning, 'add_pattern'):
                            try:
                                self.ai_learning.add_pattern(pattern)
                                patterns_learned += 1
                            except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                                logger.warning("⚠️ Ошибка добавления паттерна: %s", e)

                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                    logger.error("❌ Ошибка создания паттерна из сигнала: %s", e)

            return {
                "type": "signals",
                "patterns_learned": patterns_learned,
                "analysis": f"Проанализировано {len(signals)} сигналов"
            }

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа таблицы сигналов: %s", e)
            return {"error": str(e)}

    async def _analyze_trades_table(self, cursor, table_name: str) -> Dict[str, Any]:
        """Анализирует таблицу сделок"""
        try:
            # Проверяем структуру таблицы
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]

            # Определяем колонку для сортировки
            order_column = "ts" if "ts" in column_names else "id" if "id" in column_names else column_names[0] if column_names else "id"

            # Получаем все сделки
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY {order_column} DESC LIMIT 1000;")
            trades = cursor.fetchall()

            patterns_learned = 0
            profitable_trades = 0
            loss_trades = 0

            for trade in trades:
                try:
                    # Анализируем результат сделки (только если ИИ доступен)
                    if self.ai_learning:
                        pattern = await self._create_pattern_from_trade(trade)
                        if pattern and hasattr(self.ai_learning, 'add_pattern'):
                            try:
                                self.ai_learning.add_pattern(pattern)
                                patterns_learned += 1

                                if pattern.result == "WIN":
                                    profitable_trades += 1
                                elif pattern.result == "LOSS":
                                    loss_trades += 1
                            except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                                logger.warning("⚠️ Ошибка добавления паттерна сделки: %s", e)

                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                    logger.error("❌ Ошибка создания паттерна из сделки: %s", e)

            return {
                "type": "trades",
                "patterns_learned": patterns_learned,
                "profitable_trades": profitable_trades,
                "loss_trades": loss_trades,
                "analysis": f"Проанализировано {len(trades)} сделок"
            }

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа таблицы сделок: %s", e)
            return {"error": str(e)}

    async def _analyze_users_table(self, cursor, table_name: str) -> Dict[str, Any]:
        """Анализирует таблицу пользователей"""
        try:
            # Получаем данные пользователей
            cursor.execute(f"SELECT * FROM {table_name};")
            users = cursor.fetchall()

            return {
                "type": "users",
                "total_users": len(users),
                "analysis": f"Найдено {len(users)} пользователей"
            }

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа таблицы пользователей: %s", e)
            return {"error": str(e)}

    async def _create_pattern_from_signal(self, signal_data) -> Optional[TradingPattern]:
        """Создает паттерн из данных сигнала"""
        if not AI_MODULES_AVAILABLE or not TradingPattern:
            return None
        try:
            # Адаптируем под разные структуры таблиц
            if len(signal_data) >= 8:  # Минимальные поля
                symbol = signal_data[1] if len(signal_data) > 1 else "UNKNOWN"
                signal_type = signal_data[2] if len(signal_data) > 2 else "UNKNOWN"

                # Безопасная конвертация entry_price
                try:
                    entry_price = float(signal_data[3]) if len(signal_data) > 3 and signal_data[3] is not None else 0.0
                except (ValueError, TypeError):
                    entry_price = 0.0

                # Безопасная обработка timestamp - используем правильный индекс для entry_time
                timestamp = signal_data[6] if len(signal_data) > 6 else get_utc_now()
                if timestamp is None:
                    timestamp = get_utc_now()

                # Проверяем, что timestamp не является символом или другим некорректным значением
                if isinstance(timestamp, str):
                    # Если это выглядит как символ (содержит только буквы и цифры без T), пропускаем
                    if not any(char in timestamp for char in ['T', '-', ':', ' ']) and timestamp.isalnum():
                        logger.warning("⚠️ Пропускаем некорректный timestamp '%s' (похож на символ), используем текущее время", timestamp)
                        timestamp = get_utc_now()

                # Безопасное создание timestamp
                try:
                    if isinstance(timestamp, str):
                        # Парсим timestamp из базы данных (формат: "2025-10-01T21:05")
                        if "T" in timestamp:
                            # Добавляем секунды если их нет
                            if len(timestamp.split("T")[1]) <= 5:  # Только часы:минуты
                                timestamp += ":00"
                            pattern_timestamp = datetime.fromisoformat(timestamp)
                        else:
                            pattern_timestamp = get_utc_now()
                    elif isinstance(timestamp, (int, float)):
                        # Если timestamp - это число (Unix timestamp)
                        pattern_timestamp = datetime.fromtimestamp(timestamp)
                    else:
                        pattern_timestamp = get_utc_now()
                except (ValueError, TypeError) as e:
                    logger.warning("⚠️ Ошибка парсинга timestamp '%s': %s, используем текущее время", timestamp, e)
                    pattern_timestamp = get_utc_now()

                # Создаем базовый паттерн с проверкой данных
                pattern = TradingPattern(
                    symbol=symbol or "UNKNOWN",
                    timestamp=pattern_timestamp or get_utc_now(),
                    signal_type=signal_type or "UNKNOWN",
                    entry_price=entry_price if entry_price > 0 else 0.0,
                    tp1=entry_price * 1.02 if entry_price > 0 else 0.0,
                    tp2=entry_price * 1.04 if entry_price > 0 else 0.0,
                    risk_pct=2.0,
                    leverage=1.0,
                    indicators={},
                    market_conditions={}
                )

                return pattern

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка создания паттерна из сигнала: %s", e)

        return None

    async def _create_pattern_from_signals_log(self, signal_data) -> Optional[TradingPattern]:
        """Создает паттерн из данных signals_log"""
        if not AI_MODULES_AVAILABLE or not TradingPattern:
            return None
        try:
            if len(signal_data) >= 12:  # Минимальные поля для signals_log
                symbol = signal_data[1] if len(signal_data) > 1 else "UNKNOWN"
                entry_price = float(signal_data[2]) if len(signal_data) > 2 and signal_data[2] is not None else 0.0
                exit_price = float(signal_data[3]) if len(signal_data) > 3 and signal_data[3] is not None else entry_price

                # Безопасная обработка timestamp
                entry_time = signal_data[6] if len(signal_data) > 6 else get_utc_now()
                result = signal_data[8] if len(signal_data) > 8 else "UNKNOWN"

                # Определяем сторону сделки по результату
                if result in ["TP1", "TP2"]:
                    signal_type = "LONG"  # Предполагаем LONG для TP
                elif result in ["SL", "SL_BE"]:
                    signal_type = "LONG"  # Предполагаем LONG для SL
                else:
                    signal_type = "LONG"  # По умолчанию

                # Проверяем, что entry_time не является символом или другим некорректным значением
                if isinstance(entry_time, str):
                    # Если это выглядит как символ (содержит только буквы и цифры без T), пропускаем
                    if not any(char in entry_time for char in ['T', '-', ':', ' ']) and entry_time.isalnum():
                        logger.warning("⚠️ Пропускаем некорректный entry_time '%s' (похож на символ), используем текущее время", entry_time)
                        entry_time = get_utc_now()

                # Безопасное создание timestamp
                try:
                    if isinstance(entry_time, str):
                        if "T" in entry_time:
                            if len(entry_time.split("T")[1]) <= 5:  # Только часы:минуты
                                entry_time += ":00"
                            pattern_timestamp = datetime.fromisoformat(entry_time)
                        else:
                            pattern_timestamp = get_utc_now()
                    elif isinstance(entry_time, (int, float)):
                        pattern_timestamp = datetime.fromtimestamp(entry_time)
                    else:
                        pattern_timestamp = get_utc_now()
                except (ValueError, TypeError) as e:
                    logger.warning("⚠️ Ошибка парсинга entry_time '%s': %s, используем текущее время", entry_time, e)
                    pattern_timestamp = get_utc_now()

                # Определяем результат (ИСПРАВЛЕНО: учитываем TP1_PARTIAL как прибыльный)
                if result in ["TP1", "TP2", "TP1_PARTIAL", "TP2_PARTIAL"]:
                    result_status = "WIN"
                    if result in ["TP1", "TP1_PARTIAL"]:
                        profit_pct = 2.0  # TP1 прибыль
                    else:
                        profit_pct = 4.0  # TP2 прибыль
                elif result in ["SL", "SL_BE"]:
                    result_status = "LOSS"
                    profit_pct = -2.0 if result == "SL" else 0.0  # SL_BE = безубыток
                else:
                    result_status = "NEUTRAL"
                    profit_pct = 0.0

                # Создаем паттерн с результатом
                pattern = TradingPattern(
                    symbol=symbol or "UNKNOWN",
                    timestamp=pattern_timestamp or get_utc_now(),
                    signal_type=signal_type or "UNKNOWN",
                    entry_price=entry_price if entry_price > 0 else 0.0,
                    tp1=exit_price if exit_price > 0 else entry_price * 1.02,
                    tp2=exit_price if exit_price > 0 else entry_price * 1.04,
                    risk_pct=2.0,
                    leverage=1.0,
                    indicators={},
                    market_conditions={},
                    result=result_status or "UNKNOWN",
                    profit_pct=profit_pct or 0.0
                )

                return pattern

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка создания паттерна из signals_log: %s", e)

        return None

    async def _create_pattern_from_trade(self, trade_data) -> Optional[TradingPattern]:
        """Создает паттерн из данных сделки"""
        if not AI_MODULES_AVAILABLE or not TradingPattern:
            return None
        try:
            if len(trade_data) >= 10:  # Минимальные поля для сделки
                symbol = trade_data[1] if len(trade_data) > 1 else "UNKNOWN"
                signal_type = trade_data[2] if len(trade_data) > 2 else "UNKNOWN"

                # Безопасная конвертация цен
                try:
                    entry_price = float(trade_data[3]) if len(trade_data) > 3 and trade_data[3] is not None else 0.0
                except (ValueError, TypeError):
                    entry_price = 0.0

                try:
                    exit_price = float(trade_data[4]) if len(trade_data) > 4 and trade_data[4] is not None else 0.0
                except (ValueError, TypeError):
                    exit_price = entry_price

                # Безопасная обработка timestamp
                timestamp = trade_data[5] if len(trade_data) > 5 else get_utc_now()
                if timestamp is None:
                    timestamp = get_utc_now()

                # Проверяем, что timestamp не является символом или другим некорректным значением
                if isinstance(timestamp, str):
                    # Если это выглядит как символ (содержит только буквы и цифры без T), пропускаем
                    if not any(char in timestamp for char in ['T', '-', ':', ' ']) and timestamp.isalnum():
                        logger.warning("⚠️ Пропускаем некорректный timestamp '%s' (похож на символ), используем текущее время", timestamp)
                        timestamp = get_utc_now()

                # Безопасное создание timestamp
                try:
                    if isinstance(timestamp, str):
                        # Парсим timestamp из базы данных
                        if "T" in timestamp:
                            # Добавляем секунды если их нет
                            if len(timestamp.split("T")[1]) <= 5:  # Только часы:минуты
                                timestamp += ":00"
                            pattern_timestamp = datetime.fromisoformat(timestamp)
                        else:
                            pattern_timestamp = get_utc_now()
                    elif isinstance(timestamp, (int, float)):
                        # Если timestamp - это число (Unix timestamp)
                        pattern_timestamp = datetime.fromtimestamp(timestamp)
                    else:
                        pattern_timestamp = get_utc_now()
                except (ValueError, TypeError) as e:
                    logger.warning("⚠️ Ошибка парсим timestamp '%s': %s, используем текущее время", timestamp, e)
                    pattern_timestamp = get_utc_now()

                # Определяем результат
                if signal_type == "LONG":
                    profit_pct = (exit_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
                else:
                    profit_pct = (entry_price - exit_price) / entry_price * 100 if entry_price > 0 else 0

                result = "WIN" if profit_pct > 0 else "LOSS" if profit_pct < 0 else "NEUTRAL"

                # Создаем паттерн с результатом
                pattern = TradingPattern(
                    symbol=symbol,
                    timestamp=pattern_timestamp,
                    signal_type=signal_type,
                    entry_price=entry_price,
                    tp1=exit_price,
                    tp2=exit_price,
                    risk_pct=2.0,
                    leverage=1.0,
                    indicators={},
                    market_conditions={},
                    result=result,
                    profit_pct=profit_pct
                )

                return pattern

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка создания паттерна из сделки: %s", e)

        return None

    async def _analyze_log_file(self, log_file: str) -> Dict[str, Any]:
        """Анализирует файл лога"""
        try:
            if not os.path.exists(log_file):
                return {"error": f"Файл {log_file} не найден"}

            # Пропускаем тестовые данные ИИ системы
            try:
                from src.config.patterns import get_patterns_file_path
            except ImportError:
                from patterns_config import get_patterns_file_path
            if "ai_learning_data" in log_file or get_patterns_file_path("main") in log_file:
                return {
                    "file_name": log_file,
                    "file_size": os.path.getsize(log_file) if os.path.exists(log_file) else 0,
                    "patterns_learned": 0,
                    "data_type": "ai_test_data",
                    "analysis": "Пропущены тестовые данные ИИ системы"
                }

            with open(log_file, 'r', encoding='utf-8') as f:
                if log_file.endswith('.json'):
                    data = json.load(f)
                else:
                    # Для текстовых логов
                    content = f.read()
                    return {"type": "text_log", "size": len(content)}

            analysis = {
                "file_name": log_file,
                "file_size": os.path.getsize(log_file),
                "patterns_learned": 0,
                "data_type": "json"
            }

            # Анализируем в зависимости от типа файла
            if "signal" in log_file.lower():
                analysis.update(await self._analyze_signal_log(data))
            elif "user" in log_file.lower():
                analysis.update(await self._analyze_user_log(data))
            elif "trading" in log_file.lower():
                analysis.update(await self._analyze_trading_log(data))

            return analysis

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа файла %s: %s", log_file, e)
            return {"error": str(e)}

    async def _analyze_signal_log(self, data: Dict) -> Dict[str, Any]:
        """Анализирует лог сигналов"""
        try:
            patterns_learned = 0

            if isinstance(data, dict):
                for key, signal_data in data.items():
                    try:
                        if self.ai_learning:
                            pattern = await self._create_pattern_from_signal_data(signal_data)
                            if pattern and hasattr(self.ai_learning, 'add_pattern'):
                                try:
                                    self.ai_learning.add_pattern(pattern)
                                    patterns_learned += 1
                                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                                    logger.warning("⚠️ Ошибка добавления паттерна из данных сигнала: %s", e)
                    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                        logger.error("❌ Ошибка анализа сигнала %s: %s", key, e)

            return {
                "type": "signal_log",
                "patterns_learned": patterns_learned,
                "total_signals": len(data) if isinstance(data, dict) else 0
            }

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа лога сигналов: %s", e)
            return {"error": str(e)}

    async def _analyze_user_log(self, data: Dict) -> Dict[str, Any]:
        """Анализирует лог пользователей"""
        try:
            # Анализируем данные пользователей (НЕ считаем их как паттерны ИИ)
            total_users = 0
            total_positions = 0
            total_signals = 0
            total_trades = 0
            
            if isinstance(data, dict):
                for user_id, user_data in data.items():
                    try:
                        if isinstance(user_data, dict):
                            # Считаем торговые данные пользователей
                            open_positions = user_data.get("open_positions", [])
                            total_positions += len(open_positions)
                            
                            accepted_signals = user_data.get("accepted_signals", [])
                            total_signals += len(accepted_signals)
                            
                            trade_history = user_data.get("trade_history", [])
                            total_trades += len(trade_history)
                            
                            total_users += 1
                    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                        logger.warning("⚠️ Ошибка анализа данных пользователя %s: %s", user_id, e)
            
            return {
                "type": "user_log",
                "total_users": total_users,
                "total_positions": total_positions,
                "total_signals": total_signals,
                "total_trades": total_trades,
                "patterns_learned": 0,  # Пользовательские данные НЕ являются паттернами ИИ
                "analysis": f"Данные пользователей: {total_users} пользователей, {total_positions} позиций, {total_signals} сигналов, {total_trades} сделок"
            }

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа лога пользователей: %s", e)
            return {"error": str(e)}

    async def _analyze_ai_patterns_file(self, patterns_file: str) -> Dict[str, Any]:
        """Анализирует файл с паттернами ИИ"""
        try:
            if not os.path.exists(patterns_file):
                return {"error": f"Файл {patterns_file} не найден"}

            with open(patterns_file, 'r', encoding='utf-8') as f:
                patterns_data = json.load(f)

            patterns_count = len(patterns_data) if isinstance(patterns_data, list) else 0
            
            # Анализируем качество паттернов
            valid_patterns = 0
            profitable_patterns = 0
            symbols_count = set()
            
            for pattern in patterns_data:
                if isinstance(pattern, dict):
                    # Проверяем валидность паттерна
                    if pattern.get('symbol') and pattern.get('timestamp'):
                        valid_patterns += 1
                        symbols_count.add(pattern.get('symbol', '').split('|')[0] if '|' in pattern.get('symbol', '') else pattern.get('symbol', ''))
                    
                    # Проверяем прибыльность
                    profit_pct = pattern.get('profit_pct')
                    if profit_pct is not None and profit_pct > 0:
                        profitable_patterns += 1

            return {
                "type": "ai_patterns",
                "file_name": patterns_file,
                "file_size": os.path.getsize(patterns_file),
                "patterns_learned": patterns_count,
                "valid_patterns": valid_patterns,
                "profitable_patterns": profitable_patterns,
                "unique_symbols": len(symbols_count),
                "profitability_rate": (profitable_patterns / valid_patterns * 100) if valid_patterns > 0 else 0,
                "analysis": f"Паттерны ИИ: {patterns_count} всего, {valid_patterns} валидных, {profitable_patterns} прибыльных ({len(symbols_count)} символов)"
            }

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа файла паттернов ИИ %s: %s", patterns_file, e)
            return {"error": str(e)}

    async def _analyze_trading_log(self, data: Dict) -> Dict[str, Any]:
        """Анализирует лог торговли"""
        try:
            patterns_learned = 0

            if isinstance(data, dict):
                for key, trade_data in data.items():
                    try:
                        if self.ai_learning:
                            pattern = await self._create_pattern_from_trade_data(trade_data)
                            if pattern and hasattr(self.ai_learning, 'add_pattern'):
                                try:
                                    self.ai_learning.add_pattern(pattern)
                                    patterns_learned += 1
                                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                                    logger.warning("⚠️ Ошибка добавления паттерна из данных сделки: %s", e)
                    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                        logger.error("❌ Ошибка анализа сделки %s: %s", key, e)

            return {
                "type": "trading_log",
                "patterns_learned": patterns_learned,
                "total_trades": len(data) if isinstance(data, dict) else 0
            }

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа лога торговли: %s", e)
            return {"error": str(e)}

    async def _create_pattern_from_signal_data(self, signal_data: Dict) -> Optional[TradingPattern]:
        """Создает паттерн из данных сигнала в JSON"""
        if not AI_MODULES_AVAILABLE or not TradingPattern:
            return None
        try:
            if not isinstance(signal_data, dict):
                return None

            # Извлекаем данные
            symbol = signal_data.get('symbol', 'UNKNOWN')
            signal_type = signal_data.get('side', signal_data.get('signal_type', 'UNKNOWN'))
            entry_price = float(signal_data.get('entry_price', 0))
            timestamp = signal_data.get('timestamp', get_utc_now())

            # Создаем паттерн с проверкой данных
            pattern = TradingPattern(
                symbol=symbol or "UNKNOWN",
                timestamp=datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else (timestamp or get_utc_now()),
                signal_type=signal_type or "UNKNOWN",
                entry_price=entry_price if entry_price > 0 else 0.0,
                tp1=entry_price * 1.02 if entry_price > 0 else 0.0,
                tp2=entry_price * 1.04 if entry_price > 0 else 0.0,
                risk_pct=float(signal_data.get('risk_pct', 2.0)),
                leverage=float(signal_data.get('leverage', 1.0)),
                indicators=signal_data.get('indicators', {}),
                market_conditions=signal_data.get('market_conditions', {})
            )

            return pattern

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка создания паттерна из данных сигнала: %s", e)
            return None

    async def _create_pattern_from_trade_data(self, trade_data: Dict) -> Optional[TradingPattern]:
        """Создает паттерн из данных сделки в JSON"""
        if not AI_MODULES_AVAILABLE or not TradingPattern:
            return None
        try:
            if not isinstance(trade_data, dict):
                return None

            # Извлекаем данные
            symbol = trade_data.get('symbol', 'UNKNOWN')
            signal_type = trade_data.get('side', trade_data.get('signal_type', 'UNKNOWN'))
            entry_price = float(trade_data.get('entry_price', 0))
            exit_price = float(trade_data.get('exit_price', trade_data.get('close_price', entry_price)))
            timestamp = trade_data.get('timestamp', get_utc_now())

            # Определяем результат
            if signal_type == "LONG":
                profit_pct = (exit_price - entry_price) / entry_price * 100
            else:
                profit_pct = (entry_price - exit_price) / entry_price * 100

            result = "WIN" if profit_pct > 0 else "LOSS" if profit_pct < 0 else "NEUTRAL"

            # Создаем паттерн с проверкой данных
            pattern = TradingPattern(
                symbol=symbol or "UNKNOWN",
                timestamp=datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else (timestamp or get_utc_now()),
                signal_type=signal_type or "UNKNOWN",
                entry_price=entry_price if entry_price > 0 else 0.0,
                tp1=exit_price if exit_price > 0 else entry_price * 1.02,
                tp2=exit_price if exit_price > 0 else entry_price * 1.04,
                risk_pct=float(trade_data.get('risk_pct', 2.0)),
                leverage=float(trade_data.get('leverage', 1.0)),
                indicators=trade_data.get('indicators', {}),
                market_conditions=trade_data.get('market_conditions', {}),
                result=result or "UNKNOWN",
                profit_pct=profit_pct or 0.0
            )

            return pattern

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка создания паттерна из данных сделки: %s", e)
            return None

    def _generate_recommendations_from_analysis(self, analysis: Dict[str, Any]) -> List[str]:
        """Генерирует рекомендации на основе анализа"""
        recommendations = []

        try:
            total_signals = analysis.get("total_signals", 0)
            profitable_signals = analysis.get("profitable_signals", 0)
            # loss_signals = analysis.get("loss_signals", 0)  # Не используется

            if total_signals > 0:
                success_rate = profitable_signals / total_signals

                if success_rate > 0.7:
                    recommendations.append(f"✅ Высокая успешность: {success_rate:.1%}. Система работает хорошо!")
                elif success_rate < 0.3:
                    recommendations.append(f"⚠️ Низкая успешность: {success_rate:.1%}. Рекомендуется пересмотреть стратегию")
                else:
                    recommendations.append(f"📊 Средняя успешность: {success_rate:.1%}. Есть потенциал для улучшения")

            # Анализ по символам (только если ИИ доступен)
            if self.ai_learning and hasattr(self.ai_learning, 'patterns') and self.ai_learning.patterns:
                try:
                    if hasattr(self.ai_learning, 'analyze_patterns'):
                        # Добавляем дополнительную проверку перед вызовом
                        if not hasattr(self.ai_learning, 'patterns') or not self.ai_learning.patterns:
                            logger.warning("⚠️ ИИ система не имеет паттернов для анализа")
                            recommendations.append("ℹ️ ИИ система: нет паттернов для анализа")
                        else:
                            logger.info("🔍 Начинаем анализ паттернов ИИ системы...")
                            symbol_analysis = self.ai_learning.analyze_patterns()
                            
                            # Детальная проверка результата
                            logger.info("🔍 Результат analyze_patterns: %s (тип: %s)", symbol_analysis, type(symbol_analysis))
                            
                            # Проверяем, что analyze_patterns вернул словарь, а не строку
                            if isinstance(symbol_analysis, dict) and symbol_analysis.get("success_rates"):
                                best_symbols = sorted(
                                    symbol_analysis["success_rates"].items(),
                                    key=lambda x: x[1],
                                    reverse=True
                                )[:3]

                                for symbol, rate in best_symbols:
                                    if rate > 0.6:
                                        recommendations.append(f"🎯 Лучший символ: {symbol} (успешность {rate:.1%})")
                                    elif rate < 0.3:
                                        recommendations.append(f"⚠️ Проблемный символ: {symbol} (успешность {rate:.1%})")
                            elif isinstance(symbol_analysis, dict) and "error" in symbol_analysis:
                                logger.warning("⚠️ ИИ система сообщает: %s", symbol_analysis["error"])
                                recommendations.append(f"ℹ️ ИИ анализ: {symbol_analysis['error']}")
                            elif isinstance(symbol_analysis, str):
                                logger.warning("⚠️ analyze_patterns вернул строку вместо словаря: '%s'", symbol_analysis)
                                recommendations.append(f"⚠️ ИИ анализ: неожиданный результат '{symbol_analysis}'")
                            else:
                                logger.warning("⚠️ analyze_patterns вернул неожиданный результат: %s (тип: %s)", symbol_analysis, type(symbol_analysis))
                                recommendations.append("⚠️ ИИ анализ недоступен - неожиданный формат данных")
                    else:
                        recommendations.append("ℹ️ Метод анализа паттернов недоступен в ИИ системе")
                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                    logger.warning("⚠️ Ошибка анализа символов: %s", e)
                    # Более информативное сообщение об ошибке
                    if "BTCUSDT" in str(e):
                        recommendations.append("⚠️ Ошибка анализа BTCUSDT: проблема с данными символа")
                    elif "KeyError" in str(type(e).__name__):
                        recommendations.append("⚠️ Ошибка анализа: отсутствуют необходимые поля данных")
                    elif "TypeError" in str(type(e).__name__):
                        recommendations.append("⚠️ Ошибка анализа: неверный тип данных")
                    else:
                        recommendations.append(f"⚠️ Ошибка анализа символов: {type(e).__name__}")

            # Рекомендации по объему данных
            if total_signals < 10:
                recommendations.append("📊 Недостаточно данных для анализа. Рекомендуется больше торговли")
            elif total_signals > 1000:
                recommendations.append("📈 Большой объем данных. ИИ может дать точные рекомендации")

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка генерации рекомендаций: %s", e)
            recommendations.append("❌ Ошибка анализа данных")

        return recommendations

    async def generate_historical_analysis_report(self) -> str:
        """Генерирует отчет об анализе исторических данных"""
        try:
            analysis = await self.analyze_all_historical_data()

            report = f"""
📊 ОТЧЕТ ОБ АНАЛИЗЕ ИСТОРИЧЕСКИХ ДАННЫХ ИИ
{'='*60}

⏰ ВРЕМЯ АНАЛИЗА: {analysis.get('timestamp', 'Неизвестно')}

📈 ОБЩАЯ СТАТИСТИКА:
• Всего сигналов проанализировано: {analysis.get('total_signals', 0)}
• Прибыльных сигналов: {analysis.get('profitable_signals', 0)}
• Убыточных сигналов: {analysis.get('loss_signals', 0)}
• Паттернов изучено: {analysis.get('patterns_learned', 0)}

🗄️ АНАЛИЗ БАЗЫ ДАННЫХ:
"""

            db_analysis = analysis.get("database_analysis", {})
            if db_analysis:
                report += f"• Всего записей: {db_analysis.get('total_records', 0)}\n"
                report += f"• Таблиц проанализировано: {len(db_analysis.get('tables', {}))}\n"

                for table_name, table_data in db_analysis.get('tables', {}).items():
                    report += f"  - {table_name}: {table_data.get('total_records', 0)} записей\n"
            else:
                report += "• База данных не найдена или недоступна\n"

            report += """
📁 АНАЛИЗ ФАЙЛОВ ЛОГОВ:
"""

            log_analysis = analysis.get("log_files_analysis", {})
            for log_file, log_data in log_analysis.items():
                if log_data.get('type') == 'ai_patterns':
                    # Специальный формат для паттернов ИИ
                    report += f"• {log_file}: {log_data.get('patterns_learned', 0)} паттернов ИИ\n"
                    report += f"  - Валидных: {log_data.get('valid_patterns', 0)}\n"
                    report += f"  - Прибыльных: {log_data.get('profitable_patterns', 0)}\n"
                    report += f"  - Символов: {log_data.get('unique_symbols', 0)}\n"
                elif log_data.get('type') == 'user_log':
                    # Формат для пользовательских данных
                    report += f"• {log_file}: {log_data.get('total_users', 0)} пользователей\n"
                    report += f"  - Позиций: {log_data.get('total_positions', 0)}\n"
                    report += f"  - Сигналов: {log_data.get('total_signals', 0)}\n"
                    report += f"  - Сделок: {log_data.get('total_trades', 0)}\n"
                else:
                    # Обычный формат
                    report += f"• {log_file}: {log_data.get('patterns_learned', 0)} паттернов\n"

            report += """
💡 РЕКОМЕНДАЦИИ НА ОСНОВЕ АНАЛИЗА:
"""

            recommendations = analysis.get("recommendations", [])
            for rec in recommendations:
                report += f"• {rec}\n"

            if not recommendations:
                report += "• Недостаточно данных для генерации рекомендаций\n"

            return report

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка генерации отчета: %s", e)
            return f"❌ Ошибка генерации отчета: {e}"

# Глобальный экземпляр анализатора
historical_analyzer = HistoricalDataAnalyzer()

async def run_historical_analysis():
    """Запускает анализ исторических данных в цикле"""
    logger.info("🚀 Запуск системы анализа исторических данных...")
    
    # Импортируем shutdown_manager из main.py
    try:
        from main import shutdown_manager
    except ImportError:
        # Fallback если main.py недоступен
        class DummyShutdownManager:
            def __init__(self):
                self._shutdown_requested = False
            @property
            def shutdown_requested(self):
                return self._shutdown_requested
        shutdown_manager = DummyShutdownManager()
    
    while not shutdown_manager.shutdown_requested:
        try:
            logger.info("📊 Начало цикла анализа исторических данных...")
            
            # Выполняем полный анализ
            await historical_analyzer.analyze_all_historical_data()

            # Генерируем отчет
            report = await historical_analyzer.generate_historical_analysis_report()
            print(report)

            # Сохраняем результаты (только если ИИ доступен)
            if historical_analyzer.ai_learning:
                try:
                    if hasattr(historical_analyzer.ai_learning, 'save_patterns'):
                        historical_analyzer.ai_learning.save_patterns()
                    if hasattr(historical_analyzer.ai_learning, 'save_learning_model'):
                        historical_analyzer.ai_learning.save_learning_model()
                    if hasattr(historical_analyzer.ai_learning, 'save_metrics'):
                        historical_analyzer.ai_learning.save_metrics()
                    logger.info("✅ ИИ данные сохранены")
                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                    logger.warning("⚠️ Ошибка сохранения ИИ данных: %s", e)

            logger.info("✅ Цикл анализа исторических данных завершен, следующий через 24 часа...")
            
            # Ждем 24 часа до следующего анализа с проверкой shutdown каждую минуту
            for _ in range(24 * 60):  # 24 часа * 60 минут
                if shutdown_manager.shutdown_requested:
                    break
                await asyncio.sleep(60)  # Ждем 1 минуту

        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
            logger.error("❌ Ошибка анализа исторических данных: %s", e)
            # При ошибке ждем 1 час перед повтором с проверкой shutdown каждые 10 минут
            for _ in range(6):  # 1 час / 10 минут = 6 итераций
                if shutdown_manager.shutdown_requested:
                    break
                await asyncio.sleep(600)  # Ждем 10 минут
        except asyncio.CancelledError:
            logger.info("🛑 Анализ исторических данных отменен")
            break

if __name__ == "__main__":
    # Запуск анализа исторических данных
    asyncio.run(run_historical_analysis())
