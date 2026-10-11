import ipaddress
import os
import platform
import shutil
import sys

import yaml
from pydantic import BaseModel, Field


def get_extractor_home() -> str:
    """Determine application home directory: EXTRACTOR_HOME -> ~/.the_extractor -> current working directory."""
    if "EXTRACTOR_HOME" in os.environ:
        return os.path.abspath(os.environ["EXTRACTOR_HOME"])
    if not os.path.exists("config.yaml") and not os.path.exists("config.yaml.example"):
        return os.path.abspath(os.path.expanduser("~/.the_extractor"))
    return os.getcwd()


def get_default_config_path() -> str:
    if "EXTRACTOR_CONFIG" in os.environ:
        return os.environ["EXTRACTOR_CONFIG"]
    home = get_extractor_home()
    candidate = os.path.join(home, "config.yaml")
    if os.path.exists(candidate):
        return candidate
    return "config.yaml"


CONFIG_FILE_PATH = get_default_config_path()

class AppConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    api_key: str = ""
    env: str = "development"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:8000", "http://localhost:8000"])

class SecurityConfig(BaseModel):
    require_api_key_for_non_localhost: bool = True
    max_url_length: int = 2048
    min_api_key_length: int = 16


class PathsConfig(BaseModel):
    download_dir: str = "downloads"
    data_dir: str = "data"
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
    max_concurrent_downloads: int = 3
    max_batch_size: int = 100
    max_playlist_items: int = 500
    max_queue_size: int = 500
    task_retention_minutes: int = 10
    task_timeout_minutes: int = 60

class StorageConfig(BaseModel):
    max_storage_gb: float = 0.0      # 0.0 means unlimited / no size-based deletion
    delete_after_days: int = 0       # 0 means never delete by age
    warning_percent: float = 80.0
    critical_percent: float = 95.0

class HistoryConfig(BaseModel):
    max_records: int = 10000
    retention_days: int = 90

class Config(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    history: HistoryConfig = Field(default_factory=HistoryConfig)


    @property
    def absolute_download_dir(self) -> str:
        d = self.paths.download_dir
        if os.path.isabs(d):
            return os.path.abspath(d)
        return os.path.abspath(os.path.join(get_extractor_home(), d))

    @property
    def absolute_data_dir(self) -> str:
        d = self.paths.data_dir
        if os.path.isabs(d):
            return os.path.abspath(d)
        return os.path.abspath(os.path.join(get_extractor_home(), d))

    @property
    def database_path(self) -> str:
        return os.path.join(self.absolute_data_dir, "extractor.db")

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
    if "EXTRACTOR_DATA_DIR" in os.environ:
        data.setdefault("paths", {})["data_dir"] = os.environ["EXTRACTOR_DATA_DIR"]
    if "EXTRACTOR_API_KEY" in os.environ:
        data.setdefault("app", {})["api_key"] = os.environ["EXTRACTOR_API_KEY"]
    if "EXTRACTOR_HOST" in os.environ:
        data.setdefault("app", {})["host"] = os.environ["EXTRACTOR_HOST"]
    if "EXTRACTOR_PORT" in os.environ:
        try:
            data.setdefault("app", {})["port"] = int(os.environ["EXTRACTOR_PORT"])
        except ValueError:
            pass
    if "EXTRACTOR_ENV" in os.environ:
        data.setdefault("app", {})["env"] = os.environ["EXTRACTOR_ENV"].strip().lower()

    cfg = Config(**data)
    os.makedirs(cfg.absolute_download_dir, exist_ok=True)
    os.makedirs(cfg.absolute_data_dir, exist_ok=True)
    return cfg


LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def is_non_localhost(host: str) -> bool:
    """Returns True if the host is not a standard loopback address."""
    h = host.strip().lower()
    if h in LOOPBACK:
        return False
    try:
        ip = ipaddress.ip_address(h)
        return not ip.is_loopback
    except ValueError:
        return True


def validate_startup_security(cfg: Config) -> None:
    """
    Validates network binding, API key requirements, and production security rules (SEC-02).
    - Refuses binding to non-localhost without an API key.
    - In production mode (app.env == 'production'), requires an API key for all bindings
      and enforces a minimum key strength (min_api_key_length).
    """
    is_prod = (cfg.app.env or "").strip().lower() == "production"
    key = cfg.app.api_key.strip()
    min_len = cfg.security.min_api_key_length

    # Production mode requirements
    if is_prod:
        if not key:
            raise RuntimeError(
                "Security Error: Production mode (EXTRACTOR_ENV=production) requires an API key to be set."
            )
        if len(key) < min_len:
            raise RuntimeError(
                f"Security Error: Production mode requires an API key of at least {min_len} characters."
            )

    # Non-localhost binding requirements
    if is_non_localhost(cfg.app.host) and cfg.security.require_api_key_for_non_localhost:
        if not key:
            raise RuntimeError(
                f"Security Error: Cannot bind to '{cfg.app.host}' without an API key configured. "
                "Set 'app.api_key' in config.yaml / EXTRACTOR_API_KEY env var, or bind to '127.0.0.1'."
            )
        if is_prod and len(key) < min_len:
            raise RuntimeError(
                f"Security Error: Non-localhost production binding requires an API key of at least {min_len} characters."
            )



# Global singleton
config = load_config()


