#!/usr/bin/env python3
"""
Скрипт для одноразовой очистки паттернов:
- Удаление старых NEUTRAL паттернов (>60 дней)
- Исправление ошибок в символах
- Балансировка WIN/LOSS
- Удаление дубликатов
"""

import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def validate_symbol(symbol: str) -> bool:
    """Валидация символа"""
    if not symbol or not isinstance(symbol, str):
        return False

    clean_symbol = symbol.strip().upper()
    if not clean_symbol:
        return False

    # Проверка на допустимые символы
    if not re.match(r"^[A-Z0-9_-]+$", clean_symbol):
        return False

    # Проверка на разумную длину
    if len(clean_symbol) < 2 or len(clean_symbol) > 20:
        return False

    # Проверка на дату/время (ошибка в данных)
    if re.match(r"^\d{4}-\d{2}-\d{2}", clean_symbol):
        return False

    return True


def cleanup_patterns(patterns_file: Path, max_patterns: int = 50000) -> Dict[str, Any]:
    """Очистка и оптимизация паттернов"""

    print(f"📂 Загрузка паттернов из {patterns_file}...")

    # Загружаем паттерны
    if not patterns_file.exists():
        print(f"❌ Файл не найден: {patterns_file}")
        return {}

    with open(patterns_file, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        patterns = data
    elif isinstance(data, dict):
        patterns = data.get("patterns", [])
    else:
        patterns = []

    original_count = len(patterns)
    print(f"📊 Исходное количество паттернов: {original_count:,}")

    # Статистика до очистки
    stats_before = {
        "total": len(patterns),
        "win": sum(1 for p in patterns if isinstance(p, dict) and p.get("result") == "WIN"),
        "loss": sum(1 for p in patterns if isinstance(p, dict) and p.get("result") == "LOSS"),
        "neutral": sum(1 for p in patterns if isinstance(p, dict) and p.get("result") == "NEUTRAL"),
        "invalid_symbols": sum(
            1 for p in patterns if isinstance(p, dict) and not validate_symbol(p.get("symbol", ""))
        ),
    }

    print("\n📊 Статистика ДО очистки:")
    print(
        f"   WIN: {stats_before['win']:,} ({stats_before['win'] / stats_before['total'] * 100:.1f}%)"
    )
    print(
        f"   LOSS: {stats_before['loss']:,} ({stats_before['loss'] / stats_before['total'] * 100:.1f}%)"
    )
    print(
        f"   NEUTRAL: {stats_before['neutral']:,} ({stats_before['neutral'] / stats_before['total'] * 100:.1f}%)"
    )
    print(f"   Невалидные символы: {stats_before['invalid_symbols']:,}")

    # 1. Удаляем паттерны с невалидными символами
    print("\n🧹 Шаг 1: Удаление паттернов с невалидными символами...")
    valid_patterns = []
    invalid_count = 0
    for p in patterns:
        if not isinstance(p, dict):
            invalid_count += 1
            continue

        symbol = p.get("symbol", "")
        if validate_symbol(symbol):
            valid_patterns.append(p)
        else:
            invalid_count += 1

    print(f"   ✅ Удалено {invalid_count:,} паттернов с невалидными символами")
    print(f"   ✅ Осталось {len(valid_patterns):,} валидных паттернов")

    # 2. Удаляем старые NEUTRAL паттерны (>60 дней)
    print("\n🧹 Шаг 2: Удаление старых NEUTRAL паттернов (>60 дней)...")
    cutoff_date = datetime.now() - timedelta(days=60)
    fresh_patterns = []
    old_neutral_removed = 0

    for p in valid_patterns:
        result = p.get("result")
        timestamp_str = p.get("timestamp")

        # Парсим timestamp
        timestamp = None
        if timestamp_str:
            try:
                if isinstance(timestamp_str, str):
                    # Пробуем разные форматы
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                        try:
                            timestamp = datetime.strptime(timestamp_str, fmt)
                            break
                        except ValueError:
                            continue
                elif isinstance(timestamp_str, (int, float)):
                    timestamp = datetime.fromtimestamp(timestamp_str)
            except Exception:
                pass

        # Если NEUTRAL и старый - удаляем
        if result == "NEUTRAL" and timestamp and timestamp <= cutoff_date:
            old_neutral_removed += 1
            continue

        fresh_patterns.append(p)

    print(f"   ✅ Удалено {old_neutral_removed:,} старых NEUTRAL паттернов")
    print(f"   ✅ Осталось {len(fresh_patterns):,} паттернов")

    # 3. Балансировка WIN/LOSS
    print("\n⚖️ Шаг 3: Балансировка WIN/LOSS...")
    wins = [p for p in fresh_patterns if p.get("result") == "WIN"]
    losses = [p for p in fresh_patterns if p.get("result") == "LOSS"]
    neutrals = [p for p in fresh_patterns if p.get("result") == "NEUTRAL"]
    others = [p for p in fresh_patterns if p.get("result") not in ("WIN", "LOSS", "NEUTRAL")]

    print(f"   До балансировки: WIN={len(wins):,}, LOSS={len(losses):,}")

    # Целевое соотношение: 65% WIN / 35% LOSS
    target_win_ratio = 0.65
    target_loss_ratio = 0.35

    if len(wins) > 0 and len(losses) > 0:
        # Рассчитываем целевое количество WIN на основе LOSS
        target_wins = int(len(losses) * (target_win_ratio / target_loss_ratio))

        if len(wins) > target_wins:
            # Сортируем WIN по прибыльности и свежести
            def get_sort_key(p):
                profit = abs(p.get("profit_pct", 0) or 0)
                ts_str = p.get("timestamp", "")
                ts = 0
                if ts_str:
                    try:
                        if isinstance(ts_str, str):
                            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                                try:
                                    ts = datetime.strptime(ts_str, fmt).timestamp()
                                    break
                                except ValueError:
                                    continue
                        elif isinstance(ts_str, (int, float)):
                            ts = float(ts_str)
                    except Exception:
                        pass
                return (-profit, -ts)

            wins_sorted = sorted(wins, key=get_sort_key)
            wins = wins_sorted[:target_wins]
            print(f"   ✅ Оставлено {len(wins):,} лучших WIN из {len(wins_sorted):,}")

    # Сортируем LOSS по важности (большие убытки и свежие - важнее)
    def get_loss_sort_key(p):
        loss = abs(p.get("profit_pct", 0) or 0)
        ts_str = p.get("timestamp", "")
        ts = 0
        if ts_str:
            try:
                if isinstance(ts_str, str):
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                        try:
                            ts = datetime.strptime(ts_str, fmt).timestamp()
                            break
                        except ValueError:
                            continue
                elif isinstance(ts_str, (int, float)):
                    ts = float(ts_str)
            except Exception:
                pass
        return (loss, -ts)

    losses_sorted = sorted(losses, key=get_loss_sort_key, reverse=True)
    losses = losses_sorted

    print(
        f"   После балансировки: WIN={len(wins):,} ({len(wins) / (len(wins) + len(losses)) * 100:.1f}%), LOSS={len(losses):,} ({len(losses) / (len(wins) + len(losses)) * 100:.1f}%)"
    )

    # 4. Ограничиваем общее количество
    print(f"\n📊 Шаг 4: Ограничение общего количества паттернов (макс {max_patterns:,})...")

    # Приоритет: WIN/LOSS > свежие NEUTRAL > остальные
    balanced_patterns = wins + losses + neutrals + others

    if len(balanced_patterns) > max_patterns:
        # Оставляем только лучшие
        space_for_neutral = max_patterns - len(wins) - len(losses)
        if space_for_neutral > 0:
            neutrals = neutrals[:space_for_neutral]
        else:
            neutrals = []

        balanced_patterns = wins + losses + neutrals + others
        print(f"   ✅ Ограничено до {len(balanced_patterns):,} паттернов")

    # Статистика после очистки
    stats_after = {
        "total": len(balanced_patterns),
        "win": len(wins),
        "loss": len(losses),
        "neutral": len(neutrals),
        "others": len(others),
    }

    print("\n📊 Статистика ПОСЛЕ очистки:")
    print(
        f"   WIN: {stats_after['win']:,} ({stats_after['win'] / stats_after['total'] * 100:.1f}%)"
    )
    print(
        f"   LOSS: {stats_after['loss']:,} ({stats_after['loss'] / stats_after['total'] * 100:.1f}%)"
    )
    print(
        f"   NEUTRAL: {stats_after['neutral']:,} ({stats_after['neutral'] / stats_after['total'] * 100:.1f}%)"
    )
    print(f"   Другие: {stats_after['others']:,}")

    print("\n✅ Очистка завершена:")
    print(f"   Удалено: {original_count - len(balanced_patterns):,} паттернов")
    print(f"   Осталось: {len(balanced_patterns):,} паттернов")
    print(f"   Уменьшение: {(original_count - len(balanced_patterns)) / original_count * 100:.1f}%")

    # Сохраняем результат
    output_data = {
        "patterns": balanced_patterns,
        "metadata": {
            "cleaned_at": datetime.now().isoformat(),
            "original_count": original_count,
            "final_count": len(balanced_patterns),
            "removed_count": original_count - len(balanced_patterns),
            "stats_before": stats_before,
            "stats_after": stats_after,
        },
    }

    # Создаем бэкап
    backup_file = patterns_file.with_suffix(".json.backup")
    print(f"\n💾 Создание бэкапа: {backup_file}")
    shutil.copy2(patterns_file, backup_file)

    # Сохраняем очищенные паттерны
    print("💾 Сохранение очищенных паттернов...")
    with open(patterns_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)

    print(f"✅ Готово! Очищенные паттерны сохранены в {patterns_file}")
    print(f"   Бэкап: {backup_file}")

    return {
        "original_count": original_count,
        "final_count": len(balanced_patterns),
        "removed_count": original_count - len(balanced_patterns),
        "stats_before": stats_before,
        "stats_after": stats_after,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Очистка и оптимизация паттернов")
    parser.add_argument(
        "--patterns-file",
        type=Path,
        default=Path("ai_learning_data/trading_patterns.json"),
        help="Путь к файлу паттернов",
    )
    parser.add_argument(
        "--max-patterns", type=int, default=50000, help="Максимальное количество паттернов"
    )

    args = parser.parse_args()

    try:
        result = cleanup_patterns(args.patterns_file, args.max_patterns)
        print("\n✅ Очистка успешно завершена!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка при очистке: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
