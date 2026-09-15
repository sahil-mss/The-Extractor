import os

import pytest
from fastapi.testclient import TestClient

import database
from config import Config, config, validate_startup_security
from server import app

client = TestClient(app)

def test_startup_security_validation():
    # 1. Non-localhost (0.0.0.0) without API key must raise RuntimeError
    bad_cfg = Config()
    bad_cfg.app.host = "0.0.0.0"
    bad_cfg.app.api_key = ""
    bad_cfg.security.require_api_key_for_non_localhost = True

    with pytest.raises(RuntimeError, match="Cannot bind to '0.0.0.0' without an API key configured"):
        validate_startup_security(bad_cfg)

    # 2. Non-localhost with API key must succeed
    good_cfg = Config()
    good_cfg.app.host = "0.0.0.0"
    good_cfg.app.api_key = "secret"
    validate_startup_security(good_cfg)

    # 3. Localhost (127.0.0.1) without API key must succeed
    local_cfg = Config()
    local_cfg.app.host = "127.0.0.1"
    local_cfg.app.api_key = ""
    validate_startup_security(local_cfg)

def test_batch_size_limit_rejection():
    # Attempting to submit more than max_batch_size (100) must return 400
    excessive_urls = [f"https://www.youtube.com/watch?v=vid{i:05d}" for i in range(105)]
    response = client.post("/api/batch-download", json={"urls": excessive_urls})
    assert response.status_code == 400
    assert "exceeds maximum limit" in response.json()["detail"]

def test_batch_deduplication():
    # Submitting duplicate URLs in a batch must deduplicate them
    urls = [
        "https://www.youtube.com/watch?v=dup1111",
        "https://www.youtube.com/watch?v=dup2222",
        "https://www.youtube.com/watch?v=dup1111",
        "https://www.youtube.com/watch?v=dup1111",
    ]
    response = client.post("/api/batch-download", json={"urls": urls})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["tasks"]) == 2

def test_bulk_progress_endpoint():
    response = client.get("/api/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "summary" in data
    assert "total" in data["summary"]
    assert "queued" in data["summary"]
    assert "running" in data["summary"]
    assert isinstance(data["tasks"], list)

def test_task_cancellation():
    # Enqueue a task
    download_res = client.post("/api/download", json={"url": "https://www.youtube.com/watch?v=canceltask1"})
    assert download_res.status_code == 200
    task_id = download_res.json()["task_id"]

    # Cancel the task
    cancel_res = client.post(f"/api/tasks/{task_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["cancelled"] is True

    # Check progress shows cancelled
    prog_res = client.get(f"/api/progress/{task_id}")
    assert prog_res.status_code == 200
    assert prog_res.json()["status"] == "cancelled"

def test_cancel_all_tasks():
    cancel_res = client.post("/api/tasks/cancel-all")
    assert cancel_res.status_code == 200
    assert "cancelled_count" in cancel_res.json()

def test_safe_download_path_validation(tmp_path):
    # Valid download path inside download_dir
    allowed_dir = os.path.abspath(config.absolute_download_dir)
    valid_file = os.path.join(allowed_dir, "test.mp4")
    assert database.is_safe_download_path(valid_file) is True

    # Path traversal outside download_dir
    traversal_file = os.path.join(allowed_dir, "..", "..", "windows", "system32", "calc.exe")
    assert database.is_safe_download_path(traversal_file) is False

    # Arbitrary root/system path
    assert database.is_safe_download_path("/etc/passwd") is False
    assert database.is_safe_download_path("C:\\Windows\\System32\\cmd.exe") is False
    assert database.is_safe_download_path("") is False

def test_history_pagination_and_retention(tmp_path):
    test_db = str(tmp_path / "test_pagination.db")
    database.DB_PATH = test_db
    database.init_db()

    # Populate 15 dummy records
    for i in range(15):
        database.record_task_completed(
            task_id=f"hist-task-{i}",
            url=f"https://youtube.com/watch?v=vid{i:03d}",
            info={"id": f"vid{i:03d}", "title": f"Video {i}"},
            results={},
        )

    # Test paginated query
    res = database.get_history_paginated(page=1, page_size=5)
    assert res["total"] == 15
    assert len(res["items"]) == 5
    assert res["page"] == 1
    assert res["page_size"] == 5

    res_p2 = database.get_history_paginated(page=2, page_size=5)
    assert len(res_p2["items"]) == 5

    # Test retention pruning
    prune_res = database.apply_history_retention(max_records=10)
    assert prune_res["deleted_records"] == 5
    assert database.get_history_paginated(page=1, page_size=50)["total"] == 10

def test_already_downloaded_detection(tmp_path):
    test_db = str(tmp_path / "test_already_dl.db")
    database.DB_PATH = test_db
    database.init_db()

    database.record_task_completed(
        task_id="finished-1",
        url="https://youtube.com/watch?v=already123",
        info={"id": "already123", "title": "Already Downloaded Title"},
        results={},
    )

    found = database.find_download_by_url("https://youtube.com/watch?v=already123")
    assert found is not None
    assert found["title"] == "Already Downloaded Title"

    not_found = database.find_download_by_url("https://youtube.com/watch?v=never_downloaded")
    assert not_found is None

def test_url_length_limit():
    huge_url = "https://www.youtube.com/watch?v=abc" + ("x" * 2500)
    res = client.post("/api/inspect", json={"url": huge_url})
    assert res.status_code == 400
    assert "maximum allowed length" in res.json()["detail"]
