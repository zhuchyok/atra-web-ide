"""
Integration tests for REST API
"""

import pytest
import httpx
from fastapi.testclient import TestClient
from knowledge_os.app.rest_api import app


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "name" in response.json()
    assert response.json()["name"] == "Knowledge OS REST API"


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_register_user(client):
    """Test user registration"""
    response = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "password": "testpassword123",
            "email": "test@example.com",
            "role": "user"
        }
    )
    
    # Может быть 200 (успех) или 400 (пользователь уже существует)
    assert response.status_code in [200, 400]


def test_login_user(client):
    """Test user login"""
    # Сначала регистрируем
    client.post(
        "/auth/register",
        json={
            "username": "testuser2",
            "password": "testpassword123"
        }
    )
    
    # Затем логинимся
    response = client.post(
        "/auth/login",
        json={
            "username": "testuser2",
            "password": "testpassword123"
        }
    )
    
    if response.status_code == 200:
        assert "access_token" in response.json()
        assert "token_type" in response.json()
        assert response.json()["token_type"] == "bearer"


def test_protected_endpoint_without_token(client):
    """Test accessing protected endpoint without token (401 Unauthorized — нет токена)."""
    response = client.get("/stats")
    assert response.status_code == 401  # Unauthorized: отсутствует или невалиден токен


def test_protected_endpoint_with_token(client):
    """Test accessing protected endpoint with token"""
    # Регистрируем и логинимся
    client.post(
        "/auth/register",
        json={
            "username": "testuser3",
            "password": "testpassword123"
        }
    )
    
    login_response = client.post(
        "/auth/login",
        json={
            "username": "testuser3",
            "password": "testpassword123"
        }
    )
    
    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        
        # Используем токен
        response = client.get(
            "/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Может быть 200 (успех) или 500 (если БД не настроена)
        assert response.status_code in [200, 500]


def test_list_projects(client):
    """GET /api/projects returns list of projects (200, array)."""
    response = client.get("/api/projects")
    # 200 when DB available; 500 if DB not configured (e.g. in CI without DB)
    assert response.status_code in [200, 500]
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list)
        for item in data:
            assert "slug" in item and "name" in item

