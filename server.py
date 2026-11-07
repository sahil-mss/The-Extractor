import hmac
import ipaddress
import logging
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

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
    interactive_executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="The Extractor API", version="2.8.0", lifespan=lifespan)

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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Sanitize validation error details to ensure JSON-compliance."""
    import math

    def sanitize(val):
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return str(val)
        if isinstance(val, (int, str, bool)) or val is None:
            return val
        if isinstance(val, dict):
            return {str(k): sanitize(v) for k, v in val.items()}
        if isinstance(val, (list, tuple, set)):
            return [sanitize(v) for v in val]
        return str(val)

    safe_errors = sanitize(exc.errors())
    return JSONResponse(status_code=422, content={"detail": safe_errors})


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    # Prevent caching of dynamic API responses to save cache memory
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response

# In-memory live task tracking protected by a reentrant lock
TASKS_LOCK = threading.RLock()
TASKS: dict[str, dict[str, Any]] = {}
CANCELLED_TASKS: set[str] = set()
executor = ThreadPoolExecutor(max_workers=config.processing.max_concurrent_downloads)
interactive_executor = ThreadPoolExecutor(max_workers=2)

# In-memory auth failure tracker protected by lock: ip -> (failure_timestamps, blocked_until)
AUTH_FAILURES_LOCK = threading.Lock()
AUTH_FAILURES: dict[str, list[float]] = {}
AUTH_BLOCKED_UNTIL: dict[str, float] = {}

def validate_and_resolve_output_dir(requested_dir: str | None, client_host: str | None = None) -> str:
    """Validate requested output_dir against security boundaries and resolve it.

    Rules:
    - Default to config.absolute_download_dir if omitted.
    - If paths.allow_any_output_dir is True AND host is loopback, arbitrary dirs are permitted.
    - Otherwise, the resolved directory must be relative to one of the allowed roots
      (paths.download_dir or paths.allowed_output_roots).
    - If valid custom root, records it in known_output_dirs table so delete/Audacity allows it.
    """
    from pathlib import Path

    raw = (requested_dir or "").strip()
    if not raw:
        return config.absolute_download_dir

    if os.path.isabs(raw):
        target_abs = os.path.abspath(raw)
    else:
        target_abs = os.path.abspath(os.path.join(config.absolute_download_dir, raw))

    real_target_str = os.path.normcase(os.path.realpath(target_abs))
    target_path = Path(real_target_str)

    # Determine if loopback host
    is_loopback = False
    if client_host:
        ch = client_host.strip().lower()
        if ch in ("127.0.0.1", "localhost", "::1", "testclient"):
            is_loopback = True
        else:
            try:
                is_loopback = ipaddress.ip_address(ch).is_loopback
            except ValueError:
                is_loopback = False
    elif not is_non_localhost(config.app.host):
        is_loopback = True

    # If allow_any_output_dir is True and loopback host, allow and record
    allow_any = getattr(config.paths, "allow_any_output_dir", False) and is_loopback
    if allow_any:
        database.record_known_output_dir(target_abs)
        return target_abs

    # Otherwise must be relative to an allowed root
    allowed_roots = [os.path.normcase(os.path.realpath(os.path.abspath(config.absolute_download_dir)))]
    for r in getattr(config.paths, "allowed_output_roots", []):
        if r:
            allowed_roots.append(os.path.normcase(os.path.realpath(os.path.abspath(r))))

    for root_str in allowed_roots:
        root_path = Path(root_str)
        try:
            if target_path.is_relative_to(root_path):
                database.record_known_output_dir(target_abs)
                return target_abs
        except ValueError:
            continue

    raise HTTPException(status_code=400, detail="Invalid output_dir: path is outside allowed output directories")


def is_trusted_proxy(ip: str, trusted_list: list[str]) -> bool:
    """Check if an IP address matches any trusted proxy IP or CIDR network."""
    if not ip or not trusted_list:
        return False
    if ip in trusted_list:
        return True
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for item in trusted_list:
        try:
            if "/" in item:
                if ip_obj in ipaddress.ip_network(item, strict=False):
                    return True
            else:
                if ip_obj == ipaddress.ip_address(item):
                    return True
        except ValueError:
            continue
    return False


def get_client_ip(request: Request) -> str:
    """Extract client IP, using request.client.host unless peer is a trusted proxy.

    When the peer is trusted, take the rightmost X-Forwarded-For entry that is
    not itself a trusted proxy.
    """
    peer_ip = request.client.host if request.client else "unknown"
    trusted = getattr(config.security, "trusted_proxies", [])
    if not trusted or not is_trusted_proxy(peer_ip, trusted):
        return peer_ip

    forwarded = request.headers.get("X-Forwarded-For")
    if not forwarded:
        return peer_ip

    entries = [entry.strip() for entry in forwarded.split(",") if entry.strip()]
    for entry in reversed(entries):
        if not is_trusted_proxy(entry, trusted):
            return entry

    return entries[0] if entries else peer_ip

def check_auth_throttle(ip: str, now: float) -> None:
    """Raise 429 if IP is currently throttled due to excessive auth failures."""
    blocked_until = AUTH_BLOCKED_UNTIL.get(ip, 0.0)
    if now < blocked_until:
        retry_after = int(blocked_until - now)
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed authentication attempts. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(max(1, retry_after))},
        )

def record_auth_failure(ip: str, now: float) -> None:
    """Record an authentication failure for IP. Block for 15 minutes if 10 failures in 5 minutes."""
    history = [t for t in AUTH_FAILURES.get(ip, []) if (now - t) <= 300.0]
    history.append(now)
    AUTH_FAILURES[ip] = history
    if len(history) >= 10:
        AUTH_BLOCKED_UNTIL[ip] = now + 900.0  # 15 minutes block
        AUTH_FAILURES[ip] = []

def verify_api_key(request: Request, x_api_key: str | None = Header(None)):
    """Verify API key using constant-time comparison and in-memory rate limiting."""
    must_require = bool(config.app.api_key) or (
        is_non_localhost(config.app.host) and config.security.require_api_key_for_non_localhost
    )

    if must_require:
        client_ip = get_client_ip(request)
        now = time.time()
        with AUTH_FAILURES_LOCK:
            check_auth_throttle(client_ip, now)

        is_valid = bool(
            x_api_key and hmac.compare_digest(x_api_key.encode("utf-8"), config.app.api_key.encode("utf-8"))
        )

        if not is_valid:
            with AUTH_FAILURES_LOCK:
                record_auth_failure(client_ip, now)
                # If this 10th failure triggered the block, immediately return 429
                check_auth_throttle(client_ip, now)
            raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")

        # On successful auth, clear any failure history for this IP
        with AUTH_FAILURES_LOCK:
            AUTH_FAILURES.pop(client_ip, None)
            AUTH_BLOCKED_UNTIL.pop(client_ip, None)
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

            # Clean up expired auth failure tracking entries
            with AUTH_FAILURES_LOCK:
                for ip, block_end in list(AUTH_BLOCKED_UNTIL.items()):
                    if now >= block_end:
                        AUTH_BLOCKED_UNTIL.pop(ip, None)
                for ip, history in list(AUTH_FAILURES.items()):
                    valid_history = [t for t in history if (now - t) <= 300.0]
                    if valid_history:
                        AUTH_FAILURES[ip] = valid_history
                    else:
                        AUTH_FAILURES.pop(ip, None)

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
    fetch_comments: bool = False

class BaseMediaRequest(BaseModel):
    download_video: bool = config.defaults.download_video
    download_audio: bool = config.defaults.download_audio
    download_doc: bool = config.defaults.download_doc
    download_json: bool = False
    video_resolution: str = config.defaults.video_resolution
    audio_format: str = config.defaults.audio_format
    audio_bitrate: str = config.defaults.audio_bitrate
    start_time: float | None = Field(None, ge=0, allow_inf_nan=False)
    end_time: float | None = Field(None, gt=0, le=86400, allow_inf_nan=False)
    output_dir: str | None = None

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
        if not (self.download_video or self.download_audio or self.download_doc or self.download_json):
            raise ValueError("At least one output option (video, audio, metadata document, or JSON) must be enabled")
        if self.start_time is not None and self.end_time is not None and self.start_time >= self.end_time:
            raise ValueError("Snippet end_time must be greater than start_time")
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
    js_rt = downloader.get_detected_js_runtime()

    return {
        "download_dir": config.absolute_download_dir,
        "log_file": config.absolute_log_file,
        "audacity_detected": bool(audacity_bin),
        "audacity_path": audacity_bin or "Not Found",
        "has_cookies": bool(config.paths.cookies_file and os.path.exists(config.paths.cookies_file)),
        "auth_enabled": bool(config.app.api_key),
        "js_runtime_available": js_rt.get("available", False),
        "js_runtime_name": js_rt.get("name"),
        "js_runtime_version": js_rt.get("version"),
        "js_runtime_supported": js_rt.get("supported", False),
        "ffmpeg_available": downloader.ffmpeg_available(),
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
        data = downloader.inspect_video(url, fetch_comments=req.fetch_comments)
        return {"status": "success", "is_playlist": False, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Inspect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal inspection error. Check server logs.") from e

@app.post("/api/comments")
def api_get_comments(req: InspectRequest, max_comments: int = 50, authorized: bool = Depends(verify_api_key)):
    """Fetch user comments for searching and filtering with a 30s timeout and accurate error handling."""
    url = req.url.strip()
    valid, err_msg = downloader.is_valid_youtube_url(url)
    if not valid:
        raise HTTPException(status_code=400, detail=err_msg)

    limit = max(5, min(max_comments, 100))
    cancel_flag = threading.Event()
    future = None

    def _fetch():
        try:
            return downloader.fetch_comments_data(
                url,
                max_comments=limit,
                is_cancelled=cancel_flag.is_set,
            )
        except TypeError:
            # Fallback for mock callables or wrappers not accepting is_cancelled
            return downloader.fetch_comments_data(url, max_comments=limit)

    try:
        future = interactive_executor.submit(_fetch)
        comments = future.result(timeout=30)
        return {"status": "success", "count": len(comments), "comments": comments}
    except TimeoutError as e:
        cancel_flag.set()
        if future:
            future.cancel()
        raise HTTPException(status_code=504, detail="Fetching comments timed out after 30 seconds.") from e
    except downloader.CommentsUnavailable as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Fetch comments error: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to fetch comments: {e}") from e

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

        target_folder = validate_and_resolve_output_dir(req.output_dir)

        results = downloader.download_media_bundle(
            url=req.url,
            output_dir=target_folder,
            download_video=req.download_video,
            download_audio=req.download_audio,
            download_doc=req.download_doc,
            download_json=req.download_json,
            video_resolution=req.video_resolution,
            audio_format=req.audio_format,
            audio_bitrate=req.audio_bitrate,
            start_time=req.start_time,
            end_time=req.end_time,
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
def api_download(req: DownloadRequest, request: Request = None, authorized: bool = Depends(verify_api_key)):
    url = req.url.strip()
    valid, err_msg = downloader.is_valid_youtube_url(url)
    if not valid:
        raise HTTPException(status_code=400, detail=err_msg)

    client_ip = get_client_ip(request) if request is not None else None
    validate_and_resolve_output_dir(req.output_dir, client_host=client_ip)

    task_id = enqueue_download(req)
    return {"status": "started", "task_id": task_id}

@app.post("/api/batch-download")
def api_batch_download(req: BatchDownloadRequest, request: Request = None, authorized: bool = Depends(verify_api_key)):
    raw_urls = [u.strip() for u in req.urls if u.strip()]
    if not raw_urls:
        raise HTTPException(status_code=400, detail="At least one URL is required")

    client_ip = get_client_ip(request) if request is not None else None
    validate_and_resolve_output_dir(req.output_dir, client_host=client_ip)

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
                download_json=req.download_json,
                video_resolution=req.video_resolution,
                audio_format=req.audio_format,
                audio_bitrate=req.audio_bitrate,
                output_dir=req.output_dir,
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
@app.post("/api/browse-folder")
def api_browse_folder(request: Request, authorized: bool = Depends(verify_api_key)):
    """Opens a native OS folder picker dialog via a subprocess on loopback hosts only.

    Runs in a separate subprocess to avoid blocking worker threads or aborting on macOS main thread.
    Enforces a 120-second timeout.
    """
    client_ip = get_client_ip(request)
    # Allow only loopback host
    is_loopback = False
    if client_ip:
        ch = client_ip.strip().lower()
        if ch in ("127.0.0.1", "localhost", "::1", "testclient"):
            is_loopback = True
        else:
            try:
                is_loopback = ipaddress.ip_address(ch).is_loopback
            except ValueError:
                is_loopback = False

    if not is_loopback:
        raise HTTPException(status_code=403, detail="Folder picker dialog is only accessible from localhost")

    default_dir = config.absolute_download_dir
    script = (
        "import os, sys\n"
        "try:\n"
        "    import tkinter as tk\n"
        "    from tkinter import filedialog\n"
        "    root = tk.Tk()\n"
        "    root.withdraw()\n"
        "    root.attributes('-topmost', True)\n"
        "    init_dir = sys.argv[1] if len(sys.argv) > 1 and os.path.exists(sys.argv[1]) else None\n"
        "    folder = filedialog.askdirectory(initialdir=init_dir, title='Select Download Directory')\n"
        "    root.destroy()\n"
        "    print(folder or '')\n"
        "except Exception:\n"
        "    print('')\n"
    )

    selected_dir = ""
    try:
        res = subprocess.run(
            [sys.executable, "-c", script, default_dir],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        selected_dir = (res.stdout or "").strip()
    except subprocess.TimeoutExpired:
        logger.warning("Folder picker dialog timed out after 120 seconds")
    except Exception as e:
        logger.warning(f"Native browse-folder dialog subprocess failed: {e}")

    return {"status": "success", "folder": selected_dir or ""}

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

