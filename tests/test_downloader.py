import os

from downloader import (
    _parse_ver,
    extract_video_id,
    format_timestamp,
    is_playlist_url,
    resolve_video_format_string,
    sanitize_filename,
)


def test_parse_ver():
    assert _parse_ver("2026.8.19") == (2026, 8, 19)
    assert _parse_ver("2026.8.19rc1") == (2026, 8, 19)
    assert _parse_ver("2026.8.19rc1") <= _parse_ver("2026.8.19")
    assert _parse_ver("2.6.0") == (2, 6, 0)
    assert _parse_ver("v2.6.0") == (6, 0) or _parse_ver("2.6.0b2") == (2, 6, 0)


def test_extract_video_id():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

def test_is_playlist_url():
    assert is_playlist_url("https://www.youtube.com/playlist?list=PL123456789") is True
    assert is_playlist_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is False
    # False positive prevention: 'blacklist=1' without 'list' param
    assert is_playlist_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&blacklist=1") is False
    # youtu.be shortlink with video ID and list param treated as single video
    assert is_playlist_url("https://youtu.be/dQw4w9WgXcQ?list=PL123456789") is False
    # Video in playlist with index navigation
    assert is_playlist_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123&index=1") is True

def test_format_timestamp():
    assert format_timestamp(65) == "01:05"
    assert format_timestamp(3665) == "01:01:05"
    assert format_timestamp(0) == "00:00"

def test_sanitize_filename():
    assert sanitize_filename('Invalid: / * ? " < > | Name') == "Invalid Name"
    long_name = "A" * 150
    assert len(sanitize_filename(long_name)) == 120
    assert len(sanitize_filename(long_name, max_len=50)) == 50

def test_resolve_video_format_string():
    assert "1080" in resolve_video_format_string("1080p")
    assert "720" in resolve_video_format_string("720p")
    assert "bestvideo" in resolve_video_format_string("best")

def test_download_media_bundle_end_to_end_mock(monkeypatch, tmp_path):
    from downloader import download_media_bundle

    fake_info = {
        "id": "abc12345678",
        "title": "Tutorial Video: Part 1",
        "uploader": "Test Creator",
        "channel_url": "https://youtube.com/@test",
        "duration_str": "10:00",
        "upload_date": "2026-09-10",
        "view_count": 1000,
        "tags": ["python", "media"],
        "description": "Tutorial test description",
        "transcript": [{"start": 0.0, "duration": 2.0, "timestamp": "00:00", "text": "Hello world"}],
        "has_transcript": True,
    }

    monkeypatch.setattr("downloader.inspect_video", lambda url, cookies=None: fake_info)

    class DummyYoutubeDL:
        def __init__(self, opts):
            self.opts = opts
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def download(self, urls):
            outtmpl = self.opts.get("outtmpl", "")
            # Simulate created file
            dummy_file = outtmpl.replace(".%(ext)s", ".mp4" if "VIDEO" in outtmpl else ".mp3")
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write("mock media content")

    monkeypatch.setattr("yt_dlp.YoutubeDL", DummyYoutubeDL)

    progress_events = []
    results = download_media_bundle(
        url="https://youtube.com/watch?v=abc12345678",
        output_dir=str(tmp_path),
        download_video=True,
        download_audio=True,
        download_doc=True,
        progress_hook=lambda d: progress_events.append(d.get("phase")),
    )

    assert "abc12345678" in results["video_file"]
    assert "abc12345678" in results["audio_file"]
    assert "abc12345678" in results["doc_files"]["md"]
    assert "finished" in progress_events

def test_filename_collision_dedup(monkeypatch, tmp_path):
    """Test that two different videos with identical titles do not overwrite each other."""
    from downloader import download_media_bundle

    class DummyYoutubeDL:
        def __init__(self, opts):
            self.opts = opts
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def download(self, urls):
            pass

    monkeypatch.setattr("yt_dlp.YoutubeDL", DummyYoutubeDL)

    # Video 1
    info1 = {"id": "VID_ONE_1111", "title": "Same Title Video"}
    monkeypatch.setattr("downloader.inspect_video", lambda url, cookies=None: info1)
    res1 = download_media_bundle("https://youtube.com/watch?v=VID_ONE_1111", output_dir=str(tmp_path))

    # Video 2
    info2 = {"id": "VID_TWO_2222", "title": "Same Title Video"}
    monkeypatch.setattr("downloader.inspect_video", lambda url, cookies=None: info2)
    res2 = download_media_bundle("https://youtube.com/watch?v=VID_TWO_2222", output_dir=str(tmp_path))

    # Verify separate paths
    assert res1["video_file"] != res2["video_file"]
    assert res1["audio_file"] != res2["audio_file"]
    assert res1["doc_files"]["md"] != res2["doc_files"]["md"]
    assert "VID_ONE_1111" in res1["video_file"]
    assert "VID_TWO_2222" in res2["video_file"]

