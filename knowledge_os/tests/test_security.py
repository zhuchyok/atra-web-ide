"""
Unit tests for Security module
"""

import pytest
from knowledge_os.app.security import SecurityManager, Role, Permission


@pytest.mark.asyncio
async def test_generate_jwt_token():
    """Test JWT token generation"""
    security = SecurityManager()
    
    token = security.generate_jwt_token(
        user_id="test-user-123",
        username="testuser",
        role=Role.USER
    )
    
    assert token is not None
    assert len(token) > 0


@pytest.mark.asyncio
async def test_verify_jwt_token():
    """Test JWT token verification"""
    security = SecurityManager()
    
    # Generate token
    token = security.generate_jwt_token(
        user_id="test-user-123",
        username="testuser",
        role=Role.USER
    )
    
    # Verify token
    payload = security.verify_jwt_token(token)
    
    assert payload is not None
    assert payload['user_id'] == "test-user-123"
    assert payload['username'] == "testuser"
    assert payload['role'] == Role.USER.value


@pytest.mark.asyncio
async def test_hash_password():
    """Test password hashing"""
    security = SecurityManager()
    
    password = "testpassword123"
    hashed = security.hash_password(password)
    
    assert hashed != password
    assert len(hashed) == 64  # SHA256 produces 64 char hex string


@pytest.mark.asyncio
async def test_verify_password():
    """Test password verification"""
    security = SecurityManager()
    
    password = "testpassword123"
    hashed = security.hash_password(password)
    
    assert security.verify_password(password, hashed) is True
    assert security.verify_password("wrongpassword", hashed) is False


@pytest.mark.asyncio
async def test_encrypt_decrypt():
    """Test data encryption/decryption"""
    security = SecurityManager()
    
    sensitive_data = "sensitive@email.com"
    encrypted = security.encrypt_sensitive_data(sensitive_data)
    decrypted = security.decrypt_sensitive_data(encrypted)
    
    assert encrypted != sensitive_data
    assert decrypted == sensitive_data


def test_has_permission():
    """Test permission checking"""
    security = SecurityManager()
    
    # Admin has all permissions
    assert security.has_permission(Role.ADMIN, Permission.READ_KNOWLEDGE) is True
    assert security.has_permission(Role.ADMIN, Permission.ADMIN_ACCESS) is True
    
    # User has limited permissions
    assert security.has_permission(Role.USER, Permission.READ_KNOWLEDGE) is True
    assert security.has_permission(Role.USER, Permission.ADMIN_ACCESS) is False
    
    # Readonly has minimal permissions
    assert security.has_permission(Role.READONLY, Permission.READ_KNOWLEDGE) is True
    assert security.has_permission(Role.READONLY, Permission.WRITE_KNOWLEDGE) is False

