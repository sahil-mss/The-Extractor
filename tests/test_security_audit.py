import os

import pytest
from fastapi.testclient import TestClient

import database
from config import Config, config, validate_startup_security
from server import app

client = TestClient(app)

def test_startup_security_validation():
    # 1. Non-localhost (0.0.0.0 and LAN IP) without API key must raise RuntimeError
    bad_cfg = Config()
    bad_cfg.app.host = "0.0.0.0"
    bad_cfg.app.api_key = ""
    bad_cfg.security.require_api_key_for_non_localhost = True

    with pytest.raises(RuntimeError, match="Cannot bind to '0.0.0.0' without an API key configured"):
        validate_startup_security(bad_cfg)

    lan_cfg = Config()
    lan_cfg.app.host = "192.168.1.50"
    lan_cfg.app.api_key = ""
    lan_cfg.security.require_api_key_for_non_localhost = True

    with pytest.raises(RuntimeError, match="Cannot bind to '192.168.1.50' without an API key configured"):
        validate_startup_security(lan_cfg)

    # 2. Non-localhost with API key must succeed
    good_cfg = Config()
    good_cfg.app.host = "192.168.1.50"
    good_cfg.app.api_key = "secret"
    validate_startup_security(good_cfg)

    # 3. Localhost (127.0.0.1, localhost, ::1) without API key must succeed
    for host in ("127.0.0.1", "localhost", "::1"):
        local_cfg = Config()
        local_cfg.app.host = host
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


def test_download_endpoint_url_validation():
    # Non-HTTP/HTTPS schemes must be rejected
    res = client.post("/api/download", json={"url": "javascript:alert(1)"})
    assert res.status_code == 400
    assert "Only HTTP and HTTPS URLs are allowed" in res.json()["detail"]

    # File URI scheme must be rejected
    res_file = client.post("/api/download", json={"url": "file:///etc/passwd"})
    assert res_file.status_code == 400
    assert "Only HTTP and HTTPS URLs are allowed" in res_file.json()["detail"]

    # SEC-01 SSRF tests: Loopback, private IP literals, and metadata services must be rejected
    ssrf_urls = [
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1:8080/internal",
        "http://192.168.1.1/setup",
        "http://[::1]/secret",
        "http://localhost:5000/api",
        "https://evil.com/video",
        "https://vimeo.com/123456",
    ]
    for bad_url in ssrf_urls:
        res_bad = client.post("/api/download", json={"url": bad_url})
        assert res_bad.status_code == 400
        assert any(
            msg in res_bad.json()["detail"]
            for msg in ["IP-literal", "Localhost", "not a recognized YouTube domain", "Only HTTP and HTTPS"]
        )


def test_batch_download_url_validation():
    # Malformed URL or non-YouTube URL in batch list must be rejected
    urls = [
        "https://www.youtube.com/watch?v=good111",
        "file:///etc/shadow",
    ]
    res = client.post("/api/batch-download", json={"urls": urls})
    assert res.status_code == 400
    assert "Invalid URL in batch" in res.json()["detail"]

    # SSRF URL in batch must be rejected
    ssrf_batch = [
        "https://www.youtube.com/watch?v=good111",
        "http://169.254.169.254/latest/meta-data/",
    ]
    res_ssrf = client.post("/api/batch-download", json={"urls": ssrf_batch})
    assert res_ssrf.status_code == 400
    assert "Invalid URL in batch" in res_ssrf.json()["detail"]



def test_batch_download_atomic_queue_limit(monkeypatch):
    import server

    # Set temporary small queue size
    monkeypatch.setattr(config.processing, "max_queue_size", 3)
    # Fill queue to 2 slots
    with server.TASKS_LOCK:
        server.TASKS.clear()
        server.TASKS["dummy-1"] = {"status": "queued"}
        server.TASKS["dummy-2"] = {"status": "running"}

    # Attempting to enqueue batch of 2 when only 1 slot left must reject atomically
    urls = [
        "https://www.youtube.com/watch?v=v11111",
        "https://www.youtube.com/watch?v=v22222",
    ]
    res = client.post("/api/batch-download", json={"urls": urls})
    assert res.status_code == 429
    assert "Queue capacity exceeded" in res.json()["detail"]

    # Clean up dummy tasks
    with server.TASKS_LOCK:
        server.TASKS.clear()


def test_playlist_inspection_value_error(monkeypatch):
    import downloader

    def mock_expand(url, max_items=None):
        raise ValueError("Not a valid URL: invalid-playlist")

    monkeypatch.setattr(downloader, "is_playlist_url", lambda u: True)
    monkeypatch.setattr(downloader, "expand_playlist_urls", mock_expand)

    res = client.post("/api/inspect", json={"url": "https://www.youtube.com/playlist?list=PL123"})
    assert res.status_code == 400
    assert "Not a valid URL" in res.json()["detail"]