def test_storage_stats_and_cleanup(tmp_path):
    import time

    from downloader import get_storage_stats, perform_storage_cleanup

    # Create dummy files
    f1 = tmp_path / "video1.mp4"
    f1.write_bytes(b"A" * 1000)
    # Set mtime to 10 days ago
    old_time = time.time() - (10 * 86400)
    os.utime(f1, (old_time, old_time))

    f2 = tmp_path / "video2.mp4"
    f2.write_bytes(b"B" * 2000)
    # Set mtime to 1 hour ago (> 10 minutes)
    hour_ago = time.time() - 3600
    os.utime(f2, (hour_ago, hour_ago))

    # Add .gitkeep and .part file - both must be preserved!
    gitkeep = tmp_path / ".gitkeep"
    gitkeep.write_bytes(b"")
    os.utime(gitkeep, (old_time, old_time))

    part_file = tmp_path / "video_partial.mp4.part"
    part_file.write_bytes(b"partial")
    os.utime(part_file, (old_time, old_time))

    # Also register f1 in database to verify path nulling
    import database
    database.init_db()
    database.record_task_completed(
        task_id="cleanup-test-task",
        url="https://youtube.com/watch?v=cleanuptest1",
        info={},
        results={"video_file": str(f1)},
    )

    stats = get_storage_stats(str(tmp_path))
    assert stats["file_count"] == 4
    assert stats["total_bytes"] == 3007

    # Cleanup by age: delete older than 5 days
    cleanup_res = perform_storage_cleanup(str(tmp_path), delete_after_days=5)
    assert cleanup_res["deleted_files"] == 1
    assert cleanup_res["freed_bytes"] == 1000
    assert not f1.exists()
    assert f2.exists()
    assert gitkeep.exists()
    assert part_file.exists()

    # Verify matching path column in extraction_history was set to NULL
    with database.get_db_connection() as conn:
        row = conn.execute("SELECT video_path FROM extraction_history WHERE task_id = 'cleanup-test-task'").fetchone()
        assert row["video_path"] is None

    # Cleanup by size cap: cap at very small size
    cleanup_res2 = perform_storage_cleanup(str(tmp_path), max_storage_gb=0.0000001)
    assert cleanup_res2["deleted_files"] == 1
    assert not f2.exists()
    assert gitkeep.exists()
    assert part_file.exists()

def test_check_ytdlp_version():
    from downloader import check_ytdlp_version
    info = check_ytdlp_version()
    assert "installed" in info
    assert isinstance(info["installed"], str)


def test_find_ffmpeg_bin_checks_beyond_path(monkeypatch):
    import platform
    import shutil

    from downloader import find_ffmpeg_bin

    monkeypatch.setattr(shutil, "which", lambda x: None)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    expected_path = os.path.join("/usr/bin", "ffmpeg")
    monkeypatch.setattr(os.path, "exists", lambda p: p == expected_path or p == "/usr/bin/ffmpeg")
    assert find_ffmpeg_bin() == "/usr/bin"


def test_version_compare_ignores_zero_padding():
    from downloader import _parse_ver
    assert _parse_ver("2026.8.19") == _parse_ver("2026.08.19")


def test_inspect_video_invalid_url_raises_value_error():
    import pytest

    from downloader import inspect_video

    with pytest.raises(ValueError, match="Not a valid URL"):
        inspect_video("invalid-url-format")


