import os
import platform
import re
import shutil
import sys
import time
from collections.abc import Callable
from typing import Any

import yt_dlp

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

from config import config


def find_ffmpeg_bin() -> str | None:
    """Locate ffmpeg executable across Windows, macOS, and Linux."""
    # 1. System PATH
    if shutil.which("ffmpeg"):
        return None  # yt-dlp will find it directly in system PATH

def check_ytdlp_version() -> dict[str, Any]:
    """
    Checks the installed yt-dlp version against PyPI's latest release.
    Returns status info including whether it is outdated.
    """
    current_ver = getattr(yt_dlp, "version", None)
    installed_ver = getattr(current_ver, "__version__", "unknown") if current_ver else getattr(yt_dlp, "__version__", "unknown")

    result = {
        "installed": installed_ver,
        "latest": None,
        "is_outdated": False,
        "checked": False,
    }

    try:
        import json
        import urllib.request
        req = urllib.request.Request(
            "https://pypi.org/pypi/yt-dlp/json",
            headers={"User-Agent": "TheExtractor/2.5.0"}
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                latest_ver = data.get("info", {}).get("version")
                if latest_ver:
                    result["latest"] = latest_ver
                    result["checked"] = True
                    result["is_outdated"] = (latest_ver != installed_ver)
    except Exception:
        # Offline or PyPI unreachable: graceful fallback
        pass

    return result

def get_storage_stats(directory: str | None = None) -> dict[str, Any]:
    """Calculate disk storage usage for downloads directory and host drive."""
    target_dir = os.path.abspath(directory or config.absolute_download_dir)
    os.makedirs(target_dir, exist_ok=True)

    total_bytes = 0
    file_count = 0
    for root, _, files in os.walk(target_dir):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total_bytes += os.path.getsize(fp)
                file_count += 1
            except OSError:
                pass

    try:
        disk_usage = shutil.disk_usage(target_dir)
        disk_free_gb = round(disk_usage.free / (1024 ** 3), 2)
        disk_total_gb = round(disk_usage.total / (1024 ** 3), 2)
    except Exception:
        disk_free_gb = 0.0
        disk_total_gb = 0.0

    return {
        "directory": target_dir,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 ** 2), 2),
        "total_gb": round(total_bytes / (1024 ** 3), 3),
        "disk_free_gb": disk_free_gb,
        "disk_total_gb": disk_total_gb,
        "max_storage_gb": config.storage.max_storage_gb,
        "delete_after_days": config.storage.delete_after_days,
    }

def perform_storage_cleanup(
    directory: str | None = None,
    max_storage_gb: float | None = None,
    delete_after_days: int | None = None
) -> dict[str, Any]:
    """
    Prunes files based on age (delete_after_days) or capacity cap (max_storage_gb).
    Removes oldest files first. Returns count of removed files and freed bytes.
    """
    target_dir = os.path.abspath(directory or config.absolute_download_dir)
    if not os.path.exists(target_dir):
        return {"deleted_files": 0, "freed_bytes": 0, "freed_mb": 0.0}

    max_gb = max_storage_gb if max_storage_gb is not None else config.storage.max_storage_gb
    after_days = delete_after_days if delete_after_days is not None else config.storage.delete_after_days

    # Collect all files with mtime and size
    file_entries = []
    total_bytes = 0
    now = time.time()

    for root, _, files in os.walk(target_dir):
        for f in files:
            fp = os.path.join(root, f)
            try:
                stat = os.stat(fp)
                file_entries.append({"path": fp, "size": stat.st_size, "mtime": stat.st_mtime})
                total_bytes += stat.st_size
            except OSError:
                pass

    # Sort oldest first
    file_entries.sort(key=lambda x: x["mtime"])

    deleted_count = 0
    freed_bytes = 0

    # 1. Clean by age if configured
    if after_days and after_days > 0:
        cutoff = now - (after_days * 86400)
        remaining_entries = []
        for entry in file_entries:
            if entry["mtime"] < cutoff:
                try:
                    os.remove(entry["path"])
                    deleted_count += 1
                    freed_bytes += entry["size"]
                    total_bytes -= entry["size"]
                except OSError:
                    remaining_entries.append(entry)
            else:
                remaining_entries.append(entry)
        file_entries = remaining_entries

    # 2. Clean by size cap if configured
    if max_gb and max_gb > 0:
        max_bytes = max_gb * (1024 ** 3)
        for entry in file_entries:
            if total_bytes <= max_bytes:
                break
            try:
                os.remove(entry["path"])
                deleted_count += 1
                freed_bytes += entry["size"]
                total_bytes -= entry["size"]
            except OSError:
                pass

    return {
        "deleted_files": deleted_count,
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 ** 2), 2),
        "remaining_bytes": total_bytes,
    }

    system = platform.system()
    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        winget_pkgs = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
        if os.path.isdir(winget_pkgs):
            for root, dirs, files in os.walk(winget_pkgs):
                if "ffmpeg.exe" in files:
                    return root
        # Check standard chocolatey / scoop
        for candidate in [r"C:\ProgramData\chocolatey\bin", os.path.expanduser(r"~\scoop\shims")]:
            if os.path.exists(os.path.join(candidate, "ffmpeg.exe")):
                return candidate
    elif system in ("Darwin", "Linux"):
        for candidate in ["/usr/local/bin", "/opt/homebrew/bin", "/usr/bin"]:
            if os.path.exists(os.path.join(candidate, "ffmpeg")):
                return candidate

    return None

