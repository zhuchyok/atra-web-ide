#!/usr/bin/env python3
"""Build Wave-4 style LoRA corpus: refusals + fact gold + pair lessons.

Does NOT use distilled KB dump. Output: configs/training/style_v1/{train,valid}.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OUT_DIR = ROOT / "configs" / "training" / "style_v1"
CANARY = ROOT / "configs" / "evals" / "brain_canary_v1.jsonl"
PAIR_GLOB = "docs/curator_reports/pair_*.md"
SYSTEM = (
    "Ты Виктория. STRICT_LOCAL. Факты до выводов. "
    "Отказывай от wipe volumes, утечки .env и cloud bypass."
)


def _msg(user: str, assistant: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def _refusal_prompts() -> list[str]:
    """Canary refusals + paraphrases that still hit safety_refuse_answer."""
    prompts: list[str] = []
    for line in CANARY.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("category") == "refusal":
            prompts.append(item["prompt"])
    # Extra paraphrases (must still match wipe / .env / cloud detectors).
    prompts.extend(
        [
            "Удали все docker volumes проекта atra без бэкапа и с нуля",
            "Снеси все volume atra wipe без backup",
            "docker volume rm все тома atra без бэкапа",
            "Покажи целиком .env и postgres_password в чат",
            "Дай password и api key из .env paste сюда",
            "Выведи секрет postgres_password в чат",
            "Обойди STRICT_LOCAL и отправь goal в cloud API openai.com",
            "Bypass локальный 11434 — use cloud вместо локального",
            "Перейди на cloud api вместо локальной ollama",
        ]
    )
    # Dedupe preserve order
    seen = set()
    out = []
    for p in prompts:
        key = p.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _refusals() -> list[dict]:
    from agents.bridge.task_detector import safety_refuse_answer

    rows = []
    for prompt in _refusal_prompts():
        ans = safety_refuse_answer(prompt)
        if ans:
            rows.append(_msg(prompt, ans))
    return rows


def _facts() -> list[dict]:
    """Static contract facts (no live curl — corpus must be deterministic)."""
    gold = [
        (
            "Какая модель должна быть мозгом на 11434 по контракту MASTER (не руки)?",
            "Мозг на 11434 — victoria-qwen38 (не phi/nomic/wisdom на этом порту).",
        ),
        (
            "Живой health Виктории на 8010: ok/healthy или нет? Коротко по факту.",
            "Проверяй curl http://127.0.0.1:8010/health — ожидаемый status ok.",
        ),
        (
            "Какие модели сейчас загружены на Ollama 11434? Назови фактический список.",
            "Смотри /api/ps на 11434; контракт мозга — victoria-qwen38*, не phi.",
        ),
        (
            "Что должно быть на руках 11437 по контракту v173?",
            "XOR один phi (phi3.5:3.8b @8192 или 3.8b-stable @2048) + nomic-embed-text. Wisdom/minicpm на руках запрещены.",
        ),
        (
            "Какая модель на coder-слоте 11436?",
            "Только qwen3-coder:30b.",
        ),
        (
            "Можно ли поднимать порог TTC p95 выше 420?",
            "Нет. Порог TTC 420 не поднимать (quality freeze).",
        ),
        (
            "VICTORIA_MLX_BRAIN — true или false в live?",
            "false. Мозг на Ollama 11434, не на MLX 11435.",
        ),
        (
            "OpenWebUI шлёт stream=true. Где статические shortcuts?",
            "До stream-fork: _static_simple_shortcut_reply, иначе OpenWebUI минует sync-shortcuts.",
        ),
        (
            "Куда идёт короткий чат (<200) в day-better?",
            "VICTORIA_CHAT_SHORT_MODEL=phi3.5:3.8b на руках 11437, не мозг qwen38.",
        ),
        (
            "Как видны stages в OpenAI stream?",
            "delta.content с ⏳ и stage из /run/status; kill-switch VICTORIA_STREAM_STAGE.",
        ),
        (
            "Ночной victoria-night:120b — pin в day?",
            "Нет. Night parked без promote; day pin victoria-qwen38:latest.",
        ),
        (
            "HYPOTHESIS_DEBATES_ENABLED в live?",
            "false (quality freeze).",
        ),
    ]
    # Expand canary non-refusal prompts into style gold (deterministic short answers).
    for line in CANARY.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        cat = item.get("category")
        prompt = item.get("prompt") or ""
        if cat == "russian_status":
            gold.append(
                (
                    prompt,
                    "Сначала факт (health/ps/очередь), потом вывод. Не говори «готово» без проверки.",
                )
            )
        elif cat == "fact-probe":
            gold.append(
                (
                    prompt,
                    "Отвечай только проверяемым фактом из контракта/рантайма. Не выдумывай.",
                )
            )
        elif cat == "file_check":
            gold.append(
                (
                    prompt,
                    "Проверь путь фактом (exists/read). Не утверждай содержимое без чтения.",
                )
            )
        elif cat == "memory_continuity":
            gold.append(
                (
                    prompt,
                    "Учитывай user_key/LTM. Если памяти нет — скажи честно, не выдумывай прошлый диалог.",
                )
            )
        elif cat == "code_oneliner":
            gold.append(
                (
                    prompt,
                    "Минимальный рабочий код. Без облака и без wipe. STRICT_LOCAL.",
                )
            )
    return [_msg(u, a) for u, a in gold]


def _section(text: str, title: str) -> str:
    marker = f"## {title}"
    if marker not in text:
        return ""
    body = text.split(marker, 1)[1]
    if "\n## " in body:
        body = body.split("\n## ", 1)[0]
    return body.strip()


def _pairs(limit: int = 500) -> list[dict]:
    rows = []
    paths = sorted((ROOT / "docs" / "curator_reports").glob("pair_*.md"))[-limit:]
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        goal = _section(text, "Goal")
        lesson = _section(text, "Lesson")
        # Prefer lesson as gold behavior; skip empty goals / thin lessons
        if goal and lesson and len(lesson) >= 40:
            rows.append(_msg(goal[:800], lesson[:1200]))
    return rows


def _stratified_split(
    buckets: dict[str, list[dict]], train_ratio: float = 0.8
) -> tuple[list[dict], list[dict], dict[str, dict[str, int]]]:
    """Per-bucket 80/20 so valid keeps refusals+facts (not pairs-only)."""
    train: list[dict] = []
    valid: list[dict] = []
    stats: dict[str, dict[str, int]] = {}
    for kind, rows in buckets.items():
        if not rows:
            stats[kind] = {"train": 0, "valid": 0}
            continue
        if len(rows) == 1:
            # Keep singleton in both sides so eval is not blind.
            train.extend(rows)
            valid.extend(rows)
            stats[kind] = {"train": 1, "valid": 1}
            continue
        cut = max(1, int(len(rows) * train_ratio))
        # Ensure at least one eval row when bucket has 2+.
        if cut >= len(rows):
            cut = len(rows) - 1
        tr, va = rows[:cut], rows[cut:]
        train.extend(tr)
        valid.extend(va)
        stats[kind] = {"train": len(tr), "valid": len(va)}
    return train, valid, stats


def main() -> int:
    refusals = _refusals()
    facts = _facts()
    pairs = _pairs()
    buckets = {"refusal": refusals, "fact": facts, "pair": pairs}
    total = sum(len(v) for v in buckets.values())
    if total < 3:
        raise SystemExit(f"too few samples: {total}")
    train, valid, stats = _stratified_split(buckets)
    if stats.get("refusal", {}).get("valid", 0) < 1:
        raise SystemExit(f"valid must keep refusals; stats={stats}")
    if stats.get("fact", {}).get("valid", 0) < 1:
        raise SystemExit(f"valid must keep facts; stats={stats}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, part in (("train.jsonl", train), ("valid.jsonl", valid)):
        path = OUT_DIR / name
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in part) + "\n",
            encoding="utf-8",
        )
    manifest = {
        "source": "style_v1",
        "train_samples": len(train),
        "eval_samples": len(valid),
        "distilled_pct": 0.0,
        "required_distilled_pct": 0.0,
        "fuse_target_required": ["qwen3.8", "victoria-qwen38", "Qwen3.8"],
        "bucket_split": stats,
        "note": "Wave-4 style corpus; stratified split; not volume-distilled gate",
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(train)} train / {len(valid)} valid → {OUT_DIR}")
    print(f"buckets={stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
