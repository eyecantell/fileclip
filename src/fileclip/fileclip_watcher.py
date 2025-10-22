import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers.polling import PollingObserver

from .file_clip import copy_files, FILECLIP_REQUEST_PREFIX, FILECLIP_RESULTS_PREFIX

# Use a named logger
logger = logging.getLogger("fileclip.watcher")

def setup_logging(log_file: Path, log_level: str):
    """
    Set up logging to file with specified level.
    Args:
        log_file: Path to log file.
        log_level: Logging level (e.g., DEBUG, INFO, ERROR).
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger("fileclip.watcher")
    # Reset logger state
    logger.handlers = []  # Clear existing handlers
    logger.setLevel(level)
    logger.propagate = True  # Ensure logs propagate for caplog
    handler = logging.FileHandler(log_file)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.debug(f"Logging initialized with level {log_level} to {log_file}")

def write_result(shared_dir: Path, request_id: str, result: dict):
    """
    Write result to fileclip_results_<uuid>.json.
    Args:
        shared_dir: Directory for the result file.
        request_id: UUID for the result file.
        result: Result dictionary to write.
    """
    result_file = shared_dir / f"{FILECLIP_RESULTS_PREFIX}{request_id}.json"
    try:
        with open(result_file, "w") as f:
            json.dump(result, f)
        logger.info(f"Wrote result to {result_file}")
    except OSError as e:
        logger.error(f"Failed to write result to {result_file}: {str(e)}")

def process_file(file_path: Path, shared_dir: Path):
    """
    Process a fileclip JSON file.
    Args:
        file_path: Path to the JSON file.
        shared_dir: Directory for results.
    """
    logger.debug(f"Starting to process file: {file_path}")
    result = {
        "success": False,
        "message": "",
        "sender": "unknown",
        "request_id": "unknown",
        "errors": []
    }

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        logger.debug(f"Successfully read JSON from {file_path}: {data}")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {file_path}")
        result["message"] = "Invalid JSON"
        write_result(shared_dir, "unknown", result)
        file_path.unlink(missing_ok=True)
        return
    except OSError as e:
        logger.error(f"Error processing {file_path}: {str(e)}")
        result["message"] = f"Failed to read file: {str(e)}"
        write_result(shared_dir, "unknown", result)
        file_path.unlink(missing_ok=True)
        return

    # Check for missing sender or request_id directly
    if "sender" not in data or "request_id" not in data:
        result["message"] = "Missing request_id or sender"
        write_result(shared_dir, result["request_id"], result)
        file_path.unlink(missing_ok=True)
        return

    result["sender"] = data.get("sender", "unknown")
    result["request_id"] = data.get("request_id", "unknown")

    action = data.get("action")
    if action == "ping":
        result["success"] = True
        result["message"] = "Ping acknowledged"
        write_result(shared_dir, result["request_id"], result)
    elif action == "copy_files":
        paths = data.get("paths", [])
        valid_paths = []
        errors = []
        for path in paths:
            path_obj = Path(path)
            if path_obj.is_file():
                valid_paths.append(str(path_obj))
            else:
                errors.append(f"Invalid or inaccessible path: {path}")
                logger.error(f"Invalid path: {path}")
        if valid_paths:
            try:
                logger.debug(f"Calling copy_files with paths: {valid_paths}")
                success = copy_files(valid_paths, use_watcher=False)
                result["success"] = success
                result["message"] = f"Copied {len(valid_paths)} file(s)" if success else "Failed to copy files"
                result["errors"] = errors
                logger.info(result["message"])
            except Exception as e:  # pylint: disable=broad-except
                logger.error(f"Failed to copy files: {str(e)}")
                result["message"] = f"Failed to copy files: {str(e)}"
                result["errors"] = [str(e)] + errors
        else:
            result["message"] = "No valid files to copy"
            result["errors"] = errors
            logger.error(result["message"])
        write_result(shared_dir, result["request_id"], result)
    else:
        result["message"] = f"Unknown action: {action}"
        logger.error(result["message"])
        write_result(shared_dir, result["request_id"], result)

    file_path.unlink(missing_ok=True)
    logger.debug(f"Finished processing file: {file_path}")

class FileclipHandler(PatternMatchingEventHandler):
    """
    Watchdog handler for fileclip JSON files.
    Args:
        shared_dir: Directory to monitor and write results to.
    """

    def __init__(self, shared_dir: Path):
        super().__init__(patterns=[f"{FILECLIP_REQUEST_PREFIX}*.json"], ignore_directories=True)
        self.shared_dir = shared_dir
        logger.debug(f"Initialized FileclipHandler for {shared_dir}")

    def on_created(self, event):
        """
        Handle file creation events.
        Args:
            event: Watchdog event object.
        """
        logger.debug(f"Received watchdog event: {event}")
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if file_path.name.startswith(FILECLIP_REQUEST_PREFIX) and file_path.suffix == ".json":
            logger.debug(f"Detected new request file: {file_path}")
            process_file(file_path, self.shared_dir)
        else:
            logger.debug(f"Ignored file: {file_path}")

def main():
    """Main function to run the fileclip watcher."""
    parser = argparse.ArgumentParser(description="Fileclip watcher for container file copying")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    args = parser.parse_args()

    host_workspace = os.getenv("FILECLIP_HOST_WORKSPACE", "C:\\Temp\\fileclip")
    shared_dir = Path(host_workspace) / ".fileclip"
    log_file = shared_dir / "fileclip_watcher.log"

    setup_logging(log_file, args.log_level)
    logger.info(f"Starting fileclip-watcher, monitoring {shared_dir}")

    observer = PollingObserver(timeout=.1)
    observer.schedule(FileclipHandler(shared_dir), str(shared_dir), recursive=False)
    observer.start()
    logger.debug("PollingObserver started")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        observer.stop()

    observer.join()

if __name__ == "__main__":
    main()