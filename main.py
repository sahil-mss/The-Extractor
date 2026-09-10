import argparse
import threading
import time
import webbrowser

import uvicorn

from config import config


def open_browser_delayed(url: str, delay: float = 1.2):
    """Open default browser after server initialization."""
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(
        prog="extractor",
        description="The Extractor — Self-hosted Media Studio, Batch Downloader & Transcript Suite"
    )
    parser.add_argument("--host", type=str, default=config.app.host, help=f"Host address to bind (default: {config.app.host})")
    parser.add_argument("--port", type=int, default=config.app.port, help=f"Port to bind (default: {config.app.port})")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch the web browser")
    parser.add_argument("--reload", action="store_true", help="Enable hot reload for development")

    args = parser.parse_args()

    host = args.host
    port = args.port
    server_url = f"http://{host}:{port}"
    if host in ("0.0.0.0", "::"):
        browser_url = f"http://localhost:{port}"
    else:
        browser_url = server_url

    print("=" * 70)
    print("  🚀 The Extractor — Self-Hosted Media Studio")
    print(f"  Dashboard: {browser_url}")
    print(f"  REST API:  {browser_url}/docs")
    print(f"  Storage:   {config.absolute_download_dir}")

    # Check disk usage and run retention policy if configured
    try:
        from downloader import check_ytdlp_version, get_storage_stats, perform_storage_cleanup
        cleanup_res = perform_storage_cleanup()
        if cleanup_res.get("deleted_files", 0) > 0:
            print(f"  🧹 Retention: Cleaned {cleanup_res['deleted_files']} old file(s) ({cleanup_res['freed_mb']} MB freed)")

        stats = get_storage_stats()
        print(f"  💾 Disk:    Downloads: {stats['total_mb']} MB ({stats['file_count']} files) | Drive Free: {stats['disk_free_gb']} GB")

        # Check yt-dlp staleness
        ytdlp_status = check_ytdlp_version()
        if ytdlp_status.get("is_outdated"):
            print(f"  ⚠️  NOTICE: yt-dlp is outdated ({ytdlp_status['installed']} -> {ytdlp_status['latest']}). Run: pip install --upgrade yt-dlp")
        elif ytdlp_status.get("checked"):
            print(f"  ✅ yt-dlp:  Up to date ({ytdlp_status['installed']})")
    except Exception:
        pass

    if host in ("0.0.0.0", "::") and not config.app.api_key:
        print("  ⚠️  WARNING: Running on all interfaces with no API key set!")
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
