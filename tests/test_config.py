from config import Config, load_config


def test_default_config_loading():
    cfg = load_config("non_existent_config.yaml")
    assert cfg.app.host in ("127.0.0.1", "0.0.0.0")
    assert cfg.app.port == 8000
    assert cfg.defaults.video_resolution == "best"
    assert cfg.defaults.audio_format == "mp3"
    assert cfg.defaults.audio_bitrate == "192"

def test_audacity_resolver():
    cfg = Config()
    # Test that get_audacity_executable runs safely on any OS without throwing an exception
    path = cfg.get_audacity_executable()
    assert path is None or isinstance(path, str)

def test_audacity_resolver_configured_path(monkeypatch, tmp_path):
    custom_bin = tmp_path / "my_audacity.exe"
    custom_bin.write_text("mock binary")
    cfg = Config()
    cfg.paths.audacity_path = str(custom_bin)
    assert cfg.get_audacity_executable() == str(custom_bin)

def test_audacity_resolver_path_detection(monkeypatch):
    cfg = Config()
    monkeypatch.setattr("shutil.which", lambda name: "/mock/bin/audacity" if "audacity" in name.lower() else None)
    assert cfg.get_audacity_executable() == "/mock/bin/audacity"

def test_audacity_resolver_platform_branches(monkeypatch):
    cfg = Config()
    monkeypatch.setattr("shutil.which", lambda name: None)

    # Windows branch
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("os.path.exists", lambda path: True if "Audacity.exe" in path else False)
    assert cfg.get_audacity_executable() == r"C:\Program Files\Audacity\Audacity.exe"

    # Darwin (macOS) branch
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("os.path.exists", lambda path: True if "Applications/Audacity.app" in path else False)
    assert cfg.get_audacity_executable() == "/Applications/Audacity.app/Contents/MacOS/Audacity"

    # Linux branch
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("os.path.exists", lambda path: True if path == "/usr/bin/audacity" else False)
    assert cfg.get_audacity_executable() == "/usr/bin/audacity"
