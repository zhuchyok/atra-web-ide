"""
Security Module: Аутентификация, авторизация и безопасность

Функционал:
- JWT токены для API
- Роли и права доступа
- Аудит действий пользователей
- Шифрование чувствительных данных
"""

import jwt
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
from enum import Enum
import asyncpg
import os
import json
import logging
from cryptography.fernet import Fernet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
JWT_SECRET = os.getenv('JWT_SECRET', secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Encryption key (в продакшене должен быть в секретах)
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())


class Role(Enum):
    """Роли пользователей"""
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"
    API = "api"


class Permission(Enum):
    """Права доступа"""
    READ_KNOWLEDGE = "read_knowledge"
    WRITE_KNOWLEDGE = "write_knowledge"
    DELETE_KNOWLEDGE = "delete_knowledge"
    MANAGE_EXPERTS = "manage_experts"
    MANAGE_TASKS = "manage_tasks"
    VIEW_ANALYTICS = "view_analytics"
    MANAGE_WEBHOOKS = "manage_webhooks"
    ADMIN_ACCESS = "admin_access"


# Матрица прав доступа: роль -> список прав
ROLE_PERMISSIONS = {
    Role.ADMIN: list(Permission),
    Role.USER: [
        Permission.READ_KNOWLEDGE,
        Permission.WRITE_KNOWLEDGE,
        Permission.VIEW_ANALYTICS
    ],
    Role.READONLY: [
        Permission.READ_KNOWLEDGE,
        Permission.VIEW_ANALYTICS
    ],
    Role.API: [
        Permission.READ_KNOWLEDGE,
        Permission.WRITE_KNOWLEDGE
    ]
}


class SecurityManager:
    """Класс для управления безопасностью"""
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.encryption = Fernet(ENCRYPTION_KEY.encode())
    
    def generate_jwt_token(
        self,
        user_id: str,
        username: str,
        role: Role,
        expires_in_hours: int = JWT_EXPIRATION_HOURS
    ) -> str:
        """Генерация JWT токена"""
        payload = {
            "user_id": user_id,
            "username": username,
            "role": role.value,
            "exp": datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Проверка JWT токена"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid JWT token")
            return None
    
    def hash_password(self, password: str) -> str:
        """Хеширование пароля"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Проверка пароля"""
        return self.hash_password(password) == hashed
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Шифрование чувствительных данных"""
        return self.encryption.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Расшифровка чувствительных данных"""
        return self.encryption.decrypt(encrypted_data.encode()).decode()
    
    def has_permission(self, role: Role, permission: Permission) -> bool:
        """Проверка наличия права доступа"""
        return permission in ROLE_PERMISSIONS.get(role, [])
    
    async def create_user(
        self,
        username: str,
        password: str,
        role: Role,
        email: Optional[str] = None
    ) -> Optional[str]:
        """Создание пользователя"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                hashed_password = self.hash_password(password)
                encrypted_email = self.encrypt_sensitive_data(email) if email else None
                
                user_id = await conn.fetchval("""
                    INSERT INTO users (username, password_hash, role, email, created_at)
                    VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                    RETURNING id
                """, username, hashed_password, role.value, encrypted_email)
                
                logger.info(f"✅ Created user: {username} ({role.value})")
                return str(user_id)
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Аутентификация пользователя"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                user = await conn.fetchrow("""
                    SELECT id, username, password_hash, role, email
                    FROM users
                    WHERE username = $1
                """, username)
                
                if not user:
                    return None
                
                if not self.verify_password(password, user['password_hash']):
                    return None
                
                # Логируем успешную аутентификацию
                await self.log_audit_event(
                    str(user['id']),
                    "authentication",
                    "success",
                    {"username": username}
                )
                
                return {
                    "user_id": str(user['id']),
                    "username": user['username'],
                    "role": Role(user['role']),
                    "email": self.decrypt_sensitive_data(user['email']) if user['email'] else None
                }
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return None
    
    async def log_audit_event(
        self,
        user_id: str,
        action: str,
        status: str,
        details: Dict[str, Any] = None
    ) -> Optional[str]:
        """Логирование события аудита"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                audit_id = await conn.fetchval("""
                    INSERT INTO audit_logs (user_id, action, status, details, created_at)
                    VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                    RETURNING id
                """, user_id, action, status, json.dumps(details or {}))
                
                return str(audit_id)
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
            return None
    
    async def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Получение логов аудита"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                query = "SELECT * FROM audit_logs WHERE 1=1"
                params = []
                
                if user_id:
                    query += " AND user_id = $" + str(len(params) + 1)
                    params.append(user_id)
                
                if action:
                    query += " AND action = $" + str(len(params) + 1)
                    params.append(action)
                
                query += " ORDER BY created_at DESC LIMIT $" + str(len(params) + 1)
                params.append(limit)
                
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Error getting audit logs: {e}")
            return []


def require_permission(permission: Permission):
    """Декоратор для проверки прав доступа"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Получаем токен из заголовков
            token = kwargs.get('token') or args[0] if args else None
            if not token:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            security = SecurityManager()
            payload = security.verify_jwt_token(token)
            if not payload:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            role = Role(payload['role'])
            if not security.has_permission(role, permission):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

