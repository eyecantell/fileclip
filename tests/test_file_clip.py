import os
import sys
import pytest
import subprocess
from unittest.mock import patch
from fileclip.file_clip import copy_files
from fileclip.main import main

# Mock subprocess.run to avoid actual clipboard changes during tests
@pytest.fixture
def mock_subprocess_run():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=["mock"], returncode=0, stdout="", stderr=""
        )
        yield mock_run

@pytest.fixture
def temp_files(tmp_path):
    """Create temporary files for testing, including one with special characters."""
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.pdf"
    file3 = tmp_path / "test file@3.txt"  # Special characters
    file1.write_text("Hello, world!")
    file2.write_text("Fake PDF content")
    file3.write_text("Special char file")
    return [str(file1), str(file2), str(file3)]

@pytest.fixture
def temp_dir_with_files(tmp_path):
    """Create a temporary directory with files."""
    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()
    file1 = dir_path / "file1.txt"
    file2 = dir_path / "file2.pdf"
    file3 = dir_path / "file#3.txt"  # Special characters
    file1.write_text("File 1 content")
    file2.write_text("File 2 content")
    file3.write_text("File 3 content")
    return str(dir_path), [str(file1), str(file2), str(file3)]

def test_copy_files_valid_files(temp_files, mock_subprocess_run, monkeypatch):
    """Test copy_files with valid files."""
    if sys.platform == "linux":
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    result = copy_files(temp_files)
    assert result is True
    mock_subprocess_run.assert_called_once()
    called_args = mock_subprocess_run.call_args[0][0]
    if sys.platform == "win32":
        assert "powershell.exe" in called_args
        assert all(os.path.abspath(f) in called_args for f in temp_files)
    elif sys.platform == "darwin":
        assert called_args.startswith("osascript")
        assert all(os.path.abspath(f) in called_args for f in temp_files)
    elif sys.platform == "linux":
        assert called_args[0] in ["wl-copy", "xclip"]
        assert "text/uri-list" in called_args
        assert mock_subprocess_run.call_args[1]["input"].decode().startswith("file://")

def test_copy_files_invalid_file(temp_files):
    """Test copy_files with an invalid file."""
    invalid_files = temp_files + ["nonexistent.txt"]
    with pytest.raises(FileNotFoundError, match="File not found.*nonexistent.txt"):
        copy_files(invalid_files)

def test_copy_files_empty_list():
    """Test copy_files with an empty list."""
    result = copy_files([])
    assert result is False

def test_copy_files_directory_in_list(temp_files, tmp_path):
    """Test copy_files with a directory in the file list."""
    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()
    invalid_files = temp_files + [str(dir_path)]
    with pytest.raises(FileNotFoundError, match="File not found or not a file"):
        copy_files(invalid_files)

