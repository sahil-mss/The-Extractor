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

def test_resolve_video_format_string():
    assert "1080" in resolve_video_format_string("1080p")
    assert "720" in resolve_video_format_string("720p")
    assert "bestvideo" in resolve_video_format_string("best")
