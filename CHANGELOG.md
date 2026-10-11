# Changelog

All notable changes to **The Extractor** will be documented in this file.

## [2.6.0] - 2026-10-11

### Security & Hardening
- **Strict YouTube URL Validation & SSRF Prevention (SEC-01)**: Implemented `is_valid_youtube_url()` shared validator enforcing strict YouTube domain allowlists (`youtube.com`, `youtu.be`, etc.), blocking IP literals (IPv4/IPv6 private ranges and metadata endpoints), localhost/loopback destinations, and non-YouTube domains across all inspection, download, batch, and playlist expansion endpoints.
- **Production Security Mode & API Key Strength (SEC-02)**: Added `EXTRACTOR_ENV=production` configuration mode that requires an API key for all host bindings and mandates a minimum key strength (16+ characters).
- **Universal Non-Loopback API Key Enforcement**: Restricted unauthenticated access strictly to loopback interfaces (`127.0.0.1`, `localhost`, `::1`). Any binding to external or LAN interfaces (e.g. `192.168.x.x` or `0.0.0.0`) strictly requires `EXTRACTOR_API_KEY`.
- **Timing Attack & Non-ASCII Safe Auth**: Normalized `X-API-Key` comparison using UTF-8 encoded bytes in `hmac.compare_digest` to eliminate 500 crashes on non-ASCII credentials.
- **Security Headers Middleware**: Enforced `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: no-referrer` on all HTTP responses.
- **Docker Hardening & Host Permissions**: Configured container `user: "${UID:-1000}:${GID:-1000}"` in `docker-compose.yml` to prevent `PermissionError` on Linux host bind mounts (`./downloads`, `./data`), created non-root `appuser` (UID 1000), added container healthcheck probing `/healthz`, defaulted port publication to loopback (`127.0.0.1:8000:8000`), and enforced API key validation.

### Reliability & Resilience
- **Strict Format Option Allowlists & Input Constraints (BUG-04)**: Constrained `video_resolution` (`best`, `1080p`, `720p`, `480p`), `audio_format` (`mp3`, `wav`, `m4a`), and `audio_bitrate` (`128`, `192`, `320`) via Pydantic model validators; mandated at least one enabled output format (video, audio, or document); bounded history pagination parameters (`limit`, `page_size`, `page`).
- **Atomic Batch Task Persistence & DB Rollback (BUG-03)**: Added `record_batch_tasks_created` for transactional batch creation in SQLite and `rollback_batch_tasks` to ensure database records and in-memory entries are completely reconciled if any batch insertion fails.
- **Frontend Terminal States & Cancellation Status Checks (BUG-02, DOC-01)**: Updated `app.js` progress poller to handle `cancelled` and `interrupted` states, halting interval timers, re-enabling controls, and displaying actionable feedback; checked `res.ok` before updating local UI states on cancellation; synchronized version labels across UI header and badge to `v2.6.0`.
- **Database Persistence Retry & Logging on Success**: Wrapped completion database writes in `run_download_task` with an automated retry and `logger.error("Failed to persist completed task", exc_info=True)` to ensure persistence failures do not leave rows stuck in `queued` without diagnostic visibility.

- **Auto-Update Timeout & Non-Interactive Safety**: Added a 120-second timeout, `subprocess.TimeoutExpired` handling, and `--no-input --disable-pip-version-check` flags to `auto_update_ytdlp_if_enabled` in `main.py` to prevent startup hangs.
- **Real-Time Task Cancellation & Worker Halting on Timeout**: Ensured watchdog task timeouts add the timed-out task ID directly to `CANCELLED_TASKS`, interrupting the running download worker. Guarded completion and error status writes in `run_download_task` so worker completion cannot flip a timed-out `error` state back to `completed`.
- **Watchdog Error Visibility**: Elevated task cleanup watchdog exceptions from `debug` to `logger.warning("task cleanup failed", exc_info=True)` to make background worker issues immediately visible.
- **Suffixed Version Parsing**: Corrected `_parse_ver` in `downloader.py` to match leading digits (`re.match(r"\d+", p)`), ensuring release tags like `2026.8.19rc1` rank properly without mangling segment numbers.
- **Queue Slot Leak Prevention**: Wrapped task creation and background execution submission in atomic rollback blocks under `TASKS_LOCK`. Enqueue failures pop tasks immediately to avoid starvation.
- **Atomic Batch Task Enqueue**: Allocated batch queue slots atomically under lock before starting database and executor operations with automated rollback on failure.
- **Network & Task Timeout Protection**: Added a 30s socket timeout to all yt-dlp operations and a 60-minute task timeout worker to automatically clear hung tasks.
- **Safe Storage Cleanup**: Restricted file pruning to media formats (`.mp4`, `.mp3`, `.wav`, `.m4a`, `.md`, `.txt`), protected active downloads (`*.part`, `*.ytdl`, `.gitkeep`) and files modified within 10 minutes, and automatically nulled deleted file paths in `extraction_history`.
- **Fast Fail on Permanent Media Errors**: Distinguished permanent errors (private, deleted, age-restricted) from transient network errors (403, 429) to fail fast without wasting retries.
- **Orphaned Task Recovery on Startup**: Automatically marked leftover `queued` and `running` tasks as `interrupted` upon database initialization.
- **Graceful Lifespan Shutdown**: Integrated FastAPI lifespan shutdown to cleanly terminate background executor workers on exit.

