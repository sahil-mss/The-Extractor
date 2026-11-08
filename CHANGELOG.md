# Changelog

All notable changes to **The Extractor** will be documented in this file.

## [2.8.1] - 2026-11-08

### Security & Hardening
- **Indexed History Lookup Optimization**: Replaced O(n) history table scans in `is_known_media_file_in_history` with indexed multi-column SQL queries and added indices for `video_path`, `audio_path`, `doc_md_path`, `doc_txt_path`, and `json_path`. Seeded 50,000-row performance tests verify sub-50ms execution.
- **Strict File Containment in Safe Download Paths**: Restored strict child check (`is_relative_to(root) and real_target != root`) in `is_safe_download_path` so download roots themselves are never treated as deletable media files.
- **Removal of Silent-Exception Ignore Rules**: Removed `S110` and `S112` from Ruff ignore configuration, resolving each instance through narrowed exception handling or structured diagnostic logging (`logger.debug`/`logger.warning`).
- **Independent Comments ThreadPoolExecutor**: Separated `/api/comments` execution into an independent `ThreadPoolExecutor(max_workers=2)` so heavy download queues cannot starve or delay comment retrieval.
- **Direct Loopback Inspection**: Strengthened loopback-only endpoints to check actual peer IP against loopback addresses and verify that no client-supplied proxy headers (`X-Forwarded-For`, `Forwarded`, `X-Real-IP`) are present, preventing bypasses behind local reverse proxies.
- **Directory Trust Lifetime & Revocation**: Added `source` tracking to `known_output_dirs` table; when `allow_any_output_dir` is toggled off, historical unconstrained folders are dynamically de-authorized. For `/api/open-audacity`, exact match against recorded history entries is enforced.
- **Folder Picker Concurrency Lock**: Added non-blocking concurrency guard (`FOLDER_PICKER_LOCK`) to `/api/browse-folder` returning HTTP 409 Conflict if a dialog is already active.
- **Arbitrary Container UID Execution**: Configured `HOME=/tmp`, `DENO_DIR=/tmp/.deno`, and `PIP_CACHE_DIR=/tmp/.pip-cache` in `Dockerfile` to allow execution under custom non-root UIDs.
- **Path Resolution Consistency**: Propagated canonical realpath output directory resolution to incoming request payloads prior to worker enqueue.
- **Bandit Security Rule Enforcement**: Activated Ruff Bandit rules (`S`) with codebase annotations and per-file test exclusions.

### Code Quality, Tooling & Testing
- **Vulnerability Auditing in CI**: Added dedicated `pip-audit` security vulnerability scanning job to GitHub Actions CI workflow and updated pinned dependencies (`certifi>=2026.10.18`, `urllib3>=2.8.0`).
- **Enforced Test Coverage Threshold**: Configured `--cov=. --cov-fail-under=85` in CI test steps; current test coverage sits above 86%.
- **Pre-commit Hooks**: Added `.pre-commit-config.yaml` specifying Ruff lint and formatting hooks.
- **CLI & Launcher Test Suite**: Added dedicated regression test suites `tests/test_main.py` and `tests/test_launcher.py` covering argument parsing, hot reloading, browser dispatch, venv initialization, and fallback logic, elevating overall test suite to 116 passing tests.

## [2.8.0] - 2026-11-07

### Security & Hardening (P0)
- **Auth Throttle Trusted Proxy Hardening**: Added `security.trusted_proxies` config setting. Requests now ignore `X-Forwarded-For` unless the peer is a trusted proxy, and inspect the rightmost untrusted IP address to prevent throttle spoofing and lockout attacks.
- **Strict Output Directory Path Containment**: Added `paths.allowed_output_roots` and `paths.allow_any_output_dir` (restricted strictly to loopback). Custom paths are resolved via `os.path.realpath` and `Path.is_relative_to` to prevent arbitrary filesystem writes. Safe paths are registered in a new `known_output_dirs` SQLite table.
- **Snippet Bounds Validation**: Enforced strict validation and sanitization for snippet start and end timestamps (`ge=0`, `le=86400`, `allow_inf_nan=False`), preventing crashes on missing end bounds or `NoneType` comparisons in `yt-dlp`.
- **Folder Picker Isolation**: Restructured `/api/browse-folder` to execute in an isolated subprocess with a 120-second timeout and strictly restricted access to localhost/loopback.

### Reliability & Performance (P1 & P2)
- **Modern JavaScript Engine Runtime Validation**: Upgraded runtime checking to verify exact version compatibility (Deno >= 2.3.0, Node >= 22.0.0, Bun, QuickJS) and exposed runtime status in `/api/config`. Updated Docker container to install Deno 2.6.
- **yt-dlp Extra Engine Pinning**: Updated auto-updater and upgrade notifications to target `yt-dlp[default]` so `yt-dlp-ejs` is never left stale.
- **Single-Pass Metadata & Comment Extraction**: Consolidated comment fetching into initial video inspection, eliminated duplicate extraction passes, raised 502/504 status codes on comment errors/timeouts, and fixed HTML entity corruption during comment search highlighting.
- **Configurable Chunk Fragment Concurrency**: Added `processing.fragment_threads` (default 4, range 1-16) to avoid triggering upstream YouTube HTTP rate limits.
- **Storage Stats TTL Caching**: Added an in-memory 30-second TTL cache for directory storage calculations to prevent expensive disk traversals on `/api/config` calls.
- **Log Rotation**: Replaced `FileHandler` with `RotatingFileHandler` (5MB limit, 3 backups) to protect disk storage.
- **Launcher Resilience**: Enhanced `launcher.py` with `py -3` prioritization on Windows, extended dependency check timeout to 60s, and added platform troubleshooting advice for missing venv packages.

