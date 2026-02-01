#!/usr/bin/env python3
"""
Генерация синтетических вариаций запросов для расширения validation set.
Рекомендации QA: расширение покрытия регрессии; Technical Writer: разнообразие формулировок.
Использование: python3 scripts/generate_query_variations.py --max-per-query 2
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent

# Синонимы и перефразировки (Technical Writer: естественное разнообразие)
REPHRASE_PAIRS = [
    (r"\bкак\b", "каким образом"),
    (r"\bподскажи\b", "расскажи про"),
    (r"\bпокажи\b", "покажи информацию о"),
    (r"\bчто такое\b", "объясни что такое"),
    (r"\bсколько\b", "какая стоимость"),
    (r"\bгде\b", "где найти"),
    (r"\bвремя работы\b", "режим работы"),
    (r"\bдокументация\b", "документация по"),
    (r"\bнастроить\b", "настроить конфигурацию"),
    (r"\bметрики\b", "метрики и мониторинг"),
    (r"\bкак создать\b", "инструкция по созданию"),
    (r"\bкак отменить\b", "процедура отмены"),
    (r"\bкак сбросить\b", "сброс пароля инструкция"),
    (r"\bчасто задаваемые\b", "FAQ часто задаваемые"),
    (r"\bруководство\b", "руководство по использованию"),
    (r"\bзапустить\b", "локальный запуск проекта"),
    (r"\bпорты\b", "порты сервисов"),
    (r"\bтарифы\b", "тарифы и цены"),
    (r"\bрегистрац", "регистрация аккаунт"),
    (r"\bотмена\b", "отмена подписки"),
]
SYNONYMS = {
    "подписка": ["тариф", "план"],
    "поддержка": ["саппорт", "помощь"],
    "справка": ["руководство", "help"],
    "настроить": ["настройка", "конфиг"],
    "API": ["эндпоинты", "интерфейс"],
    "аккаунт": ["учётная запись", "account"],
    "пароль": ["password", "восстановление"],
    "контакты": ["контактная информация", "связаться"],
    "цен": ["стоимость", "прайс"],
    "вопрос": ["FAQ", "вопросы"],
    "использован": ["применение", "инструкция"],
}


def normalize_for_dedup(text: str) -> str:
    """Нормализация для дедупликации (Data Engineer)."""
    return " ".join(text.lower().split()).strip()


def generate_variations(query_text: str, max_variations: int = 2) -> List[str]:
    """Генерирует до max_variations вариаций запроса (разные формулировки)."""
    variations = []
    seen = {normalize_for_dedup(query_text)}

    # Вариации через перефразировку
    for pattern, repl in REPHRASE_PAIRS:
        if len(variations) >= max_variations:
            break
        new_q = re.sub(pattern, repl, query_text, count=1, flags=re.IGNORECASE)
        if new_q != query_text:
            norm = normalize_for_dedup(new_q)
            if norm not in seen:
                seen.add(norm)
                variations.append(new_q.strip())

    # Вариации через синонимы (одна замена на запрос)
    for word, syns in SYNONYMS.items():
        if len(variations) >= max_variations:
            break
        if word.lower() in query_text.lower():
            for syn in syns:
                new_q = re.sub(rf"\b{re.escape(word)}\b", syn, query_text, count=1, flags=re.IGNORECASE)
                if new_q != query_text:
                    norm = normalize_for_dedup(new_q)
                    if norm not in seen:
                        seen.add(norm)
                        variations.append(new_q.strip())
                        break

    return variations[:max_variations]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic query variations for validation set (QA: coverage)"
    )
    parser.add_argument(
        "--dataset",
        default="data/validation_queries.json",
        help="Path to validation_queries.json",
    )
    parser.add_argument(
        "--output",
        default="data/synthetic_query_variations.json",
        help="Output path for variations",
    )
    parser.add_argument(
        "--max-per-query",
        type=int,
        default=2,
        help="Max variations per source query",
    )
    args = parser.parse_args()

    path = REPO_ROOT / args.dataset
    if not path.exists():
        print(f"❌ Dataset not found: {path}", file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    queries = data.get("queries", data) if isinstance(data, dict) else data
    if not queries:
        print("No queries in dataset.", file=sys.stderr)
        return 1

    out_queries: List[Dict[str, Any]] = []
    for item in queries:
        q = item.get("query")
        if not q or len(q) < 3:
            continue
        ref = item.get("reference")
        ctx = item.get("context_expected", [])
        base_id = item.get("id", "v")
        for i, var_text in enumerate(generate_variations(q, args.max_per_query)):
            out_queries.append({
                "id": f"{base_id}_var{i+1}",
                "query": var_text,
                "reference": ref,
                "context_expected": ctx,
                "source_id": base_id,
                "source": "synthetic_variation",
            })

    out_path = REPO_ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"queries": out_queries, "version": "1.0", "source_dataset": str(args.dataset)},
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"✅ Сгенерировано {len(out_queries)} вариаций → {out_path}")
    print("💡 Объединить с validation set: python3 scripts/merge_validation_sources.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
