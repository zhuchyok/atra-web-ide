#!/usr/bin/env python3
"""
Адаптивная система управления качеством сигналов ATRA

Автоматически анализирует результаты каждые 3 дня и корректирует:
- Порог очков для генерации сигналов
- Веса индикаторов
- Фильтры качества
"""

import sqlite3
import json
import time
import logging
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, List, Tuple, Optional
import statistics

logger = logging.getLogger(__name__)

class AdaptiveSignalSystem:
    def __init__(self, db_path: str = "trading.db"):
        self.db_path = db_path
        self.analysis_interval_days = 3
        self.min_signals_for_analysis = 20
        self.target_win_rate = 0.55  # Целевой процент успешных сигналов
        self.target_signal_frequency = 5  # Целевое количество сигналов в день

        # Текущие настройки
        self.current_score_threshold = 4
        self.min_score_threshold = 3
        self.max_score_threshold = 7

        # Веса индикаторов (для будущего развития)
        self.indicator_weights = {
            'bb_position': 1.0,
            'ema_trend': 1.0,
            'rsi': 1.0,
            'volume_ratio': 1.0,
            'volatility': 1.0,
            'momentum': 1.0,
            'trend_strength': 1.0,
            'adx': 1.0,
            'ema50_slope': 1.0,
            'bb_direction': 1.0
        }

    def get_last_analysis_time(self) -> Optional[datetime]:
        """Получить время последнего анализа"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT value FROM system_settings
                    WHERE key = 'last_adaptive_analysis'
                """)
                result = cursor.fetchone()
                if result:
                    return datetime.fromisoformat(result[0])
        except Exception as e:
            logger.warning(f"Ошибка получения времени последнего анализа: {e}")
        return None

    def set_last_analysis_time(self, analysis_time: datetime):
        """Установить время последнего анализа"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO system_settings (key, value)
                    VALUES ('last_adaptive_analysis', ?)
                """, (analysis_time.isoformat(),))
                conn.commit()
        except Exception as e:
            logger.warning(f"Ошибка сохранения времени анализа: {e}")

    def get_signal_statistics(self, days_back: int = 3) -> Dict:
        """Получить статистику сигналов за последние N дней"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Получаем все сигналы за период
                start_time = get_utc_now() - timedelta(days=days_back)
                cursor.execute("""
                    SELECT
                        symbol, side, entry_price, tp1_price, tp2_price,
                        sl_price, created_at, status, score_threshold
                    FROM signals
                    WHERE created_at >= ?
                    ORDER BY created_at DESC
                """, (start_time.isoformat(),))

                signals = cursor.fetchall()

                if len(signals) < self.min_signals_for_analysis:
                    return {
                        'total_signals': len(signals),
                        'insufficient_data': True,
                        'win_rate': 0.0,
                        'avg_daily_signals': 0.0,
                        'avg_score_threshold': self.current_score_threshold
                    }

                # Анализируем результаты
                successful_signals = 0
                total_signals = len(signals)
                score_thresholds = []

                for signal in signals:
                    symbol, side, entry_price, tp1_price, tp2_price, sl_price, created_at, status, score_threshold = signal

                    if score_threshold:
                        score_thresholds.append(score_threshold)

                    # Определяем успешность сигнала
                    if status in ['tp1_hit', 'tp2_hit']:
                        successful_signals += 1
                    elif status == 'sl_hit':
                        pass  # Неуспешный сигнал
                    else:
                        # Для активных сигналов проверяем текущую цену
                        try:
                            # Здесь можно добавить проверку текущей цены
                            # Пока считаем как неуспешный
                            pass
                        except:
                            pass

                win_rate = successful_signals / total_signals if total_signals > 0 else 0.0
                avg_daily_signals = total_signals / days_back
                avg_score_threshold = statistics.mean(score_thresholds) if score_thresholds else self.current_score_threshold

                return {
                    'total_signals': total_signals,
                    'successful_signals': successful_signals,
                    'win_rate': win_rate,
                    'avg_daily_signals': avg_daily_signals,
                    'avg_score_threshold': avg_score_threshold,
                    'insufficient_data': False
                }

        except Exception as e:
            logger.error(f"Ошибка получения статистики сигналов: {e}")
            return {
                'total_signals': 0,
                'insufficient_data': True,
                'win_rate': 0.0,
                'avg_daily_signals': 0.0,
                'avg_score_threshold': self.current_score_threshold
            }

    def calculate_optimal_threshold(self, stats: Dict) -> int:
        """Рассчитать оптимальный порог очков на основе статистики"""
        if stats['insufficient_data']:
            return self.current_score_threshold

        win_rate = stats['win_rate']
        avg_daily_signals = stats['avg_daily_signals']

        # Логика адаптации
        new_threshold = self.current_score_threshold

        # Если win rate слишком низкий - увеличиваем порог (строже)
        if win_rate < self.target_win_rate - 0.05:  # Ниже 50%
            new_threshold = min(self.max_score_threshold, self.current_score_threshold + 1)
            logger.info(f"Win rate {win_rate:.2%} слишком низкий, увеличиваем порог до {new_threshold}")

        # Если win rate хороший, но сигналов мало - снижаем порог (мягче)
        elif win_rate >= self.target_win_rate and avg_daily_signals < self.target_signal_frequency:
            new_threshold = max(self.min_score_threshold, self.current_score_threshold - 1)
            logger.info(f"Win rate {win_rate:.2%} хороший, но сигналов мало ({avg_daily_signals:.1f}/день), снижаем порог до {new_threshold}")

        # Если win rate отличный и сигналов достаточно - оставляем как есть
        elif win_rate >= self.target_win_rate + 0.05 and avg_daily_signals >= self.target_signal_frequency:
            logger.info(f"Win rate {win_rate:.2%} отличный, сигналов достаточно ({avg_daily_signals:.1f}/день), оставляем порог {new_threshold}")

        # Если сигналов слишком много - увеличиваем порог
        elif avg_daily_signals > self.target_signal_frequency * 2:
            new_threshold = min(self.max_score_threshold, self.current_score_threshold + 1)
            logger.info(f"Слишком много сигналов ({avg_daily_signals:.1f}/день), увеличиваем порог до {new_threshold}")

        return new_threshold

    def update_score_threshold(self, new_threshold: int):
        """Обновить порог очков в системе"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO system_settings (key, value)
                    VALUES ('score_threshold', ?)
                """, (str(new_threshold),))
                conn.commit()

            self.current_score_threshold = new_threshold
            logger.info(f"Порог очков обновлен: {new_threshold}")

        except Exception as e:
            logger.error(f"Ошибка обновления порога очков: {e}")

    def get_current_threshold(self) -> int:
        """Получить текущий порог очков из БД"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT value FROM system_settings
                    WHERE key = 'score_threshold'
                """)
                result = cursor.fetchone()
                if result:
                    return int(result[0])
        except Exception as e:
            logger.warning(f"Ошибка получения порога очков: {e}")

        return self.current_score_threshold

    def run_adaptive_analysis(self) -> bool:
        """Запустить адаптивный анализ и корректировку"""
        try:
            # Проверяем, нужно ли проводить анализ
            last_analysis = self.get_last_analysis_time()
            if last_analysis:
                time_since_analysis = get_utc_now() - last_analysis
                if time_since_analysis.days < self.analysis_interval_days:
                    logger.info(f"Анализ не требуется, прошло {time_since_analysis.days} дней")
                    return False

            logger.info("Запуск адаптивного анализа сигналов...")

            # Получаем текущий порог
            self.current_score_threshold = self.get_current_threshold()

            # Анализируем статистику
            stats = self.get_signal_statistics(self.analysis_interval_days)

            if stats['insufficient_data']:
                logger.warning(f"Недостаточно данных для анализа: {stats['total_signals']} сигналов")
                return False

            # Рассчитываем новый порог
            new_threshold = self.calculate_optimal_threshold(stats)

            # Обновляем порог если изменился
            if new_threshold != self.current_score_threshold:
                self.update_score_threshold(new_threshold)

                # Логируем изменения
                logger.info(f"""
