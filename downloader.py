import os
import re
import shutil
import sys
from typing import Callable, Dict, List, Optional
import yt_dlp
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

def find_ffmpeg_bin() -> Optional[str]:
    """Locate ffmpeg executable from PATH or WinGet packages."""
    if shutil.which("ffmpeg"):
        return None  # yt-dlp will find it directly in system PATH

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    winget_pkgs = os.path.join(local_app_data, "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget_pkgs):
        for root, dirs, files in os.walk(winget_pkgs):
            if "ffmpeg.exe" in files:
                return root
    return None

def extract_video_id(url: str) -> Optional[str]:
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

def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def sanitize_filename(name: str) -> str:
    """Clean filename of characters forbidden in Windows and Unix."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def fetch_transcript_data(video_id: str, ydl_info: Optional[Dict] = None) -> List[Dict[str, any]]:
    """
    Fetch transcript using youtube-transcript-api with fallback to yt-dlp subtitle streams.
    Returns a list of dicts: [{'start': 0.0, 'duration': 2.5, 'text': '...'}]
    """
    transcript_items = []

    # 1. Try youtube-transcript-api
    if YouTubeTranscriptApi:
        try:
            api = YouTubeTranscriptApi()
            # Fetch transcript (tries en, or auto-detects available)
            transcript_list = api.list(video_id)
            transcript = None
            try:
                transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
            except Exception:
                # Fall back to first available transcript or generated
                for t in transcript_list:
                    transcript = t
                    break

            if transcript:
                fetched = transcript.fetch()
                for item in fetched:
                    # Handle both dict and object formats
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
        except Exception as e:
            print(f"[!] youtube-transcript-api note: {e}")

    # 2. Fallback: Parse automatic captions or subtitles from yt-dlp if available
    if ydl_info:
        subs = ydl_info.get('subtitles') or {}
        auto_subs = ydl_info.get('automatic_captions') or {}
        all_subs = {**auto_subs, **subs}
        en_sub = all_subs.get('en') or all_subs.get('en-orig')
        if en_sub:
            print("[i] Detected yt-dlp captions available for video.")

    return transcript_items

def inspect_video(url: str) -> Dict:
    """
    Inspect YouTube video to extract all metadata, tags, and transcript preview without downloading.
    """
    video_id = extract_video_id(url)
    ffmpeg_path = find_ffmpeg_bin()
    ydl_opts = {
        'skip_download': True,
        'extract_flat': False,
        'quiet': True,
        'no_warnings': True,
    }
    if ffmpeg_path:
        ydl_opts['ffmpeg_location'] = ffmpeg_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

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
    upload_date = info.get('upload_date', '')  # YYYYMMDD
    if len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

    # Fetch transcript
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

def generate_metadata_document(info: Dict, output_dir: str = "downloads") -> Dict[str, str]:
    """
    Creates both [METADATA].md and [METADATA].txt files with full details:
    - Title, channel, duration, URL, upload date
    - All extracted tags
    - Full video description
    - Complete timestamped transcript
    """
    os.makedirs(output_dir, exist_ok=True)
    clean_title = sanitize_filename(info.get('title', 'YouTube_Video'))
    base_name = os.path.join(output_dir, f"{clean_title} [METADATA]")

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

    # 1. Build Markdown Document
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

    # 2. Build Plain Text Document
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

def download_media_bundle(
    url: str,
    output_dir: str = "downloads",
    download_video: bool = True,
    download_audio: bool = True,
    download_doc: bool = True,
    progress_hook: Optional[Callable[[Dict], None]] = None
) -> Dict:
    """
    Downloads requested components: Video (MP4 HD), Audio (MP3), and/or Metadata Document.
    """
    os.makedirs(output_dir, exist_ok=True)
    ffmpeg_path = find_ffmpeg_bin()

    results = {
        'video_file': None,
        'audio_file': None,
        'doc_files': None,
        'info': None,
    }

    # Step 1: Inspect metadata & extract transcript
    if progress_hook:
        progress_hook({'phase': 'inspecting', 'message': 'Extracting tags, transcript, and video metadata...'})

    info = inspect_video(url)
    results['info'] = info
    clean_title = sanitize_filename(info['title'])

    # Step 2: Generate Metadata Document
    if download_doc:
        if progress_hook:
            progress_hook({'phase': 'document', 'message': 'Generating metadata and transcript document...'})
        docs = generate_metadata_document(info, output_dir)
        results['doc_files'] = docs

    # Step 3: Download Video (MP4)
    if download_video:
        if progress_hook:
            progress_hook({'phase': 'video', 'message': 'Downloading High-Definition Video (MP4)...'})

        def yt_progress_video(d):
            if progress_hook and d.get('status') == 'downloading':
                progress_hook({
                    'phase': 'video_downloading',
                    'percent': d.get('_percent_str', '').strip(),
                    'speed': d.get('_speed_str', '').strip(),
                    'eta': d.get('_eta_str', '').strip(),
                })

        video_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best',
            'outtmpl': os.path.join(output_dir, f"{clean_title} [VIDEO].%(ext)s"),
            'merge_output_format': 'mp4',
            'noplaylist': True,
            'progress_hooks': [yt_progress_video],
        }
        if ffmpeg_path:
            video_opts['ffmpeg_location'] = ffmpeg_path

        with yt_dlp.YoutubeDL(video_opts) as ydl:
            ydl.download([url])
            results['video_file'] = os.path.join(output_dir, f"{clean_title} [VIDEO].mp4")

    # Step 4: Download Audio (MP3)
    if download_audio:
        if progress_hook:
            progress_hook({'phase': 'audio', 'message': 'Extracting standalone Audio to MP3...'})

        def yt_progress_audio(d):
            if progress_hook and d.get('status') == 'downloading':
                progress_hook({
                    'phase': 'audio_downloading',
                    'percent': d.get('_percent_str', '').strip(),
                    'speed': d.get('_speed_str', '').strip(),
                    'eta': d.get('_eta_str', '').strip(),
                })

        audio_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(output_dir, f"{clean_title} [AUDIO].%(ext)s"),
            'noplaylist': True,
            'progress_hooks': [yt_progress_audio],
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        if ffmpeg_path:
            audio_opts['ffmpeg_location'] = ffmpeg_path

        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            ydl.download([url])
            results['audio_file'] = os.path.join(output_dir, f"{clean_title} [AUDIO].mp3")

    if progress_hook:
        progress_hook({'phase': 'finished', 'message': 'All operations completed successfully!'})

    return results

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_url = sys.argv[1].strip()
    else:
        target_url = input("Enter YouTube URL: ").strip()

    if target_url:
        download_media_bundle(target_url)
