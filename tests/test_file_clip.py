import os
import sys
import json
import uuid
import time
import pytest
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
from fileclip.file_clip import copy_files, is_container, translate_path, validate_path, check_watcher, write_fileclip_json, wait_for_results, _copy_files_direct
from fileclip.main import main, collect_files

# Mock subprocess.run to avoid actual clipboard changes during tests
@pytest.fixture
def mock_subprocess_run():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["mock"], returncode=0, stdout="", stderr=""
        )
        yield mock_run

# Fixture for temporary files under container_workspace
@pytest.fixture
def temp_files(tmp_path):
    """Create temporary files for testing, including one with special characters."""
    container_workspace = tmp_path / "container_workspace"
    container_workspace.mkdir(parents=True, exist_ok=True)
    file1 = container_workspace / "test1.txt"
    file2 = container_workspace / "test2.pdf"
    file3 = container_workspace / "test file@3.txt"  # Special characters
    file1.write_text("Hello, world!")
    file2.write_text("Fake PDF content")
    file3.write_text("Special char file")
    return [str(file1), str(file2), str(file3)]

# Fixture for temporary directory with files under container_workspace
@pytest.fixture
def temp_dir_with_files(tmp_path):
    """Create a temporary directory with files under container_workspace."""
    container_workspace = tmp_path / "container_workspace"
    container_workspace.mkdir(parents=True, exist_ok=True)
    dir_path = container_workspace / "test_dir"
    dir_path.mkdir()
    file1 = dir_path / "file1.txt"
    file2 = dir_path / "file2.pdf"
    file3 = dir_path / "file#3.txt"  # Special characters
    file1.write_text("File 1 content")
    file2.write_text("File 2 content")
    file3.write_text("File 3 content")
    return str(dir_path), [str(file1), str(file2), str(file3)]

# Fixture for mocking environment variables
@pytest.fixture
def mock_env(tmp_path):
    """Mock environment variables for watcher and container testing."""
    container_workspace = str(tmp_path / "container_workspace")
    host_workspace = str(tmp_path / "host_workspace")
    with patch.dict(os.environ, {
        "FILECLIP_CONTAINER_WORKSPACE": container_workspace,
        "FILECLIP_HOST_WORKSPACE": host_workspace,
        "FILECLIP_USE_WATCHER": "true"
    }):
        yield {
            "container_workspace": container_workspace,
            "host_workspace": host_workspace
        }

# Fixture for mocking container environment
@pytest.fixture
def mock_container():
    with patch("fileclip.file_clip.is_container", return_value=True):
        yield

# Fixture for mocking watchdog observer
@pytest.fixture
def mock_watchdog_observer():
    with patch("watchdog.observers.Observer") as mock_observer:
        yield mock_observer

# Fixture for mocking file I/O
@pytest.fixture
def mock_file_io():
    with patch("builtins.open") as mock_open, patch("json.load") as mock_load, patch("json.dump") as mock_dump:
        yield mock_open, mock_load, mock_dump

# Test container detection
def test_is_container_no_container():
    """Test container detection when not in a container."""
    with patch("pathlib.Path.exists", return_value=False), patch.dict(os.environ, {}, clear=True):
        assert not is_container()

def test_is_container_with_dockerenv():
    """Test container detection with /.dockerenv."""
    with patch("pathlib.Path.exists") as mock_exists, patch.dict(os.environ, {}, clear=True):
        mock_exists.side_effect = [True, False]  # True for /.dockerenv, False for /vscode
        assert is_container()
        assert mock_exists.call_count == 1  # Only /.dockerenv checked due to short-circuit

def test_is_container_with_vscode():
    """Test container detection with /vscode."""
    with patch("pathlib.Path.exists") as mock_exists, patch.dict(os.environ, {}, clear=True):
        mock_exists.side_effect = [False, True]  # False for /.dockerenv, True for /vscode
        assert is_container()
        assert mock_exists.call_count == 2  # Both /.dockerenv and /vscode checked

def test_is_container_with_env():
    """Test container detection with DEV_CONTAINER env var."""
    with patch.dict(os.environ, {"DEV_CONTAINER": "true"}), patch("pathlib.Path.exists", return_value=False):
        assert is_container()

