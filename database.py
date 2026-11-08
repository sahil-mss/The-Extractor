import contextlib
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from config import config

DB_PATH = os.environ.get("EXTRACTOR_DB", config.database_path)

def get_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-4000")  # 4MB cache
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
            json_path TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_task_id ON extraction_history(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_created_at ON extraction_history(id DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_lookup ON extraction_history(url, video_id)")

        # Migration: Ensure json_path exists in existing databases
        pragma_cursor = conn.execute("PRAGMA table_info(extraction_history)")
        columns = [row[1] for row in pragma_cursor.fetchall()]
        if "json_path" not in columns:
            conn.execute("ALTER TABLE extraction_history ADD COLUMN json_path TEXT")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_video_path ON extraction_history(video_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_audio_path ON extraction_history(audio_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_doc_md_path ON extraction_history(doc_md_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_doc_txt_path ON extraction_history(doc_txt_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_json_path ON extraction_history(json_path)")

        # Table for accepted custom output directories with source tracking
        conn.execute("""
        CREATE TABLE IF NOT EXISTS known_output_dirs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            source TEXT DEFAULT 'root',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Migration: Ensure source column exists in known_output_dirs
        pragma_dirs = conn.execute("PRAGMA table_info(known_output_dirs)")
        dir_columns = [row[1] for row in pragma_dirs.fetchall()]
        if "source" not in dir_columns:
            conn.execute("ALTER TABLE known_output_dirs ADD COLUMN source TEXT DEFAULT 'root'")

        # Mark any tasks left in 'queued' or 'running' state from previous crash/restart as 'interrupted'
        conn.execute("""
            UPDATE extraction_history
            SET status = 'interrupted',
                error_message = 'Task interrupted by application shutdown or restart',
                completed_at = CURRENT_TIMESTAMP
            WHERE status IN ('queued', 'running')
        """)

def record_task_created(task_id: str, url: str) -> None:
    with get_db_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO extraction_history (task_id, url, status)
            VALUES (?, ?, 'queued')
        """, (task_id, url))

def record_batch_tasks_created(task_pairs: list[tuple[str, str]]) -> None:
    """Atomically record multiple created tasks in SQLite within a single transaction."""
    if not task_pairs:
        return
    with get_db_connection() as conn:
        conn.executemany("""
            INSERT OR IGNORE INTO extraction_history (task_id, url, status)
            VALUES (?, ?, 'queued')
        """, task_pairs)

def rollback_batch_tasks(task_ids: list[str]) -> None:
    """Remove batch tasks that failed before submission."""
    if not task_ids:
        return
    with get_db_connection() as conn:
        conn.executemany("""
            DELETE FROM extraction_history WHERE task_id = ? AND status = 'queued'
        """, [(tid,) for tid in task_ids])


def record_task_completed(
    task_id: str,
    url: str,
    info: dict[str, Any],
    results: dict[str, Any],
    error_message: str | None = None,
    status_override: str | None = None,
) -> None:
    status = status_override or ("completed" if not error_message else "error")
    completed_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    doc_files = results.get("doc_files") or {}
    md_path = doc_files.get("md") if isinstance(doc_files, dict) else None
    txt_path = doc_files.get("txt") if isinstance(doc_files, dict) else None
    json_path = results.get("json_file")

    def _norm(p: str | None) -> str | None:
        return os.path.realpath(os.path.abspath(p)) if p else None

    video_file = _norm(results.get("video_file"))
    audio_file = _norm(results.get("audio_file"))
    md_file = _norm(md_path)
    txt_file = _norm(txt_path)
    json_file = _norm(json_path)

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO extraction_history (
                task_id, url, video_id, title, channel, duration, thumbnail,
                tags_count, has_transcript, video_path, audio_path, doc_md_path, doc_txt_path, json_path,
                status, error_message, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json_path=excluded.json_path,
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
            info.get("tag_count") if info.get("tag_count") is not None else len(info.get("tags") or []),
            1 if info.get("has_transcript") else 0,
            video_file,
            audio_file,
            md_file,
            txt_file,
            json_file,
            status,
            error_message,
            completed_at
        ))

def record_known_output_dir(dir_path: str, source: str = "root") -> None:
    """Record an approved custom output directory in the database."""
    if not dir_path:
        return
    real_p = os.path.normcase(os.path.realpath(os.path.abspath(dir_path)))
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO known_output_dirs (path, source) VALUES (?, ?) "
            "ON CONFLICT(path) DO UPDATE SET source = excluded.source",
            (real_p, source),
        )


def get_known_output_dirs(only_source: str | None = None) -> set[str]:
    """Retrieve recorded approved custom output directories."""
    with get_db_connection() as conn:
        if only_source:
            cursor = conn.execute("SELECT path FROM known_output_dirs WHERE source = ?", (only_source,))
        else:
            cursor = conn.execute("SELECT path, source FROM known_output_dirs")
            rows = cursor.fetchall()
            allow_any = getattr(config.paths, "allow_any_output_dir", False)
            valid_dirs = set()
            for path, src in rows:
                if src == "allow_any":
                    if allow_any:
                        valid_dirs.add(path)
                else:
                    valid_dirs.add(path)
            return valid_dirs
        return {row[0] for row in cursor.fetchall()}


def is_safe_download_path(file_path: str) -> bool:
    """Ensure target path is strictly located inside configured download dir or approved roots."""
    if not file_path:
        return False
    try:
        from pathlib import Path

        real_target_str = os.path.normcase(os.path.realpath(os.path.abspath(file_path)))
        real_target = Path(real_target_str)

        # Build set of candidate allowed directories
        allowed_dirs = [os.path.normcase(os.path.realpath(os.path.abspath(config.absolute_download_dir)))]
        for extra in getattr(config.paths, "allowed_output_roots", []):
            if extra:
                allowed_dirs.append(os.path.normcase(os.path.realpath(os.path.abspath(extra))))

        # Add valid dynamically recorded known output dirs (checking source validity)
        allowed_dirs.extend(get_known_output_dirs())

        for d in allowed_dirs:
            root = Path(d)
            if real_target.is_relative_to(root) and real_target != root:
                return True
        return False
    except Exception:
        return False


def is_known_media_file_in_history(file_path: str) -> bool:
    """Check if a file path was generated and recorded in extraction_history.

    Uses indexed SQL equality lookup matching raw path, realpath, and normcase variants.
    """
    if not file_path:
        return False
    raw_f = file_path
    real_f = os.path.realpath(os.path.abspath(file_path))
    norm_f = os.path.normcase(real_f)

    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT 1 FROM extraction_history
            WHERE video_path IN (?, ?, ?) OR audio_path IN (?, ?, ?) OR doc_md_path IN (?, ?, ?)
               OR doc_txt_path IN (?, ?, ?) OR json_path IN (?, ?, ?)
            LIMIT 1
            """,
            (
                raw_f, real_f, norm_f,
                raw_f, real_f, norm_f,
                raw_f, real_f, norm_f,
                raw_f, real_f, norm_f,
                raw_f, real_f, norm_f,
            ),
        )
        return cursor.fetchone() is not None

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
    """Find a completed download record by URL or video_id, ensuring at least one output file still exists on disk."""
    clean_url = url.strip()
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM extraction_history
            WHERE (url = ? OR video_id = ?) AND status = 'completed'
            ORDER BY id DESC LIMIT 5
        """, (clean_url, clean_url))
        rows = cursor.fetchall()
        for row in rows:
            record = dict(row)
            # Verify if at least one associated file exists on disk
            paths = [
                record.get("video_path"),
                record.get("audio_path"),
                record.get("doc_md_path"),
                record.get("doc_txt_path"),
            ]
            if any(p and os.path.exists(p) for p in paths):
                return record
            # If no specific path was recorded, still return if record exists
            if not any(paths):
                return record
        return None

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
            cutoff = datetime.now(UTC) - timedelta(days=ret_days)
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
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

def _remove_safe_files(rows: list[sqlite3.Row] | sqlite3.Cursor) -> None:
    for row in rows:
        for col in ("video_path", "audio_path", "doc_md_path", "doc_txt_path", "json_path"):
            try:
                fpath = row[col]
            except IndexError:
                continue
            if fpath and is_safe_download_path(fpath) and os.path.exists(fpath):
                with contextlib.suppress(OSError):
                    os.remove(fpath)

def delete_history_item(item_id: int, delete_files: bool = False) -> bool:
    with get_db_connection() as conn:
        if delete_files:
            cursor = conn.execute(
                "SELECT video_path, audio_path, doc_md_path, doc_txt_path, json_path "
                "FROM extraction_history WHERE id = ?",
                (item_id,)
            )
            row = cursor.fetchone()
            if row:
                _remove_safe_files([row])
        cursor = conn.execute("DELETE FROM extraction_history WHERE id = ?", (item_id,))
        return cursor.rowcount > 0

def clear_all_history(delete_files: bool = False) -> None:
    with get_db_connection() as conn:
        if delete_files:
            cursor = conn.execute(
                "SELECT video_path, audio_path, doc_md_path, doc_txt_path, json_path "
                "FROM extraction_history"
            )
            _remove_safe_files(cursor.fetchall())
        conn.execute("DELETE FROM extraction_history")


def null_deleted_file_paths(file_paths: list[str]) -> int:
    """Null matching path columns in extraction_history for files that were deleted."""
    if not file_paths:
        return 0

    norm_paths = {os.path.normpath(p) for p in file_paths}
    updated_count = 0

    with get_db_connection() as conn:
        for p in norm_paths:
            cur = conn.execute("""
                UPDATE extraction_history
                SET video_path = CASE WHEN video_path = ? THEN NULL ELSE video_path END,
                    audio_path = CASE WHEN audio_path = ? THEN NULL ELSE audio_path END,
                    doc_md_path = CASE WHEN doc_md_path = ? THEN NULL ELSE doc_md_path END,
                    doc_txt_path = CASE WHEN doc_txt_path = ? THEN NULL ELSE doc_txt_path END,
                    json_path = CASE WHEN json_path = ? THEN NULL ELSE json_path END
                WHERE video_path = ? OR audio_path = ? OR doc_md_path = ? OR doc_txt_path = ? OR json_path = ?
            """, (p, p, p, p, p, p, p, p, p, p))
            updated_count += cur.rowcount

    return updated_count


# Auto-initialize on import
init_db()


