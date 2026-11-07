import subprocess
import sys

import pytest

import main


def test_auto_update_ytdlp_if_enabled_disabled(monkeypatch):
    monkeypatch.delenv("EXTRACTOR_AUTO_UPDATE_YTDLP", raising=False)
    called = False

    def mock_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(subprocess, "run", mock_run)
    main.auto_update_ytdlp_if_enabled()
    assert not called


def test_auto_update_ytdlp_if_enabled_active(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_AUTO_UPDATE_YTDLP", "1")
    recorded_cmd = []

    def mock_run(cmd, *args, **kwargs):
        recorded_cmd.extend(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    main.auto_update_ytdlp_if_enabled()
    assert "yt-dlp[default]" in recorded_cmd


def test_auto_update_ytdlp_timeout_handled(monkeypatch, capsys):
    monkeypatch.setenv("EXTRACTOR_AUTO_UPDATE_YTDLP", "1")

    def mock_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="pip", timeout=120)

    monkeypatch.setattr(subprocess, "run", mock_run)
    main.auto_update_ytdlp_if_enabled()
    err = capsys.readouterr().err
    assert "timed out after 120 seconds" in err


def test_open_browser_delayed(monkeypatch):
    import webbrowser

    opened = []
    monkeypatch.setattr(main.time, "sleep", lambda s: None)
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))

    main.open_browser_delayed("http://127.0.0.1:8000")
    assert opened == ["http://127.0.0.1:8000"]


def test_main_cli_arguments_and_execution(monkeypatch):
    import uvicorn

    recorded_uvicorn = {}

    def mock_uvicorn_run(app_str, **kwargs):
        recorded_uvicorn["app"] = app_str
        recorded_uvicorn.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", mock_uvicorn_run)
    monkeypatch.setattr(main, "auto_update_ytdlp_if_enabled", lambda: None)
    monkeypatch.setattr(main, "validate_startup_security", lambda cfg: None)
    monkeypatch.setattr(main.database, "apply_history_retention", lambda: {"deleted_records": 1})

    orig_host = main.config.app.host
    orig_port = main.config.app.port
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "--host", "127.0.0.1", "--port", "8999", "--no-browser", "--reload"],
    )

    try:
        main.main()
    finally:
        main.config.app.host = orig_host
        main.config.app.port = orig_port

    assert recorded_uvicorn.get("app") == "server:app"
    assert recorded_uvicorn.get("host") == "127.0.0.1"
    assert recorded_uvicorn.get("port") == 8999
    assert recorded_uvicorn.get("reload") is True


def test_main_security_validation_failure_exits(monkeypatch):
    monkeypatch.setattr(main, "auto_update_ytdlp_if_enabled", lambda: None)

    def mock_bad_sec(cfg):
        raise RuntimeError("Insecure bind test")

    orig_host = main.config.app.host
    orig_port = main.config.app.port
    monkeypatch.setattr(main, "validate_startup_security", mock_bad_sec)
    monkeypatch.setattr(sys, "argv", ["main.py", "--host", "0.0.0.0", "--no-browser"])

    try:
        with pytest.raises(SystemExit) as exc:
            main.main()
        assert exc.value.code == 1
    finally:
        main.config.app.host = orig_host
        main.config.app.port = orig_port
