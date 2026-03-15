#!/usr/bin/env python3
"""
Собирает текст задачи для браузера агента (Victoria/Veronica): зайти в Директ и
применить заголовки и тексты из configs/setki21_direct_ads.yaml.
Без API, без одобрения заявки — агент заходит через браузер (control_browser).

Использование:
  python3 scripts/build_setki21_direct_browser_goal.py           # вывести задачу в stdout
  python3 scripts/build_setki21_direct_browser_goal.py -o FILE   # записать в файл
"""
import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "configs", "setki21_direct_ads.yaml")


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        raise SystemExit(f"Конфиг не найден: {path}")
    try:
        import yaml
    except ImportError:
        raise SystemExit("Нужен PyYAML: pip install pyyaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_goal(config: dict) -> str:
    headlines = config.get("headlines") or []
    texts = config.get("texts") or []
    if not headlines or not texts:
        raise SystemExit("В конфиге нужны списки headlines и texts")

    parts = [
        "Открой https://direct.yandex.ru и, если потребуется, войди в кабинет.",
        "Перейди в кампании → выбери нужную кампанию Setki21 → группы объявлений → открой группу с текстовыми объявлениями.",
        "Для первых пяти текстовых объявлений установи заголовок и текст объявления ТОЧНО как указано ниже (скопируй строки без кавычек).",
        "",
    ]
    for i in range(5):
        h = headlines[i % len(headlines)]
        t = texts[i % len(texts)]
        parts.extend([f"Объявление {i + 1}. Заголовок:", h, "Текст:", t, ""])
    parts.append("Сохрани изменения в кабинете Директа.")
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Собрать задачу для браузера: применение Setki21 в Директе.")
    parser.add_argument("-o", "--output", metavar="FILE", help="Записать задачу в файл")
    parser.add_argument("-c", "--config", default=CONFIG_PATH, help="Путь к YAML-конфигу (по умолчанию configs/setki21_direct_ads.yaml)")
    args = parser.parse_args()

    config = load_config(args.config)
    goal = build_goal(config)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(goal)
        print(f"Задача записана: {args.output}", file=sys.stderr)
    else:
        print(goal)


if __name__ == "__main__":
    main()
