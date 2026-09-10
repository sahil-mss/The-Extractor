from fastapi.testclient import TestClient

from server import app

client = TestClient(app)

def test_api_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "download_dir" in data
    assert "audacity_detected" in data
    assert "defaults" in data

def test_api_history():
    response = client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert isinstance(data["history"], list)

def test_api_inspect_invalid_url():
    response = client.post("/api/inspect", json={"url": ""})
    assert response.status_code == 400

def test_api_auth_enforcement(monkeypatch):
    from config import config
    monkeypatch.setattr(config.app, "api_key", "secret-test-key")

    # Unauthenticated requests must return 401
    assert client.get("/api/config").status_code == 401
    assert client.get("/api/progress/nonexistent-task").status_code == 401
    assert client.post("/api/open-folder").status_code == 401
    assert client.post("/api/open-audacity", json={}).status_code == 401
    assert client.get("/api/history").status_code == 401
    assert client.post("/api/inspect", json={"url": "https://youtu.be/dQw4w9WgXcQ"}).status_code == 401

    # Authenticated requests pass auth verification
    headers = {"X-API-Key": "secret-test-key"}
    assert client.get("/api/config", headers=headers).status_code == 200
    assert client.get("/api/history", headers=headers).status_code == 200