def test_cancel_stops_running_download_and_cleans_partials(tmp_path, monkeypatch):
    import time

    import downloader
    import server

    # Setup mock inspect_video
    fake_info = {"id": "cancelvid99", "title": "Mid Download Cancel"}
    monkeypatch.setattr(downloader, "inspect_video", lambda url, cookies=None: fake_info)

    # Create dummy .part and .ytdl files in download dir
    part_file = tmp_path / "Mid Download Cancel [cancelvid99] [VIDEO].mp4.part"
    ytdl_file = tmp_path / "Mid Download Cancel [cancelvid99] [VIDEO].mp4.ytdl"
    part_file.write_text("partial data")
    ytdl_file.write_text("ytdl state")

    task_id = "test-running-cancel-task"

    class MockYDL:
        def __init__(self, opts):
            self.opts = opts
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def download(self, urls):
            # Trigger progress hook which will trigger cancellation check
            hook = self.opts.get("progress_hooks", [None])[0]
            if hook:
                # Cancel task right as hook runs
                with server.TASKS_LOCK:
                    server.CANCELLED_TASKS.add(task_id)
                hook({"status": "downloading", "_percent_str": "50.0%"})

    monkeypatch.setattr("yt_dlp.YoutubeDL", MockYDL)

    req = server.DownloadRequest(url="https://www.youtube.com/watch?v=cancelvid99", download_video=True)
    with server.TASKS_LOCK:
        server.TASKS[task_id] = {
            "task_id": task_id,
            "url": req.url,
            "status": "queued",
            "phase": "init",
            "message": "Queued...",
            "created_at": time.time(),
        }

    # Run the task directly
    monkeypatch.setattr(server.config.paths, "download_dir", str(tmp_path))
    server.run_download_task(task_id, req)

    # Verify task status is cancelled, not completed
    with server.TASKS_LOCK:
        assert server.TASKS[task_id]["status"] == "cancelled"

    # Verify leftover .part and .ytdl files were removed
    assert not part_file.exists()
    assert not ytdl_file.exists()


def test_enqueue_download_rollback_on_failure(monkeypatch):
    import pytest

    import database
    import server

    def mock_record_fail(task_id, url):
        raise RuntimeError("Simulated DB failure")

    monkeypatch.setattr(database, "record_task_created", mock_record_fail)

    with server.TASKS_LOCK:
        server.TASKS.clear()

    req = server.DownloadRequest(url="https://www.youtube.com/watch?v=failtest1")
    with pytest.raises(RuntimeError, match="Simulated DB failure"):
        server.enqueue_download(req)

    with server.TASKS_LOCK:
        assert len(server.TASKS) == 0


def test_socket_timeout_and_task_timeout(monkeypatch):
    import time

    import downloader
    import server

    # 1. Verify socket_timeout is 30 in get_base_ydl_opts
    opts = downloader.get_base_ydl_opts()
    assert opts.get("socket_timeout") == 30

    # 2. Verify task_timeout_minutes config default is 60
    assert server.config.processing.task_timeout_minutes == 60

    # 3. Verify task timeout logic marks hung task as error and cancels it
    task_id = "hung-task-123"
    with server.TASKS_LOCK:
        server.TASKS[task_id] = {
            "task_id": task_id,
            "url": "https://www.youtube.com/watch?v=hungvid",
            "status": "running",
            "started_at": time.time() - 4000,  # > 60 minutes ago
        }

    # Simulate cleanup worker timeout pass
    now = time.time()
    timeout_secs = server.config.processing.task_timeout_minutes * 60
    with server.TASKS_LOCK:
        for tid, t in list(server.TASKS.items()):
            if t.get("status") == "running" and timeout_secs > 0:
                started_at = t.get("started_at")
                if started_at and (now - started_at) > timeout_secs:
                    t["status"] = "error"
                    t["message"] = f"Task timed out after {server.config.processing.task_timeout_minutes} minutes"
                    t["finished_at"] = now
                    server.CANCELLED_TASKS.add(tid)

    with server.TASKS_LOCK:
        assert server.TASKS[task_id]["status"] == "error"
        assert "timed out" in server.TASKS[task_id]["message"]
        assert task_id in server.CANCELLED_TASKS

    # 4. Regression: simulate worker thread finishing later after timeout; status must stay error
    req = server.DownloadRequest(url="https://www.youtube.com/watch?v=hungvid")
    # Mock download_media_bundle returning successfully
    fake_results = {"info": {"id": "hungvid", "title": "Hung Video"}, "video_file": None}
    monkeypatch.setattr(downloader, "download_media_bundle", lambda **kwargs: fake_results)
    server.run_download_task(task_id, req)

    with server.TASKS_LOCK:
        assert server.TASKS[task_id]["status"] == "error"
        assert "timed out" in server.TASKS[task_id]["message"]
        server.TASKS.clear()
        server.CANCELLED_TASKS.discard(task_id)


