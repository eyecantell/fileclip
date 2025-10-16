import pytest
import json
import logging
import sys
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from fileclip.fileclip_watcher import setup_logging, FileclipHandler, process_file, write_result, main

# Skip watcher tests on macOS if watcher is Windows-only (optional, remove if not needed)
# pytestmark = pytest.mark.skipif(sys.platform == "darwin", reason="Watcher is Windows-only")

# Fixture for temporary shared directory
@pytest.fixture
def shared_dir(tmp_path):
    """Create a temporary shared directory for testing."""
    shared_dir = tmp_path / ".fileclip"
    shared_dir.mkdir(parents=True, exist_ok=True)
    yield shared_dir
    # Ensure logging is shut down to flush files
    logging.shutdown()

# Fixture for mocking file I/O
@pytest.fixture
def mock_file_io():
    """Mock file I/O operations."""
    with patch("builtins.open", new_callable=mock_open) as mock_file, \
         patch("json.load") as mock_load, \
         patch("json.dump") as mock_dump:
        mock_file.return_value.__enter__.return_value = MagicMock()
        yield mock_file, mock_load, mock_dump

# Fixture for mocking watchdog observer
@pytest.fixture
def mock_watchdog_observer():
    """Mock watchdog observer and event handler."""
    with patch("fileclip.fileclip_watcher.Observer") as mock_observer:
        mock_observer_instance = MagicMock()
        mock_observer.return_value = mock_observer_instance
        yield mock_observer

# Fixture for mocking copy_files
@pytest.fixture
def mock_copy_files():
    """Mock fileclip.file_clip.copy_files."""
    with patch("fileclip.fileclip_watcher.copy_files") as mock_copy:
        mock_copy.return_value = True
        yield mock_copy

# Fixture for temporary files
@pytest.fixture
def temp_files(tmp_path):
    """Create temporary files for testing."""
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.pdf"
    file1.write_text("File 1 content")
    file2.write_text("File 2 content")
    return [str(file1), str(file2)]

# Test setup_logging
def test_setup_logging(shared_dir, caplog):
    """Test logging setup."""
    log_file = shared_dir / "fileclip_watcher.log"
    caplog.set_level(logging.INFO)
    
    # Explicitly create a FileHandler to ensure file creation
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.handlers = [handler]
    
    setup_logging(log_file, "INFO")
    logging.info("Test log message")
    
    assert log_file.exists()
    with open(log_file, "r") as f:
        log_content = f.read()
    assert "Test log message" in log_content
    assert "INFO" in log_content

def test_setup_logging_invalid_level(shared_dir, caplog):
    """Test setup_logging with invalid log level."""
    log_file = shared_dir / "fileclip_watcher.log"
    caplog.set_level(logging.WARNING)
    
    # Explicitly create a FileHandler to ensure file creation
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)
    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.handlers = [handler]
    
    setup_logging(log_file, "INVALID")
    assert logging.getLogger().level == logging.INFO  # Falls back to INFO
    logging.warning("Test log message")  # Use warning to match caplog level
    assert log_file.exists()
    with open(log_file, "r") as f:
        log_content = f.read()
    assert "Test log message" in log_content

# Test FileclipHandler
def test_fileclip_handler_init(shared_dir):
    """Test FileclipHandler initialization."""
    handler = FileclipHandler(shared_dir)
    assert handler.shared_dir == shared_dir
    assert handler.patterns == ["fileclip_*.json"]

def test_fileclip_handler_on_created(shared_dir, mock_copy_files):
    """Test FileclipHandler on_created method."""
    handler = FileclipHandler(shared_dir)
    event = MagicMock()
    event.is_directory = False
    event.src_path = str(shared_dir / "fileclip_test-uuid.json")
    
    with patch("fileclip.fileclip_watcher.process_file") as mock_process:
        handler.on_created(event)
        mock_process.assert_called_once_with(Path(event.src_path), shared_dir)

def test_fileclip_handler_on_created_directory(shared_dir):
    """Test FileclipHandler ignores directory events."""
    handler = FileclipHandler(shared_dir)
    event = MagicMock()
    event.is_directory = True
    event.src_path = str(shared_dir / "some_dir")
    
    with patch("fileclip.fileclip_watcher.process_file") as mock_process:
        handler.on_created(event)
        mock_process.assert_not_called()

def test_fileclip_handler_on_created_non_matching(shared_dir):
    """Test FileclipHandler ignores non-matching files."""
    handler = FileclipHandler(shared_dir)
    event = MagicMock()
    event.is_directory = False
    event.src_path = str(shared_dir / "non_fileclip_file.txt")
    
    with patch("fileclip.fileclip_watcher.process_file") as mock_process:
        handler.on_created(event)
        mock_process.assert_not_called()