def test_check_ytdlp_version_caches_for_one_hour(monkeypatch):
    import urllib.request

    import downloader

    call_count = 0

    class DummyResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def read(self):
            nonlocal call_count
            call_count += 1
            return b'{"info": {"version": "2026.10.01"}}'

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=3.0: DummyResponse())

    downloader._YTDLP_VERSION_CACHE = None
    downloader._YTDLP_VERSION_CACHE_TIME = 0.0

    res1 = downloader.check_ytdlp_version(force_refresh=True)
    assert call_count == 1
    assert res1["latest"] == "2026.10.01"

    res2 = downloader.check_ytdlp_version()
    assert call_count == 1
    assert res2["latest"] == "2026.10.01"


def test_inspect_video_fails_fast_on_permanent_error(monkeypatch):
    import pytest
    import yt_dlp

    from downloader import PermanentMediaError, inspect_video

    attempts = 0

    class FailingYoutubeDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def extract_info(self, url, download=False):
            nonlocal attempts
            attempts += 1
            raise yt_dlp.utils.DownloadError("ERROR: Video unavailable. This video is private.")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FailingYoutubeDL)

    with pytest.raises(PermanentMediaError, match="Permanent media error"):
        inspect_video("https://www.youtube.com/watch?v=private123")

    # Must fail immediately without retrying
    assert attempts == 1


def test_inspect_video_retries_transient_error(monkeypatch):
    import pytest
    import yt_dlp

    from config import config
    from downloader import inspect_video

    attempts = 0

    class TransientFailYoutubeDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def extract_info(self, url, download=False):
            nonlocal attempts
            attempts += 1
            raise yt_dlp.utils.DownloadError("HTTP Error 429: Too Many Requests")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", TransientFailYoutubeDL)
    monkeypatch.setattr(config.processing, "retry_delay_seconds", 0.01)

    with pytest.raises(RuntimeError, match="Failed to inspect video after"):
        inspect_video("https://www.youtube.com/watch?v=busy123")

    # Should have retried max_retries times
    assert attempts == config.processing.max_retries


def test_inspect_video_cancel_during_retry_sleep(monkeypatch):
    """Verify that a cancellation signal aborts retry backoff sleep immediately."""
    import threading
    import time

    import pytest
    import yt_dlp

    from config import config
    from downloader import DownloadCancelled, inspect_video

    class FailYoutubeDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def extract_info(self, url, download=False):
            raise yt_dlp.utils.DownloadError("Temporary network glitch")

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FailYoutubeDL)
    monkeypatch.setattr(config.processing, "retry_delay_seconds", 10.0)

    cancelled = False

    def is_cancelled():
        return cancelled

    start_time = time.time()

    # Cancel after a brief moment (e.g., 0.1s)
    def trigger_cancel():
        nonlocal cancelled
        time.sleep(0.1)
        cancelled = True

    t = threading.Thread(target=trigger_cancel)
    t.start()

    with pytest.raises(DownloadCancelled, match="Task was cancelled by user"):
        inspect_video("https://www.youtube.com/watch?v=busy123", is_cancelled=is_cancelled)

    t.join()
    duration = time.time() - start_time
    # It must break out much faster than the full 10.0s delay
    assert duration < 2.0


def test_js_runtime_available(monkeypatch):
    import shutil

    from downloader import js_runtime_available

    # 1. When deno is present
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/deno" if cmd == "deno" else None)
    assert js_runtime_available() is True

    # 2. When node is present
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/node" if cmd == "node" else None)
    assert js_runtime_available() is True

    # 3. When bun is present
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/bun" if cmd == "bun" else None)
    assert js_runtime_available() is True

    # 4. When quickjs/qjs is present
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/qjs" if cmd == "qjs" else None)
    assert js_runtime_available() is True

    # 5. When none are present
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    assert js_runtime_available() is False


def test_ffmpeg_available(monkeypatch):
    import shutil

    import downloader
    from downloader import ffmpeg_available

    # 1. Found on PATH
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/ffmpeg" if cmd == "ffmpeg" else None)
    monkeypatch.setattr(downloader, "find_ffmpeg_bin", lambda: None)
    assert ffmpeg_available() is True

    # 2. Found by fallback (find_ffmpeg_bin returns directory or path)
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    monkeypatch.setattr(downloader, "find_ffmpeg_bin", lambda: "/opt/ffmpeg/bin")
    assert ffmpeg_available() is True

    # 3. Missing (neither on PATH nor found by fallback)
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    monkeypatch.setattr(downloader, "find_ffmpeg_bin", lambda: None)
    assert ffmpeg_available() is False



