#!/usr/bin/env python3
"""
Анализ логов системы ATRA
Проверяет логи генерации сигналов, отправки, ошибок и производительности
"""

import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple


class LogAnalyzer:
    """Анализатор логов ATRA"""

    def __init__(self, log_dir: str = "logs", log_file: str = "atra.log"):
        self.log_dir = Path(log_dir)
        # Проверяем несколько возможных файлов логов
        possible_logs = [
            "system_improved.log",  # Основной лог из main.py
            log_dir + "/atra.log",
            log_dir + "/system.log",
            log_dir + "/signals.log",
            log_dir + "/errors.log",
        ]
        self.log_file = None
        for log_path in possible_logs:
            full_path = Path(log_path)
            if full_path.exists() and full_path.stat().st_size > 0:
                self.log_file = full_path
                break
        if not self.log_file:
            self.log_file = self.log_dir / log_file
        self.results = {
            "signals_generated": [],
            "signals_sent": [],
            "signals_failed": [],
            "no_signals": [],
            "errors": [],
            "cycles": [],
            "users": set(),
            "symbols": set(),
            "filters_blocked": defaultdict(int),
            "timestamps": [],
        }

    def analyze(self) -> Dict:
        """Анализирует логи"""
        print("🔍 АНАЛИЗ ЛОГОВ СИСТЕМЫ ATRA")
        print("=" * 80)

        if not self.log_file.exists():
            print(f"❌ Файл логов не найден: {self.log_file}")
            print(f"📁 Проверяю директорию: {self.log_dir}")
            if self.log_dir.exists():
                log_files = list(self.log_dir.glob("*.log"))
                if log_files:
                    print("📄 Найдены файлы логов:")
                    for f in log_files:
                        print(f"   - {f}")
                    # Используем первый найденный файл
                    self.log_file = log_files[0]
                    print(f"✅ Используем: {self.log_file}")
                else:
                    print("❌ Логи не найдены. Проверьте на сервере.")
                    return self._generate_empty_report()
            else:
                print("❌ Директория логов не существует.")
                return self._generate_empty_report()

        print(f"📄 Анализирую: {self.log_file}")
        print(f"📊 Размер файла: {self.log_file.stat().st_size / 1024 / 1024:.2f} MB")

        try:
            with open(self.log_file, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"❌ Ошибка чтения логов: {e}")
            return self._generate_empty_report()

        print(f"📝 Всего строк: {len(lines)}")

        # Анализируем последние 10000 строк (или все, если меньше)
        lines_to_analyze = lines[-10000:] if len(lines) > 10000 else lines
        print(f"🔍 Анализирую последние {len(lines_to_analyze)} строк...")

        self._parse_lines(lines_to_analyze)

        return self._generate_report()

    def _parse_lines(self, lines: List[str]):
        """Парсит строки логов"""
        for line in lines:
            # Извлекаем timestamp
            timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
            if timestamp_match:
                try:
                    timestamp = datetime.strptime(timestamp_match.group(1), "%Y-%m-%d %H:%M:%S")
                    self.results["timestamps"].append(timestamp)
                except:
                    pass

            # Сигналы сгенерированы
            if "SIGNAL GENERATED" in line or "✅ [SIGNAL GENERATED]" in line:
                self.results["signals_generated"].append(line)
                # Извлекаем символ
                symbol_match = re.search(r"(\w+USDT?):", line)
                if symbol_match:
                    self.results["symbols"].add(symbol_match.group(1))
                # Извлекаем пользователя
                user_match = re.search(r"пользователя (\d+)", line)
                if user_match:
                    self.results["users"].add(user_match.group(1))

            # Сигналы отправлены
            if "SEND SUCCESS" in line or "📤 [SEND SUCCESS]" in line:
                self.results["signals_sent"].append(line)

            # Сигналы не отправлены
            if "SEND FAILED" in line or "⚠️ [SEND FAILED]" in line:
                self.results["signals_failed"].append(line)

            # Нет сигналов
            if "NO SIGNAL" in line or "🚫 [NO SIGNAL]" in line:
                self.results["no_signals"].append(line)

            # Циклы
            if "Цикл #" in line or "🔍 Цикл" in line:
                self.results["cycles"].append(line)
                # Извлекаем номер цикла
                cycle_match = re.search(r"Цикл #(\d+)", line)
                if cycle_match:
                    pass  # Можно сохранить номер цикла

            # Ошибки
            if "ERROR" in line or "❌" in line or "Exception" in line or "Traceback" in line:
                self.results["errors"].append(line)

            # Фильтры заблокировали
            if "BLOCK" in line or "🚫" in line:
                # Определяем тип блокировки
                if "AI Score" in line or "ai_score" in line:
                    self.results["filters_blocked"]["AI Score"] += 1
                elif "Quality" in line or "quality" in line:
                    self.results["filters_blocked"]["Quality Score"] += 1
                elif "ML" in line or "ml_filter" in line:
                    self.results["filters_blocked"]["ML Filter"] += 1
                elif "MTF" in line or "mtf" in line:
                    self.results["filters_blocked"]["MTF Confirmation"] += 1
                elif "Correlation" in line or "correlation" in line:
                    self.results["filters_blocked"]["Correlation Risk"] += 1
                elif "Trend" in line or "trend" in line:
                    self.results["filters_blocked"]["Trend Alignment"] += 1
                elif "Volume" in line or "volume" in line:
                    self.results["filters_blocked"]["Volume Filter"] += 1
                elif "Anomaly" in line or "anomaly" in line:
                    self.results["filters_blocked"]["Anomaly Filter"] += 1
                elif "Liquidity" in line or "liquidity" in line:
                    self.results["filters_blocked"]["Liquidity Check"] += 1
                else:
                    self.results["filters_blocked"]["Other"] += 1

    def _generate_report(self) -> Dict:
        """Генерирует отчет"""
        report = {
            "summary": {},
            "signals": {},
            "cycles": {},
            "errors": {},
            "filters": {},
            "users": {},
            "symbols": {},
            "timeline": {},
        }

        # Общая статистика
        report["summary"] = {
            "total_lines_analyzed": len(self.results["timestamps"]),
            "signals_generated": len(self.results["signals_generated"]),
            "signals_sent": len(self.results["signals_sent"]),
            "signals_failed": len(self.results["signals_failed"]),
            "no_signals": len(self.results["no_signals"]),
            "cycles": len(self.results["cycles"]),
            "errors": len(self.results["errors"]),
            "unique_users": len(self.results["users"]),
            "unique_symbols": len(self.results["symbols"]),
        }

        # Статистика сигналов
        report["signals"] = {
            "generated": len(self.results["signals_generated"]),
            "sent": len(self.results["signals_sent"]),
            "failed": len(self.results["signals_failed"]),
            "success_rate": (
                len(self.results["signals_sent"]) / len(self.results["signals_generated"]) * 100
            )
            if self.results["signals_generated"]
            else 0,
        }

        # Статистика циклов
        if self.results["cycles"]:
            report["cycles"] = {
                "total": len(self.results["cycles"]),
                "last_cycle": self.results["cycles"][-1] if self.results["cycles"] else None,
            }

        # Статистика ошибок
        error_types = Counter()
        for error in self.results["errors"]:
            if "ImportError" in error:
                error_types["ImportError"] += 1
            elif "ModuleNotFoundError" in error:
                error_types["ModuleNotFoundError"] += 1
            elif "AttributeError" in error:
                error_types["AttributeError"] += 1
            elif "TypeError" in error:
                error_types["TypeError"] += 1
            elif "KeyError" in error:
                error_types["KeyError"] += 1
            else:
                error_types["Other"] += 1

        report["errors"] = dict(error_types)

        # Статистика фильтров
        report["filters"] = dict(self.results["filters_blocked"])

        # Пользователи
        report["users"] = {"count": len(self.results["users"]), "ids": list(self.results["users"])}

        # Символы
        report["symbols"] = {
            "count": len(self.results["symbols"]),
            "list": sorted(list(self.results["symbols"]))[:20],  # Первые 20
        }

        # Временная линия
        if self.results["timestamps"]:
            timestamps = sorted(self.results["timestamps"])
            report["timeline"] = {
                "first": timestamps[0].isoformat() if timestamps else None,
                "last": timestamps[-1].isoformat() if timestamps else None,
                "span_hours": (timestamps[-1] - timestamps[0]).total_seconds() / 3600
                if len(timestamps) > 1
                else 0,
            }

        return report

    def _generate_empty_report(self) -> Dict:
        """Генерирует пустой отчет если логи не найдены"""
        return {
            "summary": {
                "error": "Логи не найдены",
                "message": "Проверьте логи на сервере: tail -1000 logs/atra.log",
            }
        }

    def print_report(self, report: Dict):
        """Выводит отчет"""
        print("\n" + "=" * 80)
        print("📊 РЕЗУЛЬТАТЫ АНАЛИЗА ЛОГОВ")
        print("=" * 80)

        if "error" in report.get("summary", {}):
            print(f"\n❌ {report['summary']['error']}")
            print(f"💡 {report['summary'].get('message', '')}")
            return

        # Общая статистика
        print("\n📈 ОБЩАЯ СТАТИСТИКА:")
        summary = report["summary"]
        print(f"  • Всего строк проанализировано: {summary.get('total_lines_analyzed', 0)}")
        print(f"  • Сигналов сгенерировано: {summary.get('signals_generated', 0)}")
        print(f"  • Сигналов отправлено: {summary.get('signals_sent', 0)}")
        print(f"  • Сигналов не отправлено: {summary.get('signals_failed', 0)}")
        print(f"  • Нет сигналов (блокировка): {summary.get('no_signals', 0)}")
        print(f"  • Циклов обработки: {summary.get('cycles', 0)}")
        print(f"  • Ошибок: {summary.get('errors', 0)}")
        print(f"  • Уникальных пользователей: {summary.get('unique_users', 0)}")
        print(f"  • Уникальных символов: {summary.get('unique_symbols', 0)}")

        # Статистика сигналов
        if report.get("signals"):
            signals = report["signals"]
            print("\n📡 СТАТИСТИКА СИГНАЛОВ:")
            print(f"  • Сгенерировано: {signals.get('generated', 0)}")
            print(f"  • Отправлено: {signals.get('sent', 0)}")
            print(f"  • Не отправлено: {signals.get('failed', 0)}")
            if signals.get("generated", 0) > 0:
                success_rate = signals.get("success_rate", 0)
                print(f"  • Успешность отправки: {success_rate:.1f}%")

        # Статистика фильтров
        if report.get("filters"):
            print("\n🚫 БЛОКИРОВКИ ФИЛЬТРАМИ:")
            filters = report["filters"]
            if filters:
                for filter_name, count in sorted(filters.items(), key=lambda x: x[1], reverse=True):
                    print(f"  • {filter_name}: {count}")
            else:
                print("  • Нет блокировок (или логи не содержат информации о фильтрах)")

        # Статистика ошибок
        if report.get("errors"):
            print("\n❌ ОШИБКИ:")
            errors = report["errors"]
            if errors:
                for error_type, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
                    print(f"  • {error_type}: {count}")
            else:
                print("  • Ошибок не найдено")

        # Пользователи
        if report.get("users"):
            users = report["users"]
            print("\n👥 ПОЛЬЗОВАТЕЛИ:")
            print(f"  • Всего: {users.get('count', 0)}")
            if users.get("ids"):
                print(f"  • IDs: {', '.join(users['ids'][:10])}")

        # Символы
        if report.get("symbols"):
            symbols = report["symbols"]
            print("\n💱 СИМВОЛЫ:")
            print(f"  • Всего: {symbols.get('count', 0)}")
            if symbols.get("list"):
                print(f"  • Примеры: {', '.join(symbols['list'][:10])}")

        # Временная линия
        if report.get("timeline"):
            timeline = report["timeline"]
            if timeline.get("first") and timeline.get("last"):
                print("\n⏰ ВРЕМЕННАЯ ЛИНИЯ:")
                print(f"  • Первая запись: {timeline['first']}")
                print(f"  • Последняя запись: {timeline['last']}")
                if timeline.get("span_hours", 0) > 0:
                    print(f"  • Период: {timeline['span_hours']:.1f} часов")

        # Выводы
        print("\n" + "=" * 80)
        print("💡 ВЫВОДЫ:")

        if summary.get("signals_generated", 0) == 0:
            print("  ⚠️ Сигналы не генерируются")
            print("     Возможные причины:")
            print("     - Строгие фильтры блокируют все сигналы")
            print("     - Рыночные условия не подходят")
            print("     - Система не запущена или остановлена")
        elif summary.get("signals_sent", 0) == 0 and summary.get("signals_generated", 0) > 0:
            print("  ⚠️ Сигналы генерируются, но не отправляются")
            print("     Возможные причины:")
            print("     - Ошибки отправки в Telegram")
            print("     - Проблемы с базой данных")
            print("     - Блокировка корреляционными рисками")
        elif summary.get("signals_sent", 0) > 0:
            print("  ✅ Система работает нормально")
            print(f"     Отправлено {summary.get('signals_sent', 0)} сигналов")

        if summary.get("errors", 0) > 0:
            print(f"  ⚠️ Обнаружено {summary.get('errors', 0)} ошибок")
            print("     Проверьте детали выше")

        if summary.get("cycles", 0) == 0:
            print("  ⚠️ Циклы обработки не найдены")
            print("     Возможно, система не запущена")

        print("=" * 80)


def main():
    """Главная функция"""
    analyzer = LogAnalyzer()
    report = analyzer.analyze()
    analyzer.print_report(report)

    # Сохраняем отчет в файл
    report_file = Path("LOGS_ANALYSIS_REPORT.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("# 📊 ОТЧЕТ АНАЛИЗА ЛОГОВ ATRA\n\n")
        f.write(f"**Дата анализа:** {datetime.now().isoformat()}\n\n")
        f.write("## Результаты\n\n")
        f.write(f"```json\n{report}\n```\n")
    print(f"\n💾 Отчет сохранен: {report_file}")


if __name__ == "__main__":
    main()
