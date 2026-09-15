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

def is_safe_download_path(file_path: str) -> bool:
    """Ensure the target path is strictly located inside the configured download directory."""
    if not file_path:
        return False
    try:
        real_target = os.path.realpath(os.path.abspath(file_path))
        real_allowed = os.path.realpath(os.path.abspath(config.absolute_download_dir))
        common = os.path.commonpath([real_target, real_allowed])
        return common == real_allowed and real_target != real_allowed
    except Exception:
        return False

def get_history(limit: int = 50, offset: int = 0, search: str | None = None) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        if search and search.strip():
            query_term = f"%{search.strip()}%"
            cursor = conn.execute("""
                SELECT * FROM extraction_history
                WHERE title LIKE ? OR url LIKE ? OR channel LIKE ? OR video_id LIKE ?
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            """, (query_term, query_term, query_term, query_term, limit, offset))
        else:
            cursor = conn.execute("""
                SELECT * FROM extraction_history
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
        return [dict(row) for row in cursor.fetchall()]

def get_history_paginated(
    page: int = 1,
    page_size: int = 50,
    search: str | None = None
) -> dict[str, Any]:
    """Retrieve paginated history items with total count."""
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    offset = (page - 1) * page_size

    with get_db_connection() as conn:
        if search and search.strip():
            query_term = f"%{search.strip()}%"
            count_cursor = conn.execute("""
                SELECT COUNT(*) as cnt FROM extraction_history
                WHERE title LIKE ? OR url LIKE ? OR channel LIKE ? OR video_id LIKE ?
            """, (query_term, query_term, query_term, query_term))
            total = count_cursor.fetchone()["cnt"]

            items_cursor = conn.execute("""
                SELECT * FROM extraction_history
                WHERE title LIKE ? OR url LIKE ? OR channel LIKE ? OR video_id LIKE ?
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            """, (query_term, query_term, query_term, query_term, page_size, offset))
        else:
            count_cursor = conn.execute("SELECT COUNT(*) as cnt FROM extraction_history")
            total = count_cursor.fetchone()["cnt"]

            items_cursor = conn.execute("""
                SELECT * FROM extraction_history
                ORDER BY id DESC
                LIMIT ? OFFSET ?
            """, (page_size, offset))

        items = [dict(row) for row in items_cursor.fetchall()]
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

def find_download_by_url(url: str) -> dict[str, Any] | None:
    """Find a completed download record by URL or video_id to detect already-downloaded media."""
    clean_url = url.strip()
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM extraction_history
            WHERE (url = ? OR video_id = ?) AND status = 'completed'
            ORDER BY id DESC LIMIT 1
        """, (clean_url, clean_url))
        row = cursor.fetchone()
        return dict(row) if row else None

def apply_history_retention(
    max_records: int | None = None,
    retention_days: int | None = None
) -> dict[str, int]:
    """Prune historical database records exceeding max_records or older than retention_days."""
    max_rec = max_records if max_records is not None else config.history.max_records
    ret_days = retention_days if retention_days is not None else config.history.retention_days

    deleted_count = 0
    with get_db_connection() as conn:
        # 1. Delete records older than retention_days
        if ret_days and ret_days > 0:
            cutoff = datetime.now(timezone.utc).timestamp() - (ret_days * 86400)
            cutoff_str = datetime.fromtimestamp(cutoff, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            cur = conn.execute(
                "DELETE FROM extraction_history WHERE created_at < ?",
                (cutoff_str,)
            )
            deleted_count += cur.rowcount

        # 2. Prune records exceeding max_records
        if max_rec and max_rec > 0:
            cur = conn.execute("""
                DELETE FROM extraction_history
                WHERE id NOT IN (
                    SELECT id FROM extraction_history ORDER BY id DESC LIMIT ?
                )
            """, (max_rec,))
            deleted_count += cur.rowcount

    return {"deleted_records": deleted_count}

def delete_history_item(item_id: int, delete_files: bool = False) -> bool:
    with get_db_connection() as conn:
        if delete_files:
            cursor = conn.execute("SELECT video_path, audio_path, doc_md_path, doc_txt_path FROM extraction_history WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            if row:
                for col in ["video_path", "audio_path", "doc_md_path", "doc_txt_path"]:
                    fpath = row[col]
                    if fpath and is_safe_download_path(fpath) and os.path.exists(fpath):
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
        cursor = conn.execute("DELETE FROM extraction_history WHERE id = ?", (item_id,))
        return cursor.rowcount > 0

def clear_all_history(delete_files: bool = False) -> None:
    with get_db_connection() as conn:
        if delete_files:
            cursor = conn.execute("SELECT video_path, audio_path, doc_md_path, doc_txt_path FROM extraction_history")
            for row in cursor.fetchall():
                for col in ["video_path", "audio_path", "doc_md_path", "doc_txt_path"]:
                    fpath = row[col]
                    if fpath and is_safe_download_path(fpath) and os.path.exists(fpath):
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
        conn.execute("DELETE FROM extraction_history")

# Auto-initialize on import
init_db()