# Test process_file
def test_process_file_ping(shared_dir, mock_file_io):
    """Test process_file with ping action."""
    file_path = shared_dir / "fileclip_test-uuid.json"
    json_data = {
        "action": "ping",
        "sender": "container_test-host_1234",
        "request_id": "test-uuid"
    }
    open_mock, load_mock, dump_mock = mock_file_io
    load_mock.return_value = json_data
    
    with patch("pathlib.Path.unlink") as mock_unlink:
        process_file(file_path, shared_dir)
        dump_mock.assert_called_once()
        result = dump_mock.call_args[0][0]
        assert result["success"] is True
        assert result["message"] == "Ping acknowledged"
        assert result["sender"] == "container_test-host_1234"
        assert result["request_id"] == "test-uuid"
        mock_unlink.assert_called_once_with(missing_ok=True)

def test_process_file_copy_files_valid(shared_dir, temp_files, mock_file_io, mock_copy_files):
    """Test process_file with valid copy_files action."""
    file_path = shared_dir / "fileclip_test-uuid.json"
    json_data = {
        "action": "copy_files",
        "sender": "container_test-host_1234",
        "request_id": "test-uuid",
        "paths": temp_files
    }
    open_mock, load_mock, dump_mock = mock_file_io
    load_mock.return_value = json_data
    
    with patch("pathlib.Path.unlink") as mock_unlink:
        process_file(file_path, shared_dir)
        mock_copy_files.assert_called_once_with(temp_files, use_watcher=False)
        dump_mock.assert_called_once()
        result = dump_mock.call_args[0][0]
        assert result["success"] is True
        assert result["message"] == f"Copied {len(temp_files)} file(s)"
        assert result["sender"] == "container_test-host_1234"
        assert result["request_id"] == "test-uuid"
        assert result["errors"] == []
        mock_unlink.assert_called_once_with(missing_ok=True)

def test_process_file_copy_files_invalid_path(shared_dir, mock_file_io, mock_copy_files):
    """Test process_file with invalid paths."""
    file_path = shared_dir / "fileclip_test-uuid.json"
    json_data = {
        "action": "copy_files",
        "sender": "container_test-host_1234",
        "request_id": "test-uuid",
        "paths": ["nonexistent.txt"]
    }
    open_mock, load_mock, dump_mock = mock_file_io
    load_mock.return_value = json_data
    
    with patch("pathlib.Path.unlink") as mock_unlink:
        process_file(file_path, shared_dir)
        mock_copy_files.assert_not_called()
        dump_mock.assert_called_once()
        result = dump_mock.call_args[0][0]
        assert result["success"] is False
        assert result["message"] == "No valid files to copy"
        assert result["errors"] == ["Invalid or inaccessible path: nonexistent.txt"]
        mock_unlink.assert_called_once_with(missing_ok=True)

def test_process_file_copy_files_mixed_paths(shared_dir, temp_files, mock_file_io, mock_copy_files):
    """Test process_file with mixed valid and invalid paths."""
    file_path = shared_dir / "fileclip_test-uuid.json"
    json_data = {
        "action": "copy_files",
        "sender": "container_test-host_1234",
        "request_id": "test-uuid",
        "paths": temp_files + ["nonexistent.txt"]
    }
    open_mock, load_mock, dump_mock = mock_file_io
    load_mock.return_value = json_data
    
    with patch("pathlib.Path.unlink") as mock_unlink:
        process_file(file_path, shared_dir)
        mock_copy_files.assert_called_once_with(temp_files, use_watcher=False)
        dump_mock.assert_called_once()
        result = dump_mock.call_args[0][0]
        assert result["success"] is True
        assert result["message"] == f"Copied {len(temp_files)} file(s)"
        assert result["errors"] == ["Invalid or inaccessible path: nonexistent.txt"]
        mock_unlink.assert_called_once_with(missing_ok=True)

def test_process_file_invalid_json(shared_dir, mock_file_io):
    """Test process_file with invalid JSON."""
    file_path = shared_dir / "fileclip_test-uuid.json"
    open_mock, load_mock, dump_mock = mock_file_io
    load_mock.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
    
    with patch("pathlib.Path.unlink") as mock_unlink:
        process_file(file_path, shared_dir)
        dump_mock.assert_called_once()
        result = dump_mock.call_args[0][0]
        assert result["success"] is False
        assert result["message"] == "Invalid JSON"
        assert result["sender"] == "unknown"
        assert result["request_id"] == "unknown"
        mock_unlink.assert_called_once_with(missing_ok=True)

def test_process_file_missing_fields(shared_dir, mock_file_io):
    """Test process_file with missing request_id or sender."""
    file_path = shared_dir / "fileclip_test-uuid.json"
    json_data = {
        "action": "ping"
        # Missing sender and request_id
    }
    open_mock, load_mock, dump_mock = mock_file_io
    load_mock.return_value = json_data
    
    with patch("pathlib.Path.unlink") as mock_unlink:
        process_file(file_path, shared_dir)
        dump_mock.assert_called_once()
        result = dump_mock.call_args[0][0]
        assert result["success"] is False
        assert result["message"] == "Missing request_id or sender"
        mock_unlink.assert_called_once_with(missing_ok=True)