# Test path translation
def test_translate_path(mock_env):
    """Test path translation from container to host."""
    env = mock_env
    container_path = f"{env['container_workspace']}/test.txt"
    result = translate_path(container_path, env['container_workspace'], env['host_workspace'])
    assert result == f"{env['host_workspace']}/test.txt".replace('/', os.sep)

def test_translate_path_invalid(mock_env):
    """Test path translation with invalid container path."""
    env = mock_env
    with pytest.raises(ValueError, match="Path /other/test.txt is not under"):
        translate_path("/other/test.txt", env['container_workspace'], env['host_workspace'])

# Test path validation
def test_validate_path(mock_env):
    """Test path validation."""
    env = mock_env
    assert validate_path(f"{env['container_workspace']}/test.txt", env['container_workspace'])
    assert not validate_path("/other/test.txt", env['container_workspace'])

# Test write_fileclip_json
def test_write_fileclip_json(tmp_path):
    """Test writing fileclip_<uuid>.json."""
    shared_dir = tmp_path / ".fileclip"
    shared_dir.mkdir(parents=True, exist_ok=True)
    paths = [r"C:\host\path\test.txt"]
    sender = "container_pid_1234"
    request_id, json_file = write_fileclip_json(shared_dir, paths, sender)
    assert json_file.exists()
    with open(json_file, "r") as f:
        data = json.load(f)
    assert data["action"] == "copy_files"
    assert data["sender"] == sender
    assert data["request_id"] == request_id
    assert data["paths"] == paths

# Test check_watcher with no response
def test_check_watcher_no_response(tmp_path):
    """Test check_watcher with no response."""
    shared_dir = tmp_path / ".fileclip"
    shared_dir.mkdir(parents=True, exist_ok=True)
    assert not check_watcher(shared_dir, timeout=0.1)
    assert not list(shared_dir.glob("fileclip_*.json"))

# Test wait_for_results with timeout
def test_wait_for_results_timeout(tmp_path, mock_watchdog_observer):
    """Test wait_for_results with timeout."""
    shared_dir = tmp_path / ".fileclip"
    shared_dir.mkdir(parents=True, exist_ok=True)
    mock_observer_instance = mock_watchdog_observer.return_value
    mock_observer_instance.start.return_value = None
    mock_observer_instance.stop.return_value = None
    mock_observer_instance.join.return_value = None
    result = wait_for_results(shared_dir, "test-uuid", timeout=0.1)
    assert result == {"success": False, "message": "Timeout waiting for results after 0.1s"}

# Test copy_files with valid files (direct mode)
def test_copy_files_valid_files(temp_files, mock_subprocess_run, mock_env):
    """Test copy_files with valid files in direct mode."""
    assert copy_files(temp_files, use_watcher=False)
    mock_subprocess_run.assert_called()

# Test copy_files with invalid file
def test_copy_files_invalid_file(mock_env):
    """Test copy_files with invalid file."""
    with pytest.raises(FileNotFoundError, match="File not found or not a file"):
        copy_files(["nonexistent.txt"], use_watcher=False)

# Test copy_files with empty list
def test_copy_files_empty_list(mock_env):
    """Test copy_files with empty list."""
    assert not copy_files([], use_watcher=False)

# Test copy_files with directory in list
def test_copy_files_directory_in_list(temp_files, tmp_path, mock_env):
    """Test copy_files with a directory."""
    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()
    invalid_files = temp_files + [str(dir_path)]
    with pytest.raises(FileNotFoundError, match="File not found or not a file"):
        copy_files(invalid_files, use_watcher=False)

# Test copy_files on unsupported platform
def test_copy_files_unsupported_platform(temp_files, mock_env):
    """Test copy_files on unsupported platform."""
    with patch("sys.platform", "unsupported"):
        with pytest.raises(RuntimeError, match="Unsupported platform: unsupported"):
            copy_files(temp_files, use_watcher=False)