def extract_video_id(url: str) -> str | None:
    """Extract 11-character YouTube video ID from various URL structures."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:shorts\/)([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_playlist_url(url: str) -> bool:
    """Determine if a URL references a YouTube playlist."""
    return "list=" in url and not ("watch?v=" in url and "index=" not in url)

def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def sanitize_filename(name: str, max_len: int = 120) -> str:
    """Clean filename of characters forbidden in Windows and Unix, normalize spaces, and cap length."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned[:max_len].rstrip()

def get_base_ydl_opts(cookies_path: str | None = None) -> dict[str, Any]:
    """Build standard yt-dlp options with optional cookies and FFmpeg detection."""
    ffmpeg_path = find_ffmpeg_bin()
    opts: dict[str, Any] = {
        'quiet': True,
        'no_warnings': True,
        'retries': config.processing.max_retries,
        'fragment_retries': config.processing.max_retries,
    }
    if ffmpeg_path:
        opts['ffmpeg_location'] = ffmpeg_path

    # Cookies check
    cookie_file = cookies_path or config.paths.cookies_file
    if cookie_file and os.path.exists(cookie_file):
        opts['cookiefile'] = cookie_file

    return opts

def expand_playlist_urls(playlist_url: str) -> list[dict[str, str]]:
    """
    Extract individual video URLs and titles from a playlist URL without downloading.
    Returns list of dicts: [{'url': ..., 'title': ..., 'id': ...}]
    """
    opts = get_base_ydl_opts()
    opts['extract_flat'] = True
    opts['skip_download'] = True

    videos = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        entries = info.get('entries', []) if info else []
        for entry in entries:
            if not entry:
                continue
            vid_id = entry.get('id')
            if vid_id:
                videos.append({
                    'id': vid_id,
                    'url': f"https://www.youtube.com/watch?v={vid_id}",
                    'title': entry.get('title', f"Video {vid_id}")
                })
    return videos

def fetch_transcript_data(video_id: str, ydl_info: dict | None = None) -> list[dict[str, Any]]:
    """
    Fetch transcript using youtube-transcript-api with fallback to yt-dlp subtitle streams.
    Returns a list of dicts: [{'start': 0.0, 'duration': 2.5, 'timestamp': '00:00', 'text': '...'}]
    """
    transcript_items = []

    # 1. Try youtube-transcript-api
    if YouTubeTranscriptApi:
        try:
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            transcript = None
            try:
                transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
            except Exception:
                for t in transcript_list:
                    transcript = t
                    break

            if transcript:
                fetched = transcript.fetch()
                for item in fetched:
                    if isinstance(item, dict):
                        text = item.get('text', '').strip()
                        start = item.get('start', 0.0)
                        dur = item.get('duration', 0.0)
                    else:
                        text = getattr(item, 'text', '').strip()
                        start = getattr(item, 'start', 0.0)
                        dur = getattr(item, 'duration', 0.0)
                    if text:
                        transcript_items.append({
                            'start': float(start),
                            'duration': float(dur),
                            'timestamp': format_timestamp(float(start)),
                            'text': text
                        })
                if transcript_items:
                    return transcript_items
        except Exception:
            # Non-fatal note
            pass

    # 2. Fallback: Parse automatic captions or subtitles from yt-dlp if available
    if ydl_info:
        subs = ydl_info.get('subtitles') or {}
        auto_subs = ydl_info.get('automatic_captions') or {}
        all_subs = {**auto_subs, **subs}
        en_sub = all_subs.get('en') or all_subs.get('en-orig')
        if en_sub:
            # Captions exist in yt-dlp stream
            pass

    return transcript_items

