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

def test_api_config_storage_and_ytdlp():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "storage" in data
    assert "total_mb" in data["storage"]
    assert "ytdlp" in data
    assert "installed" in data["ytdlp"]

def test_api_storage_cleanup_endpoint():
    response = client.post("/api/storage/cleanup", json={"max_storage_gb": 100.0, "delete_after_days": 365})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "deleted_files" in data
    assert "freed_bytes" in data

def test_api_history_search(tmp_path):
    import database
    test_db = str(tmp_path / "test_api_search.db")
    database.DB_PATH = test_db
    database.init_db()

    database.record_task_completed(
        task_id="task-search-1",
        url="https://youtube.com/watch?v=unique11111",
        info={"id": "unique11111", "title": "Quantum Physics Lecture", "uploader": "Prof Science"},
        results={},
    )
    database.record_task_completed(
        task_id="task-search-2",
        url="https://youtube.com/watch?v=unique22222",
        info={"id": "unique22222", "title": "Cooking Spaghetti Carbonara", "uploader": "Chef Luigi"},
        results={},
    )

    res_all = client.get("/api/history")
    assert len(res_all.json()["history"]) == 2

    res_search = client.get("/api/history?search=Physics")
    records = res_search.json()["history"]
    assert len(records) == 1
    assert records[0]["title"] == "Quantum Physics Lecture"

    res_empty = client.get("/api/history?search=NonExistentKeyword")
    assert len(res_empty.json()["history"]) == 0