def test_copy_files_unsupported_platform(monkeypatch, tmp_path):
    """Test copy_files on an unsupported platform."""
    file = tmp_path / "test.txt"
    file.write_text("Test content")
    monkeypatch.setattr(sys, "platform", "unsupported")
    with pytest.raises(RuntimeError, match="Unsupported platform: unsupported"):
        copy_files([str(file)])

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_wlcopy_missing(temp_files, monkeypatch):
    """Test copy_files on Linux when wl-copy is missing but xclip is available."""
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
        result = copy_files(temp_files)
        assert result is True
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][0][0][0] == "wl-copy"
        assert mock_run.call_args_list[1][0][0][0] == "xclip"
        assert mock_run.call_args_list[1][1]["input"].decode().startswith("file://")

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_xclip_missing(temp_files, monkeypatch):
    """Test copy_files on Linux when both wl-copy and xclip are missing."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("DISPLAY", ":0")
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            FileNotFoundError("wl-copy not found"),
            FileNotFoundError("xclip not found")
        ]
        with pytest.raises(RuntimeError, match="xclip not found"):
            copy_files(temp_files)
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][0][0][0] == "wl-copy"
        assert mock_run.call_args_list[1][0][0][0] == "xclip"

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_timeout(temp_files, mock_subprocess_run, monkeypatch, capsys):
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
    result = copy_files(temp_files)
    assert result is False
    captured = capsys.readouterr()
    assert "Wayland clipboard operation timed out" in captured.out
    assert "X11 clipboard operation timed out" in captured.out
    assert "No functional display server detected" in captured.out
    assert "File URIs (copy manually):" in captured.out
    assert all(f"file://{os.path.abspath(f)}" in captured.out for f in temp_files)

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_no_display(temp_files, monkeypatch, capsys):
    """Test copy_files on Linux with no display server."""
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    result = copy_files(temp_files)
    assert result is False
    captured = capsys.readouterr()
    assert "No functional display server detected" in captured.out
    assert "File URIs (copy manually):" in captured.out
    assert all(f"file://{os.path.abspath(f)}" in captured.out for f in temp_files)

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_wlcopy_subprocess_error(temp_files, mock_subprocess_run, monkeypatch):
    """Test copy_files with a subprocess error on Wayland."""
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["wl-copy", "--type", "text/uri-list"],
        stderr=b"Wayland error"
    )
    with pytest.raises(RuntimeError, match="Wayland clipboard error: Wayland error"):
        copy_files(temp_files)

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_xclip_subprocess_error(temp_files, mock_subprocess_run, monkeypatch):
    """Test copy_files with a subprocess error on X11."""
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["xclip", "-selection", "clipboard", "-t", "text/uri-list"],
        stderr=b"X11 error"
    )
    with pytest.raises(RuntimeError, match="X11 clipboard error: X11 error"):
        copy_files(temp_files)

@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
def test_copy_files_macos_subprocess_error(temp_files, mock_subprocess_run):
    """Test copy_files with a subprocess error on macOS."""
    cmd = 'osascript -e \'tell app "Finder" to set the clipboard to {'
    cmd += ', '.join(f'POSIX file "{p}"' for p in temp_files)
    cmd += '}\''
    mock_subprocess_run.return_value = subprocess.CompletedProcess(
        args=cmd, returncode=1, stdout="", stderr="macOS error"
    )
    with pytest.raises(RuntimeError, match="macOS clipboard error: macOS error"):
        copy_files(temp_files)

@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
def test_copy_files_windows_subprocess_error(temp_files, mock_subprocess_run):
    """Test copy_files with a subprocess error on Windows."""
    paths = ','.join(f'"{p}"' for p in temp_files)
    cmd = f'powershell.exe -Command "Set-Clipboard -Path {paths}"'
    mock_subprocess_run.return_value = subprocess.CompletedProcess(
        args=cmd, returncode=1, stdout="", stderr="Windows error"
    )
    with pytest.raises(RuntimeError, match="Windows clipboard error: Windows error"):
        copy_files(temp_files)

def test_copy_files_large_number_of_files(tmp_path, mock_subprocess_run, monkeypatch):
    """Test copy_files with a large number of files."""
    if sys.platform == "linux":
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    files = [str(tmp_path / f"file{i}.txt") for i in range(100)]
    for f in files:
        with open(f, "w") as fp:
            fp.write("Test content")
    result = copy_files(files)
    assert result is True
    mock_subprocess_run.assert_called_once()
    if sys.platform == "linux":
        assert mock_subprocess_run.call_args[1]["input"].decode().startswith("file://")

def test_cli_valid_files(temp_files, capsys, monkeypatch, mock_subprocess_run):
    """Test CLI with valid files."""
    if sys.platform == "linux":
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(sys, "argv", ["fileclip"] + temp_files)
    main()
    captured = capsys.readouterr()
    assert "Files copied to clipboard" in captured.out
    assert "Paste into your application" in captured.out
    mock_subprocess_run.assert_called_once()
    if sys.platform == "linux":
        assert mock_subprocess_run.call_args[1]["input"].decode().startswith("file://")

def test_cli_directory(temp_dir_with_files, capsys, monkeypatch, mock_subprocess_run):
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

def test_cli_mixed_files_and_directory(temp_files, temp_dir_with_files, capsys, monkeypatch, mock_subprocess_run):
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
    assert "Error: No files specified or found in provided paths" in captured.out

def test_cli_invalid_path(capsys, monkeypatch):
    """Test CLI with an invalid path."""
    monkeypatch.setattr(sys, "argv", ["fileclip", "nonexistent_path"])
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Error: Path 'nonexistent_path' does not exist" in captured.out

def test_cli_copy_files_failure(temp_files, capsys, monkeypatch, mock_subprocess_run):
    """Test CLI when copy_files fails."""
    if sys.platform == "linux":
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    mock_subprocess_run.side_effect = RuntimeError("Test error")
    monkeypatch.setattr(sys, "argv", ["fileclip"] + temp_files)
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Failed to copy files: Test error" in captured.out

def test_copy_files_linux_mocked(temp_files, mock_subprocess_run, monkeypatch):
    """Test copy_files on Linux by mocking platform."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    result = copy_files(temp_files)
    assert result is True
    mock_subprocess_run.assert_called_once()
    assert mock_subprocess_run.call_args[0][0][0] in ["wl-copy", "xclip"]
    assert mock_subprocess_run.call_args[1]["input"].decode().startswith("file://")

def test_copy_files_macos_mocked(temp_files, mock_subprocess_run, monkeypatch):
    """Test copy_files on macOS by mocking platform."""
    monkeypatch.setattr(sys, "platform", "darwin")
    result = copy_files(temp_files)
    assert result is True
    mock_subprocess_run.assert_called_once()
    assert mock_subprocess_run.call_args[0][0].startswith("osascript")
    assert all(os.path.abspath(f) in mock_subprocess_run.call_args[0][0] for f in temp_files)

def test_copy_files_windows_mocked(temp_files, mock_subprocess_run, monkeypatch):
    """Test copy_files on Windows by mocking platform."""
    monkeypatch.setattr(sys, "platform", "win32")
    result = copy_files(temp_files)
    assert result is True
    mock_subprocess_run.assert_called_once()
    assert "powershell.exe" in mock_subprocess_run.call_args[0][0]
    assert all(os.path.abspath(f) in mock_subprocess_run.call_args[0][0] for f in temp_files)