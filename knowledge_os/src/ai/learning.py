#!/usr/bin/env python3
"""
🤖 СИСТЕМА ОБУЧЕНИЯ ИИ ДЛЯ ТОРГОВОЙ СИСТЕМЫ
Автоматическое обучение на основе торговой логики и данных

Улучшенная версия с автоматическим управлением паттернами:
- Лимит 30K паттернов (оптимально для ML)
- Умная очистка с сохранением важных данных
- Система весов для приоритизации
- Автоматическое управление без вмешательства
"""

# pylint: disable=too-many-lines

import asyncio
import json
import logging
import shutil

try:
    import numpy as np
except ImportError as e:
    print(f"❌ Ошибка импорта numpy: {e}")
    np = None
import os
import pickle
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    from src.config.patterns import (
        get_learning_metrics_path,
        get_learning_model_path,
        get_patterns_file_path,
    )
except ImportError:
    # Fallback если patterns_config недоступен
    def get_learning_metrics_path():
        return "ai_learning_data/learning_metrics.json"

    def get_learning_model_path():
        return "ai_learning_data/learning_model.pkl"

    def get_patterns_file_path(env="main"):
        return "ai_learning_data/trading_patterns.json"


# Импорт конфигурации ИИ
try:
    from ai.ai_config import get_pattern_config
except ImportError:
    try:
        from ai_config import get_pattern_config  # type: ignore
    except ImportError:
        get_pattern_config = None  # type: ignore

if callable(get_pattern_config):
    AI_CONFIG = get_pattern_config()
else:
    AI_CONFIG = {
        "max_patterns": 50000,
        "pattern_age_days": 60,
        "cleanup_frequency": 1000,
        "auto_cleanup_on_start": True,
    }

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TradingPattern:
    """Паттерн торгового сигнала для обучения"""

    symbol: str
    timestamp: datetime
    signal_type: str  # LONG/SHORT
    entry_price: float
    tp1: float
    tp2: float
    risk_pct: float
    leverage: float
    indicators: Dict[str, float]  # RSI, EMA, BB, etc.
    market_conditions: Dict[str, Any]  # BTC trend, volume, etc.
    result: Optional[str] = None  # WIN/LOSS/NEUTRAL
    profit_pct: Optional[float] = None


@dataclass
class LearningMetrics:
    """Метрики обучения ИИ"""

    total_patterns: int = 0
    successful_patterns: int = 0
    failed_patterns: int = 0
    accuracy: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    last_cleanup: Optional[str] = None


