from fastapi.testclient import TestClient

from server import app

client = TestClient(app, client=("127.0.0.1", 50000))

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
    assert "js_runtime_name" in data
    assert "js_runtime_version" in data
    assert "js_runtime_supported" in data
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

    def mock_inspect(url, cookies_path=None, **kwargs):
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
    # Mark testclient's default peer IP (127.0.0.1) as trusted proxy so X-Forwarded-For is honored
    monkeypatch.setattr(config.security, "trusted_proxies", ["127.0.0.1"])

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


def test_auth_spoofed_forwarded_for_untrusted_peer(monkeypatch):
    import server
    from config import config

    monkeypatch.setattr(config.app, "api_key", "secret-test-key")
    # Untrusted proxy: trusted_proxies is empty
    monkeypatch.setattr(config.security, "trusted_proxies", [])

    with server.AUTH_FAILURES_LOCK:
        server.AUTH_FAILURES.clear()
        server.AUTH_BLOCKED_UNTIL.clear()

    # Attacker tries rotating X-Forwarded-For to bypass throttling
    for i in range(9):
        resp = client.get(
            "/api/config",
            headers={"X-API-Key": "wrong-key", "X-Forwarded-For": f"198.51.100.{i}"}
        )
        assert resp.status_code == 401

    # On the 10th attempt, since peer IP is throttled (and spoofed header ignored), it must return 429
    resp_10 = client.get(
        "/api/config",
        headers={"X-API-Key": "wrong-key", "X-Forwarded-For": "198.51.100.99"}
    )
    assert resp_10.status_code == 429

    # Cleanup
    with server.AUTH_FAILURES_LOCK:
        server.AUTH_FAILURES.clear()
        server.AUTH_BLOCKED_UNTIL.clear()


def test_auth_forwarded_for_trusted_peer_chain(monkeypatch):
    from starlette.requests import Request

    import server
    from config import config

    trusted_proxy = "10.0.0.1"
    monkeypatch.setattr(config.security, "trusted_proxies", [trusted_proxy, "10.0.0.2"])

    # 1. Untrusted peer: returns client.host
    req_untrusted = Request({
        "type": "http",
        "client": ("192.168.1.50", 12345),
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 10.0.0.1")]
    })
    assert server.get_client_ip(req_untrusted) == "192.168.1.50"

    # 2. Trusted peer: returns rightmost non-trusted entry in chain
    req_trusted = Request({
        "type": "http",
        "client": (trusted_proxy, 12345),
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 198.51.100.5, 10.0.0.2")]
    })
    assert server.get_client_ip(req_trusted) == "198.51.100.5"


def test_api_comments_success(monkeypatch):
    import downloader

    def mock_fetch_comments(url, max_comments=50, cookies_path=None):
        return [
            {"author": "alice", "text": "Great explanation!", "likes": 12, "id": "c1"},
            {"author": "bob", "text": "Loved the audio quality", "likes": 5, "id": "c2"},
        ]

    monkeypatch.setattr(downloader, "fetch_comments_data", mock_fetch_comments)
    resp = client.post("/api/comments", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "max_comments": 20})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["count"] == 2
    assert data["comments"][0]["author"] == "alice"


def test_api_download_with_snippet_and_json(monkeypatch):
    import downloader

    recorded_kwargs = {}

    def mock_download_bundle(url, **kwargs):
        recorded_kwargs.update(kwargs)
        return {
            "title": "Snippet Video",
            "channel": "Test Channel",
            "video_path": "downloads/test.mp4",
            "audio_path": None,
            "doc_path": None,
            "json_path": "downloads/test.json",
        }

    monkeypatch.setattr(downloader, "download_media_bundle", mock_download_bundle)

    payload = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "download_video": True,
        "download_audio": False,
        "download_doc": False,
        "download_json": True,
        "start_time": 10.0,
        "end_time": 45.5,
        "output_dir": "custom_folder",
    }
    resp = client.post("/api/download", json=payload)
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]
    assert task_id is not None