=== АДАПТИВНАЯ КОРРЕКТИРОВКА ===
Период анализа: {self.analysis_interval_days} дней
Всего сигналов: {stats['total_signals']}
Успешных: {stats['successful_signals']}
Win rate: {stats['win_rate']:.2%}
Среднее сигналов/день: {stats['avg_daily_signals']:.1f}
Старый порог: {self.current_score_threshold}
Новый порог: {new_threshold}
===============================
                """)

                return True
            else:
                logger.info("Порог очков оптимален, изменений не требуется")
                return False

        except Exception as e:
            logger.error(f"Ошибка адаптивного анализа: {e}")
            return False

    def get_analysis_report(self) -> str:
        """Получить отчет о текущем состоянии системы"""
        try:
            stats = self.get_signal_statistics(self.analysis_interval_days)
            current_threshold = self.get_current_threshold()
            last_analysis = self.get_last_analysis_time()

            report = f"""
=== ОТЧЕТ АДАПТИВНОЙ СИСТЕМЫ ===
Текущий порог очков: {current_threshold}
Последний анализ: {last_analysis.strftime('%d.%m.%Y %H:%M') if last_analysis else 'Никогда'}

Статистика за {self.analysis_interval_days} дней:
• Всего сигналов: {stats['total_signals']}
• Успешных: {stats['successful_signals']}
• Win rate: {stats['win_rate']:.2%}
• Сигналов/день: {stats['avg_daily_signals']:.1f}

Цели:
• Целевой win rate: {self.target_win_rate:.0%}
• Целевых сигналов/день: {self.target_signal_frequency}
• Диапазон порога: {self.min_score_threshold}-{self.max_score_threshold}
===============================
            """

            return report

        except Exception as e:
            logger.error(f"Ошибка создания отчета: {e}")
            return "Ошибка создания отчета"


# Глобальный экземпляр системы
adaptive_system = AdaptiveSignalSystem()


def run_adaptive_analysis() -> bool:
    """Запустить адаптивный анализ (для вызова из main.py)"""
    return adaptive_system.run_adaptive_analysis()


def get_current_score_threshold() -> int:
    """Получить текущий порог очков"""
    return adaptive_system.get_current_threshold()


def get_analysis_report() -> str:
    """Получить отчет о системе"""
    return adaptive_system.get_analysis_report()


if __name__ == "__main__":
    # Тестирование системы
    logging.basicConfig(level=logging.INFO)

    print("Тестирование адаптивной системы...")
    print(get_analysis_report())

    if run_adaptive_analysis():
        print("Анализ выполнен, настройки обновлены")
    else:
        print("Анализ не требуется или не выполнен")
