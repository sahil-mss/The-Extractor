import argparse
import contextlib
import os
import subprocess
import sys
import threading
import time
import webbrowser

import uvicorn

import database
from config import config, validate_startup_security


def auto_update_ytdlp_if_enabled():
    """If EXTRACTOR_AUTO_UPDATE_YTDLP=1, update yt-dlp before server starts."""
    if os.environ.get("EXTRACTOR_AUTO_UPDATE_YTDLP") in ("1", "true", "True"):
        print("  🔄 Checking/updating yt-dlp (EXTRACTOR_AUTO_UPDATE_YTDLP enabled)...")
        try:
            cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--user",
                "-U",
                "--disable-pip-version-check",
                "--no-input",
                "yt-dlp",
            ]
            subprocess.run(cmd, check=True, timeout=120)
            print("  ✅ yt-dlp updated successfully.")
        except subprocess.TimeoutExpired:
            print("  ⚠️ Warning: yt-dlp update timed out after 120 seconds", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠️ Warning: Failed to update yt-dlp: {e}", file=sys.stderr)


def open_browser_delayed(url: str, delay: float = 1.2):
    """Open default browser after server initialization."""
    time.sleep(delay)
    with contextlib.suppress(Exception):
        webbrowser.open(url)

def main():
    parser = argparse.ArgumentParser(
        prog="extractor",
        description="The Extractor — Self-hosted Media Studio, Batch Downloader & Transcript Suite"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=config.app.host,
        help=f"Host address to bind (default: {config.app.host})"
    )
    parser.add_argument("--port", type=int, default=config.app.port, help=f"Port to bind (default: {config.app.port})")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch the web browser")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload for development")

    args = parser.parse_args()

    host = args.host
    port = args.port
    server_url = f"http://{host}:{port}"
    browser_url = f"http://localhost:{port}" if host in ("0.0.0.0", "::") else server_url

    print("=" * 70)
    print("  🚀 The Extractor — Self-Hosted Media Studio")
    print(f"  Dashboard: {browser_url}")
    print(f"  REST API:  {browser_url}/docs")
    print(f"  Config:    {config.paths.download_dir}")
    print(f"  Downloads: {config.absolute_download_dir}")
    print(f"  Database:  {config.database_path}")
    print(f"  Log File:  {config.absolute_log_file}")

    # Check opt-in yt-dlp auto-update
    auto_update_ytdlp_if_enabled()

    # Enforce startup security
    try:
        config.app.host = host
        config.app.port = port
        validate_startup_security(config)
    except RuntimeError as sec_err:
        print(f"\n❌ ERROR: {sec_err}\n", file=sys.stderr)
        sys.exit(1)

    # Run database history retention policy
    try:
        ret_res = database.apply_history_retention()
        if ret_res.get("deleted_records", 0) > 0:
            print(f"  📜 History Retention: Pruned {ret_res['deleted_records']} old record(s)")
    except Exception:
        pass

    # Check disk usage and run retention policy if configured
    try:
        from downloader import check_ytdlp_version, get_storage_stats, perform_storage_cleanup
        cleanup_res = perform_storage_cleanup()
        if cleanup_res.get("deleted_files", 0) > 0:
            deleted_count = cleanup_res['deleted_files']
            freed_mb = cleanup_res['freed_mb']
            print(f"  🧹 Retention: Cleaned {deleted_count} old file(s) ({freed_mb} MB freed)")

        stats = get_storage_stats()
        print(
            f"  💾 Disk:    Downloads: {stats['total_mb']} MB ({stats['file_count']} files) | "
            f"Drive Free: {stats['disk_free_gb']} GB"
        )

        # Check external runtimes (FFmpeg and JS engine)
        from downloader import ffmpeg_available, js_runtime_available
        if not ffmpeg_available():
            print("  ⚠️  WARNING: FFmpeg was not found. Audio extraction and format conversions may fail!")
        if not js_runtime_available():
            print("  ⚠️  WARNING: No JavaScript runtime detected (Deno/Node/Bun/QuickJS). YouTube extractions may fail!")

        # Check yt-dlp staleness
        ytdlp_status = check_ytdlp_version()
        if ytdlp_status.get("is_outdated"):
            inst_v = ytdlp_status['installed']
            latest_v = ytdlp_status['latest']
            print(f"  ⚠️  NOTICE: yt-dlp is outdated ({inst_v} -> {latest_v}). Run: pip install --upgrade yt-dlp")
        elif ytdlp_status.get("checked"):
            print(f"  ✅ yt-dlp:  Up to date ({ytdlp_status['installed']})")
    except Exception:
        pass

    print("=" * 70)


    if not args.no_browser:
        t = threading.Thread(target=open_browser_delayed, args=(browser_url,), daemon=True)
        t.start()

    # Launch production-grade ASGI server
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level="info",
    )

if __name__ == "__main__":
    main()
