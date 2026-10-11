import hmac
import logging
import os
import platform
import shutil
import subprocess
import threading
import time
import uuid
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator, model_validator

import database
import downloader
from config import config, is_non_localhost, validate_startup_security

logger = logging.getLogger("the_extractor")

# Validate binding and auth on module startup
validate_startup_security(config)

VALID_RESOLUTIONS = {"best", "1080p", "720p", "480p"}
VALID_AUDIO_FORMATS = {"mp3", "wav", "m4a"}
VALID_AUDIO_BITRATES = {"128", "192", "320"}



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup phase
    yield
    # Graceful shutdown: cancel pending futures and don't block process exit
    executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="The Extractor API", version="2.6.0", lifespan=lifespan)

# Setup GZip compression for faster wire transfers
app.add_middleware(GZipMiddleware, minimum_size=500)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.app.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

# In-memory live task tracking protected by a reentrant lock
TASKS_LOCK = threading.RLock()
TASKS: dict[str, dict[str, Any]] = {}
CANCELLED_TASKS: set[str] = set()
executor = ThreadPoolExecutor(max_workers=config.processing.max_concurrent_downloads)

def verify_api_key(request: Request, x_api_key: str | None = Header(None)):
    """Verify API key if configured, or require it for non-localhost if configured using constant-time comparison."""
    must_require = bool(config.app.api_key) or (
        is_non_localhost(config.app.host) and config.security.require_api_key_for_non_localhost
    )

    if must_require:
        if not x_api_key or not hmac.compare_digest(x_api_key.encode("utf-8"), config.app.api_key.encode("utf-8")):
            raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")
    return True

# Background thread to clean up completed/failed tasks from memory and time out hung tasks
def task_cleanup_worker():
    while True:
        try:
            time.sleep(60)
            retention_secs = config.processing.task_retention_minutes * 60
            timeout_secs = config.processing.task_timeout_minutes * 60
            now = time.time()
            expired_ids = []
            timed_out_tasks = []

            with TASKS_LOCK:
                for tid, t in list(TASKS.items()):
                    status = t.get("status")
                    if status in ("completed", "error", "cancelled"):
                        finished_at = t.get("finished_at")
                        if finished_at and (now - finished_at) > retention_secs:
                            expired_ids.append(tid)
                    elif status == "running" and timeout_secs > 0:
                        started_at = t.get("started_at")
                        if started_at and (now - started_at) > timeout_secs:
                            t["status"] = "error"
                            t["message"] = f"Task timed out after {config.processing.task_timeout_minutes} minutes"
                            t["finished_at"] = now
                            CANCELLED_TASKS.add(tid)
                            timed_out_tasks.append((tid, t.get("url", "")))

                for tid in expired_ids:
                    TASKS.pop(tid, None)
                    CANCELLED_TASKS.discard(tid)

            for tid, url in timed_out_tasks:
                try:
                    database.record_task_completed(
                        task_id=tid,
                        url=url,
                        info={},
                        results={},
                        error_message=f"Task timed out after {config.processing.task_timeout_minutes} minutes",
                    )
                except Exception:
                    logger.warning("Failed to record timed out task in DB", exc_info=True)
        except Exception:
            logger.warning("task cleanup failed", exc_info=True)

cleanup_thread = threading.Thread(target=task_cleanup_worker, daemon=True)
cleanup_thread.start()

# Pydantic Request Models
class InspectRequest(BaseModel):
    url: str