# Linux-specific tests (skipped on non-Linux)
@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_wlcopy_missing(temp_files, monkeypatch, mock_env):
    """Test copy_files on Linux with wl-copy missing."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("DISPLAY", ":0")
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            FileNotFoundError("wl-copy not found"),
            subprocess.CompletedProcess(
                args=["xclip", "-selection", "clipboard", "-t", "text/uri-list"],
                returncode=0, stdout="", stderr=""
            )
        ]
        result = copy_files(temp_files, use_watcher=False)
        assert result is True
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][0][0][0] == "wl-copy"
        assert mock_run.call_args_list[1][0][0][0] == "xclip"
        assert mock_run.call_args_list[1][1]["input"].decode().startswith("file://")

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_xclip_missing(temp_files, monkeypatch, mock_env):
    """Test copy_files on Linux when both wl-copy and xclip are missing."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("DISPLAY", ":0")
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            FileNotFoundError("wl-copy not found"),
            FileNotFoundError("xclip not found")
        ]
        with pytest.raises(RuntimeError, match="xclip not found"):
            copy_files(temp_files, use_watcher=False)
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][0][0][0] == "wl-copy"
        assert mock_run.call_args_list[1][0][0][0] == "xclip"

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_timeout(temp_files, mock_subprocess_run, monkeypatch, capsys, mock_env):
    """Test copy_files on Linux when both clipboard operations time out."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("DISPLAY", ":0")
    mock_subprocess_run.side_effect = [
        subprocess.TimeoutExpired(
            cmd=["wl-copy", "--type", "text/uri-list"],
            timeout=5
        ),
        subprocess.TimeoutExpired(
            cmd=["xclip", "-selection", "clipboard", "-t", "text/uri-list"],
            timeout=5
        )
    ]
    result = copy_files(temp_files, use_watcher=False)
    assert result is False
    captured = capsys.readouterr()
    assert "Wayland clipboard operation timed out" in captured.out
    assert "X11 clipboard operation timed out" in captured.out
    assert "No functional display server detected" in captured.out
    assert "File URIs (copy manually):" in captured.out
    assert all(f"file://{os.path.abspath(f)}" in captured.out for f in temp_files)

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_no_display(temp_files, monkeypatch, capsys, mock_env):
    """Test copy_files on Linux with no display server."""
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    result = copy_files(temp_files, use_watcher=False)
    assert result is False
    captured = capsys.readouterr()
    assert "No functional display server detected" in captured.out
    assert "File URIs (copy manually):" in captured.out
    assert all(f"file://{os.path.abspath(f)}" in captured.out for f in temp_files)

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_wlcopy_subprocess_error(temp_files, mock_subprocess_run, monkeypatch, mock_env):
    """Test copy_files with a subprocess error on Wayland."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["wl-copy", "--type", "text/uri-list"],
        stderr=b"Wayland error"
    )
    with pytest.raises(RuntimeError, match="Wayland clipboard error: Wayland error"):
        copy_files(temp_files, use_watcher=False)

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_xclip_subprocess_error(temp_files, mock_subprocess_run, monkeypatch, mock_env):
    """Test copy_files with a subprocess error on X11."""
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["xclip", "-selection", "clipboard", "-t", "text/uri-list"],
        stderr=b"X11 error"
    )
    with pytest.raises(RuntimeError, match="X11 clipboard error: X11 error"):
        copy_files(temp_files, use_watcher=False)

@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
def test_copy_files_macos_subprocess_error(temp_files, mock_subprocess_run, mock_env):
    """Test copy_files with a subprocess error on macOS."""
    cmd = 'osascript -e \'tell app "Finder" to set the clipboard to {'
    cmd += ', '.join(f'POSIX file "{p}"' for p in temp_files)
    cmd += '}\''
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=cmd,
        stderr="macOS error"
    )
    with pytest.raises(RuntimeError, match="macOS clipboard error: macOS error"):
        copy_files(temp_files, use_watcher=False)

@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
def test_copy_files_windows_subprocess_error(temp_files, mock_subprocess_run, mock_env):
    """Test copy_files with a subprocess error on Windows."""
    paths = ','.join(f'"{p}"' for p in temp_files)
    cmd = f'powershell.exe -Command "Set-Clipboard -Path {paths}"'
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=cmd,
        stderr="Windows error"
    )
    with pytest.raises(RuntimeError, match="Windows clipboard error: Windows error"):
        copy_files(temp_files, use_watcher=False)

