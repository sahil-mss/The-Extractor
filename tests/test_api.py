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
