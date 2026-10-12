from fastapi.testclient import TestClient

from server import app

client = TestClient(app)

def test_healthz_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "download_dir" in data
    assert "audacity_detected" in data
    assert "defaults" in data
    assert "js_runtime_available" in data
    assert isinstance(data["js_runtime_available"], bool)
    assert "ffmpeg_available" in data
    assert isinstance(data["ffmpeg_available"], bool)

def test_api_history():
    response = client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert isinstance(data["history"], list)

def test_api_inspect_invalid_url():
    response = client.post("/api/inspect", json={"url": ""})
    assert response.status_code == 400

    response_bad_format = client.post("/api/inspect", json={"url": "not-a-url"})
    assert response_bad_format.status_code == 400
    assert "Not a valid URL" in response_bad_format.json()["detail"]


def test_api_inspect_upstream_failure_returns_502(monkeypatch):
    import downloader

    def mock_inspect(url, cookies_path=None):
        raise RuntimeError("Failed to inspect video after 3 attempts: Connection error")

    monkeypatch.setattr(downloader, "inspect_video", mock_inspect)
    response = client.post("/api/inspect", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert response.status_code == 502


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

    # Non-ASCII header must return 401 instead of 500
    non_ascii_headers = [(b"x-api-key", "sécret".encode())]
    res = client.get("/api/config", headers=non_ascii_headers)
    assert res.status_code == 401

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


def test_auth_failure_throttle(monkeypatch):
    import server
    from config import config

    monkeypatch.setattr(config.app, "api_key", "secret-test-key")

    with server.AUTH_FAILURES_LOCK:
        server.AUTH_FAILURES.clear()
        server.AUTH_BLOCKED_UNTIL.clear()

    ip_headers = {"X-Forwarded-For": "203.0.113.42"}

    # First 9 failed attempts should return 401
    for _ in range(9):
        resp = client.get("/api/config", headers={"X-API-Key": "wrong-key", **ip_headers})
        assert resp.status_code == 401

    # 10th failed attempt triggers throttle and returns 429
    resp_10 = client.get("/api/config", headers={"X-API-Key": "wrong-key", **ip_headers})
    assert resp_10.status_code == 429
    assert "Too many failed authentication attempts" in resp_10.json()["detail"]
    assert "Retry-After" in resp_10.headers

    # Subsequent attempt within 15 minutes is still throttled with 429 even if key is correct or wrong
    resp_subsequent = client.get("/api/config", headers={"X-API-Key": "secret-test-key", **ip_headers})
    assert resp_subsequent.status_code == 429

    # Another IP address is not affected
    resp_other_ip = client.get(
        "/api/config",
        headers={"X-API-Key": "secret-test-key", "X-Forwarded-For": "198.51.100.10"}
    )
    assert resp_other_ip.status_code == 200

    # Cleanup
    with server.AUTH_FAILURES_LOCK:
        server.AUTH_FAILURES.clear()
        server.AUTH_BLOCKED_UNTIL.clear()

