# Changelog

All notable changes to **The Extractor** will be documented in this file.

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