class BaseMediaRequest(BaseModel):
    download_video: bool = config.defaults.download_video
    download_audio: bool = config.defaults.download_audio
    download_doc: bool = config.defaults.download_doc
    video_resolution: str = config.defaults.video_resolution
    audio_format: str = config.defaults.audio_format
    audio_bitrate: str = config.defaults.audio_bitrate

    @field_validator("video_resolution")
    @classmethod
    def validate_resolution(cls, v: str) -> str:
        clean = (v or "").strip().lower()
        if clean not in VALID_RESOLUTIONS:
            raise ValueError(f"Invalid video_resolution '{v}'. Allowed: {sorted(VALID_RESOLUTIONS)}")
        return clean

    @field_validator("audio_format")
    @classmethod
    def validate_audio_format(cls, v: str) -> str:
        clean = (v or "").strip().lower()
        if clean not in VALID_AUDIO_FORMATS:
            raise ValueError(f"Invalid audio_format '{v}'. Allowed: {sorted(VALID_AUDIO_FORMATS)}")
        return clean

    @field_validator("audio_bitrate")
    @classmethod
    def validate_audio_bitrate(cls, v: str) -> str:
        clean = (v or "").strip()
        if clean not in VALID_AUDIO_BITRATES:
            raise ValueError(f"Invalid audio_bitrate '{v}'. Allowed: {sorted(VALID_AUDIO_BITRATES)}")
        return clean

    @model_validator(mode="after")
    def validate_at_least_one_output(self) -> "BaseMediaRequest":
        if not (self.download_video or self.download_audio or self.download_doc):
            raise ValueError("At least one output option (video, audio, or metadata document) must be enabled")
        return self


class DownloadRequest(BaseMediaRequest):
    url: str


class BatchDownloadRequest(BaseMediaRequest):
    urls: list[str]


class AudacityRequest(BaseModel):
    file_path: str | None = None

class CleanupRequest(BaseModel):
    max_storage_gb: float | None = None
    delete_after_days: int | None = None

# Cross-platform folder opener
def open_system_folder(folder_path: str):
    system = platform.system()
    resolved_path = os.path.normpath(folder_path)
    if system == "Windows":
        explorer_exe = shutil.which("explorer") or "explorer"
        subprocess.Popen([explorer_exe, resolved_path])
    elif system == "Darwin":
        open_exe = shutil.which("open") or "open"
        subprocess.Popen([open_exe, resolved_path])
    else:
        xdg_exe = shutil.which("xdg-open") or "xdg-open"
        subprocess.Popen([xdg_exe, resolved_path])

@app.get("/healthz")
def healthz():
    """Unauthenticated healthcheck endpoint for Docker / orchestration."""
    return {"status": "ok", "app": "The Extractor"}

@app.get("/api/config")
def api_get_config(authorized: bool = Depends(verify_api_key)):
    """Expose system configuration, detected binaries, disk stats, and yt-dlp version status."""
    audacity_bin = config.get_audacity_executable()
    storage_stats = downloader.get_storage_stats()
    ytdlp_info = downloader.check_ytdlp_version()

    return {
        "download_dir": config.absolute_download_dir,
        "audacity_detected": bool(audacity_bin),
        "audacity_path": audacity_bin or "Not Found",
        "has_cookies": bool(config.paths.cookies_file and os.path.exists(config.paths.cookies_file)),
        "auth_enabled": bool(config.app.api_key),
        "defaults": config.defaults.model_dump(),
        "storage": storage_stats,
        "ytdlp": ytdlp_info,
        "processing": {
            "max_batch_size": config.processing.max_batch_size,
            "max_playlist_items": config.processing.max_playlist_items,
            "max_queue_size": config.processing.max_queue_size,
        }
    }

@app.post("/api/storage/cleanup")
def api_storage_cleanup(req: CleanupRequest | None = None, authorized: bool = Depends(verify_api_key)):
    max_gb = req.max_storage_gb if req else None
    days = req.delete_after_days if req else None
    result = downloader.perform_storage_cleanup(
        max_storage_gb=max_gb,
        delete_after_days=days
    )
    result["storage"] = downloader.get_storage_stats()
    return {"status": "success", **result}

