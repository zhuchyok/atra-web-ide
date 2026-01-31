#!/usr/bin/env python3
"""
Victoria Chat - Standalone версия для использования на любом устройстве
Не требует наличия проекта atra-web-ide, только Python и requests

Использование:
  python3 victoria_chat_standalone.py
  VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 victoria_chat_standalone.py

Скрипт автоматически установит зависимости при первом запуске!

Быстрая установка на другое устройство:
  curl -sSL https://raw.githubusercontent.com/your-repo/atra-web-ide/main/scripts/victoria_chat_standalone.py -o ~/.local/bin/victoria_chat && chmod +x ~/.local/bin/victoria_chat && ~/.local/bin/victoria_chat
"""

import sys
import os
import json
import subprocess
from typing import Optional

# Автоматическая установка зависимостей
def ensure_requests():
    """Проверить и установить requests если нужно"""
    try:
        import requests
        return requests
    except ImportError:
        print("📦 Обнаружено отсутствие модуля 'requests'")
        print("🔧 Автоматическая установка...")
        
        try:
            # Пробуем pip3
            subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"], 
                                stdout=subprocess.DEVNULL, 
                                stderr=subprocess.DEVNULL)
            print("✅ 'requests' успешно установлен!")
            import requests
            return requests
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                # Пробуем pip
                subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
                print("✅ 'requests' успешно установлен!")
                import requests
                return requests
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("❌ Не удалось автоматически установить 'requests'")
                print("💡 Установите вручную:")
                print("   pip install requests")
                print("   или: pip3 install requests")
                sys.exit(1)

# Устанавливаем requests если нужно
requests = ensure_requests()

# URL Victoria
VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
REMOTE_URL = os.getenv("VICTORIA_REMOTE_URL", "http://185.177.216.15:8010")

def check_victoria_health(url: str, verbose: bool = False) -> bool:
    """Проверить доступность Victoria"""
    try:
        if verbose:
            print(f"🔍 Проверяю {url}...", end="", flush=True)
        response = requests.get(f"{url}/health", timeout=5)
        if verbose:
            if response.status_code == 200:
                print(" ✅")
            else:
                print(f" ❌ (HTTP {response.status_code})")
        return response.status_code == 200
    except requests.exceptions.ConnectionError as e:
        if verbose:
            print(f" ❌ (Connection Error)")
        return False
    except requests.exceptions.Timeout:
        if verbose:
            print(" ❌ (Timeout)")
        return False
    except Exception as e:
        if verbose:
            print(f" ❌ (Error: {type(e).__name__})")
        return False

def send_message(url: str, goal: str, max_steps: int = 500, project_context: Optional[str] = None, session_id: Optional[str] = None, chat_history: Optional[list] = None) -> Optional[dict]:
    """Отправить сообщение Victoria"""
    try:
        print("   (это может занять некоторое время...)")
        
        payload = {"goal": goal, "max_steps": max_steps}
        if project_context:
            payload["project_context"] = project_context
        if session_id:
            payload["session_id"] = session_id
        if chat_history:
            payload["chat_history"] = chat_history
        
        response = requests.post(
            f"{url}/run",
            json=payload,
            timeout=300,
            stream=False
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("\n⏱️  Таймаут: Victoria не ответила за 5 минут")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ Ошибка подключения: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Ошибка запроса: {e}")
        return None

def main():
    print("=" * 60)
    print("🤖 VICTORIA CHAT - Интерактивный чат с Victoria")
    print("=" * 60)
    print()
    
    # Определяем URL
    force_remote = os.getenv("VICTORIA_REMOTE_URL") is not None
    
    url = None
    print("🔍 Поиск доступной Victoria...")
    print()
    
    if force_remote:
        print(f"🌐 Использование удаленной Victoria: {REMOTE_URL}")
        if check_victoria_health(REMOTE_URL, verbose=True):
            url = REMOTE_URL
            print(f"✅ Подключено к удаленной Victoria: {REMOTE_URL}")
        else:
            print(f"❌ Удаленная Victoria недоступна: {REMOTE_URL}")
            print()
            print("💡 Проверьте:")
            print("   1. Доступность сервера:")
            print("      ping 185.177.216.15")
            print()
            print("   2. Порт открыт:")
            print("      curl http://185.177.216.15:8010/health")
            print()
            print("   3. SSH туннель запущен на Mac Studio")
            sys.exit(1)
    else:
        if check_victoria_health(VICTORIA_URL, verbose=True):
            url = VICTORIA_URL
            print(f"✅ Подключено к локальной Victoria: {VICTORIA_URL}")
        elif check_victoria_health(REMOTE_URL, verbose=True):
            url = REMOTE_URL
            print(f"✅ Подключено к удаленной Victoria: {REMOTE_URL}")
        else:
            print(f"❌ Victoria недоступна!")
            print()
            print("🔍 Проверка подключений:")
            check_victoria_health(VICTORIA_URL, verbose=True)
            check_victoria_health(REMOTE_URL, verbose=True)
            print()
            print("💡 Используйте удаленную Victoria:")
            print("   VICTORIA_REMOTE_URL=http://185.177.216.15:8010 python3 victoria_chat_standalone.py")
            sys.exit(1)
    
    # Настройки чата
    project_context = os.getenv("PROJECT_CONTEXT", "atra-web-ide")
    session_id = os.getenv("SESSION_ID", f"terminal_{os.getpid()}")
    chat_history = []
    
    print()
    print(f"📁 Проект: {project_context}")
    print(f"🔑 Сессия: {session_id}")
    print()
    print("💬 Введите ваше сообщение (или 'exit' для выхода):")
    print("💡 Команды: /status, /health, /project <name>, /help")
    print("-" * 60)
    print()
    
    while True:
        try:
            user_input = input("👤 Вы: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'выход', 'quit', 'q']:
                print("\n👋 До свидания!")
                break
            
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
                print("   /help            - показать эту справку")
                print("   exit / выход     - выйти из чата")
                print()
                continue
            
            print("\n🤔 Victoria думает...", end="", flush=True)
            result = send_message(url, user_input, project_context=project_context, session_id=session_id, chat_history=chat_history[-5:] if chat_history else None)
            
            if result:
                if result.get("status") == "success":
                    output = result.get("output", "")
                    knowledge = result.get("knowledge", {})
                    
                    print("\n" + "=" * 60)
                    print("🤖 Victoria:")
                    print("=" * 60)
                    print(output)
                    
                    if knowledge:
                        method = knowledge.get("method")
                        if method:
                            print(f"\n📊 Использован метод: {method}")
                        project_ctx = knowledge.get("project_context")
                        if project_ctx:
                            print(f"📁 Проект: {project_ctx}")
                    
                    chat_history.append({"user": user_input, "assistant": output})
                    if len(chat_history) > 20:
                        chat_history.pop(0)
                    
                    print("=" * 60)
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
