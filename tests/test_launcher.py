import subprocess
import sys

import launcher


def test_launcher_log(tmp_path, monkeypatch):
    test_log = tmp_path / "test_launcher.log"
    monkeypatch.setattr(launcher, "LOG_FILE", str(test_log))

    launcher.log("Hello from test launcher")
    assert test_log.exists()
    content = test_log.read_text(encoding="utf-8")
    assert "Hello from test launcher" in content


def test_launcher_get_base_python(monkeypatch):
    res = launcher.get_base_python()
    assert isinstance(res, list)
    assert len(res) >= 1


def test_launcher_get_venv_python():
    vpy = launcher.get_venv_python()
    assert isinstance(vpy, str)
    assert ".venv" in vpy


def test_launcher_check_and_setup_venv_already_exists(monkeypatch, tmp_path):
    fake_python = tmp_path / ("python.exe" if sys.platform == "win32" else "python")
    fake_python.write_text("fake binary", encoding="utf-8")

    monkeypatch.setattr(launcher, "get_venv_python", lambda: str(fake_python))

    def mock_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="READY\n", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_run)

    res = launcher.check_and_setup_venv()
    assert res == str(fake_python)


def test_launcher_check_and_setup_venv_creation_failure_falls_back(monkeypatch, tmp_path):
    missing_python = tmp_path / "missing_py"
    monkeypatch.setattr(launcher, "get_venv_python", lambda: str(missing_python))

    def mock_run_fail(*args, **kwargs):
        raise RuntimeError("Failed to create venv")

    monkeypatch.setattr(subprocess, "run", mock_run_fail)

    res = launcher.check_and_setup_venv()
    assert res == sys.executable


def test_launcher_main_invocation(monkeypatch, tmp_path):
    fake_python = tmp_path / ("python.exe" if sys.platform == "win32" else "python")
    fake_python.write_text("fake binary", encoding="utf-8")
    monkeypatch.setattr(launcher, "check_and_setup_venv", lambda: str(fake_python))

    executed_cmd = []

    def mock_run(cmd, *args, **kwargs):
        executed_cmd.extend(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr(sys, "argv", ["launcher.py", "--no-browser"])

    launcher.main()
    assert str(fake_python) in executed_cmd
    assert "--no-browser" in executed_cmd
