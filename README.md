# The Extractor 🎬🎙️📝

> **A modern, cross-platform media downloader, batch & playlist processor, tag inspector, timestamped transcript generator, and Audacity audio studio.**

[![CI](https://github.com/sahil-mss/The-Extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/sahil-mss/The-Extractor/actions/workflows/ci.yml)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](docker-compose.yml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blueviolet)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 💡 What is this in simple words? (1-Minute Explanation)

Imagine you found a great YouTube video or playlist, and you want:
- 🎬 The **video file** to watch offline.
- 🎵 Just the **audio file** (MP3 or WAV) to listen to or edit in music software like Audacity.
- 📝 The **exact words spoken (transcript)** with clean timestamps so you can read along, take notes, or create summaries.
- 🏷️ The **hidden tags and keywords** the creator used to rank the video.

**The Extractor** does all of this for you automatically from a clean, beautiful web screen right on your computer. You simply paste a YouTube link, click a button, and it saves everything into your folder.

---

## 🏃 Quick Start (3 Steps for Anyone)

### Step 1: Open your terminal or command prompt
- **Windows**: Press `Win + R`, type `cmd`, and press Enter.
- **Mac**: Press `Cmd + Space`, type `Terminal`, and press Enter.
- **Linux**: Open your regular terminal window.

### Step 2: Install and start
Run these two commands:
```bash
pip install -r requirements.txt
python main.py
```

### Step 3: Use it in your browser!
Your web browser will automatically open to:
👉 **`http://localhost:8000`**

Paste any YouTube link into the box, click **Inspect & Extract**, and you're done!

---

## 📑 Table of Contents
- [What is this?](#-what-is-this-in-simple-words-1-minute-explanation)
- [Quick 3-Step Start](#-quick-start-3-steps-for-anyone)
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
- [YouTube Needs a JavaScript Runtime](#youtube-needs-a-javascript-runtime)
- [Responsible Use](#responsible-use)
- [Hosting Beyond Localhost](#hosting-beyond-localhost)
- [CLI / Standalone Mode](#cli--standalone-mode)
- [REST API Reference](#rest-api-reference)
- [Troubleshooting & FAQs](#troubleshooting--faqs)
- [Testing & Quality Assurance](#testing--quality-assurance)

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
Access the dashboard at `http://localhost:8000`. All downloaded files persist in `./downloads` and database records persist in `./data`.

> [!NOTE]
> **Linux Host Permissions:** The compose service runs with `user: "${UID:-1000}:${GID:-1000}"`. In bash, `$UID` is a shell variable rather than an exported environment variable. Before starting, export your UID/GID into a `.env` file and create the directories owned by your current user:
> ```bash
> echo "UID=$(id -u)" >> .env && echo "GID=$(id -g)" >> .env
> mkdir -p downloads data && sudo chown -R "$(id -u):$(id -g)" downloads data
> ```

> [!TIP]
> **Keeping yt-dlp Updated in Docker:**
> YouTube extractors evolve frequently. You can:
> - Enable automated startup upgrades by setting `EXTRACTOR_AUTO_UPDATE_YTDLP=1` in your environment or `docker-compose.yml`.
> - Or manually rebuild the container image without cache:
>   ```bash
>   docker compose build --pull --no-cache
>   docker compose up -d
>   ```

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

### 🎥 1. How to Download a Single Video (Step-by-Step)
1. **Paste URL**: Copy the link of any YouTube video or YouTube Short from your browser and paste it into the search box.
2. **Inspect**: Click the blue **Inspect & Extract** button (or press Enter on your keyboard).
3. **Choose Options**:
   - 📺 **Video Quality**: Pick `Best (HD/4K)` or a specific resolution like `1080p` or `720p`.
   - 🎧 **Audio Quality**: Pick your audio format, such as `MP3 (320k - Best Quality)` or `WAV (Lossless)`.
   - 📦 **Checkboxes**: Leave **Video**, **Audio**, or **Metadata** checked depending on what you want to save.
4. **Download**: Click **Start Extraction & Download**.
5. **Watch Progress**: You will see a live progress bar showing percentage, download speed, and estimated time remaining. When finished, your files will be safely stored in your `downloads/` folder!

---

### 📚 2. How to Download a Playlist or Multiple Links at Once
1. Click the **Batch & Playlists** tab at the top.
2. Paste multiple video links (one link per line) OR paste a single YouTube playlist link (e.g., `https://www.youtube.com/playlist?list=...`).
3. Click **Queue Batch Download**.
4. The system will automatically download every video one-by-one in the background without slowing down your computer.

---

### 🎨 3. What Format Should I Pick?
- **For watching videos**: Choose `Best Available (HD/4K)` or `1080p Full HD`.
- **For listening to music or podcasts on your phone/car**: Choose `MP3 (320 kbps - Studio)`.
- **For music editing or recording software (Audacity, FL Studio, Premiere)**: Choose `WAV (Lossless PCM)`.
- **For reading transcripts or notes**: Check the `Document & Transcript` box to get a `.md` and `.txt` file containing all spoken words and timestamps!

---

### 📜 4. Job History
- Click the **📜 History** button in the top right corner anytime.
- You can view everything you have previously downloaded, see file locations on your hard drive, or remove past records.

---

### 🎛️ 5. Audacity & Folder Shortcuts
- **Open Downloads Folder**: Opens your computer's folder directly to show you your saved files.
- **Edit in Audacity**: If you have Audacity installed, clicking this button automatically launches Audacity with your downloaded audio file loaded into the editor!

---

## Configuration Reference (`config.yaml`)

You can create a `config.yaml` file in the root directory (copy from `config.yaml.example`):

```yaml
app:
  host: "127.0.0.1"          # Set to "0.0.0.0" for Docker or LAN hosting
  port: 8000
  api_key: ""                 # Set a secret key to secure your API
  cors_origins:
    - "http://127.0.0.1:8000"
    - "http://localhost:8000"

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

### Home Directory & Path Resolution (`EXTRACTOR_HOME`)
The application determines its root working directory (`EXTRACTOR_HOME`) using the following resolution order:
1. **Explicit Environment Variable**: `EXTRACTOR_HOME` if set in the environment.
2. **Current Working Directory**: If `config.yaml` or `config.yaml.example` exists in the current directory (`os.getcwd()`).
3. **User Home Directory**: Defaults to `~/.the_extractor` when started from other directories without local configuration files.

The active download folder, database, and configuration paths are resolved from `EXTRACTOR_HOME` and displayed at startup.

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

## YouTube Needs a JavaScript Runtime

Modern YouTube video extraction frequently relies on executing JavaScript challenges to verify client identity and resolve stream playback URLs. 

The Extractor bundles `yt-dlp[default]`, which includes `yt-dlp-ejs`. To execute challenge solving scripts, **at least one supported JavaScript runtime must be installed on your system PATH**:

- **Deno** (Recommended by yt-dlp): `curl -fsSL https://deno.land/install.sh | sh` or `winget install DenoLand.Deno`
- **Node.js**: `apt install nodejs`, `brew install node`, or `winget install OpenJS.NodeJS`
- **Bun**: `curl -fsSL https://bun.sh/install | bash` or `winget install Oven-sh.Bun`
- **QuickJS**: `quickjs` or `qjs` binary

The Extractor automatically detects installed runtimes and passes them to yt-dlp. You can inspect whether a JS runtime is detected in the startup terminal banner, `/api/config`, or the web dashboard. In Docker, Node.js is automatically pre-installed.

---

## Responsible Use

The Extractor is designed and intended strictly for **personal, research, educational, and authorized media workflows**. When using this software:
- **Respect Copyright & Ownership**: Only download media that you own, have explicit permission to access, or that is made available under permissive licenses (such as Creative Commons) or fair dealing/fair use provisions applicable in your jurisdiction.
- **Platform Terms of Service**: You are responsible for ensuring that your usage complies with YouTube's Terms of Service and any other applicable platform agreements.
- **No Warranty**: The software is provided "as is" under the MIT License, without warranty of any kind, express or implied. The authors and maintainers assume no liability for misuse, copyright infringement, account bans, or data loss resulting from the use of this tool.

---

## Hosting Beyond Localhost

If you plan to expose The Extractor to your local area network (LAN), virtual private network (VPN), or a public server / VPS, follow these production deployment guidelines:

### 1. Always Run Behind a TLS Reverse Proxy
Do not expose the raw Uvicorn server directly to the public internet on HTTP. Terminate TLS using a reverse proxy such as **Caddy** or **Nginx**.

#### Example Caddy Configuration (`Caddyfile`)
```caddy
media.yourdomain.com {
    reverse_proxy 127.0.0.1:8000
}
```

#### Example Nginx Configuration (`/etc/nginx/sites-available/extractor`)
```nginx
server {
    listen 80;
    server_name media.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name media.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/media.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/media.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. Always Configure an API Key
When hosting beyond `localhost` / `127.0.0.1`, The Extractor requires authentication to protect your disk storage and server resources:
```bash
export EXTRACTOR_API_KEY="your-strong-random-api-key-here"
```
Or in `config.yaml`:
```yaml
app:
  api_key: "your-strong-random-api-key-here"
```
Clients must provide this key via the `X-API-Key` HTTP header.

### 3. Run a Single Process (Do Not Use `--workers N`)
**Important**: Task queues, live download progress polling, active cancellations, and rate limiters maintain synchronized in-memory state. **Do not run Uvicorn with multiple workers (`--workers N`)**, as requests routed across distinct processes will not share task state. Use the default single worker architecture:
```bash
extractor --host 0.0.0.0 --port 8000
```

---

## Troubleshooting & yt-dlp Breakage Runbook

### 1. Bot Checks & Cloud / VPS IP Blocks
Data center and cloud provider IP blocks (AWS, GCP, DigitalOcean, Hetzner, etc.) are heavily throttled or completely blocked by YouTube's anti-bot protections (`Sign in to confirm you're not a bot` or HTTP 429).
- **Solution**: Export valid browser cookies into `cookies.txt` (see [Cookies & Age-Restricted Videos](#cookies--age-restricted-videos)) from an active, non-datacenter residential session.
- Run The Extractor on a residential network or route traffic through a residential proxy or VPN if hosting on a VPS.

### 2. Cookie Expiry & Stale Sessions
If previously functioning downloads begin failing with authentication or sign-in prompts:
- YouTube session cookies expire periodically or are invalidated upon logging out of your browser.
- Refresh your `cookies.txt` file by re-exporting it from your active browser session and replacing the file on the server.

### 3. JavaScript Runtime Missing or Broken
- YouTube challenge solving requires `yt-dlp-ejs` and a working JavaScript runtime.
- If extractions fail with "video not available" or challenge execution errors, ensure `deno`, `node`, `bun`, or `quickjs` is installed and reachable on your `PATH`.
- Check `/api/config` or the dashboard notification banner to verify that `js_runtime_available: true`.

### 4. "Video not available" or Extraction Failures
If you encounter errors stating that a video is unavailable, sign-in is required, or extraction failed on a valid public video:
1. **Missing JavaScript Runtime**: Check if a JavaScript engine (Deno or Node.js) is installed. Without a JS runtime, modern YouTube challenges fail and report the video as unavailable. Check the banner in the dashboard or terminal startup log.
2. **Outdated yt-dlp**: YouTube regularly adjusts player mechanisms. Update yt-dlp via:
   ```bash
   pip install -U "yt-dlp[default]"
   ```
3. **Bot Detection or Geo-blocking**: Use `cookies.txt` to authenticate requests from your browser session.

### 5. Downloads suddenly failing?
YouTube frequently changes its internal player APIs, which can temporarily break video or audio extraction.
If downloads suddenly start failing with extraction errors, upgrade `yt-dlp` to the latest release:

```bash
pip install -U "yt-dlp[default]"
```

The Extractor also automatically checks PyPI every hour to notify you in the settings/status panel whenever your installed `yt-dlp` version becomes outdated.

A weekly automated healthcheck workflow in CI also continuously monitors extraction against public test videos to catch upstream breakages early.

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