class AILearningSystem:
    """Система обучения ИИ для торговой системы"""

    _instance = None
    _initialized = False

    def __new__(cls, data_dir: str = "ai_learning_data"):
        if cls._instance is None:
            cls._instance = super(AILearningSystem, cls).__new__(cls)
        return cls._instance

    def __init__(self, data_dir: str = "ai_learning_data"):
        # Предотвращаем повторную инициализацию
        if AILearningSystem._initialized:
            return
        AILearningSystem._initialized = True
        self.data_dir = data_dir
        self.patterns_file = get_patterns_file_path("main")
        self.learning_model_file = get_learning_model_path()
        self.metrics_file = get_learning_metrics_path()

        # Создаем директорию для данных
        os.makedirs(data_dir, exist_ok=True)

        # Загружаем существующие данные
        self.patterns = self.load_patterns()
        self.learning_model = self.load_learning_model()
        self.metrics = self.load_metrics()

        logger.info("🤖 ИИ система инициализирована. Паттернов: %d", len(self.patterns))

        # Автоматическая очистка при старте (из конфига)
        max_patterns = AI_CONFIG.get("max_patterns", 50000)
        auto_cleanup = AI_CONFIG.get("auto_cleanup_on_start", True)

        if auto_cleanup and len(self.patterns) > max_patterns:
            logger.info(
                "🧹 Обнаружено %d паттернов, запускаем умную автоочистку...", len(self.patterns)
            )
            self.auto_manage_patterns(max_patterns=max_patterns)

    def load_patterns(self) -> List[TradingPattern]:
        """Загружает существующие паттерны"""
        if not os.path.exists(self.patterns_file):
            logger.warning("⚠️ Файл паттернов не найден: %s", self.patterns_file)
            return []

        try:
            logger.info("📥 Загружаем паттерны из %s (UTF-8 JSON)", self.patterns_file)
            with open(self.patterns_file, encoding="utf-8") as file:
                data = json.load(file)
        except OSError as io_err:
            logger.error("❌ Ошибка чтения файла паттернов: %s", io_err)
            return []
        except json.JSONDecodeError as json_err:
            logger.error("❌ JSONDecodeError при загрузке паттернов: %s", json_err)
            backup_file = f"{self.patterns_file}.backup"
            logger.info("💾 Создаём резервную копию битого файла → %s", backup_file)
            try:
                shutil.copyfile(self.patterns_file, backup_file)
            except Exception as copy_err:  # pragma: no cover
                logger.warning("⚠️ Не удалось создать резервную копию: %s", copy_err)
            logger.info("♻️ Сбрасываем файл паттернов и создаём пустой список")
            try:
                with open(self.patterns_file, "w", encoding="utf-8") as file:
                    json.dump([], file, ensure_ascii=False, indent=2)
            except Exception as reset_err:
                logger.error("❌ Не удалось пересоздать файл паттернов: %s", reset_err)
            return []

        if not isinstance(data, list):
            logger.error(
                "❌ Некорректный формат паттернов: ожидается список, получено %s", type(data)
            )
            return []

        patterns: List[TradingPattern] = []
        skipped = 0

        for idx, item in enumerate(data):
            try:
                pattern = TradingPattern(
                    symbol=item["symbol"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    signal_type=item["signal_type"],
                    entry_price=float(item["entry_price"]),
                    tp1=float(item["tp1"]),
                    tp2=float(item["tp2"]),
                    risk_pct=float(item["risk_pct"]),
                    leverage=float(item["leverage"]),
                    indicators=item["indicators"],
                    market_conditions=item["market_conditions"],
                    result=item.get("result"),
                    profit_pct=item.get("profit_pct"),
                )
            except (KeyError, TypeError, ValueError) as exc:
                skipped += 1
                if skipped <= 5:
                    logger.warning("⚠️ Некорректный паттерн на позиции %d: %s", idx, exc)
                continue

            patterns.append(pattern)

        if skipped:
            logger.warning(
                "⚠️ При загрузке паттернов пропущено %d записей из %d", skipped, len(data)
            )

        return patterns

    def save_patterns(self):
        """Сохраняет паттерны"""
        try:
            data = []
            for pattern in self.patterns:
                # Безопасная обработка timestamp
                if pattern.timestamp is None:
                    logger.warning("⚠️ Паттерн %s имеет None timestamp, пропускаем", pattern.symbol)
                    continue

                data.append(
                    {
                        "symbol": pattern.symbol,
                        "timestamp": pattern.timestamp.isoformat(),
                        "signal_type": pattern.signal_type,
                        "entry_price": pattern.entry_price,
                        "tp1": pattern.tp1,
                        "tp2": pattern.tp2,
                        "risk_pct": pattern.risk_pct,
                        "leverage": pattern.leverage,
                        "indicators": pattern.indicators,
                        "market_conditions": pattern.market_conditions,
                        "result": pattern.result,
                        "profit_pct": pattern.profit_pct,
                    }
                )

            with open(self.patterns_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info("💾 Сохранено %d паттернов", len(self.patterns))
        except (OSError, TypeError) as e:
            logger.error("Ошибка сохранения паттернов: %s", e)

    def load_learning_model(self) -> Dict:
        """Загружает модель обучения"""
        if os.path.exists(self.learning_model_file):
            try:
                with open(self.learning_model_file, "rb") as f:
                    return pickle.load(f)
            except (OSError, pickle.UnpicklingError, EOFError) as e:
                logger.error("Ошибка загрузки модели: %s", e)
        return {"weights": {}, "biases": {}, "feature_importance": {}, "last_updated": None}

    def save_learning_model(self):
        """Сохраняет модель обучения"""
        try:
            with open(self.learning_model_file, "wb") as f:
                pickle.dump(self.learning_model, f)
            logger.info("💾 Модель обучения сохранена")
        except (OSError, pickle.PicklingError) as e:
            logger.error("Ошибка сохранения модели: %s", e)

    def load_metrics(self) -> LearningMetrics:
        """Загружает метрики обучения"""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, encoding="utf-8") as f:
                    data = json.load(f)
                return LearningMetrics(**data)
            except (OSError, json.JSONDecodeError, TypeError, KeyError) as e:
                logger.error("Ошибка загрузки метрик: %s", e)
        return LearningMetrics()

    def save_metrics(self):
        """Сохраняет метрики"""
        try:
            data = {
                "total_patterns": self.metrics.total_patterns,
                "successful_patterns": self.metrics.successful_patterns,
                "failed_patterns": self.metrics.failed_patterns,
                "accuracy": self.metrics.accuracy,
                "profit_factor": self.metrics.profit_factor,
                "max_drawdown": self.metrics.max_drawdown,
                "sharpe_ratio": self.metrics.sharpe_ratio,
            }

            with open(self.metrics_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info("💾 Метрики сохранены")
        except (OSError, TypeError) as e:
            logger.error("Ошибка сохранения метрик: %s", e)

    def _validate_symbol(self, symbol: str) -> bool:
        """Валидация символа перед добавлением паттерна"""
        if not symbol or not isinstance(symbol, str):
            return False

        # Очистка
        clean_symbol = symbol.strip().upper()
        if not clean_symbol:
            return False

        # Проверка на допустимые символы (буквы, цифры, дефис, подчеркивание)
        import re

        if not re.match(r"^[A-Z0-9_-]+$", clean_symbol):
            return False

        # Проверка на разумную длину (2-20 символов)
        if len(clean_symbol) < 2 or len(clean_symbol) > 20:
            return False

        # Проверка на дату/время (ошибка в данных)
        if re.match(r"^\d{4}-\d{2}-\d{2}", clean_symbol):
            return False

        return True

    def add_pattern(self, pattern: TradingPattern):
        """Добавляет новый паттерн для обучения с автоматическим управлением"""
        # Валидация символа
        if not self._validate_symbol(pattern.symbol):
            logger.warning("⚠️ Пропущен паттерн с невалидным символом: '%s'", pattern.symbol)
            return

        self.patterns.append(pattern)
        self.metrics.total_patterns += 1

        if pattern.result == "WIN":
            self.metrics.successful_patterns += 1
        elif pattern.result == "LOSS":
            self.metrics.failed_patterns += 1

        # Пересчитываем метрики
        self.update_metrics()

        logger.info("📊 Добавлен паттерн: %s %s", pattern.symbol, pattern.signal_type)

        # Автоматическое управление паттернами (частота из конфига)
        cleanup_freq = AI_CONFIG.get("cleanup_frequency", 1000)
        if len(self.patterns) % cleanup_freq == 0:
            self.auto_manage_patterns()

    def update_metrics(self):
        """Обновляет метрики обучения"""
        if self.metrics.total_patterns > 0:
            self.metrics.accuracy = self.metrics.successful_patterns / self.metrics.total_patterns

            # Рассчитываем profit factor
            wins = [p.profit_pct for p in self.patterns if p.result == "WIN" and p.profit_pct]
            losses = [
                abs(p.profit_pct) for p in self.patterns if p.result == "LOSS" and p.profit_pct
            ]

            if wins and losses:
                total_wins = sum(wins)
                total_losses = sum(losses)
                if total_losses > 0:
                    self.metrics.profit_factor = total_wins / total_losses

        logger.info("📈 Метрики обновлены: Точность %.2f%%", self.metrics.accuracy * 100)

    def auto_manage_patterns(self, max_patterns=None):
        """
        Автоматически управляет количеством паттернов с умной очисткой

        Стратегия (на основе ML best practices):
        - Максимум 30K паттернов (оптимально для ML моделей)
        - Все WIN/LOSS паттерны сохраняются (важны для обучения)
        - Свежие паттерны (<60 дней) приоритетны
        - Старые нейтральные удаляются
        - Редкие символы сохраняются (важны для диверсификации)
        """
        # Используем конфигурацию
        if max_patterns is None:
            max_patterns = AI_CONFIG.get("max_patterns", 50000)

        if len(self.patterns) <= max_patterns:
            return  # Все в пределах нормы

        logger.info(
            "🧹 Начинаем умную очистку паттернов: %d → макс %d", len(self.patterns), max_patterns
        )

        pattern_age_days = AI_CONFIG.get("pattern_age_days", 60)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=pattern_age_days)

        # Категории паттернов по важности
        critical = []  # WIN/LOSS - всегда сохраняем
        important = []  # Свежие (<60 дней)
        rare_symbols = []  # Редкие символы (< 100 паттернов)
        neutral_old = []  # Старые нейтральные - кандидаты на удаление

        # Подсчитываем частоту символов
        symbol_counts = Counter(
            p.symbol
            for p in self.patterns
            if hasattr(p, "symbol") and self._validate_symbol(p.symbol)
        )
        rare_threshold = AI_CONFIG.get("rare_symbol_threshold", 100)

        # Классифицируем паттерны по важности и успешности
        for p in self.patterns:
            # Пропускаем паттерны с невалидными символами
            if not self._validate_symbol(p.symbol):
                continue

            # Критичные (WIN/LOSS) - приоритет сохранения
            if hasattr(p, "result") and p.result in ("WIN", "LOSS"):
                critical.append(p)
            # Свежие - сохраняем
            elif hasattr(p, "timestamp") and p.timestamp:
                # Нормализация для сравнения (устранение TypeError)
                p_ts = p.timestamp
                if p_ts.tzinfo is None:
                    p_ts = p_ts.replace(tzinfo=timezone.utc)

                if p_ts > cutoff_date:
                    important.append(p)
            # Остальные - кандидаты на удаление
            else:
                neutral_old.append(p)

        # 🎯 БАЛАНСИРОВКА WIN/LOSS
        wins = [p for p in critical if hasattr(p, "result") and p.result == "WIN"]
        losses = [p for p in critical if hasattr(p, "result") and p.result == "LOSS"]

        # Целевое соотношение: 65% WIN / 35% LOSS
        target_win_ratio = 0.65
        target_loss_ratio = 0.35

        # Если слишком много WIN, ограничиваем их количество
        if len(wins) > 0 and len(losses) > 0:
            # Рассчитываем целевое количество WIN на основе LOSS
            target_wins = int(len(losses) * (target_win_ratio / target_loss_ratio))

            if len(wins) > target_wins:
                # Сортируем WIN по прибыльности и свежести, оставляем только лучшие
                wins_sorted = sorted(
                    wins,
                    key=lambda x: (
                        -(hasattr(x, "profit_pct") and x.profit_pct or 0),
                        -(
                            x.timestamp.timestamp()
                            if hasattr(x, "timestamp") and x.timestamp
                            else 0
                        ),
                    ),
                )
                wins = wins_sorted[:target_wins]
                logger.info(
                    "   ⚖️ Балансировка: оставлено %d WIN из %d (цель: %d)",
                    len(wins),
                    len(wins_sorted),
                    target_wins,
                )

        # Сортируем LOSS по важности (более свежие и с большими убытками - важнее для обучения)
        losses_sorted = sorted(
            losses,
            key=lambda x: (
                # Приоритет большим убыткам (важно для обучения)
                abs(hasattr(x, "profit_pct") and x.profit_pct or 0),
                # Затем по свежести (новые первыми)
                -(x.timestamp.timestamp() if hasattr(x, "timestamp") and x.timestamp else 0),
            ),
            reverse=True,
        )
        losses = losses_sorted

        # Объединяем сбалансированные списки
        critical = wins + losses

        logger.info(
            "   ⚖️ Балансировка WIN/LOSS: WIN=%d (%.1f%%), LOSS=%d (%.1f%%)",
            len(wins),
            len(wins) / len(critical) * 100 if critical else 0,
            len(losses),
            len(losses) / len(critical) * 100 if critical else 0,
        )

        # Из нейтральных выделяем редкие символы для диверсификации
        # (но только если есть место)
        # УЛУЧШЕНИЕ: Удаляем старые NEUTRAL паттерны (>60 дней) сразу
        neutral_old_filtered = []
        for p in neutral_old:
            if hasattr(p, "timestamp") and p.timestamp and p.timestamp <= cutoff_date:
                # Старый NEUTRAL - удаляем
                continue
            neutral_old_filtered.append(p)
        neutral_old = neutral_old_filtered

        if neutral_old:
            rare_symbols_from_neutral = []
            for p in neutral_old:
                if (
                    hasattr(p, "symbol")
                    and self._validate_symbol(p.symbol)
                    and symbol_counts.get(p.symbol, 0) < rare_threshold
                ):
                    rare_symbols_from_neutral.append(p)

            # Добавляем редкие символы только если есть место
            space_available = max_patterns - len(critical) - len(important)
            if space_available > 0:
                # Сортируем редкие по времени (новые первыми)
                rare_sorted = sorted(
                    rare_symbols_from_neutral,
                    key=lambda x: x.timestamp
                    if hasattr(x, "timestamp") and x.timestamp
                    else datetime.min,
                    reverse=True,
                )
                rare_symbols = rare_sorted[: min(len(rare_sorted), space_available)]

                # Убираем выбранные редкие из нейтральных
                for rare_p in rare_symbols:
                    if rare_p in neutral_old:
                        neutral_old.remove(rare_p)

        # Рассчитываем сколько можем оставить
        essential_count = len(critical) + len(important) + len(rare_symbols)

        # УЛУЧШЕНИЕ: Если критичных слишком много, отсеиваем менее успешные
        if len(critical) > max_patterns * 0.8:  # Если критика больше 80% лимита
            logger.warning("⚠️ Критичных паттернов слишком много: %d", len(critical))
            # Оставляем только самые успешные критические паттерны
            space_for_critical = int(max_patterns * 0.7)  # 70% места для критичных
            critical = critical[:space_for_critical]
            logger.info(
                "   ✅ Оставлено топ-%d самых успешных критичных паттернов", space_for_critical
            )

        if essential_count > max_patterns:
            # Даже важных слишком много - оставляем самые успешные
            logger.warning(
                "⚠️ Важных паттернов больше лимита: %d > %d", essential_count, max_patterns
            )

            # УЛУЧШЕНИЕ: Сортируем важные по успешности, затем по свежести
            important_sorted = sorted(
                important,
                key=lambda x: (
                    # Сначала по прибыльности (если есть)
                    -(hasattr(x, "profit_pct") and x.profit_pct or 0),
                    # Затем по свежести (новые первыми)
                    -(x.timestamp.timestamp() if hasattr(x, "timestamp") and x.timestamp else 0),
                ),
            )

            space_for_important = max_patterns - len(critical) - len(rare_symbols)
            if space_for_important > 0:
                important = important_sorted[:space_for_important]
            else:
                important = []
            neutral_old = []
        else:
            # Есть место для нейтральных - берем самые свежие
            space_for_neutral = max_patterns - essential_count
            if space_for_neutral > 0 and neutral_old:
                # Сортируем нейтральные по времени (новые первыми)
                neutral_sorted = sorted(
                    neutral_old,
                    key=lambda x: x.timestamp
                    if hasattr(x, "timestamp") and x.timestamp
                    else datetime.min,
                    reverse=True,
                )
                neutral_old = neutral_sorted[:space_for_neutral]
            else:
                neutral_old = []

        # Собираем финальный список
        original_count = len(self.patterns)
        self.patterns = critical + important + rare_symbols + neutral_old

        # УЛУЧШЕННАЯ статистика очистки
        final_count = len(self.patterns)

        # Считаем успешность сохраненных паттернов
        win_count = sum(1 for p in critical if hasattr(p, "result") and p.result == "WIN")
        loss_count = sum(1 for p in critical if hasattr(p, "result") and p.result == "LOSS")

        # Средняя прибыль
        profits = [p.profit_pct for p in critical if hasattr(p, "profit_pct") and p.profit_pct]
        avg_profit = sum(profits) / len(profits) if profits else 0.0

        logger.info("✅ УМНАЯ очистка завершена:")
        logger.info(
            "   🏆 Критичные (WIN/LOSS): %d (WIN: %d, LOSS: %d)",
            len(critical),
            win_count,
            loss_count,
        )
        logger.info("   💰 Средняя прибыль сохраненных: %.2f%%", avg_profit)
        logger.info("   🕐 Свежие (<60д): %d", len(important))
        logger.info("   💎 Редкие символы: %d", len(rare_symbols))
        logger.info("   📊 Нейтральные: %d", len(neutral_old))
        logger.info("   ✅ Итого сохранено: %d паттернов (было: %d)", final_count, original_count)

        # Сохраняем очищенные паттерны
        self.save_patterns()

    def calculate_pattern_importance(self, pattern: TradingPattern) -> float:
        """
        Рассчитывает важность паттерна для обучения (0.0 - 1.0)

        Критерии важности:
        - WIN/LOSS: высокая важность (0.9-1.0)
        - Свежесть: новые важнее старых
        - Редкость символа: редкие важнее частых
        - Прибыльность: большие прибыли/убытки важнее
        """
        importance = 0.0

        # Результат сделки (40% веса)
        if hasattr(pattern, "result") and pattern.result:
            if pattern.result == "WIN":
                importance += 0.4
                # Бонус за высокую прибыль
                if (
                    hasattr(pattern, "profit_pct")
                    and pattern.profit_pct
                    and pattern.profit_pct > 5.0
                ):
                    importance += 0.1
            elif pattern.result == "LOSS":
                importance += 0.4
                # Бонус за большой убыток (учимся избегать)
                if (
                    hasattr(pattern, "profit_pct")
                    and pattern.profit_pct
                    and abs(pattern.profit_pct) > 3.0
                ):
                    importance += 0.1

        # Свежесть (30% веса)
        if hasattr(pattern, "timestamp") and pattern.timestamp:
            age_days = (
                datetime.now(timezone.utc) - pattern.timestamp.replace(tzinfo=timezone.utc)
                if pattern.timestamp.tzinfo is None
                else pattern.timestamp
            ).days
            if age_days < 7:
                importance += 0.3
            elif age_days < 30:
                importance += 0.2
            elif age_days < 60:
                importance += 0.1

        # Редкость символа (20% веса)
        if hasattr(pattern, "symbol") and pattern.symbol:
            symbol_counts = Counter(p.symbol for p in self.patterns if hasattr(p, "symbol"))
            symbol_frequency = symbol_counts.get(pattern.symbol, 0)
            if symbol_frequency < 50:
                importance += 0.2
            elif symbol_frequency < 100:
                importance += 0.1

        # Уникальные условия (10% веса)
        if hasattr(pattern, "market_conditions") and pattern.market_conditions:
            # Паттерны с редкими рыночными условиями более ценны
            conditions = pattern.market_conditions
            if isinstance(conditions, dict) and conditions.get("volatility", "normal") in (
                "high",
                "low",
            ):
                importance += 0.05
            if isinstance(conditions, dict) and conditions.get("trend_strength", 0) > 70:
                importance += 0.05

        return min(importance, 1.0)  # Ограничиваем 1.0

    def analyze_patterns(self) -> Dict[str, Any]:
        """Анализирует паттерны и выявляет закономерности"""
        if not self.patterns:
            return {"error": "Нет данных для анализа"}

        analysis = {
            "total_patterns": len(self.patterns),
            "symbols": {},
            "signal_types": {"LONG": 0, "SHORT": 0},
            "success_rates": {},
            "best_indicators": {},
            "market_conditions": {},
        }

        # Анализ по символам
        for pattern in self.patterns:
            # Проверяем наличие обязательных полей
            if not hasattr(pattern, "symbol") or pattern.symbol is None:
                logger.warning("⚠️ Паттерн без символа пропущен")
                continue

            symbol = pattern.symbol

            if symbol not in analysis["symbols"]:
                analysis["symbols"][symbol] = {"total": 0, "wins": 0, "losses": 0}

            analysis["symbols"][symbol]["total"] += 1

            # Безопасная проверка результата
            if hasattr(pattern, "result") and pattern.result is not None:
                if pattern.result == "WIN":
                    analysis["symbols"][symbol]["wins"] += 1
                elif pattern.result == "LOSS":
                    analysis["symbols"][symbol]["losses"] += 1

            # Безопасная проверка типа сигнала
            if hasattr(pattern, "signal_type") and pattern.signal_type is not None:
                signal_type = pattern.signal_type
                if signal_type in analysis["signal_types"]:
                    analysis["signal_types"][signal_type] += 1
                else:
                    # Если тип сигнала не LONG/SHORT, добавляем в общий счетчик
                    if "OTHER" not in analysis["signal_types"]:
                        analysis["signal_types"]["OTHER"] = 0
                    analysis["signal_types"]["OTHER"] += 1

        # Расчет успешности по символам
        for symbol, data in analysis["symbols"].items():
            if data["total"] > 0:
                success_rate = data["wins"] / data["total"]
                analysis["success_rates"][symbol] = success_rate

        logger.info("🔍 Анализ завершен: %d символов", len(analysis["symbols"]))
        return analysis

    def get_learning_recommendations(self) -> List[str]:
        """Получает рекомендации на основе обучения"""
        recommendations = []

        if self.metrics.accuracy < 0.6:
            recommendations.append("⚠️ Низкая точность сигналов. Рекомендуется улучшить фильтры")

        if self.metrics.profit_factor < 1.2:
            recommendations.append(
                "⚠️ Низкий profit factor. Рекомендуется пересмотреть риск-менеджмент"
            )

        # Анализ лучших символов
        analysis = self.analyze_patterns()
        if analysis.get("success_rates"):
            best_symbols = sorted(
                analysis["success_rates"].items(), key=lambda x: x[1], reverse=True
            )[:3]

            for symbol, rate in best_symbols:
                recommendations.append(f"✅ {symbol}: успешность {rate:.1%}")

        return recommendations

    def validate_system_data(self) -> Dict[str, Any]:
        """Проверяет все данные системы"""
        validation_results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
            "errors": [],
            "warnings": [],
            "recommendations": [],
        }

        # Проверка файлов конфигурации
        config_files = ["config.py", "user_data.json", "trading.db"]
        for file in config_files:
            if os.path.exists(file):
                validation_results["checks"][f"file_{file}"] = "✅ Найден"
            else:
                validation_results["errors"].append(f"❌ Файл {file} не найден")

        # Проверка API подключений
        validation_results["checks"]["api_status"] = "🔍 Проверка API..."

        # Проверка данных пользователей
        try:
            with open("user_data.json", encoding="utf-8") as f:
                user_data = json.load(f)

            for user_id, data in user_data.items():
                required_fields = ["deposit", "trade_mode", "filter_mode"]
                for field in required_fields:
                    if field not in data or data[field] is None:
                        validation_results["warnings"].append(
                            f"⚠️ Пользователь {user_id}: отсутствует {field}"
                        )
        except (OSError, json.JSONDecodeError, KeyError) as e:
            validation_results["errors"].append(f"❌ Ошибка чтения user_data.json: {e}")

        logger.info("🔍 Валидация завершена: %d ошибок", len(validation_results["errors"]))
        return validation_results

    def auto_optimize_parameters(self) -> Dict[str, Any]:
        """Автоматически оптимизирует ВСЕ параметры системы для максимальной прибыльности"""
        optimization_results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "optimizations": {},
            "improvements": [],
            "parameter_changes": {},
        }

        # Проверяем доступность pandas/numpy
        if np is None:
            optimization_results["improvements"].append("⚠️ numpy недоступен для оптимизации")
            return optimization_results

        # Анализ текущих паттернов
        if len(self.patterns) < 10:
            optimization_results["improvements"].append(
                "📊 Недостаточно данных для оптимизации. Нужно больше паттернов"
            )
            return optimization_results

        # Анализ лучших параметров
        analysis = self.analyze_patterns()

        # 1. ОПТИМИЗАЦИЯ РИСКА И ЛЕВЕРИДЖА
        successful_patterns = [p for p in self.patterns if p.result == "WIN"]
        if successful_patterns:
            avg_successful_risk = np.mean([p.risk_pct for p in successful_patterns])
            avg_successful_leverage = np.mean([p.leverage for p in successful_patterns])

            optimization_results["parameter_changes"]["optimal_risk_pct"] = round(
                avg_successful_risk, 2
            )
            optimization_results["parameter_changes"]["optimal_leverage"] = round(
                avg_successful_leverage, 1
            )
            optimization_results["improvements"].append(
                f"🎯 Оптимальный риск: {avg_successful_risk:.2f}%, леверидж: {avg_successful_leverage:.1f}x"
            )

        # 2. ОПТИМИЗАЦИЯ ТЕЙК-ПРОФИТОВ
        tp1_profits = [p.profit_pct for p in successful_patterns if p.tp1 and p.profit_pct <= 3.0]
        tp2_profits = [p.profit_pct for p in successful_patterns if p.tp2 and p.profit_pct > 3.0]

        if tp1_profits:
            optimal_tp1 = np.percentile(tp1_profits, 75)  # 75-й перцентиль
            optimization_results["parameter_changes"]["optimal_tp1"] = round(optimal_tp1, 2)

        if tp2_profits:
            optimal_tp2 = np.percentile(tp2_profits, 75)
            optimization_results["parameter_changes"]["optimal_tp2"] = round(optimal_tp2, 2)

        # 3. ОПТИМИЗАЦИЯ ФИЛЬТРОВ (RSI, EMA, Volume)
        rsi_analysis = self._analyze_indicator_performance("RSI")
        if rsi_analysis:
            optimization_results["parameter_changes"]["optimal_rsi_oversold"] = rsi_analysis.get(
                "best_oversold",
                30,
            )
            optimization_results["parameter_changes"]["optimal_rsi_overbought"] = rsi_analysis.get(
                "best_overbought",
                70,
            )

        ema_analysis = self._analyze_indicator_performance("EMA")
        if ema_analysis:
            optimization_results["parameter_changes"]["optimal_ema_fast"] = ema_analysis.get(
                "best_fast", 21
            )
            optimization_results["parameter_changes"]["optimal_ema_slow"] = ema_analysis.get(
                "best_slow", 50
            )

        # 4. ОПТИМИЗАЦИЯ РЫНОЧНЫХ УСЛОВИЙ
        market_conditions_analysis = self._analyze_market_conditions()
        if market_conditions_analysis:
            optimization_results["parameter_changes"]["optimal_btc_trend"] = (
                market_conditions_analysis.get("best_btc_trend", "BULLISH")
            )
            optimization_results["parameter_changes"]["optimal_volume_class"] = (
                market_conditions_analysis.get("best_volume", "HIGH")
            )

        # 5. ОПТИМИЗАЦИЯ СИМВОЛОВ
        if analysis.get("success_rates"):
            best_symbols = [
                symbol for symbol, rate in analysis["success_rates"].items() if rate > 0.7
            ]
            if best_symbols:
                optimization_results["parameter_changes"]["preferred_symbols"] = best_symbols
                optimization_results["improvements"].append(
                    f"✅ Рекомендуется фокус на символы: {', '.join(best_symbols)}"
                )

        # 6. ОПТИМИЗАЦИЯ ВРЕМЕНИ ТОРГОВЛИ
        time_analysis = self._analyze_time_performance()
        if time_analysis:
            optimization_results["parameter_changes"]["optimal_trading_hours"] = time_analysis.get(
                "best_hours", [9, 15, 21]
            )
            optimization_results["improvements"].append(
                f"⏰ Лучшее время торговли: {time_analysis['best_hours']}"
            )

        # 7. ОПТИМИЗАЦИЯ STOP-LOSS
        sl_analysis = self._analyze_stop_loss_performance()
        if sl_analysis:
            optimization_results["parameter_changes"]["optimal_stop_loss_pct"] = round(
                sl_analysis.get("best_sl_pct", 2.0), 2
            )

        logger.info(
            "🔧 Полная оптимизация завершена: %d параметров, %d улучшений",
            len(optimization_results["parameter_changes"]),
            len(optimization_results["improvements"]),
        )
        return optimization_results

    def apply_optimized_parameters(self, optimization_results: Dict[str, Any]) -> bool:
        """Автоматически применяет оптимизированные параметры в систему"""
        try:
            if not optimization_results.get("parameter_changes"):
                logger.warning("⚠️ Нет параметров для применения")
                return False

            applied_count = 0
            parameter_changes = optimization_results["parameter_changes"]

            # 1. Применяем параметры риска и левериджа
            if "optimal_risk_pct" in parameter_changes:
                self._update_system_parameter("risk_pct", parameter_changes["optimal_risk_pct"])
                applied_count += 1
                logger.info(
                    "🎯 Применен оптимальный риск: %s%%", parameter_changes["optimal_risk_pct"]
                )

            if "optimal_leverage" in parameter_changes:
                self._update_system_parameter("leverage", parameter_changes["optimal_leverage"])
                applied_count += 1
                logger.info(
                    "⚡ Применен оптимальный леверидж: %sx", parameter_changes["optimal_leverage"]
                )

            # 2. Применяем тейк-профиты
            if "optimal_tp1" in parameter_changes:
                self._update_system_parameter("tp1", parameter_changes["optimal_tp1"])
                applied_count += 1
                logger.info("🎯 Применен оптимальный TP1: %s%%", parameter_changes["optimal_tp1"])

            if "optimal_tp2" in parameter_changes:
                self._update_system_parameter("tp2", parameter_changes["optimal_tp2"])
                applied_count += 1
                logger.info("🎯 Применен оптимальный TP2: %s%%", parameter_changes["optimal_tp2"])

            # 3. Применяем параметры индикаторов
            if "optimal_rsi_oversold" in parameter_changes:
                self._update_system_parameter(
                    "rsi_oversold", parameter_changes["optimal_rsi_oversold"]
                )
                applied_count += 1
                logger.info(
                    "📊 Применен оптимальный RSI oversold: %s",
                    parameter_changes["optimal_rsi_oversold"],
                )

            if "optimal_rsi_overbought" in parameter_changes:
                self._update_system_parameter(
                    "rsi_overbought", parameter_changes["optimal_rsi_overbought"]
                )
                applied_count += 1
                logger.info(
                    "📊 Применен оптимальный RSI overbought: %s",
                    parameter_changes["optimal_rsi_overbought"],
                )

            if "optimal_ema_fast" in parameter_changes:
                self._update_system_parameter("ema_fast", parameter_changes["optimal_ema_fast"])
                applied_count += 1
                logger.info(
                    "📈 Применен оптимальный EMA fast: %s", parameter_changes["optimal_ema_fast"]
                )

            if "optimal_ema_slow" in parameter_changes:
                self._update_system_parameter("ema_slow", parameter_changes["optimal_ema_slow"])
                applied_count += 1
                logger.info(
                    "📈 Применен оптимальный EMA slow: %s", parameter_changes["optimal_ema_slow"]
                )

            # 4. Применяем stop-loss
            if "optimal_stop_loss_pct" in parameter_changes:
                self._update_system_parameter(
                    "stop_loss_pct", parameter_changes["optimal_stop_loss_pct"]
                )
                applied_count += 1
                logger.info(
                    "🛡️ Применен оптимальный Stop-Loss: %s%%",
                    parameter_changes["optimal_stop_loss_pct"],
                )

            # 5. Применяем предпочтительные символы
            if "preferred_symbols" in parameter_changes:
                self._update_system_parameter(
                    "preferred_symbols", parameter_changes["preferred_symbols"]
                )
                applied_count += 1
                logger.info(
                    "🎯 Применены предпочтительные символы: %s",
                    parameter_changes["preferred_symbols"],
                )

            # 6. Применяем оптимальное время торговли
            if "optimal_trading_hours" in parameter_changes:
                self._update_system_parameter(
                    "trading_hours", parameter_changes["optimal_trading_hours"]
                )
                applied_count += 1
                logger.info(
                    "⏰ Применены оптимальные часы торговли: %s",
                    parameter_changes["optimal_trading_hours"],
                )

            logger.info("✅ Успешно применено %d параметров", applied_count)
            return applied_count > 0

        except (KeyError, TypeError, ValueError) as e:
            logger.error("❌ Ошибка применения параметров: %s", e)
            return False

    def _update_system_parameter(self, parameter_name: str, value: Any) -> bool:
        """Обновляет параметр в системе (в базе данных или конфиге)"""
        try:
            # Здесь можно интегрировать с базой данных или конфигом
            # Пока сохраняем в файл для демонстрации

            # Создаем файл с оптимизированными параметрами
            optimized_params_file = os.path.join(self.data_dir, "optimized_parameters.json")

            # Читаем существующие параметры
            if os.path.exists(optimized_params_file):
                with open(optimized_params_file, encoding="utf-8") as f:
                    params = json.load(f)
            else:
                params = {}

            # Обновляем параметр
            params[parameter_name] = value
            params["last_updated"] = datetime.now(timezone.utc).isoformat()

            # Сохраняем обратно
            with open(optimized_params_file, "w", encoding="utf-8") as f:
                json.dump(params, f, ensure_ascii=False, indent=2)

            logger.debug("📝 Параметр %s обновлен в %s", parameter_name, optimized_params_file)
            return True

        except (OSError, json.JSONDecodeError, TypeError) as e:
            logger.error("❌ Ошибка обновления параметра %s: %s", parameter_name, e)
            return False

    def _analyze_indicator_performance(self, indicator_name: str) -> Optional[Dict[str, Any]]:
        """Анализирует эффективность индикатора"""
        try:
            if not self.patterns:
                return None

            successful_patterns = [p for p in self.patterns if p.result == "WIN"]
            if not successful_patterns:
                return None

            # Анализ RSI
            if indicator_name == "RSI":
                rsi_values = []
                for pattern in successful_patterns:
                    if "RSI" in pattern.indicators:
                        rsi_values.append(pattern.indicators["RSI"])

                if rsi_values:
                    avg_rsi = np.mean(rsi_values)
                    return {
                        "best_oversold": max(25, min(35, avg_rsi - 10)),
                        "best_overbought": min(75, max(65, avg_rsi + 10)),
                    }

            # Анализ EMA
            elif indicator_name == "EMA":
                ema_fast_values = []
                ema_slow_values = []
                for pattern in successful_patterns:
                    if "EMA_Fast" in pattern.indicators:
                        ema_fast_values.append(pattern.indicators["EMA_Fast"])
                    if "EMA_Slow" in pattern.indicators:
                        ema_slow_values.append(pattern.indicators["EMA_Slow"])

                if ema_fast_values and ema_slow_values:
                    return {
                        "best_fast": max(10, min(30, int(np.mean(ema_fast_values)))),
                        "best_slow": max(40, min(60, int(np.mean(ema_slow_values)))),
                    }

            return None

        except (KeyError, TypeError, ValueError, AttributeError) as e:
            logger.error("❌ Ошибка анализа %s: %s", indicator_name, e)
            return None

    def _analyze_market_conditions(self) -> Optional[Dict[str, Any]]:
        """Анализирует эффективность рыночных условий"""
        try:
            if not self.patterns:
                return None

            successful_patterns = [p for p in self.patterns if p.result == "WIN"]
            if not successful_patterns:
                return None

            # Анализ BTC тренда
            btc_trends = {}
            volume_classes = {}

            for pattern in successful_patterns:
                if "BTC_Trend" in pattern.market_conditions:
                    trend = pattern.market_conditions["BTC_Trend"]
                    btc_trends[trend] = btc_trends.get(trend, 0) + 1

                if "Volume_Class" in pattern.market_conditions:
                    volume_class = pattern.market_conditions["Volume_Class"]
                    volume_classes[volume_class] = volume_classes.get(volume_class, 0) + 1

            result = {}
            if btc_trends:
                best_btc_trend = max(btc_trends, key=btc_trends.get)
                result["best_btc_trend"] = best_btc_trend

            if volume_classes:
                best_volume = max(volume_classes, key=volume_classes.get)
                result["best_volume"] = best_volume

            return result if result else None

        except (KeyError, TypeError, AttributeError) as e:
            logger.error("❌ Ошибка анализа рыночных условий: %s", e)
            return None

    def _analyze_time_performance(self) -> Optional[Dict[str, Any]]:
        """Анализирует эффективность по времени"""
        try:
            if not self.patterns:
                return None

            successful_patterns = [p for p in self.patterns if p.result == "WIN"]
            if not successful_patterns:
                return None

            # Анализ по часам
            hour_performance = {}
            for pattern in successful_patterns:
                hour = pattern.timestamp.hour
                hour_performance[hour] = hour_performance.get(hour, 0) + 1

            if hour_performance:
                # Находим 3 лучших часа
                best_hours = sorted(hour_performance, key=hour_performance.get, reverse=True)[:3]
                return {"best_hours": best_hours}

            return None

        except (AttributeError, TypeError) as e:
            logger.error("❌ Ошибка анализа времени: %s", e)
            return None

    def _analyze_stop_loss_performance(self) -> Optional[Dict[str, Any]]:
        """Анализирует эффективность stop-loss"""
        try:
            if not self.patterns:
                return None

            # Анализируем неудачные паттерны для определения оптимального SL
            failed_patterns = [p for p in self.patterns if p.result == "LOSS"]
            if not failed_patterns:
                return None

            # Рассчитываем средние потери
            losses = [abs(p.profit_pct) for p in failed_patterns if p.profit_pct is not None]
            if losses:
                avg_loss = np.mean(losses)
                # Оптимальный SL должен быть меньше среднего убытка
                optimal_sl = max(1.0, min(3.0, avg_loss * 0.8))
                return {"best_sl_pct": optimal_sl}

            return None

        except (AttributeError, TypeError, ValueError) as e:
            logger.error("❌ Ошибка анализа stop-loss: %s", e)
            return None

    def generate_learning_report(self) -> str:
        """Генерирует отчет об обучении"""
        report = f"""
🤖 ОТЧЕТ ОБ ОБУЧЕНИИ ИИ СИСТЕМЫ
{"=" * 50}

📊 ОБЩАЯ СТАТИСТИКА:
• Всего паттернов: {self.metrics.total_patterns}
• Успешных: {self.metrics.successful_patterns}
• Неудачных: {self.metrics.failed_patterns}
• Точность: {self.metrics.accuracy:.1%}
• Profit Factor: {self.metrics.profit_factor:.2f}

🔍 АНАЛИЗ ПАТТЕРНОВ:
"""

        analysis = self.analyze_patterns()
        if analysis.get("success_rates"):
            report += "\n📈 ЛУЧШИЕ СИМВОЛЫ:\n"
            for symbol, rate in sorted(
                analysis["success_rates"].items(), key=lambda x: x[1], reverse=True
            )[:5]:
                report += f"• {symbol}: {rate:.1%}\n"

        # Рекомендации
        recommendations = self.get_learning_recommendations()
        if recommendations:
            report += "\n💡 РЕКОМЕНДАЦИИ:\n"
            for rec in recommendations:
                report += f"• {rec}\n"

        return report

    async def continuous_learning(self):
        """Непрерывное обучение системы"""
        logger.info("🔄 Запуск непрерывного обучения...")

        while True:
            try:
                # Валидация данных
                validation = self.validate_system_data()
                if validation["errors"]:
                    logger.warning("⚠️ Найдены ошибки: %s", validation["errors"])

                # Оптимизация параметров
                optimization = self.auto_optimize_parameters()
                if optimization["improvements"]:
                    logger.info("🔧 Улучшения: %s", optimization["improvements"])

                # Автоматическое применение оптимизированных параметров
                if optimization.get("parameter_changes"):
                    logger.info("🤖 Применяем оптимизированные параметры...")
                    applied = self.apply_optimized_parameters(optimization)
                    if applied:
                        logger.info("✅ Оптимизированные параметры успешно применены!")
                    else:
                        logger.warning("⚠️ Не удалось применить некоторые параметры")

                # Сохранение данных
                self.save_patterns()
                self.save_learning_model()
                self.save_metrics()

                # Генерация отчета
                self.generate_learning_report()
                logger.info("📊 Отчет об обучении сгенерирован")

                # Пауза между циклами обучения
                await asyncio.sleep(3600)  # 1 час

            except (OSError, KeyError, TypeError, ValueError) as e:
                logger.error("❌ Ошибка в непрерывном обучении: %s", e)
                await asyncio.sleep(300)  # 5 минут при ошибке


# Глобальный экземпляр системы обучения
ai_learning = AILearningSystem()


async def start_ai_learning():
    """Запускает систему обучения ИИ"""
    logger.info("🚀 Запуск системы обучения ИИ...")
    await ai_learning.continuous_learning()


if __name__ == "__main__":
    # Тестирование системы
    print("🤖 Тестирование системы обучения ИИ...")

    # Создаем тестовый паттерн
    test_pattern = TradingPattern(
        symbol="BTCUSDT",
        timestamp=datetime.now(timezone.utc),
        signal_type="LONG",
        entry_price=50000.0,
        tp1=51000.0,
        tp2=52000.0,
        risk_pct=2.0,
        leverage=1.0,
        indicators={"RSI": 45.0, "EMA7": 50000.0, "BB_upper": 51000.0},
        market_conditions={"BTC_trend": "BULLISH", "volume": "HIGH"},
        result="WIN",
        profit_pct=2.0,
    )

    # Добавляем паттерн
    ai_learning.add_pattern(test_pattern)

    # Генерируем отчет
    test_report = ai_learning.generate_learning_report()
    print(test_report)