def test_copy_files_large_number_of_files(tmp_path, mock_subprocess_run, monkeypatch, mock_env):
    """Test copy_files with a large number of files."""
    container_workspace = tmp_path / "container_workspace"
    container_workspace.mkdir(parents=True, exist_ok=True)
    files = [str(container_workspace / f"file{i}.txt") for i in range(100)]
    for f in files:
        Path(f).write_text("Test content")
    if sys.platform == "linux":
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    result = copy_files(files, use_watcher=False)
    assert result is True
    mock_subprocess_run.assert_called_once()
    if sys.platform == "linux":
        assert mock_subprocess_run.call_args[1]["input"].decode().startswith("file://")

def test_cli_valid_files(temp_files, capsys, monkeypatch, mock_subprocess_run, mock_env):
    """Test CLI with valid files."""
    if sys.platform == "linux":
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(sys, "argv", ["fileclip"] + temp_files)
    main()
    captured = capsys.readouterr()
    assert "Files copied to clipboard" in captured.out
    mock_subprocess_run.assert_called_once()
    if sys.platform == "linux":
        assert mock_subprocess_run.call_args[1]["input"].decode().startswith("file://")

def test_cli_directory(temp_dir_with_files, capsys, monkeypatch, mock_subprocess_run, mock_env):
    """Test CLI with a directory path."""
    if sys.platform == "linux":
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    dir_path, expected_files = temp_dir_with_files
    monkeypatch.setattr(sys, "argv", ["fileclip", dir_path])
    main()
    captured = capsys.readouterr()
    assert "Files copied to clipboard" in captured.out
    mock_subprocess_run.assert_called_once()
    called_args = mock_subprocess_run.call_args[0][0]
    if sys.platform == "linux":
        assert called_args[0] in ["wl-copy", "xclip"]
        assert all(f"file://{os.path.abspath(f)}" in mock_subprocess_run.call_args[1]["input"].decode() for f in expected_files)
    elif sys.platform == "darwin":
        assert called_args.startswith("osascript")
        assert all(os.path.abspath(f) in called_args for f in expected_files)
    elif sys.platform == "win32":
        assert "powershell.exe" in called_args
        assert all(os.path.abspath(f) in called_args for f in expected_files)

def test_cli_mixed_files_and_directory(temp_files, temp_dir_with_files, capsys, monkeypatch, mock_subprocess_run, mock_env):
    """Test CLI with a mix of file and directory paths."""
    if sys.platform == "linux":
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    dir_path, dir_files = temp_dir_with_files
    mixed_paths = temp_files + [dir_path]
    monkeypatch.setattr(sys, "argv", ["fileclip"] + mixed_paths)
    main()
    captured = capsys.readouterr()
    assert "Files copied to clipboard" in captured.out
    mock_subprocess_run.assert_called_once()
    called_args = mock_subprocess_run.call_args[0][0]
    if sys.platform == "linux":
        assert called_args[0] in ["wl-copy", "xclip"]
        assert all(f"file://{os.path.abspath(f)}" in mock_subprocess_run.call_args[1]["input"].decode() for f in temp_files + dir_files)
    elif sys.platform == "darwin":
        assert called_args.startswith("osascript")
        assert all(os.path.abspath(f) in called_args for f in temp_files + dir_files)
    elif sys.platform == "win32":
        assert "powershell.exe" in called_args
        assert all(os.path.abspath(f) in called_args for f in temp_files + dir_files)

def test_cli_no_paths(capsys, monkeypatch):
    """Test CLI with no paths."""
    monkeypatch.setattr(sys, "argv", ["fileclip"])
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Error: No files specified or found in provided paths" in captured.err

def test_cli_invalid_path(capsys, monkeypatch):
    """Test CLI with an invalid path."""
    monkeypatch.setattr(sys, "argv", ["fileclip", "nonexistent_path"])
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Error: Path nonexistent_path does not exist" in captured.err

def test_cli_copy_files_failure(temp_files, capsys, monkeypatch, mock_subprocess_run, mock_env):
    """Test CLI when copy_files fails."""
    if sys.platform == "linux":
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    mock_subprocess_run.side_effect = RuntimeError("Test error")
    monkeypatch.setattr(sys, "argv", ["fileclip"] + temp_files)
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Failed to copy files: Test error" in captured.err

