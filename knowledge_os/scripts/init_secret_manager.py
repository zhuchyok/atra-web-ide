#!/usr/bin/env python3
"""
Инициализация Secret Manager для Singularity 8.0
"""

import asyncio
import os
import sys
from pathlib import Path

# Добавляем путь к knowledge_os
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


async def init_secret_manager():
    """Инициализирует Secret Manager"""
    print("🔐 Инициализация Secret Manager...\n")

    try:
        from secret_manager import SecretManager

        # Проверяем, есть ли мастер-ключ
        master_key = os.getenv("SECRET_MASTER_KEY")

        if not master_key:
            print("⚠️ SECRET_MASTER_KEY не установлен")
            print("\nГенерация нового мастер-ключа...")
            master_key = SecretManager.generate_master_key()
            print("\n✅ Сгенерирован мастер-ключ:")
            print(f"   {master_key}")

            # Автоматически сохраняем в .env файл
            env_file = Path(__file__).parent.parent.parent / ".env"
            try:
                env_content = ""
                if env_file.exists():
                    env_content = env_file.read_text()

                if "SECRET_MASTER_KEY" not in env_content:
                    if env_content and not env_content.endswith("\n"):
                        env_content += "\n"
                    env_content += f"SECRET_MASTER_KEY={master_key}\n"
                    env_file.write_text(env_content)
                    print(f"\n✅ Мастер-ключ автоматически сохранен в {env_file}")
                else:
                    # Обновляем существующий ключ
                    import re

                    env_content = re.sub(
                        r"SECRET_MASTER_KEY=.*", f"SECRET_MASTER_KEY={master_key}", env_content
                    )
                    env_file.write_text(env_content)
                    print(f"\n✅ Мастер-ключ обновлен в {env_file}")

                # Устанавливаем в текущую сессию
                os.environ["SECRET_MASTER_KEY"] = master_key
            except Exception as e:
                print(f"\n⚠️ Не удалось сохранить в .env: {e}")
                print("\n⚠️ ВАЖНО: Сохраните этот ключ вручную:")
                print(f"   export SECRET_MASTER_KEY='{master_key}'")
                print(f"   или добавьте в {env_file}:")
                print(f"   SECRET_MASTER_KEY={master_key}")
        else:
            print("✅ SECRET_MASTER_KEY найден")

        # Инициализируем Secret Manager с новым ключом
        secret_manager = SecretManager(master_key=master_key)

        if not secret_manager.fernet:
            print("❌ Secret Manager не инициализирован (неверный мастер-ключ?)")
            return False

        print("✅ Secret Manager инициализирован")

        # Предлагаем зашифровать существующие секреты
        print("\n📝 Хотите зашифровать существующие секреты?")
        print("   (TG_TOKEN, OPENAI_API_KEY и т.д.)")

        tg_token = os.getenv("TG_TOKEN")
        openai_key = os.getenv("OPENAI_API_KEY")

        # Проверяем, есть ли токены в коде telegram_simple.py (fallback)
        telegram_file = Path(__file__).parent.parent / "app" / "telegram_simple.py"
        if telegram_file.exists():
            content = telegram_file.read_text()
            import re

            tg_token_match = re.search(r'TG_TOKEN\s*=\s*"([^"]+)"', content)
            if tg_token_match and not tg_token:
                tg_token = tg_token_match.group(1)
                print("  ℹ️ Найден TG_TOKEN в коде telegram_simple.py")

        if tg_token:
            print("\n🔐 Шифрование TG_TOKEN...")
            success = await secret_manager.encrypt_secret("TG_TOKEN", tg_token)
            if success:
                print("  ✅ TG_TOKEN зашифрован и сохранен")
            else:
                print("  ❌ Ошибка шифрования TG_TOKEN")
        else:
            print("\n⚠️ TG_TOKEN не найден (ни в переменных окружения, ни в коде)")
            print("   Установите TG_TOKEN перед шифрованием")

        if openai_key:
            print("\n🔐 Шифрование OPENAI_API_KEY...")
            success = await secret_manager.encrypt_secret("OPENAI_API_KEY", openai_key)
            if success:
                print("  ✅ OPENAI_API_KEY зашифрован и сохранен")
            else:
                print("  ❌ Ошибка шифрования OPENAI_API_KEY")
        else:
            print("\n⚠️ OPENAI_API_KEY не найден")
            print("   Установите OPENAI_API_KEY перед шифрованием (опционально)")

        print("\n✅ Secret Manager готов к использованию!")
        return True

    except Exception as e:
        print(f"❌ Ошибка инициализации Secret Manager: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(init_secret_manager())
    sys.exit(0 if success else 1)
