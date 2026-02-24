#!/usr/bin/env python3
"""
Удаление дубликатов монет, оставляя оптимизированные версии
"""

import re
from pathlib import Path

target_file = Path("src/ai/intelligent_filter_system.py")
content = target_file.read_text(encoding="utf-8")

# Дубликаты
duplicates = [
    "APTUSDT",
    "ARBUSDT",
    "ATOMUSDT",
    "BONKUSDT",
    "CRVUSDT",
    "FETUSDT",
    "FILUSDT",
    "FLOKIUSDT",
    "HBARUSDT",
    "MATICUSDT",
    "OPUSDT",
    "SEIUSDT",
    "SHIBUSDT",
    "STXUSDT",
    "WIFUSDT",
    "WLDUSDT",
]

print("=" * 80)
print("🗑️  УДАЛЕНИЕ ДУБЛИКАТОВ")
print("=" * 80)
print()

removed_count = 0
kept_count = 0

for symbol in duplicates:
    # Находим все вхождения
    pattern = rf"('{symbol}':\s*\{{[^}}]+?}}),?\s*\n"
    matches = list(re.finditer(pattern, content, re.DOTALL))

    if len(matches) > 1:
        # Анализируем каждое вхождение
        entries_info = []
        for match in matches:
            block = match.group(1)
            has_results = "# Результаты" in block
            is_recent = "13.12.2025" in block or "переоптимизация" in block or "30.11.2025" in block
            position = match.start()

            # Извлекаем volume_ratio для сравнения
            vol_match = re.search(r"'volume_ratio':\s*([0-9.]+)", block)
            vol_ratio = float(vol_match.group(1)) if vol_match else 0

            entries_info.append(
                {
                    "match": match,
                    "block": block,
                    "has_results": has_results,
                    "is_recent": is_recent,
                    "position": position,
                    "vol_ratio": vol_ratio,
                }
            )

        # Сортируем: сначала оптимизированные с результатами, потом по позиции
        entries_info.sort(
            key=lambda x: (
                not x["has_results"],  # С результатами - выше
                not x["is_recent"],  # Недавние - выше
                x["position"],  # Раньше в файле - выше
            )
        )

        # Оставляем первую (лучшую), остальные удаляем
        keep_entry = entries_info[0]
        remove_entries = entries_info[1:]

        status = (
            "✅ ОПТИМИЗИРОВАНА"
            if (keep_entry["has_results"] and keep_entry["is_recent"])
            else ("✅ ЕСТЬ РЕЗУЛЬТАТЫ" if keep_entry["has_results"] else "📋 ДЕФОЛТНАЯ")
        )
        print(f"{symbol:12s} | Оставляем: {status} | VR={keep_entry['vol_ratio']:.2f}")

        # Удаляем дубликаты (в обратном порядке, чтобы не сместить позиции)
        for entry in reversed(remove_entries):
            # Удаляем блок с запятой и переносами строк
            match = entry["match"]
            # Ищем запятую перед блоком и удаляем весь блок с запятой
            start_pos = match.start()
            end_pos = match.end()

            # Проверяем, есть ли запятая перед блоком
            before = content[max(0, start_pos - 10) : start_pos]
            if "," in before or before.strip().endswith(","):
                # Удаляем вместе с запятой
                if start_pos > 0 and content[start_pos - 1] == ",":
                    start_pos -= 1

            content = content[:start_pos] + content[end_pos:]
            removed_count += 1

        kept_count += 1

# Сохраняем
if removed_count > 0:
    target_file.write_text(content, encoding="utf-8")
    print()
    print("=" * 80)
    print(f"✅ Удалено дубликатов: {removed_count}")
    print(f"✅ Оставлено записей: {kept_count}")
    print("=" * 80)
else:
    print()
    print("⚠️ Дубликаты не найдены или уже удалены")
