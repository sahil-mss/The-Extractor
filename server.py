import logging
import os
import platform
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database
import downloader
from config import config, validate_startup_security

logger = logging.getLogger("the_extractor")

# Validate binding and auth on module startup
validate_startup_security(config)

app = FastAPI(title="The Extractor API", version="2.5.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.app.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory live task tracking
TASKS: dict[str, dict[str, Any]] = {}
CANCELLED_TASKS: set[str] = set()
executor = ThreadPoolExecutor(max_workers=config.processing.max_concurrent_downloads)

def verify_api_key(request: Request, x_api_key: str | None = Header(None)):
    """Verify API key if configured, or require it for non-localhost if configured."""
    is_non_localhost = config.app.host in ("0.0.0.0", "::")
    must_require = bool(config.app.api_key) or (is_non_localhost and config.security.require_api_key_for_non_localhost)

    if must_require:
        if not x_api_key or x_api_key != config.app.api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")
    return True

# Background thread to clean up completed/failed tasks from memory after task_retention_minutes
def task_cleanup_worker():
    while True:
        try:
            time.sleep(60)
            retention_secs = config.processing.task_retention_minutes * 60
            now = time.time()
            expired_ids = []
            for tid, t in list(TASKS.items()):
                if t.get("status") in ("completed", "error", "cancelled"):
                    finished_at = t.get("finished_at")
                    if finished_at and (now - finished_at) > retention_secs:
                        expired_ids.append(tid)

            for tid in expired_ids:
                TASKS.pop(tid, None)
                CANCELLED_TASKS.discard(tid)
        except Exception as ex:
            logger.debug(f"Task cleanup error: {ex}")

cleanup_thread = threading.Thread(target=task_cleanup_worker, daemon=True)
cleanup_thread.start()

# Pydantic Request Models
class InspectRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    download_video: bool = config.defaults.download_video
    download_audio: bool = config.defaults.download_audio
    download_doc: bool = config.defaults.download_doc
    video_resolution: str = config.defaults.video_resolution
    audio_format: str = config.defaults.audio_format
    audio_bitrate: str = config.defaults.audio_bitrate

class BatchDownloadRequest(BaseModel):
    urls: list[str]
    download_video: bool = config.defaults.download_video
    download_audio: bool = config.defaults.download_audio
    download_doc: bool = config.defaults.download_doc
    video_resolution: str = config.defaults.video_resolution
    audio_format: str = config.defaults.audio_format
    audio_bitrate: str = config.defaults.audio_bitrate

class AudacityRequest(BaseModel):
    file_path: str | None = None

class CleanupRequest(BaseModel):
    max_storage_gb: float | None = None
    delete_after_days: int | None = None

# Cross-platform folder opener
def open_system_folder(folder_path: str):
    system = platform.system()
    if system == "Windows":
        subprocess.Popen(["explorer", os.path.normpath(folder_path)])
    elif system == "Darwin":
        subprocess.Popen(["open", folder_path])
    else:
        subprocess.Popen(["xdg-open", folder_path])

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
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    if len(url) > config.security.max_url_length:
        raise HTTPException(
            status_code=400,
            detail=f"URL exceeds maximum allowed length of {config.security.max_url_length} characters"
        )

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
        except Exception as e:
            logger.error(f"Playlist inspection error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to inspect playlist. Check server logs.")

    try:
        data = downloader.inspect_video(url)
        return {"status": "success", "is_playlist": False, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Inspect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal inspection error. Check server logs.")

@app.get("/api/check-downloaded")
def api_check_downloaded(url: str, authorized: bool = Depends(verify_api_key)):
    """Check if URL was already downloaded."""
    record = database.find_download_by_url(url)
    if record:
        return {"already_downloaded": True, "record": record}
    return {"already_downloaded": False, "record": None}

def run_download_task(task_id: str, req: DownloadRequest):
    if task_id in CANCELLED_TASKS:
        TASKS[task_id]["status"] = "cancelled"
        TASKS[task_id]["message"] = "Download cancelled"
        TASKS[task_id]["finished_at"] = time.time()
        return

    def progress_callback(info: dict):
        if task_id in TASKS:
            TASKS[task_id].update(info)

    def is_cancelled_check() -> bool:
        return task_id in CANCELLED_TASKS

    try:
        TASKS[task_id]["status"] = "running"
        TASKS[task_id]["message"] = "Processing download..."

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

        TASKS[task_id]["status"] = "completed"
        TASKS[task_id]["results"] = results
        TASKS[task_id]["message"] = "Completed successfully!"
        TASKS[task_id]["finished_at"] = time.time()

        # Persist to database
        database.record_task_completed(
            task_id=task_id,
            url=req.url,
            info=results.get("info", {}),
            results=results,
        )
    except Exception as e:
        if is_cancelled_check():
            TASKS[task_id]["status"] = "cancelled"
            TASKS[task_id]["message"] = "Task cancelled by user"
        else:
            TASKS[task_id]["status"] = "error"
            TASKS[task_id]["message"] = str(e)
            logger.error(f"Download task {task_id} failed: {e}", exc_info=True)

        TASKS[task_id]["finished_at"] = time.time()
        # Record in db
        database.record_task_completed(
            task_id=task_id,
            url=req.url,
            info={},
            results={},
            error_message=str(e),
        )

def enqueue_download(req: DownloadRequest) -> str:
    # Check max queue size limit
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
    database.record_task_created(task_id, req.url)
    executor.submit(run_download_task, task_id, req)
    return task_id

@app.post("/api/download")
def api_download(req: DownloadRequest, authorized: bool = Depends(verify_api_key)):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    if len(url) > config.security.max_url_length:
        raise HTTPException(
            status_code=400,
            detail=f"URL exceeds maximum allowed length of {config.security.max_url_length} characters"
        )

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

    # Deduplicate input URLs while preserving order
    seen = set()
    deduped_urls = []
    for u in raw_urls:
        if u not in seen:
            seen.add(u)
            deduped_urls.append(u)

    all_urls = []
    # Expand playlists if any
    for u in deduped_urls:
        if downloader.is_playlist_url(u):
            try:
                playlist_items = downloader.expand_playlist_urls(u, max_items=config.processing.max_playlist_items)
                all_urls.extend([p["url"] for p in playlist_items])
            except Exception:
                all_urls.append(u)
        else:
            all_urls.append(u)

    # Re-deduplicate expanded playlist list
    final_urls = []
    for u in all_urls:
        if u not in final_urls:
            final_urls.append(u)

    task_ids = []
    for u in final_urls:
        sub_req = DownloadRequest(
            url=u,
            download_video=req.download_video,
            download_audio=req.download_audio,
            download_doc=req.download_doc,
            video_resolution=req.video_resolution,
            audio_format=req.audio_format,
            audio_bitrate=req.audio_bitrate
        )
        task_id = enqueue_download(sub_req)
        task_ids.append({"task_id": task_id, "url": u})

    return {"status": "started", "tasks": task_ids, "total": len(task_ids)}

# Bulk progress endpoint (EXT-004)
@app.get("/api/progress")
def api_bulk_progress(authorized: bool = Depends(verify_api_key)):
    """Return all active tasks and status summary in a single HTTP request."""
    tasks_list = list(TASKS.values())
    summary = {
        "total": len(tasks_list),
        "queued": sum(1 for t in tasks_list if t.get("status") == "queued"),
        "running": sum(1 for t in tasks_list if t.get("status") == "running"),
        "completed": sum(1 for t in tasks_list if t.get("status") == "completed"),
        "error": sum(1 for t in tasks_list if t.get("status") == "error"),
        "cancelled": sum(1 for t in tasks_list if t.get("status") == "cancelled"),
    }
    return {"status": "success", "summary": summary, "tasks": tasks_list}

@app.get("/api/progress/{task_id}")
def api_progress(task_id: str, authorized: bool = Depends(verify_api_key)):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    return TASKS[task_id]

# Task cancellation endpoint (EXT-006)
@app.post("/api/tasks/{task_id}/cancel")
@app.delete("/api/tasks/{task_id}")
def api_cancel_task(task_id: str, authorized: bool = Depends(verify_api_key)):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")

    CANCELLED_TASKS.add(task_id)
    if TASKS[task_id]["status"] == "queued":
        TASKS[task_id]["status"] = "cancelled"
        TASKS[task_id]["message"] = "Cancelled before start"
        TASKS[task_id]["finished_at"] = time.time()
    return {"status": "success", "task_id": task_id, "cancelled": True}

@app.post("/api/tasks/cancel-all")
def api_cancel_all_tasks(authorized: bool = Depends(verify_api_key)):
    count = 0
    now = time.time()
    for tid, t in TASKS.items():
        if t.get("status") in ("queued", "running"):
            CANCELLED_TASKS.add(tid)
            if t.get("status") == "queued":
                t["status"] = "cancelled"
                t["message"] = "Cancelled by user"
                t["finished_at"] = now
            count += 1
    return {"status": "success", "cancelled_count": count}

# History Endpoints with Pagination & Retention
@app.get("/api/history")
def api_get_history(
    limit: int = 50,
    offset: int = 0,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
    authorized: bool = Depends(verify_api_key)
):
    # Support both page/page_size and limit/offset for backward compatibility
    if page > 1 or page_size != 50:
        paginated = database.get_history_paginated(page=page, page_size=page_size, search=search)
        return {"status": "success", "history": paginated["items"], **paginated}

    paginated = database.get_history_paginated(page=1, page_size=limit, search=search)
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
        raise HTTPException(status_code=500, detail="Failed to open folder")

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
        raise HTTPException(status_code=500, detail="Failed to launch Audacity")

# Mount static web UI (locates package web assets relative to file, not CWD)
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
os.makedirs(WEB_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.app.host, port=config.app.port)

