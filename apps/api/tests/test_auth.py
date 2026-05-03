import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@patch("app.api.v1.routers.auth.register_user", new_callable=AsyncMock)
def test_register_user(mock_register):
    mock_register.return_value = {
        "user": {"id": "123", "email": "test@example.com", "is_active": True, "is_verified": False, "full_name": "Test", "created_at": "2026-05-03T10:00:00Z"},
        "workspace": {"id": "456", "name": "Test Workspace", "slug": "test", "plan": "free", "is_active": True, "created_at": "2026-05-03T10:00:00Z"},
        "access_token": "fake-token",
        "token_type": "bearer"
    }
    
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123", "full_name": "Test"}
    )
    assert response.status_code == 201
    assert "access_token" in response.json()

@patch("app.api.v1.routers.auth.authenticate_user", new_callable=AsyncMock)
def test_login_user(mock_auth):
    # Mocking User model returned from authenticate_user
    class MockUser:
        id = "123"
        is_active = True
    
    mock_auth.return_value = MockUser()
    
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

@patch("app.api.v1.routers.auth.authenticate_user", new_callable=AsyncMock)
def test_login_wrong_password(mock_auth):
    mock_auth.return_value = None
    
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

def test_auth_me_requires_token():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
