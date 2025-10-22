import json
import os
import time
import pytest
import logging
import threading
from pathlib import Path
from unittest.mock import patch
from fileclip.fileclip_watcher import main as watcher_main
from fileclip.main import main as fileclip_main

# Fixture for container and host directories
@pytest.fixture
def setup_dirs(tmp_path):
    """Set up container and host directories with .fileclip subdirs."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    (workspace / ".fileclip").mkdir()
    
    # Create a test file in workspace
    test_file = workspace / "test.txt"
    test_file.write_text("Test content")
    
    yield {
        "container_dir": workspace,  # Same as host_dir to simulate shared mount
        "host_dir": workspace,
        "test_file": test_file,
        "host_test_file": workspace / "test.txt"
    }

# Fixture to mock _copy_files_direct to avoid clipboard access
@pytest.fixture
def mock_direct_copy():
    """Mock fileclip.file_clip._copy_files_direct to avoid clipboard access."""
    with patch("fileclip.file_clip._copy_files_direct") as mock_direct:
        mock_direct.return_value = True
        yield mock_direct

# Fixture to mock environment variables
@pytest.fixture
def mock_env(setup_dirs):
    """Set up environment variables for container and host."""
    env_vars = {
        "FILECLIP_CONTAINER_WORKSPACE": str(setup_dirs["container_dir"]),
        "FILECLIP_HOST_WORKSPACE": str(setup_dirs["host_dir"]),
        "FILECLIP_USE_WATCHER": "true"
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars

# Fixture to mock is_container to always return True
@pytest.fixture
def mock_is_container():
    """Mock fileclip.main.is_container to simulate container environment."""
    with patch("fileclip.main.is_container", return_value=True):
        yield

# Fixture to mock check_watcher
@pytest.fixture
def mock_check_watcher():
    """Mock fileclip.file_clip.check_watcher to return True."""
    with patch("fileclip.file_clip.check_watcher", return_value=True):
        yield

# Fixture to run watcher in background
@pytest.fixture
def run_watcher(setup_dirs):
    """Run fileclip-watcher in a background thread."""
    log_file = setup_dirs["host_dir"] / ".fileclip" / "fileclip_watcher.log"
    with patch("sys.argv", ["fileclip-watcher", "--log-level", "DEBUG"]):
        watcher_thread = threading.Thread(target=watcher_main)
        watcher_thread.daemon = True
        watcher_thread.start()
        time.sleep(15)  # Increased for macOS CI reliability
        yield
        # No explicit stop needed; daemon thread exits with pytest

# Test integration of fileclip and watcher
def test_watcher_integration(setup_dirs, mock_direct_copy, mock_env, mock_is_container, mock_check_watcher, run_watcher, caplog):
    """Test fileclip-to-watcher IPC via shared directory."""
    caplog.set_level(logging.DEBUG, logger="fileclip.watcher")
    caplog.set_level(logging.DEBUG, logger="fileclip.file_clip")
    
    # Simulate running `pdm run fileclip test.txt --use-watcher --watcher-timeout 20`
    with patch("sys.argv", ["fileclip", str(setup_dirs["test_file"]), "--use-watcher", "--watcher-timeout", "30"]):
        fileclip_main()
        # Force filesystem sync to ensure request file is written
        os.sync()
    
    # Wait for watcher to process
    time.sleep(20)  # Increased for CI reliability
    
    # Check for request JSON (should be deleted by watcher)
    request_files = list((setup_dirs["container_dir"] / ".fileclip").glob("fileclip_request_*.json"))
    assert len(request_files) == 0, f"Request JSON not cleaned up by watcher: {request_files}"
    
    # Check watcher log
    log_file = setup_dirs["host_dir"] / ".fileclip" / "fileclip_watcher.log"
    assert log_file.exists(), f"Watcher log file not created at {log_file}"
    with open(log_file, "r") as f:
        log_content = f.read()
    assert "Starting fileclip-watcher" in log_content, "Watcher did not start"
    assert "Detected new request file" in log_content, f"Watcher did not detect request JSON. Log:\n{log_content}"
    assert "Successfully read JSON" in log_content, f"Watcher did not read JSON. Log:\n{log_content}"
    assert "Copied 1 file(s)" in log_content, f"Watcher did not process copy request. Log:\n{log_content}"
    
    # Check result JSON (should be deleted by fileclip)
    result_files = list((setup_dirs["host_dir"] / ".fileclip").glob("fileclip_results_*.json"))
    assert len(result_files) == 0, f"Result JSON not cleaned up by fileclip: {result_files}. Log:\n{log_content}"
    
    # Verify _copy_files_direct was called with the correct path
    print(f"Mock direct copy call args: {mock_direct_copy.call_args}")
    mock_direct_copy.assert_called_once_with([str(setup_dirs["host_test_file"])])

# Test with invalid file
def test_watcher_invalid_file(setup_dirs, mock_direct_copy, mock_env, mock_is_container, mock_check_watcher, run_watcher, caplog):
    """Test fileclip-to-watcher with an invalid file path."""
    caplog.set_level(logging.DEBUG, logger="fileclip.watcher")
    caplog.set_level(logging.DEBUG, logger="fileclip.file_clip")
    
    invalid_file = setup_dirs["container_dir"] / "nonexistent.txt"
    with patch("sys.argv", ["fileclip", str(invalid_file)]):
        with pytest.raises(SystemExit):
            fileclip_main()
    
    # Wait for watcher (shouldn't process due to early failure)
    time.sleep(10)  # Increased for CI reliability
    
    # Check watcher log (no copy should occur)
    log_file = setup_dirs["host_dir"] / ".fileclip" / "fileclip_watcher.log"
    assert log_file.exists(), f"Watcher log file not created at {log_file}"
    with open(log_file, "r") as f:
        log_content = f.read()
    assert "Starting fileclip-watcher" in log_content, "Watcher did not start"
    assert "Copied" not in log_content, f"Watcher processed invalid file. Log:\n{log_content}"
    
    # No result JSON should exist
    result_files = list((setup_dirs["host_dir"] / ".fileclip").glob("fileclip_results_*.json"))
    assert len(result_files) == 0, f"Unexpected result JSON found: {result_files}. Log:\n{log_content}"
    
    # _copy_files_direct should not be called
    mock_direct_copy.assert_not_called()