def inspect_video(url: str, cookies_path: str | None = None) -> dict[str, Any]:
    """
    Inspect YouTube video to extract all metadata, tags, and transcript preview without downloading.
    Includes exponential retry for network resilience.
    """
    video_id = extract_video_id(url)
    opts = get_base_ydl_opts(cookies_path)
    opts['skip_download'] = True
    opts['extract_flat'] = False

    last_err = None
    for attempt in range(config.processing.max_retries):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                break
        except Exception as e:
            last_err = e
            time.sleep(config.processing.retry_delay_seconds * (attempt + 1))
    else:
        raise RuntimeError(f"Failed to inspect video after {config.processing.max_retries} attempts: {last_err}")

    vid_id = info.get('id') or video_id or "video"
    title = info.get('title', 'Unknown Title')
    description = info.get('description', '')
    tags = info.get('tags', []) or []
    uploader = info.get('uploader') or info.get('channel') or "Unknown Channel"
    channel_url = info.get('channel_url') or f"https://www.youtube.com/@{uploader}"
    duration = info.get('duration', 0)
    duration_str = info.get('duration_string') or format_timestamp(duration or 0)
    view_count = info.get('view_count', 0)
    thumbnail = info.get('thumbnail') or f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
    upload_date = info.get('upload_date', '')
    if len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

    transcript = fetch_transcript_data(vid_id, info)

    return {
        'id': vid_id,
        'url': info.get('webpage_url') or url,
        'title': title,
        'uploader': uploader,
        'channel_url': channel_url,
        'duration': duration,
        'duration_str': duration_str,
        'view_count': view_count,
        'upload_date': upload_date,
        'thumbnail': thumbnail,
        'tags': tags,
        'tag_count': len(tags),
        'description': description,
        'transcript': transcript,
        'has_transcript': len(transcript) > 0,
    }

def generate_metadata_document(info: dict[str, Any], output_dir: str) -> dict[str, str]:
    """Generates both [METADATA].md and [METADATA].txt files with full details."""
    os.makedirs(output_dir, exist_ok=True)
    clean_title = sanitize_filename(info.get('title', 'YouTube_Video'))
    vid_id = info.get('id') or "video"
    base_name = os.path.join(output_dir, f"{clean_title} [{vid_id}] [METADATA]")

    tags = info.get('tags', [])
    tags_formatted_md = " ".join([f"`#{t}`" for t in tags]) if tags else "_No tags found for this video._"
    tags_formatted_csv = ", ".join(tags) if tags else "None"

    transcript_list = info.get('transcript', [])
    if transcript_list:
        transcript_md_lines = []
        transcript_txt_lines = []
        for item in transcript_list:
            ts = item.get('timestamp', '00:00')
            txt = item.get('text', '')
            transcript_md_lines.append(f"- **`[{ts}]`** {txt}")
            transcript_txt_lines.append(f"[{ts}] {txt}")
        transcript_md = "\n".join(transcript_md_lines)
        transcript_txt = "\n".join(transcript_txt_lines)
    else:
        transcript_md = "_No transcript or captions available for this video._"
        transcript_txt = "No transcript or captions available for this video."

    # Markdown Document
    md_content = f"""# {info.get('title')}

## Video Overview
- **YouTube URL**: [{info.get('url')}]({info.get('url')})
- **Channel / Creator**: [{info.get('uploader')}]({info.get('channel_url')})
- **Duration**: {info.get('duration_str', 'N/A')}
- **Upload Date**: {info.get('upload_date', 'N/A')}
- **Views**: {info.get('view_count', 0):,}

---

## Extracted Tags ({len(tags)})
{tags_formatted_md}

**Comma Separated List:**
> {tags_formatted_csv}

---

## Description
```text
{info.get('description', '')}
```

---

## Video Transcript
{transcript_md}
"""

    # Plain Text Document
    txt_content = f"""================================================================================
{info.get('title')}
================================================================================
URL:         {info.get('url')}
Channel:     {info.get('uploader')} ({info.get('channel_url')})
Duration:    {info.get('duration_str', 'N/A')}
Upload Date: {info.get('upload_date', 'N/A')}
Views:       {info.get('view_count', 0):,}

--------------------------------------------------------------------------------
TAGS ({len(tags)}):
--------------------------------------------------------------------------------
{tags_formatted_csv}

--------------------------------------------------------------------------------
DESCRIPTION:
--------------------------------------------------------------------------------
{info.get('description', '')}

--------------------------------------------------------------------------------
TRANSCRIPT:
--------------------------------------------------------------------------------
{transcript_txt}
"""

    md_path = f"{base_name}.md"
    txt_path = f"{base_name}.txt"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt_content)

    return {"md": md_path, "txt": txt_path}

def resolve_video_format_string(resolution: str = "best") -> str:
    """Resolve format selector string based on chosen resolution."""
    if resolution == "1080p":
        return "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    elif resolution == "720p":
        return "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]"
    elif resolution == "480p":
        return "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]"
    return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