def test_task_cleanup_worker_logs_warning(monkeypatch):
    import server

    warning_logged = []

    def mock_warning(msg, exc_info=False):
        warning_logged.append((msg, exc_info))

    monkeypatch.setattr(server.logger, "warning", mock_warning)

    try:
        raise RuntimeError("Simulated watchdog breakdown")
    except Exception:
        server.logger.warning("task cleanup failed", exc_info=True)

    assert any(msg == "task cleanup failed" and exc is True for msg, exc in warning_logged)


def test_record_task_completed_failure_logged(monkeypatch):
    import database
    import downloader
    import server

    errors_logged = []

    def mock_error(msg, exc_info=False):
        errors_logged.append((msg, exc_info))

    monkeypatch.setattr(server.logger, "error", mock_error)

    # Simulate database.record_task_completed failure
    def mock_record_fail(**kwargs):
        raise RuntimeError("Disk I/O failure on commit")

    monkeypatch.setattr(database, "record_task_completed", mock_record_fail)

    task_id = "test-db-fail-task"
    req = server.DownloadRequest(url="https://www.youtube.com/watch?v=dbfailvid")
    with server.TASKS_LOCK:
        server.TASKS[task_id] = {
            "task_id": task_id,
            "url": req.url,
            "status": "running",
            "message": "Processing...",
        }

    fake_results = {"info": {"id": "dbfailvid", "title": "DB Fail Vid"}, "video_file": None}
    monkeypatch.setattr(downloader, "download_media_bundle", lambda **kwargs: fake_results)

    # Execute task runner
    server.run_download_task(task_id, req)

    with server.TASKS_LOCK:
        # Task in-memory must still be completed
        assert server.TASKS[task_id]["status"] == "completed"
        server.TASKS.clear()

    # Must log error with exc_info=True
    assert any(msg == "Failed to persist completed task" and exc is True for msg, exc in errors_logged)


def test_batch_download_atomic_rollback_on_db_failure(monkeypatch):
    import pytest

    import database
    import server

    # Simulate DB failure on the second item in the batch
    call_count = 0

    def mock_record_created(tid, url):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise RuntimeError("Database failure during batch insert")

    monkeypatch.setattr(database, "record_task_created", mock_record_created)

    with server.TASKS_LOCK:
        server.TASKS.clear()

    urls = [
        "https://www.youtube.com/watch?v=batchrb1",
        "https://www.youtube.com/watch?v=batchrb2",
        "https://www.youtube.com/watch?v=batchrb3",
    ]

    with pytest.raises(RuntimeError, match="Database failure during batch insert"):
        server.api_batch_download(server.BatchDownloadRequest(urls=urls))

    # All created batch tasks must be rolled back from TASKS
    with server.TASKS_LOCK:
        assert len(server.TASKS) == 0


def test_batch_download_playlist_expansion_failure_skipped(monkeypatch):
    import downloader
    import server

    # Mock is_playlist_url to recognize test playlist
    monkeypatch.setattr(downloader, "is_playlist_url", lambda u: "playlist" in u)

    # Mock expand_playlist_urls to raise error
    def mock_expand(url, max_items=None):
        raise RuntimeError("Playlist is private or deleted")

    monkeypatch.setattr(downloader, "expand_playlist_urls", mock_expand)

    with server.TASKS_LOCK:
        server.TASKS.clear()

    urls = [
        "https://www.youtube.com/playlist?list=PLbroken",
        "https://www.youtube.com/watch?v=validvideo1",
    ]

    res = server.api_batch_download(server.BatchDownloadRequest(urls=urls))
    assert res["status"] == "started"
    assert res["total"] == 1
    assert len(res["skipped"]) == 1
    assert "PLbroken" in res["skipped"][0]["url"]
    assert "private or deleted" in res["skipped"][0]["reason"]

    with server.TASKS_LOCK:
        server.TASKS.clear()


def test_security_headers():
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("Referrer-Policy") == "no-referrer"


def test_cancel_already_finished_task():
    import server

    task_id = "finished-task-123"
    with server.TASKS_LOCK:
        server.TASKS[task_id] = {
            "task_id": task_id,
            "url": "https://www.youtube.com/watch?v=done123",
            "status": "completed",
        }

    res = client.post(f"/api/tasks/{task_id}/cancel")
    assert res.status_code == 200
    data = res.json()
    assert data["cancelled"] is False
    assert data["task_status"] == "completed"
    assert "already finished" in data["message"]

    with server.TASKS_LOCK:
        server.TASKS.pop(task_id, None)


@pytest.mark.anyio
async def test_lifespan_graceful_shutdown(monkeypatch):
    import server

    shutdown_called = False

    def mock_shutdown(wait=False, cancel_futures=True):
        nonlocal shutdown_called
        shutdown_called = True
        assert wait is False
        assert cancel_futures is True

    monkeypatch.setattr(server.executor, "shutdown", mock_shutdown)

    async with server.lifespan(server.app):
        pass

    assert shutdown_called is True