@app.post("/api/inspect")
def api_inspect(req: InspectRequest, authorized: bool = Depends(verify_api_key)):
    url = req.url.strip()
    valid, err_msg = downloader.is_valid_youtube_url(url)
    if not valid:
        raise HTTPException(status_code=400, detail=err_msg)


    # Check if playlist
    if downloader.is_playlist_url(url):
        try:
            items = downloader.expand_playlist_urls(url, max_items=config.processing.max_playlist_items)
            return {
                "status": "success",
                "is_playlist": True,
                "playlist_count": len(items),
                "items": items,
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Playlist inspection error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to inspect playlist. Check server logs.") from e

    try:
        data = downloader.inspect_video(url)
        return {"status": "success", "is_playlist": False, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Inspect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal inspection error. Check server logs.") from e

@app.get("/api/check-downloaded")
def api_check_downloaded(url: str, authorized: bool = Depends(verify_api_key)):
    """Check if URL was already downloaded."""
    clean_url = url.strip()
    valid, err_msg = downloader.is_valid_youtube_url(clean_url)
    if not valid:
        raise HTTPException(status_code=400, detail=err_msg)
    record = database.find_download_by_url(clean_url)
    if record:
        return {"already_downloaded": True, "record": record}
    return {"already_downloaded": False, "record": None}


def run_download_task(task_id: str, req: DownloadRequest):
    already_cancelled = False
    with TASKS_LOCK:
        if task_id in CANCELLED_TASKS:
            already_cancelled = True
            task_entry = TASKS.get(task_id)
            if task_entry and task_entry.get("status") in ("queued", "running"):
                task_entry["status"] = "cancelled"
                task_entry["message"] = "Download cancelled"
                task_entry["finished_at"] = time.time()
                should_persist_cancel = True
            else:
                should_persist_cancel = False

    if already_cancelled:
        if should_persist_cancel:
            database.record_task_completed(
                task_id=task_id,
                url=req.url,
                info={},
                results={},
                error_message="Download cancelled by user",
                status_override="cancelled",
            )
        return

    def progress_callback(info: dict):
        with TASKS_LOCK:
            if task_id in TASKS:
                TASKS[task_id].update(info)

    def is_cancelled_check() -> bool:
        with TASKS_LOCK:
            return task_id in CANCELLED_TASKS

    try:
        with TASKS_LOCK:
            if task_id in TASKS:
                TASKS[task_id]["status"] = "running"
                TASKS[task_id]["message"] = "Processing download..."
                TASKS[task_id]["started_at"] = time.time()

        results = downloader.download_media_bundle(
            url=req.url,
            output_dir=config.absolute_download_dir,
            download_video=req.download_video,
            download_audio=req.download_audio,
            download_doc=req.download_doc,
            video_resolution=req.video_resolution,
            audio_format=req.audio_format,
            audio_bitrate=req.audio_bitrate,
            progress_hook=progress_callback,
            is_cancelled=is_cancelled_check,
        )

        if is_cancelled_check():
            with TASKS_LOCK:
                if task_id in TASKS and TASKS[task_id].get("status") == "running":
                    TASKS[task_id]["status"] = "cancelled"
                    TASKS[task_id]["message"] = "Download cancelled by user"
                    TASKS[task_id]["finished_at"] = time.time()
            database.record_task_completed(
                task_id=task_id,
                url=req.url,
                info={},
                results={},
                error_message="Download cancelled by user",
                status_override="cancelled",
            )
            return

        with TASKS_LOCK:
            task_entry = TASKS.get(task_id)
            if task_entry and task_entry.get("status") == "running":
                task_entry["status"] = "completed"
                task_entry["results"] = results
                task_entry["message"] = "Completed successfully!"
                task_entry["finished_at"] = time.time()
                persisted = True
            else:
                persisted = False

        # Persist to database only if task was still running and completed normally
        if persisted:
            try:
                database.record_task_completed(
                    task_id=task_id,
                    url=req.url,
                    info=results.get("info", {}),
                    results=results,
                )
            except Exception:
                # Retry once in case of transient SQLite busy lock
                try:
                    time.sleep(0.5)
                    database.record_task_completed(
                        task_id=task_id,
                        url=req.url,
                        info=results.get("info", {}),
                        results=results,
                    )
                except Exception:
                    logger.error("Failed to persist completed task", exc_info=True)
    except Exception as e:
        cancelled = is_cancelled_check() or isinstance(e, downloader.DownloadCancelled)
        persisted = False
        with TASKS_LOCK:
            task_entry = TASKS.get(task_id)
            if task_entry and task_entry.get("status") == "running":
                if cancelled:
                    task_entry["status"] = "cancelled"
                    task_entry["message"] = "Task cancelled by user"
                else:
                    task_entry["status"] = "error"
                    task_entry["message"] = str(e)
                task_entry["finished_at"] = time.time()
                persisted = True

        if not cancelled and persisted:
            logger.error(f"Download task {task_id} failed: {e}", exc_info=True)

        # Record in db only if the task was still in running state
        if persisted:
            database.record_task_completed(
                task_id=task_id,
                url=req.url,
                info={},
                results={},
                error_message="Task cancelled by user" if cancelled else str(e),
                status_override="cancelled" if cancelled else None,
            )

def enqueue_download(req: DownloadRequest) -> str:
    with TASKS_LOCK:
        active_count = sum(1 for t in TASKS.values() if t.get("status") in ("queued", "running"))
        if active_count >= config.processing.max_queue_size:
            raise HTTPException(
                status_code=429,
                detail=f"Queue limit reached ({config.processing.max_queue_size} tasks). Please wait."
            )

        task_id = str(uuid.uuid4())
        TASKS[task_id] = {
            "task_id": task_id,
            "url": req.url,
            "status": "queued",
            "phase": "init",
            "message": "Queued for download...",
            "percent": "0%",
            "speed": "",
            "eta": "",
            "results": None,
            "created_at": time.time(),
            "finished_at": None,
        }

    try:
        database.record_task_created(task_id, req.url)
        executor.submit(run_download_task, task_id, req)
    except Exception:
        with TASKS_LOCK:
            TASKS.pop(task_id, None)
        raise

    return task_id

@app.post("/api/download")
def api_download(req: DownloadRequest, authorized: bool = Depends(verify_api_key)):
    url = req.url.strip()
    valid, err_msg = downloader.is_valid_youtube_url(url)
    if not valid:
        raise HTTPException(status_code=400, detail=err_msg)

    task_id = enqueue_download(req)
    return {"status": "started", "task_id": task_id}

@app.post("/api/batch-download")
def api_batch_download(req: BatchDownloadRequest, authorized: bool = Depends(verify_api_key)):
    raw_urls = [u.strip() for u in req.urls if u.strip()]
    if not raw_urls:
        raise HTTPException(status_code=400, detail="At least one URL is required")

    # Enforce max batch size limit
    if len(raw_urls) > config.processing.max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds maximum limit of {config.processing.max_batch_size} URLs"
        )

    # Validate each raw URL before expansion
    for u in raw_urls:
        valid, err_msg = downloader.is_valid_youtube_url(u)
        if not valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid URL in batch: {err_msg} ({u})"
            )

    # Deduplicate input URLs while preserving order
    deduped_urls = list(dict.fromkeys(raw_urls))

    all_urls = []
    skipped_urls = []
    # Expand playlists if any
    for u in deduped_urls:
        if downloader.is_playlist_url(u):
            try:
                playlist_items = downloader.expand_playlist_urls(u, max_items=config.processing.max_playlist_items)
                all_urls.extend([p["url"] for p in playlist_items])
            except Exception as ex:
                logger.warning(f"Failed to expand playlist '{u}': {ex}")
                skipped_urls.append({"url": u, "reason": f"Failed to expand playlist: {ex}"})
        else:
            all_urls.append(u)

    # Re-deduplicate expanded playlist list and validate length and structure
    final_urls = []
    seen_final = set()
    for u in all_urls:
        if u not in seen_final:
            valid, err_msg = downloader.is_valid_youtube_url(u)
            if not valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid URL in batch: {err_msg} ({u})"
                )
            seen_final.add(u)
            final_urls.append(u)


    # Atomically check capacity and allocate all batch TASKS entries under lock
    created_tasks = []
    with TASKS_LOCK:
        active_count = sum(1 for t in TASKS.values() if t.get("status") in ("queued", "running"))
        if active_count + len(final_urls) > config.processing.max_queue_size:
            available_slots = max(0, config.processing.max_queue_size - active_count)
            raise HTTPException(
                status_code=429,
                detail=f"Queue capacity exceeded. Available slots: {available_slots}, requested: {len(final_urls)}."
            )

        now = time.time()
        for u in final_urls:
            tid = str(uuid.uuid4())
            sub_req = DownloadRequest(
                url=u,
                download_video=req.download_video,
                download_audio=req.download_audio,
                download_doc=req.download_doc,
                video_resolution=req.video_resolution,
                audio_format=req.audio_format,
                audio_bitrate=req.audio_bitrate,
            )
            TASKS[tid] = {
                "task_id": tid,
                "url": u,
                "status": "queued",
                "phase": "init",
                "message": "Queued for download...",
                "percent": "0%",
                "speed": "",
                "eta": "",
                "results": None,
                "created_at": now,
                "finished_at": None,
            }
            created_tasks.append((tid, sub_req))

    # Perform atomic DB write and executor submits outside lock, rolling back on failure
    task_ids = []
    submitted_futures = []
    created_pairs = [(tid, sub_req.url) for tid, sub_req in created_tasks]
    try:
        database.record_batch_tasks_created(created_pairs)
        for tid, sub_req in created_tasks:
            future = executor.submit(run_download_task, tid, sub_req)
            submitted_futures.append((tid, future))
            task_ids.append({"task_id": tid, "url": sub_req.url})
    except Exception:
        # Cancel any already-submitted futures if they haven't started yet
        all_tids = [tid for tid, _ in created_tasks]
        with TASKS_LOCK:
            for tid, future in submitted_futures:
                future.cancel()
                CANCELLED_TASKS.add(tid)
            for tid in all_tids:
                TASKS.pop(tid, None)

        try:
            database.rollback_batch_tasks(all_tids)
        except Exception:
            logger.warning("Failed to rollback batch tasks in DB", exc_info=True)
        raise


    return {
        "status": "started",
        "tasks": task_ids,
        "total": len(task_ids),
        "skipped": skipped_urls,
    }

