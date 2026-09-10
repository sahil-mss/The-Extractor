import os

from downloader import (
    extract_video_id,
    format_timestamp,
    is_playlist_url,
    resolve_video_format_string,
    sanitize_filename,
)


def test_extract_video_id():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

def test_is_playlist_url():
    assert is_playlist_url("https://www.youtube.com/playlist?list=PL123456789") is True
    assert is_playlist_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is False

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

    stats = get_storage_stats(str(tmp_path))
    assert stats["file_count"] == 2
    assert stats["total_bytes"] == 3000

    # Cleanup by age: delete older than 5 days
    cleanup_res = perform_storage_cleanup(str(tmp_path), delete_after_days=5)
    assert cleanup_res["deleted_files"] == 1
    assert cleanup_res["freed_bytes"] == 1000
    assert not f1.exists()
    assert f2.exists()

    # Cleanup by size cap: cap at very small size
    cleanup_res2 = perform_storage_cleanup(str(tmp_path), max_storage_gb=0.0000001)
    assert cleanup_res2["deleted_files"] == 1
    assert not f2.exists()

def test_check_ytdlp_version():
    from downloader import check_ytdlp_version
    info = check_ytdlp_version()
    assert "installed" in info
    assert isinstance(info["installed"], str)
