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
