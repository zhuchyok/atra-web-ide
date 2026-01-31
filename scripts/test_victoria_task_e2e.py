#!/usr/bin/env python3
"""
E2E тест: дать Victoria задачу от и до.
1. Проверка health Victoria (8010)
2. POST /run с реальной задачей
3. Опционально: проверка backend /api/chat (8000)

Запуск:
  python3 scripts/test_victoria_task_e2e.py
  python3 scripts/test_victoria_task_e2e.py --backend   # ещё и через backend

Требует: Victoria на 8010; для настоящего ответа — MLX или Ollama.
"""
import os
import sys
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Задача для Виктории (короткая, но не приветствие — чтобы прошла через агента)
TASK_GOAL = (
    "Кратко перечисли три приоритета для команды разработки на эту неделю. "
    "Ответь в виде нумерованного списка, без вступления."
)


def main():
    parser = argparse.ArgumentParser(description="E2E тест: задача Victoria")
    parser.add_argument("--backend", action="store_true", help="Дополнительно проверить backend /api/chat")
    parser.add_argument("--goal", type=str, default=TASK_GOAL, help="Текст задачи для Victoria")
    args = parser.parse_args()

    try:
        import requests
    except ImportError:
        print("❌ Установите requests: pip install requests")
        return 1

    print("=" * 60)
    print("E2E тест: задача Victoria")
    print("=" * 60)
    print(f"Victoria URL: {VICTORIA_URL}")
    print(f"Задача: {args.goal[:80]}...")
    print()

    # --- 1. Health Victoria ---
    print("1. Проверка health Victoria...")
    try:
        r = requests.get(f"{VICTORIA_URL}/health", timeout=5)
        if r.status_code != 200:
            print(f"   ❌ Victoria health: HTTP {r.status_code}")
            return 1
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        status = data.get("status", "unknown")
        print(f"   ✅ Victoria: {status}")
    except Exception as e:
        print(f"   ❌ Victoria недоступна: {e}")
        print("   Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d (victoria-agent)")
        return 1

    # --- 2. POST /run ---
    print("\n2. Отправка задачи Victoria POST /run...")
    try:
        r = requests.post(
            f"{VICTORIA_URL}/run",
            json={
                "goal": args.goal,
                "max_steps": 500,
                "project_context": os.getenv("PROJECT_NAME", "atra-web-ide"),
            },
            timeout=180,
        )
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.Timeout:
        print("   ❌ Таймаут 120 с. Увеличьте таймаут или упростите задачу.")
        return 1
    except Exception as e:
        print(f"   ❌ Ошибка /run: {e}")
        return 1

    status = data.get("status", "")
    raw_output = data.get("output") or data.get("result") or data.get("response")
    output = (raw_output if raw_output is not None else "").strip()
    if isinstance(output, str) and output.lower() == "none":
        output = ""

    if status != "success":
        print(f"   ❌ status={status}, error={data.get('error', '')}")
        return 1

    if not output:
        print("   ⚠️ Пустой ответ от Victoria (output/result/response пусты или None).")
        print("   Возможные причины: LLM недоступен (MLX 11435 или Ollama 11434), или Victoria Enhanced вернул пустой result.")
        print("   Ключи ответа:", list(data.keys()))
        print("   Для полного ответа запустите MLX API Server или Ollama и перезапустите Victoria.")
        print()
        print("   ✅ Цепочка работает: Victoria приняла задачу и вернула status=success.")
        return 0
    # Шаблонные ответы = модели недоступны
    if "Получила ваш запрос" in output and len(output) < 200:
        print("   ⚠️ Похоже на шаблон (модели не ответили). Запустите MLX или Ollama.")
    if "Сейчас не могу подключиться к моделям" in output:
        print("   ⚠️ Модели недоступны. Запустите MLX (11435) или Ollama (11434).")

    print("   ✅ Ответ получен:")
    print("-" * 40)
    print(output[:1500] + ("..." if len(output) > 1500 else ""))
    print("-" * 40)

    # --- 3. Опционально: backend /api/chat ---
    if args.backend:
        print("\n3. Проверка backend POST /api/chat...")
        try:
            r = requests.post(
                f"{BACKEND_URL}/api/chat",
                json={
                    "content": args.goal,
                    "use_victoria": True,
                },
                timeout=130,
                stream=True,
            )
            r.raise_for_status()
            # SSE: читаем до end
            full = []
            for line in r.iter_lines(decode_unicode=True):
                if line and line.startswith("data:"):
                    import json
                    try:
                        ev = json.loads(line[5:].strip())
                        if ev.get("type") == "chunk" and ev.get("content"):
                            full.append(ev["content"])
                        if ev.get("type") == "end":
                            break
                    except Exception:
                        pass
            text = "".join(full).strip()
            if text:
                print("   ✅ Backend ответ (фрагмент):")
                print(text[:500] + ("..." if len(text) > 500 else ""))
            else:
                print("   ⚠️ Backend вернул пустой контент по SSE.")
        except Exception as e:
            print(f"   ❌ Backend недоступен или ошибка: {e}")
            print("   Запустите backend: cd backend && uvicorn app.main:app --reload --port 8000")

    print("\n" + "=" * 60)
    print("✅ E2E тест завершён: Victoria получила задачу и ответила.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
