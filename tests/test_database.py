import os
import pytest
import database

def test_db_lifecycle(tmp_path):
    # Point database to temporary SQLite file
    test_db = str(tmp_path / "test_extractor.db")
    database.DB_PATH = test_db
    database.init_db()

    # Record task creation
    task_id = "test-task-123"
    database.record_task_created(task_id, "https://youtube.com/watch?v=sample123")

    history = database.get_history()
    assert len(history) == 1
    assert history[0]["task_id"] == task_id
    assert history[0]["status"] == "queued"

    # Complete task
    dummy_info = {
        "id": "sample123",
        "title": "Sample Video Title",
        "uploader": "Test Channel",
        "duration_str": "05:20",
        "thumbnail": "https://img.youtube.com/vi/sample123/0.jpg",
        "tag_count": 5,
        "has_transcript": True
    }
    dummy_results = {
        "video_file": "downloads/Sample [VIDEO].mp4",
        "audio_file": "downloads/Sample [AUDIO].mp3",
        "doc_files": {"md": "downloads/Sample.md", "txt": "downloads/Sample.txt"}
    }
    database.record_task_completed(task_id, "https://youtube.com/watch?v=sample123", dummy_info, dummy_results)

    updated_history = database.get_history()
    assert len(updated_history) == 1
    assert updated_history[0]["status"] == "completed"
    assert updated_history[0]["title"] == "Sample Video Title"

    # Delete record
    item_id = updated_history[0]["id"]
    deleted = database.delete_history_item(item_id)
    assert deleted is True
    assert len(database.get_history()) == 0
