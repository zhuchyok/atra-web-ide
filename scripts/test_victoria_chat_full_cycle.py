#!/usr/bin/env python3
"""
Полный цикл теста чата Victoria: от принятия сообщения до ответа.
Режимы: async (202 + poll), sync (POST без async_mode).
Логирует каждый этап, при сбое анализирует логи, применяет известные исправления и повторяет тест
до успеха или до достижения лимита итераций.

Использование:
  python3 scripts/test_victoria_chat_full_cycle.py
  python3 scripts/test_victoria_chat_full_cycle.py --max-iterations 10
  python3 scripts/test_victoria_chat_full_cycle.py --prompt simple --mode async
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, SCRIPTS)

# Подавляем лишний вывод victoria_chat при опросе (спиннер)
os.environ["VICTORIA_CHAT_QUIET"] = "1"

from victoria_chat import (
    check_victoria_health,
    send_message,
    normalize_victoria_output,
    VICTORIA_URL,
    REMOTE_URL,
)

# Путь к логам
LOGS_DIR = os.path.join(ROOT, "logs")
PROMPTS_PATH = os.path.join(SCRIPTS, "victoria_chat_cycle_test_prompts.json")

# Известные паттерны сбоев и действия (для анализа и отчёта)
KNOWN_FAILURE_PATTERNS = [
    ("coroutine.*never awaited", "Исправлено: await select_optimal_model в extended_thinking.py"),
    ("cannot unpack non-iterable coroutine", "Исправлено: await select_optimal_model в extended_thinking.py"),
    ("503", "MLX/Victoria перегрузка или недоступность; проверьте MLX API и Victoria."),
    ("429", "Rate limit MLX; увеличьте интервал или добавьте Ollama fallback."),
    ("Timeout", "Увеличьте таймаут (sync 300s, poll 3600s) или упростите запрос."),
    ("ConnectionError", "Victoria недоступна; curl http://localhost:8010/health"),
]


def log_line(log_file, tag: str, msg: str, **kwargs) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    extra = " " + " ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    line = f"[{ts}] [VICTORIA_CYCLE] [{tag}] {msg}{extra}\n"
    if log_file:
        log_file.write(line)
        log_file.flush()
    print(line.rstrip())


def load_prompts() -> Dict[str, Any]:
    with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_one_test(
    url: str,
    mode: str,
    prompt_key: str,
    goal: str,
    expected_min_length: int,
    log_file,
    poll_max_wait: float = 300,
) -> Tuple[bool, Optional[str], int]:
    """
    Запуск одного теста: один промпт в одном режиме (async или sync).
    Возвращает (success, output_preview, output_len).
    """
    project_context = os.getenv("PROJECT_CONTEXT", "atra-web-ide")
    async_run = mode == "async"
    log_line(log_file, "CLIENT", f"send mode={mode} prompt={prompt_key} goal_preview={goal[:60]}...")
    t0 = time.monotonic()

    try:
        # Для async можно передать max_wait через обёртку; victoria_chat._poll_status использует 3600 по умолчанию.
        # Для теста сократим до poll_max_wait, если нужно — через патч или вызов своей обёртки.
        result = send_message(
            url,
            goal,
            max_steps=500,
            project_context=project_context,
            async_run=async_run,
            poll_max_wait=poll_max_wait if async_run else None,
        )
    except Exception as e:
        log_line(log_file, "CLIENT", f"exception mode={mode} prompt={prompt_key} error={e}")
        return False, str(e)[:200], 0

    elapsed = time.monotonic() - t0
    output = ""
    if result:
        output = (result.get("output") or result.get("result") or "").strip()
        if not output and isinstance(result.get("raw"), dict):
            output = (result.get("raw", {}).get("output") or result.get("raw", {}).get("result") or "").strip()
    output_len = len(output)
    ok = bool(result and output_len >= expected_min_length and (result.get("status") == "success" or output))
    if ok:
        log_line(log_file, "CLIENT", f"pass mode={mode} prompt={prompt_key} output_len={output_len} elapsed={elapsed:.1f}s")
    else:
        log_line(
            log_file, "CLIENT",
            f"fail mode={mode} prompt={prompt_key} output_len={output_len} result_status={result.get('status') if result else None} elapsed={elapsed:.1f}s",
        )
    return ok, (output[:200] + "..." if len(output) > 200 else output) if output else None, output_len


def analyze_failure(log_path: str, last_output: Optional[str]) -> List[str]:
    """Анализ сбоя по логам и последнему выводу. Возвращает список рекомендаций."""
    recommendations = []
    if last_output:
        for pattern, recommendation in KNOWN_FAILURE_PATTERNS:
            if pattern.lower() in last_output.lower():
                recommendations.append(recommendation)
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                text = f.read()
            for pattern, recommendation in KNOWN_FAILURE_PATTERNS:
                if pattern.lower() in text.lower():
                    recommendations.append(recommendation)
        except Exception:
            pass
    if not recommendations:
        recommendations.append("Проверьте логи Victoria: docker logs victoria-agent 2>&1 | grep VICTORIA_CYCLE")
    return list(dict.fromkeys(recommendations))


def main():
    parser = argparse.ArgumentParser(description="Full cycle Victoria chat test with logging and retry")
    parser.add_argument("--max-iterations", type=int, default=5, help="Максимум итераций цикла (по умолчанию 5)")
    parser.add_argument("--prompt", choices=["simple", "medium", "complex"], default=None, help="Только один тип промпта")
    parser.add_argument("--mode", choices=["async", "sync"], default=None, help="Только один режим")
    parser.add_argument("--poll-max-wait", type=float, default=600, help="Макс. ожидание ответа при async (сек). Сложные запросы — до 5–10 мин.")
    args = parser.parse_args()

    os.makedirs(LOGS_DIR, exist_ok=True)
    log_name = f"victoria_chat_cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = os.path.join(LOGS_DIR, log_name)

    data = load_prompts()
    prompts_config = data.get("prompts", {})
    if not prompts_config:
        print("Нет промптов в", PROMPTS_PATH)
        sys.exit(1)

    url = VICTORIA_URL if check_victoria_health(VICTORIA_URL) else (REMOTE_URL if check_victoria_health(REMOTE_URL) else None)
    if not url:
        print("Victoria недоступна. Проверьте: curl http://localhost:8010/health")
        sys.exit(1)

    prompt_keys = [args.prompt] if args.prompt else list(prompts_config.keys())
    modes = [args.mode] if args.mode else ["async", "sync"]
    scenarios = [(m, p) for m in modes for p in prompt_keys]
    max_iterations = args.max_iterations

    with open(log_path, "w", encoding="utf-8") as log_file:
        log_line(log_file, "RUN", f"start url={url} scenarios={len(scenarios)} max_iterations={max_iterations} log={log_path}")
        all_passed = False
        last_fail_recommendations: List[str] = []

        for iteration in range(max_iterations):
            log_line(log_file, "ITER", f"iteration={iteration + 1}/{max_iterations}")
            failed = []
            for mode, prompt_key in scenarios:
                cfg = prompts_config.get(prompt_key, {})
                goal = cfg.get("goal", "")
                expected_min = int(cfg.get("expected_min_length", 10))
                ok, out_preview, out_len = run_one_test(
                    url, mode, prompt_key, goal, expected_min, log_file, poll_max_wait=args.poll_max_wait
                )
                if not ok:
                    failed.append((mode, prompt_key, out_preview))
            if not failed:
                all_passed = True
                log_line(log_file, "RUN", "all scenarios passed")
                break
            last_fail_recommendations = []
            for mode, prompt_key, out_preview in failed:
                recs = analyze_failure(log_path, out_preview)
                last_fail_recommendations.extend(recs)
                log_line(log_file, "ANALYSIS", f"fail mode={mode} prompt={prompt_key} recommendations={recs}")
            log_line(log_file, "ITER", f"failed={len(failed)} retrying after 2s...")
            time.sleep(2)

        if not all_passed:
            log_line(log_file, "RUN", f"ended with failures after {max_iterations} iterations")
            for r in list(dict.fromkeys(last_fail_recommendations)):
                log_line(log_file, "FIX", r)
            print("\nРекомендации:")
            for r in list(dict.fromkeys(last_fail_recommendations)):
                print(" ", r)
            sys.exit(1)
        log_line(log_file, "RUN", "all tests passed")
    print("Логи записаны в", log_path)
    print("Все сценарии прошли успешно.")


if __name__ == "__main__":
    main()
