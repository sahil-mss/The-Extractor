import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from config import config

DB_PATH = os.environ.get("EXTRACTOR_DB", config.database_path)

def get_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize SQLite database tables for persistent job history with indexing."""
    with get_db_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS extraction_history (
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_task_id ON extraction_history(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_created_at ON extraction_history(id DESC)")

def record_task_created(task_id: str, url: str) -> None:
    with get_db_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO extraction_history (task_id, url, status)
            VALUES (?, ?, 'queued')
        """, (task_id, url))

def record_task_completed(
    task_id: str,
    url: str,
    info: dict[str, Any],
    results: dict[str, Any],
    error_message: str | None = None
) -> None:
    status = "completed" if not error_message else "error"
    completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    doc_files = results.get("doc_files") or {}
    md_path = doc_files.get("md") if isinstance(doc_files, dict) else None
    txt_path = doc_files.get("txt") if isinstance(doc_files, dict) else None

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO extraction_history (
                task_id, url, video_id, title, channel, duration, thumbnail,
                tags_count, has_transcript, video_path, audio_path, doc_md_path, doc_txt_path,
                status, error_message, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                url=excluded.url,
                video_id=excluded.video_id,
                title=excluded.title,
                channel=excluded.channel,
                duration=excluded.duration,
                thumbnail=excluded.thumbnail,
                tags_count=excluded.tags_count,
                has_transcript=excluded.has_transcript,
                video_path=excluded.video_path,
                audio_path=excluded.audio_path,
                doc_md_path=excluded.doc_md_path,
                doc_txt_path=excluded.doc_txt_path,
                status=excluded.status,
                error_message=excluded.error_message,
                completed_at=excluded.completed_at
        """, (
            task_id,
            url,
            info.get("id"),
            info.get("title"),
            info.get("uploader"),
            info.get("duration_str"),
            info.get("thumbnail"),
            info.get("tag_count", len(info.get("tags", []))),
            1 if info.get("has_transcript") else 0,
            results.get("video_file"),
            results.get("audio_file"),
            md_path,
            txt_path,
            status,
            error_message,
            completed_at
        ))

def get_history(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM extraction_history
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return [dict(row) for row in cursor.fetchall()]

def delete_history_item(item_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM extraction_history WHERE id = ?", (item_id,))
        return cursor.rowcount > 0

def clear_all_history() -> None:
    with get_db_connection() as conn:
        conn.execute("DELETE FROM extraction_history")

# Auto-initialize on import
init_db()