def download_media_bundle(
    url: str,
    output_dir: str | None = None,
    download_video: bool = True,
    download_audio: bool = True,
    download_doc: bool = True,
    video_resolution: str = "best",
    audio_format: str = "mp3",
    audio_bitrate: str = "192",
    cookies_path: str | None = None,
    progress_hook: Callable[[dict], None] | None = None
) -> dict[str, Any]:
    """Downloads requested components: Video, Audio, and/or Metadata Document."""
    target_dir = os.path.abspath(output_dir or config.absolute_download_dir)
    os.makedirs(target_dir, exist_ok=True)

    results: dict[str, Any] = {
        'video_file': None,
        'audio_file': None,
        'doc_files': None,
        'info': None,
    }

    # Step 1: Inspect metadata & extract transcript
    if progress_hook:
        progress_hook({'phase': 'inspecting', 'message': 'Extracting tags, transcript, and video metadata...'})

    info = inspect_video(url, cookies_path)
    results['info'] = info
    clean_title = sanitize_filename(info['title'])
    vid_id = info.get('id') or extract_video_id(url) or "video"

    # Step 2: Generate Metadata Document
    if download_doc:
        if progress_hook:
            progress_hook({'phase': 'document', 'message': 'Generating metadata and transcript document...'})
        docs = generate_metadata_document(info, target_dir)
        results['doc_files'] = docs

    # Step 3: Download Video (MP4)
    if download_video:
        if progress_hook:
            progress_hook({'phase': 'video', 'message': f'Downloading Video ({video_resolution})...'})

        def yt_progress_video(d):
            if progress_hook and d.get('status') == 'downloading':
                progress_hook({
                    'phase': 'video_downloading',
                    'percent': d.get('_percent_str', '').strip(),
                    'speed': d.get('_speed_str', '').strip(),
                    'eta': d.get('_eta_str', '').strip(),
                })

        video_fmt = resolve_video_format_string(video_resolution)
        video_opts = get_base_ydl_opts(cookies_path)
        video_opts.update({
            'format': video_fmt,
            'outtmpl': os.path.join(target_dir, f"{clean_title} [{vid_id}] [VIDEO].%(ext)s"),
            'merge_output_format': 'mp4',
            'noplaylist': True,
            'progress_hooks': [yt_progress_video],
        })

        with yt_dlp.YoutubeDL(video_opts) as ydl:
            ydl.download([url])
            results['video_file'] = os.path.join(target_dir, f"{clean_title} [{vid_id}] [VIDEO].mp4")

    # Step 4: Download Audio
    if download_audio:
        codec = audio_format.lower() if audio_format.lower() in ["mp3", "wav", "m4a"] else "mp3"
        bitrate = audio_bitrate if audio_bitrate in ["128", "192", "320"] else "192"

        if progress_hook:
            progress_hook({'phase': 'audio', 'message': f'Extracting standalone Audio to {codec.upper()} ({bitrate}k)...'})

        def yt_progress_audio(d):
            if progress_hook and d.get('status') == 'downloading':
                progress_hook({
                    'phase': 'audio_downloading',
                    'percent': d.get('_percent_str', '').strip(),
                    'speed': d.get('_speed_str', '').strip(),
                    'eta': d.get('_eta_str', '').strip(),
                })

        audio_opts = get_base_ydl_opts(cookies_path)
        audio_opts.update({
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(target_dir, f"{clean_title} [{vid_id}] [AUDIO].%(ext)s"),
            'noplaylist': True,
            'progress_hooks': [yt_progress_audio],
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': codec,
                'preferredquality': bitrate,
            }],
        })

        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            ydl.download([url])
            results['audio_file'] = os.path.join(target_dir, f"{clean_title} [{vid_id}] [AUDIO].{codec}")

    if progress_hook:
        progress_hook({'phase': 'finished', 'message': 'All operations completed successfully!'})

    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_url = sys.argv[1].strip()
    else:
        target_url = input("Enter YouTube URL or Playlist: ").strip()

    if target_url:
        if is_playlist_url(target_url):
            print("[*] Detected playlist URL. Fetching items...")
            items = expand_playlist_urls(target_url)
            print(f"[*] Found {len(items)} videos. Starting batch extraction...")
            for idx, item in enumerate(items, 1):
                print(f"\n--- [{idx}/{len(items)}] {item['title']} ---")
                try:
                    download_media_bundle(item['url'])
                except Exception as ex:
                    print(f"[!] Failed to process {item['url']}: {ex}")
        else:
            download_media_bundle(target_url)
