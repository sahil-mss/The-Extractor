import os
import subprocess
import threading
import uuid
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import downloader

app = FastAPI(title="The Extractor API", version="2.0.0")

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOADS_DIR = os.path.abspath("downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# In-memory task tracking
TASKS: Dict[str, Dict] = {}

class InspectRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    download_video: bool = True
    download_audio: bool = True
    download_doc: bool = True

class AudacityRequest(BaseModel):
    file_path: Optional[str] = None

@app.post("/api/inspect")
def api_inspect(req: InspectRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL is required")
    try:
        data = downloader.inspect_video(url)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def run_download_task(task_id: str, req: DownloadRequest):
    def progress_callback(info: Dict):
        if task_id in TASKS:
            TASKS[task_id].update(info)

    try:
        TASKS[task_id]["status"] = "running"
        TASKS[task_id]["message"] = "Starting process..."
        results = downloader.download_media_bundle(
            url=req.url,
            output_dir=DOWNLOADS_DIR,
            download_video=req.download_video,
            download_audio=req.download_audio,
            download_doc=req.download_doc,
            progress_hook=progress_callback,
        )
        TASKS[task_id]["status"] = "completed"
        TASKS[task_id]["results"] = results
        TASKS[task_id]["message"] = "Download and extraction complete!"
    except Exception as e:
        TASKS[task_id]["status"] = "error"
        TASKS[task_id]["message"] = str(e)

@app.post("/api/download")
def api_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL is required")

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "phase": "init",
        "message": "Queued for download...",
        "percent": "0%",
        "speed": "",
        "eta": "",
        "results": None
    }

    thread = threading.Thread(target=run_download_task, args=(task_id, req), daemon=True)
    thread.start()

    return {"status": "started", "task_id": task_id}

@app.get("/api/progress/{task_id}")
def api_progress(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    return TASKS[task_id]

@app.post("/api/open-folder")
def api_open_folder():
    try:
        if os.name == "nt":
            os.startfile(DOWNLOADS_DIR)
        else:
            subprocess.Popen(["xdg-open", DOWNLOADS_DIR])
        return {"status": "success", "folder": DOWNLOADS_DIR}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/open-audacity")
def api_open_audacity(req: AudacityRequest):
    audacity_path = r"C:\Program Files\Audacity 4\bin\Audacity4.exe"
    target_file = req.file_path

    # If no file specified, pick the most recent MP3 in the downloads folder
    if not target_file or not os.path.exists(target_file):
        mp3s = [
            os.path.join(DOWNLOADS_DIR, f)
            for f in os.listdir(DOWNLOADS_DIR)
            if f.lower().endswith(".mp3")
        ]
        if mp3s:
            mp3s.sort(key=os.path.getmtime, reverse=True)
            target_file = mp3s[0]

    try:
        args = [audacity_path]
        if target_file and os.path.exists(target_file):
            args.append(target_file)
        subprocess.Popen(args)
        return {"status": "success", "file": target_file}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch Audacity: {e}")

# Mount static web directory
WEB_DIR = os.path.abspath("web")
os.makedirs(WEB_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
