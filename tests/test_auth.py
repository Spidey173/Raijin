import pytest
from datetime import timedelta
from fastapi import status
from app.auth import create_access_token
from app.config import settings

def test_issue_token_success(unauthenticated_client):
    response = unauthenticated_client.post("/auth/token", json={"user_id": "test_engineer"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user_id"] == "test_engineer"
    assert data["expires_in_seconds"] > 0

def test_issue_token_empty_user_rejected(unauthenticated_client):
    response = unauthenticated_client.post("/auth/token", json={"user_id": "  "})
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_get_me_with_valid_jwt(unauthenticated_client):
    token = create_access_token("alice_tenant")
    response = unauthenticated_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "authenticated": True,
        "user_id": "alice_tenant"
    }

def test_tampered_jwt_rejected(unauthenticated_client):
    token = create_access_token("alice_tenant")
    tampered_token = token[:-5] + "ABCDE"
    response = unauthenticated_client.get("/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "invalid token" in response.json()["detail"].lower()

def test_expired_jwt_rejected(unauthenticated_client):
    expired_token = create_access_token("alice_tenant", expires_delta=timedelta(seconds=-10))
    response = unauthenticated_client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "expired" in response.json()["detail"].lower()

def test_unauthenticated_identity_spoofing_blocked(unauthenticated_client):
    # An attacker tries to send an arbitrary X-User-ID header without valid authentication
    response = unauthenticated_client.get("/auth/me", headers={"X-User-ID": "admin"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "untrusted identity header" in response.json()["detail"].lower()

def test_missing_credentials_rejected_when_dev_mode_disabled(unauthenticated_client, monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_ANONYMOUS_DEV_MODE", False)
    response = unauthenticated_client.get("/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_api_key_authentication_success(unauthenticated_client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "super-secret-service-key")
    response = unauthenticated_client.get(
        "/auth/me",
        headers={
            "X-API-Key": "super-secret-service-key",
            "X-User-ID": "internal_cron_job"
        }
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["user_id"] == "internal_cron_job"

def test_invalid_api_key_rejected(unauthenticated_client, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "super-secret-service-key")
    response = unauthenticated_client.get(
        "/auth/me",
        headers={"X-API-Key": "wrong-key"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "invalid api key" in response.json()["detail"].lower()