def test_output_dir_validation_and_safety(tmp_path, monkeypatch):
    import database
    import downloader
    from config import config

    # Mock download_media_bundle so worker thread does not download real video over network
    monkeypatch.setattr(downloader, "download_media_bundle", lambda **kwargs: {})

    # Set up dedicated downloads root
    dl_root = tmp_path / "downloads"
    dl_root.mkdir()
    allowed_custom = tmp_path / "allowed_custom"
    allowed_custom.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    monkeypatch.setattr(config.paths, "download_dir", str(dl_root))
    monkeypatch.setattr(config.paths, "allowed_output_roots", [str(allowed_custom)])
    monkeypatch.setattr(config.paths, "allow_any_output_dir", False)

    # 1. Traversal escape rejected
    resp_escape = client.post("/api/download", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "output_dir": "../../../../etc"
    })
    assert resp_escape.status_code == 400
    assert "Invalid output_dir" in resp_escape.json()["detail"]

    # 2. Arbitrary outside absolute dir rejected
    resp_outside = client.post("/api/download", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "output_dir": str(outside_dir)
    })
    assert resp_outside.status_code == 400

    # 3. Subfolder within download_dir accepted
    sub_dl = "subfolder/project"
    resp_dl = client.post("/api/download", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "output_dir": sub_dl
    })
    assert resp_dl.status_code == 200

    # 4. Folder within allowed_output_roots accepted and recognized as safe download path
    custom_sub = allowed_custom / "music"
    custom_sub.mkdir()
    custom_file = custom_sub / "track.mp3"
    custom_file.write_text("dummy")

    resp_custom = client.post("/api/download", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "output_dir": str(custom_sub)
    })
    assert resp_custom.status_code == 200
    assert database.is_safe_download_path(str(custom_file)) is True

    # 5. Direct loopback vs proxy forwarded for allow_any_output_dir
    monkeypatch.setattr(config.paths, "allow_any_output_dir", True)
    arbitrary_dir = tmp_path / "arbitrary_test_dir"
    arbitrary_dir.mkdir()

    # Direct loopback (without proxy headers) -> Allowed
    resp_loopback = client.post("/api/download", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "output_dir": str(arbitrary_dir)
    })
    assert resp_loopback.status_code == 200

    # Behind reverse proxy (carrying X-Forwarded-For or X-Real-IP) -> Rejected (400)
    resp_proxied = client.post(
        "/api/download",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "output_dir": str(arbitrary_dir)},
        headers={"X-Forwarded-For": "203.0.113.195"}
    )
    assert resp_proxied.status_code == 400
    assert "Invalid output_dir" in resp_proxied.json()["detail"]



def test_snippet_clips_validation_and_range_func(monkeypatch):
    import yt_dlp

    import downloader

    # Mock download_media_bundle so worker thread does not download real video over network
    monkeypatch.setattr(downloader, "download_media_bundle", lambda **kwargs: {})

    # 1. Start-only valid payload
    resp_start_only = client.post("/api/download", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "start_time": 30.0,
        "end_time": None
    })
    assert resp_start_only.status_code == 200

    # 2. End-only valid payload
    resp_end_only = client.post("/api/download", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "start_time": None,
        "end_time": 60.0
    })
    assert resp_end_only.status_code == 200

    # 3. Negative start time rejected (422)
    resp_neg_start = client.post("/api/download", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "start_time": -5.0
    })
    assert resp_neg_start.status_code == 422

    # 4. NaN rejected (422) via raw JSON payload
    resp_nan = client.post(
        "/api/download",
        content='{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "start_time": NaN}',
        headers={"Content-Type": "application/json"}
    )
    assert resp_nan.status_code == 422

    # 5. Huge values exceeding 86400 (24h) rejected (422)
    resp_huge = client.post("/api/download", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "end_time": 1e308
    })
    assert resp_huge.status_code == 422

    # 6. start_time >= end_time rejected (422)
    resp_inverted = client.post("/api/download", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "start_time": 50.0,
        "end_time": 40.0
    })
    assert resp_inverted.status_code == 422

    # 7. Test download_range_func with start-only (end = inf)
    range_fn = yt_dlp.utils.download_range_func(None, [(30.0, float("inf"))])
    ranges = list(range_fn({"duration": 120}, None))
    assert len(ranges) == 1
    assert ranges[0]["start_time"] == 30.0
    assert ranges[0]["end_time"] == float("inf")


def test_api_browse_folder_subprocess_and_permissions(monkeypatch):
    import subprocess
    from unittest.mock import MagicMock

    # 1. Loopback client succeeds and runs via subprocess
    called_args = []

    def mock_run(args, **kwargs):
        called_args.append(args)
        assert kwargs.get("timeout") == 120
        return MagicMock(stdout="/home/user/custom_downloads\n", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)
    resp = client.post("/api/browse-folder")
    assert resp.status_code == 200
    assert resp.json()["folder"] == "/home/user/custom_downloads"
    assert len(called_args) == 1
    assert "-c" in called_args[0]

    # 2. Non-loopback client is rejected with 403
    from config import config
    monkeypatch.setattr(config.security, "trusted_proxies", ["testclient"])
    resp_remote = client.post("/api/browse-folder", headers={"X-Forwarded-For": "203.0.113.195"})
    assert resp_remote.status_code == 403
    assert "only accessible from localhost" in resp_remote.json()["detail"]


