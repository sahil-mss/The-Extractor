import os
import platform
import shutil
import sys

import yaml
from pydantic import BaseModel, Field

CONFIG_FILE_PATH = os.environ.get("EXTRACTOR_CONFIG", "config.yaml")

class AppConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    api_key: str = ""
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

class PathsConfig(BaseModel):
    download_dir: str = "downloads"
    cookies_file: str = ""
    audacity_path: str = ""

class DefaultsConfig(BaseModel):
    video_resolution: str = "best"
    audio_format: str = "mp3"
    audio_bitrate: str = "192"
    download_video: bool = True
    download_audio: bool = True
    download_doc: bool = True

class ProcessingConfig(BaseModel):
    max_retries: int = 3
    retry_delay_seconds: int = 2
    max_concurrent_downloads: int = 2

class Config(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)

    @property
    def absolute_download_dir(self) -> str:
        return os.path.abspath(self.paths.download_dir)

    def get_audacity_executable(self) -> str | None:
        """Cross-platform Audacity executable detection."""
        # 1. Configured explicit path
        if self.paths.audacity_path and os.path.exists(self.paths.audacity_path):
            return self.paths.audacity_path

        # 2. PATH check
        path_bin = shutil.which("audacity") or shutil.which("Audacity") or shutil.which("Audacity4")
        if path_bin:
            return path_bin

        # 3. Platform specific defaults
        system = platform.system()
        if system == "Windows":
            candidates = [
                r"C:\Program Files\Audacity\Audacity.exe",
                r"C:\Program Files (x86)\Audacity\Audacity.exe",
                r"C:\Program Files\Audacity 4\bin\Audacity4.exe",
                r"C:\Program Files\Audacity 4\Audacity.exe",
            ]
            # Check local app data for user installs
            local_app = os.environ.get("LOCALAPPDATA", "")
            if local_app:
                candidates.append(os.path.join(local_app, "Programs", "Audacity", "Audacity.exe"))
            for c in candidates:
                if os.path.exists(c):
                    return c
        elif system == "Darwin":  # macOS
            mac_candidates = [
                "/Applications/Audacity.app/Contents/MacOS/Audacity",
                os.path.expanduser("~/Applications/Audacity.app/Contents/MacOS/Audacity"),
            ]
            for c in mac_candidates:
                if os.path.exists(c):
                    return c
        elif system == "Linux":
            linux_candidates = [
                "/usr/bin/audacity",
                "/usr/local/bin/audacity",
                "/var/lib/flatpak/exports/bin/org.audacityteam.Audacity",
                "/snap/bin/audacity",
            ]
            for c in linux_candidates:
                if os.path.exists(c):
                    return c

        return None

def load_config(config_path: str | None = None) -> Config:
    """Load configuration from YAML file or environment variables with graceful fallback."""
    path = config_path or CONFIG_FILE_PATH
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except Exception as e:
            print(f"[!] Warning: Failed to parse {path}, using defaults. Error: {e}", file=sys.stderr)
    elif os.path.exists("config.yaml.example") and not os.path.exists(path):
        # Fallback to config.yaml.example if config.yaml doesn't exist yet
        try:
            with open("config.yaml.example", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except Exception:
            pass

    # Environment variable overrides
    if "EXTRACTOR_DOWNLOAD_DIR" in os.environ:
        data.setdefault("paths", {})["download_dir"] = os.environ["EXTRACTOR_DOWNLOAD_DIR"]
    if "EXTRACTOR_API_KEY" in os.environ:
        data.setdefault("app", {})["api_key"] = os.environ["EXTRACTOR_API_KEY"]
    if "EXTRACTOR_HOST" in os.environ:
        data.setdefault("app", {})["host"] = os.environ["EXTRACTOR_HOST"]
    if "EXTRACTOR_PORT" in os.environ:
        try:
            data.setdefault("app", {})["port"] = int(os.environ["EXTRACTOR_PORT"])
        except ValueError:
            pass

    cfg = Config(**data)
    os.makedirs(cfg.absolute_download_dir, exist_ok=True)
    return cfg

# Global singleton
config = load_config()