def test_process_file_unknown_action(shared_dir, mock_file_io):
    """Test process_file with unknown action."""
    file_path = shared_dir / "fileclip_test-uuid.json"
    json_data = {
        "action": "invalid_action",
        "sender": "container_test-host_1234",
        "request_id": "test-uuid"
    }
    open_mock, load_mock, dump_mock = mock_file_io
    load_mock.return_value = json_data
    
    with patch("pathlib.Path.unlink") as mock_unlink:
        process_file(file_path, shared_dir)
        dump_mock.assert_called_once()
        result = dump_mock.call_args[0][0]
        assert result["success"] is False
        assert result["message"] == "Unknown action: invalid_action"
        mock_unlink.assert_called_once_with(missing_ok=True)

def test_process_file_copy_files_error(shared_dir, temp_files, mock_file_io, mock_copy_files):
    """Test process_file when copy_files raises an error."""
    file_path = shared_dir / "fileclip_test-uuid.json"
    json_data = {
        "action": "copy_files",
        "sender": "container_test-host_1234",
        "request_id": "test-uuid",
        "paths": temp_files
    }
    open_mock, load_mock, dump_mock = mock_file_io
    load_mock.return_value = json_data
    mock_copy_files.side_effect = RuntimeError("Clipboard error")
    
    with patch("pathlib.Path.unlink") as mock_unlink:
        process_file(file_path, shared_dir)
        mock_copy_files.assert_called_once_with(temp_files, use_watcher=False)
        dump_mock.assert_called_once()
        result = dump_mock.call_args[0][0]
        assert result["success"] is False
        assert result["message"] == "Failed to copy files: Clipboard error"
        assert "Clipboard error" in result["errors"]
        mock_unlink.assert_called_once_with(missing_ok=True)

# Test write_result
def test_write_result(shared_dir, mock_file_io):
    """Test write_result function."""
    result = {
        "sender": "container_test-host_1234",
        "request_id": "test-uuid",
        "success": True,
        "message": "Test result",
        "errors": []
    }
    open_mock, load_mock, dump_mock = mock_file_io
    write_result(shared_dir, "test-uuid", result)
    dump_mock.assert_called_once_with(result, open_mock.return_value.__enter__.return_value)
    open_mock.assert_called_once_with(shared_dir / "fileclip_results_test-uuid.json", "w")

def test_write_result_io_error(shared_dir, caplog):
    """Test write_result with I/O error."""
    result = {
        "sender": "container_test-host_1234",
        "request_id": "test-uuid",
        "success": True,
        "message": "Test result",
        "errors": []
    }
    # Mock open specifically for write_result to raise OSError
    with patch("builtins.open", new_callable=mock_open) as mock_file:
        mock_file.side_effect = OSError("Permission denied")
        caplog.set_level(logging.ERROR)
        write_result(shared_dir, "test-uuid", result)
        assert "Failed to write result" in caplog.text
        assert "Permission denied" in caplog.text
        mock_file.assert_called_once_with(shared_dir / "fileclip_results_test-uuid.json", "w")

# Test main
def test_main(shared_dir, mock_watchdog_observer, mock_copy_files, monkeypatch, caplog):
    """Test main function with default settings."""
    monkeypatch.setattr("sys.argv", ["fileclip-watcher", "--log-level=DEBUG"])
    monkeypatch.setenv("FILECLIP_HOST_WORKSPACE", str(shared_dir.parent))
    caplog.set_level(logging.DEBUG)
    
    mock_observer = mock_watchdog_observer
    mock_observer_instance = mock_observer.return_value
    mock_observer_instance.start.return_value = None
    mock_observer_instance.stop.return_value = None
    mock_observer_instance.join.return_value = None
    
    with patch("time.sleep", side_effect=[None, KeyboardInterrupt]):
        main()
        assert mock_observer.called
        mock_observer_instance.schedule.assert_called_once()
        assert mock_observer_instance.schedule.call_args[0][0].__class__ == FileclipHandler
        assert mock_observer_instance.schedule.call_args[0][1] == str(shared_dir)
        assert mock_observer_instance.schedule.call_args[1]["recursive"] is False
        mock_observer_instance.start.assert_called_once()
        mock_observer_instance.stop.assert_called_once()
        mock_observer_instance.join.assert_called_once()
        
        # Check logs to diagnose early exits
        log_file = shared_dir / "fileclip_watcher.log"
        assert log_file.exists()
        with open(log_file, "r") as f:
            log_content = f.read()
        assert "Starting fileclip-watcher, monitoring" in log_content
        assert "Received shutdown signal" in log_content

def test_main_invalid_log_level(shared_dir, mock_watchdog_observer, mock_copy_files, monkeypatch, capsys):
    """Test main with invalid log level."""
    monkeypatch.setattr("sys.argv", ["fileclip-watcher", "--log-level=INVALID"])
    monkeypatch.setenv("FILECLIP_HOST_WORKSPACE", str(shared_dir.parent))
    
    mock_observer = mock_watchdog_observer
    mock_observer.start.return_value = None
    mock_observer.stop.return_value = None
    mock_observer.join.return_value = None
    
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "invalid choice: 'INVALID'" in captured.err
    log_file = shared_dir / "fileclip_watcher.log"
    assert not log_file.exists()  # Log file not created due to early exit