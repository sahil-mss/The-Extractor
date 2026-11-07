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


def test_init_db_marks_orphaned_tasks_interrupted(tmp_path):
    test_db = str(tmp_path / "test_interrupted.db")
    database.DB_PATH = test_db
    database.init_db()

    # Create orphaned queued and running tasks
    database.record_task_created("orphan-1", "https://youtube.com/watch?v=orphan1")
    database.record_task_created("orphan-2", "https://youtube.com/watch?v=orphan2")
    with database.get_db_connection() as conn:
        conn.execute("UPDATE extraction_history SET status = 'running' WHERE task_id = 'orphan-2'")

    # Re-run init_db (simulating app restart)
    database.init_db()

    history = database.get_history()
    assert len(history) == 2
    for h in history:
        assert h["status"] == "interrupted"
        assert "interrupted" in h["error_message"].lower()
        assert h["completed_at"] is not None


def test_init_db_migration_pragma_check(tmp_path):
    import sqlite3

    test_db = str(tmp_path / "legacy_schema.db")
    database.DB_PATH = test_db

    # Create a table missing json_path as in older schema versions (prior to v2.5.0)
    with sqlite3.connect(test_db) as conn:
        conn.execute("""
        CREATE TABLE extraction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE,
            url TEXT NOT NULL,
            video_id TEXT,
            title TEXT,
            channel TEXT,
            duration TEXT,
            thumbnail TEXT,
            tags_count INTEGER DEFAULT 0,
            has_transcript BOOLEAN DEFAULT 0,
            video_path TEXT,
            audio_path TEXT,
            doc_md_path TEXT,
            doc_txt_path TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
        """)

    # Running init_db must detect via PRAGMA table_info and add json_path without failure
    database.init_db()

    with sqlite3.connect(test_db) as conn:
        cursor = conn.execute("PRAGMA table_info(extraction_history)")
        columns = [row[1] for row in cursor.fetchall()]
        assert "json_path" in columns

    # Running init_db again (idempotent) should not error or add it twice
    database.init_db()


