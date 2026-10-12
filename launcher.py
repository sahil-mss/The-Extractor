#!/usr/bin/env python3
"""
The Extractor — One-Click Smart Launcher
=========================================
Features:
- Checks if virtual environment (.venv) exists; automatically creates one if not.
- Inspects requirements.txt against installed packages; installs them automatically on first launch.
- Checks if a JavaScript runtime (Deno/Node/Bun/QuickJS) and FFmpeg are present.
- Launches The Extractor server and opens your web browser.
- Automatically mirrors all execution logs to `extractor.log`.
"""

import os
import shutil
import subprocess
import sys
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, ".venv")
REQ_FILE = os.path.join(PROJECT_DIR, "requirements.txt")
LOG_FILE = os.path.join(PROJECT_DIR, "extractor.log")

BANNER_ART = r"""
  +-----------------------------------------------------------------------+
  |    _____ _            ______      _                  _                |
  |   |_   _| |           | ___ \    | |                | |               |
  |     | | | |__   ___   | |_/ /__ _| |_ _ __ __ _  ___| |_ ___  _ __    |
  |     | | | '_ \ / _ \  |  __/ __| | __| '__/ _` |/ __| __/ _ \| '__|   |
  |     | | | | | |  __/  | |  \__ \ | |_| | | (_| | (__| || (_) | |      |
  |     \_/ |_| |_|\___|  \_|  |___/_|\__|_|  \__,_|\___|\__\___/|_|      |
  |                                                                       |
  |             Video  *  Audio  *  Transcripts  *  Tags                  |
  +-----------------------------------------------------------------------+
"""


def log(msg: str):
    """Prints to console and appends to log file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [LAUNCHER] {msg}"
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def get_venv_python() -> str:
    """Returns the path to Python inside .venv."""
    if sys.platform == "win32":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def check_and_setup_venv() -> str:
    """Ensures .venv exists and has all requirements installed."""
    venv_python = get_venv_python()

    # 1. Create venv if missing
    if not os.path.exists(venv_python):
        log("📦 Virtual environment (.venv) not found. Creating one for you...")
        try:
            subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True, cwd=PROJECT_DIR)
            log("✅ Virtual environment (.venv) created successfully.")
        except Exception as e:
            log(f"⚠️ Could not create virtual environment: {e}. Falling back to system Python.")
            return sys.executable

    # 2. Check if dependencies are installed
    check_code = (
        "import fastapi, uvicorn, pydantic, yt_dlp, youtube_transcript_api, yaml, requests, aiosqlite, httpx; "
        "print('READY')"
    )
    deps_ready = False
    try:
        res = subprocess.run(
            [venv_python, "-c", check_code],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=10,
        )
        if "READY" in res.stdout:
            deps_ready = True
    except Exception:
        deps_ready = False

    if not deps_ready:
        log("📥 Dependencies are missing or incomplete. Automatically installing requirements.txt...")
        log("   (This only happens once on your first run — please wait a moment!)")
        try:
            # Upgrade pip first silently
            subprocess.run(
                [venv_python, "-m", "pip", "install", "--upgrade", "pip", "--disable-pip-version-check"],
                check=False,
                cwd=PROJECT_DIR,
            )
            # Install requirements
            subprocess.run(
                [venv_python, "-m", "pip", "install", "-r", REQ_FILE, "--disable-pip-version-check"],
                check=True,
                cwd=PROJECT_DIR,
            )
            log("🎉 All requirements installed successfully!")
        except Exception as e:
            log(f"❌ Error installing requirements: {e}")
            log("Please check your internet connection or install manually using:")
            log(f"   {venv_python} -m pip install -r requirements.txt")

    return venv_python


def main():
    print(BANNER_ART)
    log("[*] Starting The Extractor Launcher...")
    log(f"[*] Project Directory: {PROJECT_DIR}")
    log(f"[*] Log File:          {LOG_FILE}")

    # Check JS runtime
    js_runtime = (
        shutil.which("deno")
        or shutil.which("node")
        or shutil.which("bun")
        or shutil.which("quickjs")
        or shutil.which("qjs")
    )
    if js_runtime:
        log(f"[+] JavaScript Runtime: Found ({os.path.basename(js_runtime)})")
    else:
        log("[!] Notice: No JavaScript runtime (Node.js/Deno) found on PATH. Some YouTube videos may need it.")

    # Check FFmpeg
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        log("[+] FFmpeg Audio/Video Suite: Found")
    else:
        log("[!] Notice: FFmpeg not detected on system PATH. Install FFmpeg for video merges & audio conversion.")

    # Prepare Python environment
    target_python = check_and_setup_venv()

    log("[*] Launching The Extractor Web Application...")
    log("=" * 75)
    log("  * The web interface will open in your browser automatically.")
    log("  * To stop the app, press Ctrl + C in this window.")
    log("=" * 75)
    print()

    # Pass any extra CLI arguments directly to main.py
    cmd = [target_python, os.path.join(PROJECT_DIR, "main.py")] + sys.argv[1:]
    try:
        subprocess.run(cmd, cwd=PROJECT_DIR)
    except KeyboardInterrupt:
        print()
        log("👋 The Extractor stopped by user. Goodbye!")
    except Exception as e:
        log(f"❌ Execution error: {e}")


if __name__ == "__main__":
    main()
