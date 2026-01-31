import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class KeyEncryption:
    """Шифрование/расшифрование ключей биржи через Fernet."""

    def __init__(self):
        self.cipher = None
        try:
            from cryptography.fernet import Fernet
            
            # Читаем ключ напрямую из файла 'env' (без dotenv)
            encryption_key = None
            # Проверяем в текущей директории и в корне проекта
            possible_env_files = [
                os.path.join(os.path.dirname(__file__), 'env'),
                os.path.join(os.getcwd(), 'env'),
                '/root/atra/env'
            ]
            
            for env_file_path in possible_env_files:
                if os.path.exists(env_file_path):
                    try:
                        with open(env_file_path, 'r') as f:
                            for line in f:
                                if line.strip().startswith('ATRA_ENCRYPTION_KEY='):
                                    encryption_key = line.strip().split('=', 1)[1]
                                    logger.info(f"🔐 Ключ шифрования загружен из файла: {env_file_path}")
                                    break
                        if encryption_key: break
                    except Exception as e:
                        logger.debug("Ошибка чтения env файла %s: %s", env_file_path, e)
            
            # Fallback: проверяем переменную окружения
            if not encryption_key:
                encryption_key = os.getenv('ATRA_ENCRYPTION_KEY')
            
            if not encryption_key:
                # Генерируем новый ключ (сохраните его в env!)
                encryption_key = Fernet.generate_key().decode()
                logger.warning("🔐 Сгенерирован новый ключ шифрования. СОХРАНИТЕ в env: ATRA_ENCRYPTION_KEY=%s", encryption_key)
            
            self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            logger.info("✅ Шифрование ключей активировано")
        except Exception as e:
            logger.warning("⚠️ Шифрование недоступно (cryptography не установлен): %s", e)
            self.cipher = None

    def encrypt(self, value: str) -> str:
        """Шифрует строку. Если шифрование недоступно — возвращает как есть."""
        if not value:
            return value
        try:
            if self.cipher:
                return self.cipher.encrypt(value.encode()).decode()
            return value
        except Exception as e:
            logger.error("❌ Ошибка шифрования: %s", e)
            return value

    def decrypt(self, encrypted_value: str) -> str:
        """Расшифровывает строку. Если шифрование недоступно — возвращает как есть."""
        if not encrypted_value:
            return encrypted_value
        try:
            if self.cipher:
                return self.cipher.decrypt(encrypted_value.encode()).decode()
            return encrypted_value
        except Exception as e:
            logger.error("❌ Ошибка расшифрования: %s", e)
            return encrypted_value


_key_encryption_instance: Optional[KeyEncryption] = None


def get_key_encryption() -> KeyEncryption:
    """Singleton для KeyEncryption."""
    global _key_encryption_instance
    if _key_encryption_instance is None:
        _key_encryption_instance = KeyEncryption()
    return _key_encryption_instance