# Bulk progress endpoint (EXT-004)
@app.get("/api/progress")
def api_bulk_progress(authorized: bool = Depends(verify_api_key)):
    """Return all active tasks and status summary in a single HTTP request."""
    with TASKS_LOCK:
        tasks_list = [t.copy() for t in TASKS.values()]

    queued = 0
    running = 0
    completed = 0
    error = 0
    cancelled = 0
    for t in tasks_list:
        st = t.get("status")
        if st == "queued":
            queued += 1
        elif st == "running":
            running += 1
        elif st == "completed":
            completed += 1
        elif st == "error":
            error += 1
        elif st == "cancelled":
            cancelled += 1

    summary = {
        "total": len(tasks_list),
        "queued": queued,
        "running": running,
        "completed": completed,
        "error": error,
        "cancelled": cancelled,
    }
    return {"status": "success", "summary": summary, "tasks": tasks_list}

@app.get("/api/progress/{task_id}")
def api_progress(task_id: str, authorized: bool = Depends(verify_api_key)):
    with TASKS_LOCK:
        if task_id not in TASKS:
            raise HTTPException(status_code=404, detail="Task not found")
        task_data = TASKS[task_id].copy()
        if task_id in CANCELLED_TASKS and task_data.get("status") not in ("completed", "error"):
            task_data["status"] = "cancelled"
            if not task_data.get("message") or task_data.get("message") == "Processing download...":
                task_data["message"] = "Download cancelled by user"
        return task_data

