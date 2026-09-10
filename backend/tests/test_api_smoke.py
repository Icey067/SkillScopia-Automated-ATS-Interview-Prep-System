from fastapi.testclient import TestClient

from app.main import app


def test_authentication_lifecycle_and_health():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}

        created = client.post(
            "/auth/register",
            json={"email": "candidate@example.com", "password": "secure-password"},
        )
        assert created.status_code == 201

        login = client.post(
            "/auth/login",
            json={"email": "candidate@example.com", "password": "secure-password"},
        )
        assert login.status_code == 200
        tokens = login.json()

        refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert refreshed.status_code == 200
        assert refreshed.json()["refresh_token"] != tokens["refresh_token"]

        assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
        assert client.post("/auth/logout", json={"refresh_token": refreshed.json()["refresh_token"]}).status_code == 204
