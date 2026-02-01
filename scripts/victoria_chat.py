#!/usr/bin/env python3
"""
Интерактивный чат с Victoria в терминале
Использование: python3 scripts/victoria_chat.py
           python3 scripts/victoria_chat.py --verbose  # Debug mode
           python3 scripts/victoria_chat.py -v          # Debug mode

Для удаленного доступа:
VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 scripts/victoria_chat.py
"""

import sys
import os
import json
import threading
import time
import requests
import textwrap
import shutil
import argparse
from typing import Optional

# Global verbose flag
VERBOSE = False


def wrap_to_terminal(text: str, width: Optional[int] = None) -> str:
    """Перенос длинных строк по ширине терминала (мировые практики UX)."""
    if width is None:
        try:
            width = shutil.get_terminal_size().columns - 2
        except Exception:
            width = 72
    width = max(40, min(width, 120))
    return textwrap.fill(text, width=width, replace_whitespace=False, drop_whitespace=False)


def _extract_last_answer_from_long_output(s: str) -> str:
    """Из длинного вывода с планом/галлюцинациями извлечь последний блок {\"answer\": \"...\"}."""
    import re
    last_m = None
    for m in re.finditer(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', s):
        last_m = m
    if last_m:
        try:
            return last_m.group(1).replace("\\n", "\n").replace('\\"', '"')
        except Exception:
            pass
    return ""


def normalize_victoria_output(raw) -> str:
    """Из ответа Victoria (dict или str в виде {'thought':..., 'tool':...}) извлечь текст для пользователя."""
    if raw is None:
        return ""
    if isinstance(raw, dict):
        ti = raw.get("tool_input") if isinstance(raw.get("tool_input"), dict) else {}
        out = (ti.get("output") if ti else None) or raw.get("thought") or raw.get("response") or raw.get("message") or raw.get("output")
        return (out if isinstance(out, str) else str(out)) if out else ""
    if isinstance(raw, str):
        s = raw.strip()
        # Признаки вымысла/шлака: длинный текст с планами, несуществующими инструментами, галлюцинациями
        garbage_markers = (
            "Дополнительная сложность", "ТВОЙ ПЛАН:", "ПРИСТУПАЙ К ВЫПОЛНЕНИЮ",
            "СОБИРЕХТ", "Python для школьников", "Collective Memory", "ReCAP Framework",
            "Tree of Thoughts", "Swarm Intelligence", "Hierarchical Orchestration",
            "/path/to/", "web_edit", "git_run", "web_review", "action: {",
            "tool_execution", "final_output", "git_search", "web_check", "git_commit", "websocket",
            "Врачебная задача", "СЕДАРДАН", "CMP", "ЗАПИТАНЯ", "ОБРАТУРЫ",
            "psych_assessment", "patient_interview", "therapy_technique", "ethical_dilemma", "empathetic_communication",
            "web_search", "swarm_intelligence", "consensus", "tree_of_thoughts",
        )
        # Уже нормализовано сервером (усечение + подсказка) — не заменять на общее сообщение
        if "\n\n[...]\n\n" in s or "💡 Если выше только план" in s:
            if len(s) > 2000:
                return s[:2000].rstrip() + "\n\n[... ответ обрезан ...]"
            return s
        is_likely_garbage = len(s) > 800 and any(m in s for m in garbage_markers)
        if is_likely_garbage:
            last = _extract_last_answer_from_long_output(s)
            if last and len(last) < 2000 and not any(m in last for m in garbage_markers):
                return last
            # Показываем усечённый ответ вместо полного скрытия
            head, tail = 700, 400
            footer = "\n\n💡 Попробуйте один шаг: «покажи файлы в frontend» или «найди ошибки в frontend»."
            if len(s) <= head + tail:
                return s.strip() + footer
            return s[:head].rstrip() + "\n\n[...]\n\n" + s[-tail:].lstrip() + footer
        if s.startswith("{") and ("thought" in s or "tool" in s):
            data = None
            try:
                data = json.loads(s)
            except json.JSONDecodeError:
                try:
                    import ast
                    data = ast.literal_eval(s)
                except Exception:
                    return s
            if isinstance(data, dict):
                ti = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
                out = (ti.get("output") if ti else None) or data.get("thought") or data.get("response") or data.get("message") or data.get("output")
                return (out if isinstance(out, str) else str(out)) if out else s
        # Жёсткий лимит: не показывать пользователю огромный дамп
        if len(s) > 2000:
            return s[:2000].rstrip() + "\n\n[... ответ обрезан, слишком длинный ...]"
        return s
    return str(raw)

# Проверяем наличие requests
try:
    import requests
except ImportError:
    print("❌ Ошибка: не установлен модуль 'requests'")
    print("💡 Установите: pip install requests")
    sys.exit(1)

# Автоматически находим корень проекта
def find_project_root():
    """Найти корень проекта atra-web-ide"""
    # Возможные пути
    possible_paths = [
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # Относительно скрипта
        os.path.expanduser("~/Documents/atra-web-ide"),
        os.path.expanduser("~/atra-web-ide"),
        os.path.join(os.path.expanduser("~"), "Documents", "atra-web-ide"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and os.path.exists(os.path.join(path, "src", "agents", "bridge", "victoria_server.py")):
            return path
    
    # Если не нашли, используем текущую директорию
    return os.getcwd()

ROOT = find_project_root()
sys.path.insert(0, ROOT)

# URL Victoria (можно переопределить через переменную окружения)
VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
REMOTE_URL = os.getenv("VICTORIA_REMOTE_URL", "http://185.177.216.15:8010")

def check_victoria_health(url: str, verbose: bool = False) -> bool:
    """Проверить доступность Victoria"""
    try:
        if verbose:
            print(f"[DEBUG] Checking health at {url}/health...", end="", flush=True)
        response = requests.get(f"{url}/health", timeout=5)
        if verbose:
            if response.status_code == 200:
                health_data = response.json()
                print(f" ✅ OK")
                print(f"[DEBUG] Health response: {json.dumps(health_data, indent=2)}")
            else:
                print(f" ❌ (HTTP {response.status_code})")
        return response.status_code == 200
    except requests.exceptions.ConnectionError as e:
        if verbose:
            print(f" ❌ (Connection Error: {e})")
        return False
    except requests.exceptions.Timeout:
        if verbose:
            print(" ❌ (Timeout)")
        return False
    except Exception as e:
        if verbose:
            print(f" ❌ (Error: {e})")
        return False

# Sync timeout: по best practices для ML API 300-600 сек; сложные задачи — до 10 мин
VICTORIA_SYNC_TIMEOUT = int(os.getenv("VICTORIA_SYNC_TIMEOUT", "600"))

def _do_request(url: str, payload: dict, result_holder: list, error_holder: list) -> None:
    """Выполнить POST в фоне; результат в result_holder[0], исключение в error_holder."""
    try:
        response = requests.post(
            f"{url}/run",
            json=payload,
            timeout=VICTORIA_SYNC_TIMEOUT,
            stream=False,
        )
        response.raise_for_status()
        result_holder.append(response.json())
    except Exception as e:
        error_holder.append(e)


def _poll_status(url: str, task_id: str, poll_interval: float = 2.5, max_wait: float = 3600) -> Optional[dict]:
    """Опрос GET /run/status/{task_id} до completed/failed. Возвращает результат в формате чата или None."""
    deadline = time.monotonic() + max_wait
    spinner = "|/-\\"
    idx = 0
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{url}/run/status/{task_id}", timeout=10)
            if r.status_code != 200:
                return None
            data = r.json()
            status = data.get("status", "")
            if status == "completed":
                print("\r" + " " * 60 + "\r", end="", flush=True)
                return {
                    "status": "success",
                    "output": data.get("output") or "",
                    "knowledge": data.get("knowledge"),
                }
            if status == "failed":
                print("\r" + " " * 60 + "\r", end="", flush=True)
                print(f"\n❌ Задача завершилась с ошибкой: {data.get('error', 'unknown')}")
                return None
            # queued или running
            idx += 1
            print(f"\r📋 Статус: {status}... {spinner[idx % len(spinner)]} ", end="", flush=True)
        except Exception as e:
            print(f"\r⚠️ Ошибка опроса: {e} ", end="", flush=True)
        time.sleep(poll_interval)
    print("\n⏱️ Таймаут ожидания результата (1 ч). Проверьте статус вручную: GET /run/status/" + task_id)
    return None


def send_message(url: str, goal: str, max_steps: int = 500, project_context: Optional[str] = None, session_id: Optional[str] = None, chat_history: Optional[list] = None, async_run: bool = True, poll_max_wait: Optional[float] = None) -> Optional[dict]:
    """Отправить сообщение Victoria. async_run=True: 202 + опрос статуса (результат в чат по завершении). poll_max_wait — макс. сек ожидания при async (по умолчанию 3600)."""
    payload = {"goal": goal, "max_steps": max_steps}
    if project_context:
        payload["project_context"] = project_context
    if session_id:
        payload["session_id"] = session_id
    if chat_history:
        payload["chat_history"] = chat_history

    if VERBOSE:
        print(f"\n[DEBUG] ========== Sending request ==========")
        print(f"[DEBUG] URL: {url}/run")
        print(f"[DEBUG] Async mode: {async_run}")
        print(f"[DEBUG] Goal: {goal[:100]}...")
        print(f"[DEBUG] Max steps: {max_steps}")
        print(f"[DEBUG] Project context: {project_context}")
        print(f"[DEBUG] Payload: {json.dumps(payload, ensure_ascii=False)[:500]}")

    # Асинхронный режим: POST с async_mode=1 → 202 + task_id, затем опрос до completed
    if async_run:
        try:
            start_time = time.time()
            r = requests.post(f"{url}/run", json=payload, params={"async_mode": "true"}, timeout=30)
            elapsed = time.time() - start_time
            
            if VERBOSE:
                print(f"[DEBUG] Response status: {r.status_code}, Time: {elapsed:.2f}s")
            
            if r.status_code == 202:
                data = r.json()
                task_id = data.get("task_id")
                correlation_id = data.get("correlation_id")
                
                if VERBOSE:
                    print(f"[DEBUG] Task ID: {task_id}")
                    print(f"[DEBUG] Correlation ID: {correlation_id}")
                
                if not task_id:
                    print("\n❌ Сервер вернул 202 без task_id")
                    return None
                print("\n📋 Задача принята, выполняется в фоне. Ожидаю результат...")
                max_wait = 3600.0 if poll_max_wait is None else float(poll_max_wait)
                return _poll_status(url, task_id, max_wait=max_wait)
            if r.status_code == 200:
                result = r.json()
                if VERBOSE:
                    print(f"[DEBUG] Sync response received")
                    print(f"[DEBUG] Response keys: {list(result.keys()) if isinstance(result, dict) else 'not dict'}")
                return result
            
            # Log error response
            if VERBOSE:
                print(f"[DEBUG] Error response body: {r.text[:500]}")
            r.raise_for_status()
        except requests.exceptions.Timeout:
            print("\n⏱️ Таймаут подключения к Victoria.")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"\n❌ Ошибка подключения: {e}")
            print(f"💡 Проверьте: curl {url}/health")
            return None
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            if VERBOSE:
                import traceback
                traceback.print_exc()
            return None

    # Синхронный режим (как раньше)
    result_holder: list = []
    error_holder: list = []
    thread = threading.Thread(target=_do_request, args=(url, payload, result_holder, error_holder), daemon=True)
    thread.start()

    status_phases = ["думаю...", "подключаю модель...", "генерирую ответ...", "проверяю контекст...", "формулирую ответ...", "собираю мысли..."]
    spinner = "|/-\\"
    phase_idx = 0
    spin_idx = 0
    last_phase_time = time.monotonic()
    while thread.is_alive():
        now = time.monotonic()
        if now - last_phase_time >= 2.5:
            phase_idx = (phase_idx + 1) % len(status_phases)
            last_phase_time = now
        phase = status_phases[phase_idx]
        char = spinner[spin_idx % len(spinner)]
        spin_idx += 1
        print(f"\r🤔 Victoria: {phase} {char} ", end="", flush=True)
        time.sleep(0.12)
    print("\r" + " " * 60 + "\r", end="", flush=True)

    if error_holder:
        e = error_holder[0]
        if isinstance(e, requests.exceptions.Timeout):
            print(f"\n⏱️  Таймаут: Victoria не ответила за {VICTORIA_SYNC_TIMEOUT // 60} мин")
            print("💡 Попробуйте упростить запрос или проверить логи Victoria.")
        elif isinstance(e, requests.exceptions.ConnectionError):
            print(f"\n❌ Ошибка подключения: {e}")
            print(f"💡 Проверьте: curl {url}/health")
        else:
            print(f"\n❌ Ошибка: {e}")
        return None
    if not result_holder:
        return None

    result = result_holder[0]
    if result.get("status") != "success" and "error" in result:
        error_msg = result.get("error", "Неизвестная ошибка")
        print(f"\n⚠️  Victoria вернула ошибку: {error_msg}")
        print("💡 Попробуйте упростить запрос или проверить логи victoria-agent.")
    return result

def main():
    global VERBOSE
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Victoria Chat - Interactive terminal chat')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Enable verbose/debug mode for detailed logging')
    parser.add_argument('--debug', action='store_true',
                       help='Same as --verbose')
    args = parser.parse_args()
    
    VERBOSE = args.verbose or args.debug or os.getenv("VICTORIA_DEBUG", "false").lower() in ("true", "1", "yes")
    
    print("=" * 60)
    print("🤖 VICTORIA CHAT - Интерактивный чат с Victoria")
    if VERBOSE:
        print("🐛 DEBUG MODE ENABLED")
    print("=" * 60)
    print()
    
    # Определяем URL (приоритет: локальный, затем удаленный)
    url = None
    if VERBOSE:
        print(f"[DEBUG] Checking local Victoria at: {VICTORIA_URL}")
    if check_victoria_health(VICTORIA_URL, verbose=VERBOSE):
        url = VICTORIA_URL
        print(f"✅ Подключено к локальной Victoria: {VICTORIA_URL}")
    elif check_victoria_health(REMOTE_URL, verbose=VERBOSE):
        url = REMOTE_URL
        print(f"✅ Подключено к удаленной Victoria: {REMOTE_URL}")
    else:
        print(f"❌ Victoria недоступна!")
        print(f"   Локальная: {VICTORIA_URL}")
        print(f"   Удаленная: {REMOTE_URL}")
        print()
        print("💡 Запустите Victoria:")
        print("   docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent")
        sys.exit(1)
    
    # Прогрев кэша: сканирование доступных моделей MLX и Ollama (могут меняться)
    try:
        r = requests.get(f"{url}/api/available-models", timeout=5)
        if r.status_code == 200:
            data = r.json()
            mlx_models = data.get("mlx", [])
            ollama_models = data.get("ollama", [])
            mlx_n, ollama_n = len(mlx_models), len(ollama_models)
            if mlx_n or ollama_n:
                print(f"   Модели: MLX {mlx_n}, Ollama {ollama_n}")
            if VERBOSE:
                print(f"[DEBUG] MLX models: {mlx_models}")
                print(f"[DEBUG] Ollama models: {ollama_models}")
    except Exception as e:
        if VERBOSE:
            print(f"[DEBUG] Failed to get available models: {e}")

    # Настройки чата
    project_context = os.getenv("PROJECT_CONTEXT", "atra-web-ide")
    session_id = os.getenv("SESSION_ID", f"terminal_{os.getpid()}")
    chat_history = []

    print()
    print(f"📁 Проект: {project_context}")
    print(f"🔑 Сессия: {session_id}")
    print()
    print("💬 Введите сообщение (exit — выход):")
    print("💡 Команды: /status, /health, /project <name>, /clear, /help, /debug")
    print("-" * 60)
    print()

    while True:
        try:
            user_input = input("👤 Вы: ").strip()

            if not user_input:
                continue

            # Выход
            if user_input.lower() in ['exit', 'выход', 'quit', 'q']:
                print("\n👋 До свидания!")
                break

            # Специальные команды
            if user_input.lower() == '/clear':
                chat_history.clear()
                print("\n🗑 История чата очищена.")
                print()
                continue

            if user_input.lower() == '/status':
                try:
                    response = requests.get(f"{url}/status", timeout=5)
                    if response.status_code == 200:
                        status = response.json()
                        print(f"\n📊 Статус Victoria: {json.dumps(status, indent=2, ensure_ascii=False)}")
                    else:
                        print("❌ Не удалось получить статус")
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
                print()
                continue
            
            if user_input.lower() == '/health':
                try:
                    response = requests.get(f"{url}/health", timeout=5)
                    if response.status_code == 200:
                        health = response.json()
                        print(f"\n🏥 Health: {json.dumps(health, indent=2, ensure_ascii=False)}")
                    else:
                        print("❌ Victoria нездорова")
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
                print()
                continue
            
            if user_input.lower().startswith('/project '):
                new_project = user_input.split(' ', 1)[1].strip()
                project_context = new_project
                print(f"\n📁 Проект изменен на: {project_context}")
                print()
                continue
            
            if user_input.lower() == '/help':
                print("\n📚 Доступные команды:")
                print("   /status          - показать статус Victoria")
                print("   /health          - проверить здоровье Victoria")
                print("   /project <name>  - изменить контекст проекта")
                print("   /clear           - очистить историю чата")
                print("   /debug           - переключить режим отладки")
                print("   /models          - показать доступные модели")
                print("   /help            - показать эту справку")
                print("   exit / выход     - выйти из чата")
                print()
                continue
            
            if user_input.lower() == '/debug':
                VERBOSE = not VERBOSE
                print(f"\n🐛 Режим отладки: {'ВКЛЮЧЕН' if VERBOSE else 'ВЫКЛЮЧЕН'}")
                print()
                continue
            
            if user_input.lower() == '/models':
                try:
                    print("\n🔍 Получаю список моделей...")
                    r = requests.get(f"{url}/api/available-models", timeout=10)
                    if r.status_code == 200:
                        data = r.json()
                        print("\n📦 Доступные модели:")
                        print(f"   MLX ({len(data.get('mlx', []))}): {data.get('mlx', [])}")
                        print(f"   Ollama ({len(data.get('ollama', []))}): {data.get('ollama', [])}")
                    else:
                        print(f"❌ Ошибка: HTTP {r.status_code}")
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
                print()
                continue

            # Отправляем сообщение (история — вся сессия, в запрос последние 30 пар)
            print("\n🤔 Victoria думает...", end="", flush=True)
            result = send_message(url, user_input, project_context=project_context, session_id=session_id, chat_history=chat_history[-30:] if chat_history else None)
            
            if result:
                if VERBOSE:
                    print(f"\n[DEBUG] ========== Response received ==========")
                    print(f"[DEBUG] Status: {result.get('status')}")
                    print(f"[DEBUG] Correlation ID: {result.get('correlation_id')}")
                    print(f"[DEBUG] Raw output type: {type(result.get('output')).__name__}")
                    print(f"[DEBUG] Raw output length: {len(str(result.get('output', '')))}")
                    if result.get('knowledge'):
                        knowledge_debug = result.get('knowledge', {})
                        print(f"[DEBUG] Knowledge keys: {list(knowledge_debug.keys())}")
                        if knowledge_debug.get('metadata'):
                            print(f"[DEBUG] Metadata: {json.dumps(knowledge_debug.get('metadata', {}), indent=2)}")
                        if knowledge_debug.get('execution_trace'):
                            print(f"[DEBUG] Execution trace: {json.dumps(knowledge_debug.get('execution_trace', {}), indent=2)}")
                
                if result.get("status") == "success":
                    output = normalize_victoria_output(result.get("output"))
                    if not isinstance(output, str):
                        output = str(output) if output is not None else ""
                    output = (output or "").strip()
                    knowledge = result.get("knowledge", {})
                    
                    print("\n" + "=" * 60)
                    print("🤖 Victoria:")
                    print("=" * 60)
                    if output:
                        try:
                            term_width = max(40, shutil.get_terminal_size().columns - 2)
                        except Exception:
                            term_width = 72
                        for line in output.splitlines():
                            if len(line) > term_width:
                                print(wrap_to_terminal(line, width=term_width))
                            else:
                                print(line)
                    else:
                        print("(Ответ пуст)")
                        print("💡 Возможно, задача делегирована или результат ещё не сформирован. Проверьте логи Victoria.")
                    
                    # Всегда показываем модель (важно для пользователя)
                    meta = (result.get("knowledge") or {}).get("metadata") or {}
                    model_used = meta.get("model_used") or meta.get("model")
                    source = meta.get("source") or meta.get("note")
                    if not model_used and result.get("knowledge"):
                        model_used = "local"
                    if model_used or source:
                        parts = []
                        if model_used:
                            parts.append(f"модель: {model_used}")
                        if source:
                            parts.append(f"источник: {source}")
                        print(f"\n🔧 {', '.join(parts)}")
                    else:
                        print("\n🔧 модель: не указана")
                    if knowledge:
                        method = knowledge.get("method")
                        delegated_to = knowledge.get("delegated_to")
                        task_id = knowledge.get("task_id")
                        if method:
                            print(f"📊 Метод: {method}")
                        if delegated_to:
                            print(f"   📋 Выполнено через: {delegated_to}" + (f" (task_id: {task_id})" if task_id else ""))
                        project_ctx = knowledge.get("project_context")
                        if project_ctx:
                            print(f"   📁 Проект: {project_ctx}")
                    if result.get("error"):
                        print(f"\n❌ Ошибка цепочки: {result.get('error')}")
                    
                    # Сохраняем в историю
                    chat_history.append({"user": user_input, "assistant": output})
                    if len(chat_history) > 100:
                        chat_history.pop(0)
                        print("\n   📋 История обрезана: сохранены последние 100 сообщений (старые удалены).")
                    
                    print("=" * 60)
                    # Подсказка, если Victoria вернула шаблон (модели недоступны или старый код)
                    if "Получила ваш запрос" in output or "Сейчас не могу подключиться к моделям" in output:
                        print("\n💡 Чтобы получать настоящие ответы:")
                        print("   1. Перезапусти Victoria: docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent")
                        print("   2. Запусти MLX API Server (порт 11435) или Ollama (11434): curl -s http://localhost:11435/ || curl -s http://localhost:11434/api/tags")
                else:
                    error = result.get("error", "Неизвестная ошибка")
                    print(f"\n❌ Ошибка: {error}")
            else:
                print("\n❌ Не удалось получить ответ от Victoria")
            
            print()
            
        except KeyboardInterrupt:
            print("\n\n👋 До свидания!")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}\n")

if __name__ == "__main__":
    main()
