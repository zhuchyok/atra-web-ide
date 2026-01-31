"""
Secret Manager
Шифрование и безопасное хранение секретов
Singularity 8.0: Security and Reliability
"""

import os
import logging
import base64
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger.warning("⚠️ cryptography не установлен, шифрование недоступно")

class SecretManager:
    """
    Менеджер секретов с шифрованием.
    Использует Fernet для симметричного шифрования.
    """
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Args:
            master_key: Мастер-ключ для шифрования (из environment variable)
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            logger.error("❌ cryptography не установлен, SecretManager недоступен")
            self._fernet = None
            return
        
        # Получаем мастер-ключ из environment variable
        if master_key is None:
            master_key = os.getenv('SECRET_MASTER_KEY')
        
        if not master_key:
            # Генерируем ключ на основе SECRET_KEY или создаем новый
            secret_key = os.getenv('SECRET_KEY', 'default_secret_key_change_me')
            master_key = self._derive_key(secret_key)
            logger.warning("⚠️ [SECRET MANAGER] Используется производный ключ. Установите SECRET_MASTER_KEY для безопасности.")
        else:
            # Если ключ в base64, декодируем
            try:
                master_key = base64.b64decode(master_key)
            except:
                # Если не base64, используем как есть
                pass
        
        try:
            self._fernet = Fernet(master_key if isinstance(master_key, bytes) else Fernet.generate_key())
        except Exception as e:
            logger.error(f"❌ [SECRET MANAGER] Ошибка инициализации Fernet: {e}")
            self._fernet = None
    
    def _derive_key(self, password: str) -> bytes:
        """Производный ключ из пароля"""
        if not CRYPTOGRAPHY_AVAILABLE:
            return b''
        
        salt = os.getenv('SECRET_SALT', 'default_salt_change_me').encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, plaintext: str) -> Optional[str]:
        """
        Шифрует текст.
        
        Args:
            plaintext: Открытый текст
        
        Returns:
            Зашифрованный текст в base64 или None при ошибке
        """
        if not self._fernet:
            logger.error("❌ [SECRET MANAGER] Fernet не инициализирован")
            return None
        
        try:
            encrypted = self._fernet.encrypt(plaintext.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"❌ [SECRET MANAGER] Ошибка шифрования: {e}")
            return None
    
    def decrypt(self, ciphertext: str) -> Optional[str]:
        """
        Расшифровывает текст.
        
        Args:
            ciphertext: Зашифрованный текст в base64
        
        Returns:
            Расшифрованный текст или None при ошибке
        """
        if not self._fernet:
            logger.error("❌ [SECRET MANAGER] Fernet не инициализирован")
            return None
        
        try:
            encrypted = base64.b64decode(ciphertext.encode())
            decrypted = self._fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"❌ [SECRET MANAGER] Ошибка расшифровки: {e}")
            return None
    
    def encrypt_dict(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Шифрует словарь (шифрует только строковые значения).
        
        Args:
            data: Словарь с данными
        
        Returns:
            Словарь с зашифрованными значениями или None при ошибке
        """
        if not self._fernet:
            return None
        
        encrypted_data = {}
        for key, value in data.items():
            if isinstance(value, str):
                encrypted_value = self.encrypt(value)
                if encrypted_value:
                    encrypted_data[key] = encrypted_value
                else:
                    return None
            else:
                encrypted_data[key] = value
        
        return encrypted_data
    
    def decrypt_dict(self, encrypted_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Расшифровывает словарь.
        
        Args:
            encrypted_data: Словарь с зашифрованными значениями
        
        Returns:
            Словарь с расшифрованными значениями или None при ошибке
        """
        if not self._fernet:
            return None
        
        decrypted_data = {}
        for key, value in encrypted_data.items():
            if isinstance(value, str):
                decrypted_value = self.decrypt(value)
                if decrypted_value:
                    decrypted_data[key] = decrypted_value
                else:
                    return None
            else:
                decrypted_data[key] = value
        
        return decrypted_data
    
    @staticmethod
    def generate_master_key() -> str:
        """
        Генерирует новый мастер-ключ для шифрования.
        
        Returns:
            Мастер-ключ в base64 формате
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("cryptography не установлен")
        
        key = Fernet.generate_key()
        return base64.b64encode(key).decode()
    
    @property
    def fernet(self):
        """Возвращает Fernet экземпляр"""
        return self._fernet
    
    async def encrypt_secret(self, key_name: str, secret_value: str) -> bool:
        """
        Шифрует и сохраняет секрет в БД.
        
        Args:
            key_name: Имя секрета (например, TG_TOKEN, OPENAI_API_KEY)
            secret_value: Значение секрета для шифрования
        
        Returns:
            True если успешно, False при ошибке
        """
        if not self._fernet:
            logger.error("❌ SecretManager не инициализирован (нет мастер-ключа).")
            return False
        
        try:
            encrypted_value = self.encrypt(secret_value)
            if not encrypted_value:
                logger.error(f"❌ Ошибка шифрования секрета '{key_name}'")
                return False
            
            # Сохраняем в БД
            try:
                import asyncpg
                import getpass
                
                USER_NAME = getpass.getuser()
                db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
                
                conn = await asyncpg.connect(db_url)
                try:
                    # Определяем тип секрета на основе имени
                    secret_type = 'token' if 'TOKEN' in key_name else 'api_key' if 'API_KEY' in key_name else 'password'
                    
                    await conn.execute("""
                        INSERT INTO encrypted_secrets (secret_name, encrypted_value, secret_type, updated_at)
                        VALUES ($1, $2, $3, NOW())
                        ON CONFLICT (secret_name) DO UPDATE
                        SET encrypted_value = EXCLUDED.encrypted_value,
                            secret_type = EXCLUDED.secret_type,
                            updated_at = NOW()
                    """, key_name, encrypted_value, secret_type)
                    logger.info(f"✅ Секрет '{key_name}' успешно зашифрован и сохранен.")
                    return True
                finally:
                    await conn.close()
            except ImportError:
                logger.debug("ℹ️ asyncpg не установлен, секрет не сохранен в БД (только зашифрован, опциональный компонент)")
                return True  # Шифрование успешно, но сохранение в БД не удалось
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения секрета '{key_name}' в БД: {e}")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка шифрования/сохранения секрета '{key_name}': {e}")
            return False

# Singleton instance
_secret_manager_instance: Optional[SecretManager] = None

def get_secret_manager(master_key: Optional[str] = None) -> SecretManager:
    """Получить singleton экземпляр Secret Manager"""
    global _secret_manager_instance
    if _secret_manager_instance is None:
        _secret_manager_instance = SecretManager(master_key=master_key)
    return _secret_manager_instance