### Usability & Performance
- **Container yt-dlp Auto-Upgrade**: Added opt-in `EXTRACTOR_AUTO_UPDATE_YTDLP=1` support to automatically upgrade `yt-dlp` at container launch before starting the server.
- **Docker Compose UID/GID Export Guide**: Documented exporting `UID=$(id -u)` and `GID=$(id -g)` to `.env` to prevent permission issues on host bind mounts when `$UID` is unexported in shells.
- **Documented Home Directory Resolution Order**: Clarified working directory rules in documentation (`EXTRACTOR_HOME` -> current working directory if `config.yaml` / `config.yaml.example` is present -> `~/.the_extractor`).
- **Environment-Aware Path Resolution**: Resolved configuration and default directories relative to `EXTRACTOR_HOME` or user directory instead of current working directory, printing resolved paths at startup.
- **1-Hour PyPI Cache**: Added thread-safe in-memory caching for `check_ytdlp_version` to keep `/api/config` non-blocking.
- **Lock Contention Reduction**: Moved database I/O outside `TASKS_LOCK` during task cancellation.
- **Accurate Cancellation Statuses**: Returned accurate status reports when attempting to cancel finished or failed tasks.
- **Playlist Expansion Error Visibility**: Logged expansion errors and surfaced skipped items in batch responses and UI toasts.
- **Accurate Playlist Detection**: Switched `is_playlist_url` to `urllib.parse.parse_qs` to prevent false positives on query parameters like `blacklist=1`.
- **yt-dlp Maintenance Runbook & CI Healthcheck**: Documented `pip install -U yt-dlp` runbook and added weekly scheduled CI extraction healthchecks.

---

## [2.5.0] - 2026-09-06

### Added
- **Self-Hosted CLI & Packaging**: Packaged as an installable Python module with CLI commands `extractor` and `the-extractor`, plus standalone `python main.py`.
- **CLI Options**: Added `--host`, `--port`, `--no-browser`, and `--reload` options.
- **Batch & Playlist Support**: Automatic YouTube playlist expansion (`expand_playlist_urls`) and batch URL queueing via `/api/batch-download`.
- **Persistent SQLite Job History**: Embedded SQLite database (`extractor.db`) with indices tracking job history, metadata, and downloaded file paths.
- **Dynamic Configuration**: YAML-based configuration (`config.yaml` / `config.yaml.example`) and environment variable overrides (`EXTRACTOR_*`).
- **Format Flexibility**: User-selectable video resolutions (Best/4K, 1080p, 720p, 480p) and audio codecs/bitrates (MP3 320k/192k/128k, WAV, M4A).
- **Cross-Platform System Integration**: Dynamic Audacity detection across Windows, macOS, and Linux; universal folder opening using platform-specific subprocess calls.
- **Containerization**: Added production `Dockerfile` and `docker-compose.yml`.
- **CI & Quality Assurance**: GitHub Actions multi-OS test matrix (`ubuntu`, `macos`, `windows`) and `ruff` linting workflow.
- **License**: Added official MIT License.

### Changed
- Refactored database operations with connection context managers for atomic transactions and zero resource leaks.
- Replaced third-party GitHub Actions FFmpeg runner with native OS package managers (`apt`, `brew`, `choco`).
- Separated development dependencies (`requirements-dev.txt`) from runtime dependencies (`requirements.txt`).
- Modernized packaging with `pyproject.toml`.

### Removed
- Deprecated Windows-only `run.bat` and shell `run.sh` in favor of standard CLI entrypoints and direct Python execution.

---

## [2.0.0] - 2026-09-05

### Added
- Initial FastAPI backend and Golden Ratio web dashboard.
- Real-time video metadata, tag inspection, and transcript extraction.
- High-definition MP4 merging and MP3 audio transcoding.
- Live progress polling.
