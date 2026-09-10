import os
import platform
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database
import downloader
from config import config

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
executor = ThreadPoolExecutor(max_workers=config.processing.max_concurrent_downloads)

def verify_api_key(x_api_key: str | None = Header(None)):
    """Simple API Key verification if configured."""
    if config.app.api_key:
        if not x_api_key or x_api_key != config.app.api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")
    return True

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
    """Expose system configuration & detected binaries to frontend."""
    audacity_bin = config.get_audacity_executable()
    return {
        "download_dir": config.absolute_download_dir,
        "audacity_detected": bool(audacity_bin),
        "audacity_path": audacity_bin or "Not Found",
        "has_cookies": bool(config.paths.cookies_file and os.path.exists(config.paths.cookies_file)),
        "auth_enabled": bool(config.app.api_key),
        "defaults": config.defaults.model_dump(),
    }

@app.post("/api/inspect")
def api_inspect(req: InspectRequest, authorized: bool = Depends(verify_api_key)):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Check if playlist
    if downloader.is_playlist_url(url):
        try:
            items = downloader.expand_playlist_urls(url)
            return {
                "status": "success",
                "is_playlist": True,
                "playlist_count": len(items),
                "items": items,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to inspect playlist: {e}")

    try:
        data = downloader.inspect_video(url)
        return {"status": "success", "is_playlist": False, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def run_download_task(task_id: str, req: DownloadRequest):
    def progress_callback(info: dict):
        if task_id in TASKS:
            TASKS[task_id].update(info)

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
        )

        TASKS[task_id]["status"] = "completed"
        TASKS[task_id]["results"] = results
        TASKS[task_id]["message"] = "Completed successfully!"

        # Persist to database
        database.record_task_completed(
            task_id=task_id,
            url=req.url,
            info=results.get("info", {}),
            results=results,
        )
    except Exception as e:
        TASKS[task_id]["status"] = "error"
        TASKS[task_id]["message"] = str(e)
        # Record failure in db
        database.record_task_completed(
            task_id=task_id,
            url=req.url,
            info={},
            results={},
            error_message=str(e),
        )

def enqueue_download(req: DownloadRequest) -> str:
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
        "results": None
    }
    database.record_task_created(task_id, req.url)
    executor.submit(run_download_task, task_id, req)
    return task_id

@app.post("/api/download")
def api_download(req: DownloadRequest, authorized: bool = Depends(verify_api_key)):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    task_id = enqueue_download(req)
    return {"status": "started", "task_id": task_id}

@app.post("/api/batch-download")
def api_batch_download(req: BatchDownloadRequest, authorized: bool = Depends(verify_api_key)):
    raw_urls = [u.strip() for u in req.urls if u.strip()]
    if not raw_urls:
        raise HTTPException(status_code=400, detail="At least one URL is required")

    all_urls = []
    # Expand playlists if any
    for u in raw_urls:
        if downloader.is_playlist_url(u):
            try:
                playlist_items = downloader.expand_playlist_urls(u)
                all_urls.extend([p["url"] for p in playlist_items])
            except Exception:
                all_urls.append(u)
        else:
            all_urls.append(u)

    task_ids = []
    for u in all_urls:
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

@app.get("/api/progress/{task_id}")
def api_progress(task_id: str, authorized: bool = Depends(verify_api_key)):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    return TASKS[task_id]

# History Endpoints
@app.get("/api/history")
def api_get_history(limit: int = 50, offset: int = 0, authorized: bool = Depends(verify_api_key)):
    records = database.get_history(limit=limit, offset=offset)
    return {"status": "success", "history": records}

@app.delete("/api/history/{item_id}")
def api_delete_history(item_id: int, authorized: bool = Depends(verify_api_key)):
    success = database.delete_history_item(item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "deleted_id": item_id}

@app.delete("/api/history")
def api_clear_history(authorized: bool = Depends(verify_api_key)):
    database.clear_all_history()
    return {"status": "success", "message": "History cleared"}

# OS Integration Endpoints
@app.post("/api/open-folder")
def api_open_folder(authorized: bool = Depends(verify_api_key)):
    try:
        downloads_dir = config.absolute_download_dir
        open_system_folder(downloads_dir)
        return {"status": "success", "folder": downloads_dir}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

    try:
        args = [audacity_path]
        if target_file and os.path.exists(target_file):
            args.append(target_file)
        subprocess.Popen(args)
        return {"status": "success", "file": target_file}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch Audacity: {e}")

# Mount static web UI (locates package web assets relative to file, not CWD)
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
os.makedirs(WEB_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.app.host, port=config.app.port)