def test_copy_files_linux_mocked(temp_files, mock_subprocess_run, monkeypatch, mock_env):
    """Test copy_files on Linux by mocking platform."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    result = copy_files(temp_files, use_watcher=False)
    assert result is True
    mock_subprocess_run.assert_called_once()
    assert mock_subprocess_run.call_args[0][0][0] in ["wl-copy", "xclip"]
    assert mock_subprocess_run.call_args[1]["input"].decode().startswith("file://")

def test_copy_files_macos_mocked(temp_files, mock_subprocess_run, monkeypatch, mock_env):
    """Test copy_files on macOS by mocking platform."""
    monkeypatch.setattr(sys, "platform", "darwin")
    result = copy_files(temp_files, use_watcher=False)
    assert result is True
    mock_subprocess_run.assert_called_once()
    assert mock_subprocess_run.call_args[0][0].startswith("osascript")
    assert all(os.path.abspath(f) in mock_subprocess_run.call_args[0][0] for f in temp_files)

def test_copy_files_windows_mocked(temp_files, mock_subprocess_run, mock_env):
    """Test copy_files on Windows by mocking platform."""
    with patch("sys.platform", "win32"):
        result = copy_files(temp_files, use_watcher=False)
        assert result is True
        mock_subprocess_run.assert_called_once()
        assert "powershell.exe" in mock_subprocess_run.call_args[0][0]
        assert all(os.path.abspath(f) in mock_subprocess_run.call_args[0][0] for f in temp_files)

def test_copy_files_with_watcher(temp_files, mock_container, mock_env, mock_file_io, mock_watchdog_observer, mock_subprocess_run):
    """Test copy_files with watcher mode."""
    env = mock_env
    shared_dir = Path(env['container_workspace']) / ".fileclip"
    shared_dir.mkdir(parents=True, exist_ok=True)
    open_mock, load_mock, dump_mock = mock_file_io
    open_mock.return_value = MagicMock()  # Mock file context
    load_mock.return_value = {"success": True, "message": "Copied 3 files"}
    
    with patch("fileclip.file_clip.check_watcher", return_value=True):
        with patch("fileclip.file_clip.wait_for_results", return_value={"success": True, "message": "Copied 3 files"}):
            result = copy_files(temp_files, use_watcher=True)
            assert result is True
            dump_mock.assert_called()  # JSON dump for fileclip_<uuid>.json
            load_mock.assert_not_called()  # Since wait_for_results is mocked, load is not called in test
            mock_subprocess_run.assert_not_called()  # No fallback to direct copy

def test_copy_files_watcher_failure(temp_files, mock_container, mock_env, mock_subprocess_run, mock_file_io, mock_watchdog_observer):
    """Test copy_files with watcher failure and fallback."""
    env = mock_env
    shared_dir = Path(env['container_workspace']) / ".fileclip"
    shared_dir.mkdir(parents=True, exist_ok=True)
    open_mock, load_mock, dump_mock = mock_file_io
    open_mock.return_value = MagicMock()
    load_mock.return_value = {"success": False, "message": "Watcher error"}
    
    with patch("fileclip.file_clip.check_watcher", return_value=True):
        with patch("fileclip.file_clip.wait_for_results", return_value={"success": False, "message": "Watcher error"}):
            result = copy_files(temp_files, use_watcher=True)
            assert result is True  # Fallback succeeds
            dump_mock.assert_called()  # JSON dump for fileclip_<uuid>.json
            load_mock.assert_not_called()  # Since wait_for_results is mocked, load is not called in test
            mock_subprocess_run.assert_called()  # Fallback called _copy_files_direct

def test_copy_files_no_watcher(temp_files, mock_container, mock_subprocess_run, mock_env):
    """Test copy_files with watcher disabled."""
    result = copy_files(temp_files, use_watcher=False)
    assert result is True
    mock_subprocess_run.assert_called()

def test_collect_files(temp_files, temp_dir_with_files):
    """Test collect_files for files and directories."""
    dir_path, dir_files = temp_dir_with_files
    files = collect_files(temp_files + [dir_path])
    assert set(files) == set(temp_files + dir_files)

def test_collect_files_invalid():
    """Test collect_files with invalid path."""
    with pytest.raises(FileNotFoundError, match="Path nonexistent does not exist"):
        collect_files(["nonexistent"])