# Task cancellation endpoint (EXT-006)
@app.post("/api/tasks/{task_id}/cancel")
@app.delete("/api/tasks/{task_id}")
def api_cancel_task(task_id: str, authorized: bool = Depends(verify_api_key)):
    db_record = None
    with TASKS_LOCK:
        if task_id not in TASKS:
            raise HTTPException(status_code=404, detail="Task not found")

        current_status = TASKS[task_id].get("status")
        if current_status in ("completed", "error"):
            # Task already reached a terminal non-cancelled state
            return {
                "status": "ignored",
                "task_id": task_id,
                "cancelled": False,
                "task_status": current_status,
                "message": f"Task already finished with status '{current_status}'",
            }

        CANCELLED_TASKS.add(task_id)
        if current_status == "queued":
            TASKS[task_id]["status"] = "cancelled"
            TASKS[task_id]["message"] = "Cancelled before start"
            TASKS[task_id]["finished_at"] = time.time()
            db_record = (task_id, TASKS[task_id]["url"])

    if db_record:
        database.record_task_completed(
            task_id=db_record[0],
            url=db_record[1],
            info={},
            results={},
            error_message="Cancelled before start",
            status_override="cancelled",
        )

    return {
        "status": "success",
        "task_id": task_id,
        "cancelled": True,
        "task_status": "cancelled",
    }

