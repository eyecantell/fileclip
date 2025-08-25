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

def test_copy_files_valid_files(temp_files, mock_subprocess_run):
    """Test copy_files with valid files."""
    result = copy_files(temp_files)
    assert result is True
    if sys.platform == "win32":
        mock_subprocess_run.assert_called_once()
        cmd = mock_subprocess_run.call_args[0][0]
        assert "powershell.exe" in cmd
        assert all(os.path.abspath(f) in cmd for f in temp_files)
    elif sys.platform == "darwin":
        mock_subprocess_run.assert_called_once()
        cmd = mock_subprocess_run.call_args[0][0]
        assert "osascript" in cmd
        assert all(os.path.abspath(f) in cmd for f in temp_files)
    elif sys.platform == "linux":
        mock_subprocess_run.assert_called_once()
        assert mock_subprocess_run.call_args[0][0][0] == "xclip"
        assert "text/uri-list" in mock_subprocess_run.call_args[0][0]

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

def test_copy_files_unsupported_platform(monkeypatch):
    """Test copy_files on an unsupported platform."""
    monkeypatch.setattr(sys, "platform", "unsupported")
    with pytest.raises(RuntimeError, match="Unsupported platform: unsupported"):
        copy_files(["test.txt"])

@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
def test_copy_files_linux_xclip_missing(temp_files, monkeypatch):
    """Test copy_files on Linux when xclip is missing."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("xclip not found")
        with pytest.raises(RuntimeError, match="xclip not found.*"):
            copy_files(temp_files)

@pytest.mark.skipif(sys.platform == "darwin", reason="Non-macOS test")
def test_copy_files_windows_linux_subprocess_error(temp_files, mock_subprocess_run):
    """Test copy_files with a subprocess error on Windows/Linux."""
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["mock"], stderr="Error".encode()
    )
    with pytest.raises(RuntimeError, match="clipboard error: Error"):
        copy_files(temp_files)

@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
def test_copy_files_macos_subprocess_error(temp_files, mock_subprocess_run):
    """Test copy_files with a subprocess error on macOS."""
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd=["mock"], stderr="macOS error".encode()
    )
    with pytest.raises(RuntimeError, match="macOS clipboard error: macOS error"):
        copy_files(temp_files)

def test_copy_files_large_number_of_files(tmp_path, mock_subprocess_run):
    """Test copy_files with a large number of files."""
    files = [str(tmp_path / f"file{i}.txt") for i in range(100)]
    for f in files:
        with open(f, "w") as fp:
            fp.write("Test content")
    result = copy_files(files)
    assert result is True
    mock_subprocess_run.assert_called_once()

def test_cli_valid_files(temp_files, capsys, monkeypatch):
    """Test CLI with valid files."""
    monkeypatch.setattr(sys, "argv", ["fileclip"] + temp_files)
    with patch("fileclip.file_clip.copy_files") as mock_copy_files:
        mock_copy_files.return_value = True
        main()
        captured = capsys.readouterr()
        assert "Files copied to clipboard" in captured.out
        assert "Paste into your application" in captured.out

def test_cli_directory(temp_dir_with_files, capsys, monkeypatch):
    """Test CLI with --dir option."""
    dir_path, expected_files = temp_dir_with_files
    monkeypatch.setattr(sys, "argv", ["fileclip", "--dir", dir_path])
    with patch("fileclip.file_clip.copy_files") as mock_copy_files:
        mock_copy_files.return_value = True
        main()
        captured = capsys.readouterr()
        assert "Files copied to clipboard" in captured.out
        assert mock_copy_files.called
        called_args = mock_copy_files.call_args[0][0]
        assert all(f in called_args for f in expected_files)

def test_cli_no_files(capsys, monkeypatch):
    """Test CLI with no files or --dir."""
    monkeypatch.setattr(sys, "argv", ["fileclip"])
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Error: No files specified" in captured.out

def test_cli_invalid_dir(capsys, monkeypatch):
    """Test CLI with invalid --dir."""
    monkeypatch.setattr(sys, "argv", ["fileclip", "--dir", "nonexistent_dir"])
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "Error: Directory 'nonexistent_dir' does not exist" in captured.out

def test_cli_copy_files_failure(temp_files, capsys, monkeypatch):
    """Test CLI when copy_files fails."""
    monkeypatch.setattr(sys, "argv", ["fileclip"] + temp_files)
    with patch("fileclip.file_clip.copy_files") as mock_copy_files:
        mock_copy_files.return_value = False
        with pytest.raises(SystemExit):
            main()
        captured = capsys.readouterr()
        assert "Failed to copy files" in captured.out