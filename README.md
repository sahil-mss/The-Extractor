# The Extractor 🎬🎙️📝

> **A high-performance media downloader, tag inspector, transcript extractor, and Audacity audio preparation suite for YouTube.**

---

## 📑 Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [How It Works (Architecture & Data Flow)](#how-it-works-architecture--data-flow)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start & How to Use](#quick-start--how-to-use)
- [Detailed Usage Guide](#detailed-usage-guide)
- [CLI / Standalone Mode](#cli--standalone-mode)
- [API Endpoints Reference](#api-endpoints-reference)
- [Configuration & Customization](#configuration--customization)
- [Troubleshooting & FAQs](#troubleshooting--faqs)

---

## Overview

**The Extractor** is a local desktop-grade web application and automation suite designed for content creators, researchers, audio engineers, and video editors. Given any YouTube URL (standard video, Short, or embed), it inspects video metadata in real time, parses hidden keywords/tags, fetches timestamped speech-to-text transcripts, and downloads high-definition video (MP4) and standalone audio (MP3) ready for editing in audio software such as Audacity.

---

## Key Features

- ⚡ **Instant Metadata & Tag Inspection**: Extract all video information (title, channel, views, duration, upload date) and uncover YouTube video tags/keywords that are normally hidden.
- 📜 **Timestamped Transcript Extraction**: Automatically pulls subtitle and speech-to-text transcripts with precise start timestamps formatted as `[MM:SS]` or `[HH:MM:SS]`.
- 📦 **Dual Metadata Documents**: Automatically generates organized `[METADATA].md` (Markdown) and `[METADATA].txt` (Plain Text) files containing video details, tag lists (both pill badges and comma-separated formats), full description, and the transcript.
- 🎥 **HD Video Downloader**: Downloads the best available merged video and audio streams into standard MP4 format via `yt-dlp` and `FFmpeg`.
- 🎧 **Audacity-Ready Audio Extraction**: Automatically extracts high-quality audio (192 kbps MP3) optimized for podcasting, transcription, and sound editing.
- 🎙️ **Direct Audacity Integration**: One-click button inside the UI to launch Audacity directly loaded with the newly extracted MP3.
- 🌐 **Modern Golden-Ratio Web UI**: Clean, glassmorphic dark interface with real-time download progress tracking (speed, ETA, percentages), copy-to-clipboard buttons, and direct folder openers.
- 💻 **One-Click Windows Launcher**: Run simply by double-clicking `run.bat`.

---

## How It Works (Architecture & Data Flow)

The application consists of three main layers: **Frontend Dashboard**, **FastAPI Backend**, and the **Core Extraction Engine**.

```
┌─────────────────────────────────────────────────────────────┐
│                    Web UI (Golden Ratio)                    │
│      (HTML5 / CSS Glassmorphic / Vanilla JavaScript)        │
└──────────────┬──────────────────────────────▲───────────────┘
               │ HTTP Requests                │ Poll Progress
               ▼                              │
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Server                           │
│                 (server.py on :8000)                        │
└──────────────┬──────────────────────────────▲───────────────┘
               │ Invokes                      │ Progress Hooks
               ▼                              │
┌─────────────────────────────────────────────────────────────┐
│                 Downloader Engine                           │
│                   (downloader.py)                           │
│                                                             │
│   ├── yt-dlp: Stream querying, HD video & audio extraction  │
│   ├── youtube-transcript-api / fallback: Subtitles          │
│   ├── FFmpeg: Video merging & MP3 audio transcoding         │
│   └── File Generator: Builds .md & .txt documentation       │
└─────────────────────────────────────────────────────────────┘
```

### 1. Inspection Phase (`/api/inspect`)
1. The user pastes a YouTube URL into the interface or clicks **Paste**.
2. The URL is sent to `server.py`, which triggers `downloader.inspect_video(url)`.
3. `yt-dlp` queries the video metadata without downloading video streams (`skip_download: True`).
4. `youtube-transcript-api` (with fallback to `yt-dlp` captions) fetches subtitle tracks and parses them into timestamped chunks.
5. The extracted tags, description, channel info, and transcript are returned as JSON and displayed immediately on the UI.

### 2. Download & Extraction Phase (`/api/download`)
1. The user selects desired items (Video MP4, Audio MP3, Metadata Docs) and clicks **Start Extraction & Download**.
2. A unique `task_id` is generated and a background worker thread executes `run_download_task`.
3. The frontend polls `/api/progress/{task_id}` every 500ms to display dynamic progress bars, speed, and ETA.
4. The backend coordinates:
   - **Documentation**: Generates `<Video_Title> [METADATA].md` and `.txt`.
   - **Video**: Merges best video and audio streams into `<Video_Title> [VIDEO].mp4`.
   - **Audio**: Extracts and transcodes the audio track into `<Video_Title> [AUDIO].mp3` (192 kbps).
5. Output files are placed in the `downloads/` directory.

### 3. Post-Processing & External Actions
- Clicking **Open in Explorer** triggers the OS to open the `downloads/` directory (`os.startfile` on Windows).
- Clicking **Edit Audio in Audacity** locates the local Audacity installation and opens the newly downloaded MP3.

---

## Project Structure

```
The Extractor/
│
├── downloader.py          # Core engine: metadata extraction, transcripts, yt-dlp & FFmpeg routines
├── server.py              # FastAPI server, background worker threads, and static file hosting
├── run.bat                # Windows one-click launcher (starts server & opens browser)
├── requirements.txt       # Python dependencies
│
├── web/                   # Frontend Web Application (served at http://localhost:8000)
│   ├── index.html         # Golden-ratio dual-column UI layout
│   ├── styles.css         # Modern glassmorphism, responsive grid, dark theme CSS
│   └── app.js             # Client state management, polling, and clipboard interactions
│
└── downloads/             # Target directory where all extracted media and docs are saved
```

---

## Prerequisites

Before running the application, ensure you have:

1. **Python 3.10+** installed on your system.
2. **FFmpeg** installed and accessible in your system `PATH` (or via WinGet).
   - *Windows (via Winget)*:
     ```powershell
     winget install Gyan.FFmpeg
     ```
3. *(Optional)* **Audacity**: Installed at `C:\Program Files\Audacity 4\bin\Audacity4.exe` (or your preferred path) if you want direct one-click audio launching.

---

## Quick Start & How to Use

### Method 1: The One-Click Launcher (Windows)
1. Double-click **`run.bat`** in the project root folder.
2. The batch script automatically:
   - Starts the FastAPI backend on `http://127.0.0.1:8000`.
   - Opens your default web browser to the dashboard.
3. Keep the terminal window open while using the app. Press `Ctrl + C` in the terminal when you wish to stop the server.

### Method 2: Manual Terminal Startup
1. Open a terminal in the project directory:
   ```bash
   cd "d:\Projects\The Extractor"
   ```
2. Activate your virtual environment:
   - **Windows**:
     ```powershell
     .\.venv\Scripts\activate
     ```
   - **macOS / Linux**:
     ```bash
     source .venv/bin/activate
     ```
3. Install dependencies (first time only):
   ```bash
   pip install -r requirements.txt
   ```
4. Start the server:
   ```bash
   python server.py
   ```
5. Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

---

## Detailed Usage Guide

### Step 1: Input the Video
- Copy any YouTube video link (Standard URL, Short, or `youtu.be` link).
- Click the **Paste** button on the dashboard or press `Ctrl + V`.
- Hit **Enter** or click **Inspect & Extract**.

### Step 2: Review Extracted Information
- **Hero Card**: View thumbnail, channel name, total views, and duration.
- **Keywords Cloud**: View all hidden tags attached to the video. Click **Copy** to grab all tags as a comma-separated list.
- **Transcript Panel**: Scroll through timestamped transcript segments. Click individual timestamps or copy the entire transcript.
- **Description**: Expand or copy the full original video description.

### Step 3: Select Package & Download
Under **Package Selection**, check or uncheck:
- [x] **Video (MP4 HD)**: Full video in highest resolution.
- [x] **Audio (MP3)**: Separate 192kbps audio track.
- [x] **Metadata & Transcript**: Formatted `.md` and `.txt` files.

Click **Start Extraction & Download**. Monitor real-time download speed, percentage, and ETA.

### Step 4: Access Your Extracted Files
Once complete, you can:
- Click **📁 Open in Explorer** to immediately view your downloaded files.
- Click **🎙️ Edit Audio in Audacity** to load the MP3 directly into Audacity for cleanup or editing.

---

## CLI / Standalone Mode

You can also use `downloader.py` directly from the command line without launching the web server:

```powershell
python downloader.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

This will run the full bundle extraction (Video, MP3, and Metadata Documents) and save the results directly to the `downloads/` folder.

---

## API Endpoints Reference

The backend exposes the following REST endpoints:

| Method | Endpoint | Description | Payload Example |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/inspect` | Inspects metadata, tags, and transcripts without downloading. | `{"url": "https://youtu.be/..."}` |
| `POST` | `/api/download` | Starts an asynchronous download bundle task. | `{"url": "...", "download_video": true, "download_audio": true, "download_doc": true}` |
| `GET` | `/api/progress/{task_id}` | Polls status, percentage, speed, and results of a task. | _None_ |
| `POST` | `/api/open-folder` | Opens the local `downloads/` directory in File Explorer. | _None_ |
| `POST` | `/api/open-audacity` | Launches Audacity with a given or the latest MP3 file. | `{"file_path": "downloads/sample.mp3"}` |

---

## Configuration & Customization

- **Download Folder**: Default is `./downloads`. This can be customized in `server.py` (`DOWNLOADS_DIR`) and `downloader.py`.
- **Audio Quality**: The default MP3 bitrate is `192 kbps`. You can modify `preferredquality` under `audio_opts` in `downloader.py:347`.
- **Audacity Executable Path**: Set in `server.py` line 118:
  ```python
  audacity_path = r"C:\Program Files\Audacity 4\bin\Audacity4.exe"
  ```
  Adjust this path if your Audacity executable is located elsewhere (e.g. `C:\Program Files\Audacity\Audacity.exe`).

---

## Troubleshooting & FAQs

### 1. `FFmpeg not found` or audio conversion fails
- **Cause**: FFmpeg is required by `yt-dlp` to merge video/audio streams and convert to MP3.
- **Solution**: Install FFmpeg via `winget install Gyan.FFmpeg` or download from [ffmpeg.org](https://ffmpeg.org/) and add the `bin` folder to your system `PATH`. `downloader.py` also automatically scans the WinGet directory.

### 2. Transcripts not appearing
- **Cause**: Some videos do not have closed captions or automatic speech recognition enabled, or creator-restricted transcripts.
- **Behavior**: The app will indicate that no captions were found and continue downloading the video and audio normally.

### 3. Audacity button does not open Audacity
- Verify that Audacity is installed on your computer.
- If installed in a different folder, update `audacity_path` in `server.py` to point to your `Audacity.exe`.