def test_comment_highlight_logic_in_frontend():
    # Read web/app.js to verify highlight() implementation doesn't double-escape or break HTML entities
    with open("web/app.js", encoding="utf-8") as f:
        js = f.read()

    assert "function highlight(text, query)" in js
    assert "escapeHtml(text.slice(last, m.index))" in js
    assert "<mark class='highlight'>" in js
    assert "escapeHtml(m[0])" in js

    # Test equivalent highlighting logic in Python to ensure correctness
    import html
    import re

    def py_highlight(text, query):
        if not text:
            return ""
        if not query:
            return html.escape(text)
        re_pat = re.compile(re.escape(query), re.IGNORECASE)
        out = ""
        last = 0
        for m in re_pat.finditer(text):
            out += html.escape(text[last:m.start()]) + f"<mark class='highlight'>{html.escape(m.group(0))}</mark>"
            last = m.end()
        out += html.escape(text[last:])
        return out

    # Test case 1: normal text highlighting
    assert py_highlight("Hello world", "world") == "Hello <mark class='highlight'>world</mark>"

    # Test case 2: text with HTML characters like & and <
    # Query matching part of text containing & should escape & properly without double-escaping entities
    res = py_highlight("AT&T is great <3", "AT&T")
    assert res == "<mark class='highlight'>AT&amp;T</mark> is great &lt;3"

    # Query matching inside <3
    res2 = py_highlight("Rock & Roll <3", "<3")
    assert res2 == "Rock &amp; Roll <mark class='highlight'>&lt;3</mark>"


def test_api_comments_error_handling_and_no_duplication(monkeypatch):
    import downloader
    # 1. Test CommentsUnavailable raises 502
    def mock_fetch_fail(url, max_comments=50):
        raise downloader.CommentsUnavailable("Comments are disabled for this video.")

    monkeypatch.setattr(downloader, "fetch_comments_data", mock_fetch_fail)
    resp = client.post("/api/comments", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert resp.status_code == 502
    assert "Comments are disabled" in resp.json()["detail"]

    # 2. Test timeout handling (504)
    def mock_fetch_timeout(url, max_comments=50):
        import time
        time.sleep(0.05)
        raise TimeoutError("timeout")

    monkeypatch.setattr(downloader, "fetch_comments_data", mock_fetch_timeout)
    resp_timeout = client.post("/api/comments", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
    assert resp_timeout.status_code == 504
    assert "timed out" in resp_timeout.json()["detail"]

    # 3. Test inspect_video extracts comments in single pass when fetch_comments=True
    calls = []

    class DummyYDL:
        def __init__(self, opts):
            self.opts = opts
            calls.append(opts)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, url, download=False):
            return {
                "id": "dQw4w9WgXcQ",
                "title": "Never Gonna Give You Up",
                "uploader": "Rick Astley",
                "duration": 213,
                "comments": [{"id": "c1", "author": "Alice", "text": "Classic!"}],
            }

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", DummyYDL)
    data = downloader.inspect_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ", fetch_comments=True)
    assert len(calls) == 1
    assert calls[0].get("getcomments") is True
    assert len(data["comments"]) == 1
    assert data["comments"][0]["author"] == "Alice"


def test_api_comments_independent_executor_from_downloads(monkeypatch):
    import threading

    import downloader
    import server

    # Saturate all download workers in server.executor
    block_event = threading.Event()
    worker_started = threading.Event()

    def blocking_job():
        worker_started.set()
        block_event.wait(timeout=5)

    # Submit 10 jobs to completely fill worker queue
    futures = [server.executor.submit(blocking_job) for _ in range(10)]
    assert worker_started.wait(timeout=5)

    try:
        # Mock comments to return immediately
        monkeypatch.setattr(
            downloader,
            "fetch_comments_data",
            lambda url, max_comments=50, is_cancelled=None: [{"id": "c1", "author": "Alice", "text": "Hi"}],
        )

        # Call /api/comments while download executor is completely saturated
        resp = client.post("/api/comments", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert len(resp.json()["comments"]) == 1
    finally:
        block_event.set()
        for f in futures:
            f.result(timeout=5)



def test_frontend_accessibility_labels_and_attributes():
    with open("web/index.html", encoding="utf-8") as f:
        html = f.read()

    # Check input accessibility labels
    assert 'id="ytUrlInput"' in html and 'aria-label="YouTube Video or Playlist URL"' in html
    assert 'id="rangeStart"' in html and 'aria-label="Snippet Start Percentage"' in html
    assert 'id="rangeEnd"' in html and 'aria-label="Snippet End Percentage"' in html
    assert 'id="transcriptSearchInput"' in html and 'aria-label="Search spoken words in transcript"' in html
    assert 'id="descSearchInput"' in html and 'aria-label="Filter description words or links"' in html
    assert 'id="commentSearchInput"' in html and 'aria-label="Search comments"' in html
    assert 'id="historySearchInput"' in html and 'aria-label="Search history by title, URL, channel, or video ID"' in html

    # Check aria-live attributes for dynamic indicators
    assert 'id="progressCard"' in html and 'aria-live="polite"' in html
    assert 'id="inspectLoader"' in html and 'aria-live="polite"' in html
    assert 'id="errorBanner"' in html and 'aria-live="assertive"' in html
    assert 'id="toast"' in html and 'aria-live="polite"' in html

    # Check styles.css for focus-visible and prefers-reduced-motion
    with open("web/styles.css", encoding="utf-8") as f:
        css = f.read()

    assert ":focus-visible" in css
    assert "@media (prefers-reduced-motion: reduce)" in css