@app.post("/api/tasks/cancel-all")
def api_cancel_all_tasks(authorized: bool = Depends(verify_api_key)):
    count = 0
    now = time.time()
    db_records = []
    with TASKS_LOCK:
        for tid, t in TASKS.items():
            if t.get("status") in ("queued", "running"):
                CANCELLED_TASKS.add(tid)
                if t.get("status") == "queued":
                    t["status"] = "cancelled"
                    t["message"] = "Cancelled by user"
                    t["finished_at"] = now
                    db_records.append((tid, t["url"]))
                count += 1

    for tid, url in db_records:
        database.record_task_completed(
            task_id=tid,
            url=url,
            info={},
            results={},
            error_message="Cancelled by user",
            status_override="cancelled",
        )

    return {"status": "success", "cancelled_count": count}

# History Endpoints with Pagination & Retention
@app.get("/api/history")
def api_get_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = None,
    authorized: bool = Depends(verify_api_key)
):

    safe_limit = max(1, min(limit, 200))
    safe_page_size = max(1, min(page_size, 200))
    safe_page = max(1, page)

    # Use effective page and page_size for pagination
    effective_page = safe_page
    effective_page_size = safe_page_size if (safe_page > 1 or safe_page_size != 50) else safe_limit

    paginated = database.get_history_paginated(page=effective_page, page_size=effective_page_size, search=search)
    return {"status": "success", "history": paginated["items"], **paginated}


@app.delete("/api/history/{item_id}")
def api_delete_history(item_id: int, delete_files: bool = False, authorized: bool = Depends(verify_api_key)):
    success = database.delete_history_item(item_id, delete_files=delete_files)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "deleted_id": item_id}

@app.delete("/api/history")
def api_clear_history(delete_files: bool = False, authorized: bool = Depends(verify_api_key)):
    database.clear_all_history(delete_files=delete_files)
    return {"status": "success", "message": "History cleared"}

# OS Integration Endpoints
@app.post("/api/open-folder")
def api_open_folder(authorized: bool = Depends(verify_api_key)):
    try:
        downloads_dir = config.absolute_download_dir
        open_system_folder(downloads_dir)
        return {"status": "success", "folder": downloads_dir}
    except Exception as e:
        logger.error(f"Open folder error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to open folder") from e

@app.post("/api/open-audacity")
def api_open_audacity(req: AudacityRequest, authorized: bool = Depends(verify_api_key)):
    audacity_path = config.get_audacity_executable()
    if not audacity_path:
        raise HTTPException(
            status_code=404,
            detail="Audacity executable not found. Please install Audacity or configure its path in config.yaml"
        )

    target_file = req.file_path
    downloads_dir = config.absolute_download_dir

    if not target_file or not os.path.exists(target_file):
        audio_files = [
            os.path.join(downloads_dir, f)
            for f in os.listdir(downloads_dir)
            if f.lower().endswith((".mp3", ".wav", ".m4a"))
        ]
        if audio_files:
            audio_files.sort(key=os.path.getmtime, reverse=True)
            target_file = audio_files[0]

    # Validate that target_file is within downloads directory
    if target_file and not database.is_safe_download_path(target_file):
        raise HTTPException(status_code=403, detail="Forbidden file path")

    try:
        args = [audacity_path]
        if target_file and os.path.exists(target_file):
            args.append(target_file)
        subprocess.Popen(args)
        return {"status": "success", "file": target_file}
    except Exception as e:
        logger.error(f"Launch Audacity error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to launch Audacity") from e

# Mount static web UI (locates package web assets relative to file, not CWD)
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
os.makedirs(WEB_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.app.host, port=config.app.port)