### Accessibility & Tooling (P2 & P3)
- **Web Accessibility**: Added comprehensive `aria-label` attributes across input controls, `aria-live` polite/assertive regions for spinners, progress monitors, toasts, and alert banners, plus high-contrast `:focus-visible` styles and `@media (prefers-reduced-motion: reduce)`.
- **Code Quality & Linter Expansion**: Added `flake8-bugbear` (`B`), `flake8-simplify` (`SIM`), and `flake8-comprehensions` (`C4`) to Ruff configuration.


### Features & YouTube Compatibility (P0 & P1)
- **JavaScript Runtime & EJS Engine Support (P0)**: Updated dependencies to `yt-dlp[default]>=2024.0.0` ensuring `yt-dlp-ejs` is installed; configured `js_runtimes` in `get_base_ydl_opts` to support Deno, Node.js, Bun, and QuickJS for solving YouTube JavaScript challenges; added Node.js to Docker image; implemented `js_runtime_available()` detection with startup banner alerts, `/api/config` reporting, and web UI alerts.
- **FFmpeg Binary Detection & Health Reporting (P1)**: Implemented `ffmpeg_available() -> bool` checking system `PATH` and platform-specific fallback locations (WinGet, Chocolatey, Scoop, Homebrew); surfaced status via startup banner, `/api/config`, and dashboard alert banner; added unit tests for PATH detection, fallback resolution, and missing states.

### Infrastructure & CI Modernization (P1 & P2)
- **Python Matrix Modernization (P1)**: Raised `requires-python` to `>=3.11` (given Python 3.10 EOL), updated Ruff lint target to `py311`, aligned Dockerfile base image to `python:3.11-slim`, and expanded CI test matrix to test Python 3.11, 3.12, 3.13, and 3.14 across Ubuntu, macOS, and Windows.
- **Dependency Hygiene & Dependabot (P2)**: Relaxed `youtube-transcript-api` to `>=1.2.4,<2.0.0` in `pyproject.toml`; configured `.github/dependabot.yml` for weekly updates across `pip`, `docker`, and `github-actions`; added non-blocking CI job testing `pytest -W error::DeprecationWarning` to surface upstream deprecations early.
- **Comprehensive Documentation Updates (P2)**: Added "Responsible Use" policy, "Hosting Beyond Localhost" deployment guide (with Caddy & Nginx reverse proxy examples and single-worker warnings), and expanded troubleshooting guidelines for cloud/VPS IP bot checks, cookie expiry, and JS runtimes.

### Security & Hardening (P3)
- **API Key Authentication Failure Throttling (P3)**: Added in-memory per-IP failure tracking with lock protection and `X-Forwarded-For` support; throttles requests with HTTP 429 (`Retry-After: 900`) for 15 minutes upon 10 failed `X-API-Key` attempts within a 5-minute sliding window; added unit tests verifying throttling thresholds and IP isolation.

### Security & Hardening
- **URL Validator Parser Bypass Remediation (SEC-01)**: Refactored `downloader.is_valid_youtube_url()` to extract the target hostname strictly via `urllib.parse.urlparse().hostname` (lowercased) rather than parsing `netloc` strings, effectively blocking credential-delimiter bypasses (e.g. `youtube.com:443@127.0.0.1`). Explicitly rejected URLs containing userinfo (`username`/`password`), enforced strict allowlist checks with `host == d or host.endswith("." + d)`, restricted port numbers strictly to `None`, `80`, or `443` with `ValueError` protection, and tightened `downloader.is_playlist_url` from substring checks to exact hostname matching.
- **yt-dlp Extractor Scoping (SEC-01 Defense-in-Depth)**: Configured `'allowed_extractors': ['youtube.*']` across base yt-dlp extraction options (`get_base_ydl_opts`), permanently disabling the generic extractor from fetching non-YouTube URLs or local loopback/metadata services even if invoked directly.

### Reliability & Resilience
- **Cancel-Aware Retry Backoff Sleeps (P3)**: Enhanced exponential retry loops in `downloader.inspect_video` to accept an `is_cancelled` callback and replaced blocking `time.sleep()` calls with a non-blocking 0.5-second polling loop that immediately raises `DownloadCancelled` upon receiving a user cancellation signal.
- **Executor Submission Failure Rollback Verification (P3)**: Added regression test `test_batch_executor_submit_failure_rollback` verifying that partial thread pool submission failures properly cancel already-scheduled futures, set cancellation flags, prevent orphaned ghost tasks in memory, and roll back batch records in the database.

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
