# The Extractor 🎬🎙️📝

> **A modern, cross-platform media downloader, batch & playlist processor, tag inspector, timestamped transcript generator, and Audacity audio studio.**

[![CI](https://github.com/sahil-mss/The-Extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/sahil-mss/The-Extractor/actions/workflows/ci.yml)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](docker-compose.yml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blueviolet)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📑 Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
  - [1. Install & Run CLI (`extractor`)](#1-install--run-cli-extractor)
  - [2. Run Directly with Python (`python main.py`)](#2-run-directly-with-python-python-mainpy)
  - [3. Docker / Docker Compose](#3-docker--docker-compose)
  - [4. Background System Service (Linux / VPS)](#4-background-system-service-linux--vps)
- [How It Works (Architecture & Data Flow)](#how-it-works-architecture--data-flow)
- [Project Structure](#project-structure)
- [User Guide & Workflows](#user-guide--workflows)
  - [Single Video Mode](#single-video-mode)
  - [Batch & Playlist Mode](#batch--playlist-mode)
  - [Format & Quality Customization](#format--quality-customization)
  - [Persistent Job History](#persistent-job-history)
  - [Audacity & System Integration](#audacity--system-integration)
- [Configuration Reference (`config.yaml`)](#configuration-reference-configyaml)
- [Cookies & Age-Restricted Videos](#cookies--age-restricted-videos)
- [CLI / Standalone Mode](#cli--standalone-mode)
- [REST API Reference](#rest-api-reference)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Troubleshooting & FAQs](#troubleshooting--faqs)

---

## Overview

**The Extractor** is a local web application and automation suite designed for content creators, researchers, audio engineers, and video editors. Given any YouTube URL, playlist, or list of URLs, it inspects metadata in real time, parses hidden tags, extracts timestamped speech-to-text transcripts, and downloads customized video (MP4) and standalone audio (MP3/WAV/M4A) ready for audio mastering in tools like Audacity.

Unlike basic download scripts, The Extractor features:
- **True cross-platform compatibility** across Windows, macOS, and Linux.
- **Batch & playlist processing** with an asynchronous worker queue.
- **Persistent SQLite history** recording every extraction and local file path.
- **Dynamic configuration** via YAML files and environment variables.
- **Docker containerization** with FFmpeg pre-bundled.
- **Automated test coverage & linting** via `pytest` and `ruff`.

---

## Key Features

- ⚡ **Instant Metadata & Tag Inspection**: Extract all video information (title, channel, views, duration, upload date) and uncover YouTube video tags/keywords that are normally hidden.
- 📜 **Timestamped Transcript Extraction**: Automatically pulls subtitle and speech-to-text transcripts with precise start timestamps formatted as `[MM:SS]` or `[HH:MM:SS]`.
- 🔁 **Batch & Playlist Ingestion**: Input a list of URLs (one per line or comma-separated) or a YouTube playlist URL. The background task worker processes them smoothly with real-time queue monitors.
- 💾 **Persistent SQLite Job History**: All tasks, file locations, titles, tags, and execution statuses are saved in an embedded SQLite database (`extractor.db`). Never lose track of what you've extracted.
- 🎚️ **Format & Quality Selection**: Select video resolutions (**Best/4K, 1080p, 720p, 480p**) and audio formats (**MP3 320k/192k/128k, WAV lossless, M4A**).
- 📦 **Dual Metadata Documents**: Generates clean `[METADATA].md` (Markdown) and `[METADATA].txt` files containing channel stats, tags, description, and transcripts.
- 🎙️ **Cross-Platform Audacity Studio**: Dynamic binary detection for Audacity on Windows, macOS (`/Applications/Audacity.app`), and Linux (`/usr/bin/audacity`). One-click launching with the extracted audio track loaded.
- 🍪 **Cookies & Auth Support**: Optional `cookies.txt` support for age-restricted or bot-detected YouTube videos, plus optional API key protection for LAN/remote hosting.
- 🐳 **Docker & Compose Ready**: Bundles Python, FFmpeg, and dependencies inside a production Docker container.

---

## Quick Start

The Extractor is packaged as a standard Python application and self-contained web service. No `.bat` or `.sh` script files are needed.

### 1. Install & Run CLI (`extractor`)

Install in your active environment:
```bash
pip install -e .
```

Now, launch the application from anywhere:
```bash
extractor
```

Custom options:
```bash
# Bind to all network interfaces (for LAN/VPS hosting)
extractor --host 0.0.0.0 --port 8000

# Run headless without opening browser
extractor --no-browser

# Enable hot reload for development
extractor --reload
```

### 2. Run Directly with Python (`python main.py`)

If you prefer running without installing the package:
```bash
pip install -r requirements.txt
python main.py
```

### 3. Docker / Docker Compose

To deploy containerized with FFmpeg pre-bundled:
```bash
docker compose up -d
```
Access the dashboard at `http://localhost:8000`. All downloaded files persist in `./downloads`.

### 4. Background System Service (Linux / VPS)

To run The Extractor permanently as a systemd service:
```ini
# /etc/systemd/system/extractor.service
[Unit]
Description=The Extractor - Self-Hosted Media Studio
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/opt/The-Extractor
ExecStart=/opt/The-Extractor/.venv/bin/extractor --host 0.0.0.0 --port 8000 --no-browser
Restart=always

[Install]
WantedBy=multi-user.target
```
Enable and start:
```bash
sudo systemctl enable --now extractor
```

---

## How It Works (Architecture & Data Flow)

```
┌─────────────────────────────────────────────────────────────┐
│                    Web UI (Golden Ratio)                    │
│   • Single & Batch Tabs   • Queue Monitor  • History Modal  │
│   • Quality Selectors     • Audacity & Folder Triggers      │
└──────────────┬──────────────────────────────▲───────────────┘
               │ REST HTTP                    │ Polling Progress
               ▼                              │
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Server (server.py)               │
│   • ThreadPoolExecutor Queue   • Cross-Platform Launchers   │
│   • Auth Verification          • Configuration Provider     │
└───────┬──────────────────────────────┬──────────────────────┘
        │ Saves/Queries History        │ Dispatches Jobs
        ▼                              ▼
┌──────────────┐             ┌────────────────────────────────┐
│   SQLite DB  │             │   Downloader Engine            │
│(database.py) │             │     (downloader.py)            │
│              │             │  • yt-dlp + FFmpeg stream merge│
│ • History    │             │  • youtube-transcript-api      │
│ • Job Status │             │  • Exponential retry backoff   │
│ • File paths │             │  • Playlist URL expansion      │
└──────────────┘             └────────────────────────────────┘
```

---

## Project Structure

```
The Extractor/
│
├── config.py              # Configuration manager (config.yaml, .env, defaults)
├── config.yaml.example    # Configuration template
├── database.py            # SQLite history repository and lifecycle tracking
├── downloader.py          # Core engine: metadata inspection, transcripts, yt-dlp & FFmpeg
├── main.py                # Standalone CLI entrypoint with argparse
├── server.py              # FastAPI server, background worker queue, and API endpoints
├── setup.py               # Package metadata and entry_points definition
├── pyproject.toml         # Modern packaging specification
├── Dockerfile             # Multi-stage production container with FFmpeg
├── docker-compose.yml     # Docker Compose definition with volume mounts
├── .dockerignore          # Docker build exclusions
├── LICENSE                # MIT License
├── CHANGELOG.md           # Release history and updates
├── pytest.ini             # Pytest configuration
├── requirements.txt       # Production runtime dependencies
├── requirements-dev.txt   # Development dependencies (pytest, ruff)
│
├── tests/                 # Automated test suite
│   ├── test_api.py        # API endpoint tests
│   ├── test_config.py     # Configuration and Audacity resolution tests
│   ├── test_database.py   # SQLite CRUD and lifecycle tests
│   └── test_downloader.py # URL parser, sanitize, and format resolver tests
│
├── web/                   # Web Application (served at http://localhost:8000)
│   ├── index.html         # Golden-ratio dual-mode interface
│   ├── styles.css         # Glassmorphic dark theme, responsive grid
│   └── app.js             # Client state, batch queue tracker, history loader
│
└── downloads/             # Directory where media and docs are saved (auto-created)
```

---

## User Guide & Workflows

### Single Video Mode
1. Ensure the **Single Video** tab is active.
2. Paste any YouTube URL (Standard, Short, or `youtu.be` link) and click **Inspect & Extract** (or press Enter).
3. Review the video preview, view counts, hidden tags, and timestamped speech-to-text transcript.
4. Select your preferred **Video Quality** (e.g., 1080p) and **Audio Quality** (e.g., MP3 320k).
5. Choose what packages to download (**Video**, **Audio**, **Metadata & Transcript**).
6. Click **Start Extraction & Download** and monitor the live progress bar, speed, and ETA.

### Batch & Playlist Mode
1. Click the **Batch & Playlists** tab.
2. Paste multiple video URLs (separated by newlines or commas) or a YouTube playlist URL.
3. Click **Queue Batch Download**.
4. The background queue will sequentially process each video without freezing the UI.
5. You can dismiss finished items or monitor errors if any single item fails.

### Format & Quality Customization
Choose between:
- **Video**: `Best Available (HD/4K)`, `1080p Full HD`, `720p HD`, or `480p SD`.
- **Audio**: `MP3 (320 kbps - Studio)`, `MP3 (192 kbps - Standard)`, `MP3 (128 kbps - Voice)`, `WAV (Lossless PCM)`, or `M4A (AAC)`.

### Persistent Job History
- Click the **📜 History** button in the header at any time.
- View past extractions, statuses (`completed`, `queued`, `error`), channels, and timestamps.
- Remove individual records or clear all history.

### Audacity & System Integration
- **Open Downloads Folder**: Opens the local output folder in File Explorer (Windows), Finder (macOS), or your default file manager (Linux).
- **Edit Audio in Audacity**: Launches Audacity directly with the newly downloaded audio track ready for noise reduction, equalization, and editing.

---

## Configuration Reference (`config.yaml`)

You can create a `config.yaml` file in the root directory (copy from `config.yaml.example`):

```yaml
app:
  host: "127.0.0.1"          # Set to "0.0.0.0" for Docker or LAN hosting
  port: 8000
  api_key: ""                 # Set a secret key to secure your API
  cors_origins: ["*"]

paths:
  download_dir: "downloads"   # Custom downloads path
  cookies_file: ""            # Path to cookies.txt (e.g., "cookies.txt")
  audacity_path: ""           # Explicit path to Audacity (auto-detected if blank)

defaults:
  video_resolution: "best"    # "best", "1080p", "720p", "480p"
  audio_format: "mp3"         # "mp3", "wav", "m4a"
  audio_bitrate: "192"        # "320", "192", "128"
  download_video: true
  download_audio: true
  download_doc: true

processing:
  max_retries: 3              # Retry attempts for transient network issues
  retry_delay_seconds: 2
  max_concurrent_downloads: 2 # Max parallel queue workers
```

---

## Cookies & Age-Restricted Videos

To download age-restricted or bot-protected YouTube videos:
1. Export your YouTube cookies using a browser extension (such as *Get cookies.txt LOCALLY*) into a file named `cookies.txt`.
2. Place `cookies.txt` in the root folder.
3. In `config.yaml`, set:
   ```yaml
   paths:
     cookies_file: "cookies.txt"
   ```
4. Restart the server. The settings drawer in the web interface will display `Cookies Configured: ✅ Yes`.

---

## CLI / Standalone Mode

`downloader.py` can also be executed directly from your terminal:

```bash
# Single video extraction
python downloader.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Playlist extraction
python downloader.py "https://www.youtube.com/playlist?list=PL..."
```

---

## REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/config` | Returns system status, detected Audacity binary, and active defaults. |
| `POST` | `/api/inspect` | Inspects a single video or expands a playlist without downloading. |
| `POST` | `/api/download` | Dispatches an asynchronous single video download task. |
| `POST` | `/api/batch-download`| Enqueues a batch of URLs or playlist items into the worker queue. |
| `GET` | `/api/progress/{task_id}`| Checks live progress, percent, speed, ETA, and result filepaths. |
| `GET` | `/api/history` | Fetches SQLite job extraction history. |
| `DELETE` | `/api/history/{id}` | Deletes a record from history. |
| `DELETE` | `/api/history` | Clears all persistent history. |
| `POST` | `/api/open-folder` | Opens downloads directory in OS file manager. |
| `POST` | `/api/open-audacity`| Launches Audacity loaded with the latest or specified audio file. |

---

## Testing & Quality Assurance

Run the automated test suite:
```bash
pytest -v
```

Run code quality linting:
```bash
ruff check .
```

---

## License

Released under the [MIT License](LICENSE).
Copyright (c) 2026 Muhammed Sahil Subair.
