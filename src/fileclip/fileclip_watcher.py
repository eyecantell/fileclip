import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import sys
import time
import os
from pathlib import Path
from typing import List
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from fileclip.file_clip import copy_files

def setup_logging(log_file: Path, log_level: str):
    """
    Set up logging to file with specified level.
    Args:
        log_file: Path to log file.
        log_level: Logging level (e.g., DEBUG, INFO, ERROR).
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    handler = logging.FileHandler(log_file)
    handler.setLevel(level)  # Explicitly set handler level
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.handlers = [handler]
    handler.flush()  # Ensure logs are written immediately

class FileclipHandler(PatternMatchingEventHandler):
    """Handle fileclip_<uuid>.json creation events."""
    def __init__(self, shared_dir: Path):
        super().__init__(patterns=["fileclip_*.json"])
        self.shared_dir = shared_dir

    def on_created(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.name.startswith("fileclip_") and file_path.suffix == ".json":
                process_file(file_path, self.shared_dir)

def process_file(file_path: Path, shared_dir: Path):
    """
    Process a fileclip_<uuid>.json file.
    Args:
        file_path: Path to the JSON file.
        shared_dir: Directory containing the file.
    """
    try:
        logging.info(f"Processing file: {file_path}")
        with open(file_path, "r") as f:
            data = json.load(f)

        request_id = data.get("request_id")
        sender = data.get("sender")
        action = data.get("action")
        result = {"sender": sender, "request_id": request_id, "success": False, "message": "", "errors": []}

        if not request_id or not sender:
            result["message"] = "Missing request_id or sender"
            logging.error(result["message"])
            write_result(shared_dir, request_id, result)
            file_path.unlink(missing_ok=True)
            return

        if action == "ping":
            logging.info(f"Received ping from {sender}")
            result["success"] = True
            result["message"] = "Ping acknowledged"
            write_result(shared_dir, request_id, result)
            file_path.unlink(missing_ok=True)
            return

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
                    logging.error(f"Invalid path: {path}")

            if not valid_paths:
                result["message"] = "No valid files to copy"
                result["errors"] = errors
                logging.error(result["message"])
                write_result(shared_dir, request_id, result)
                file_path.unlink(missing_ok=True)
                return

            try:
                success = copy_files(valid_paths, use_watcher=False)
                result["success"] = success
                result["message"] = f"Copied {len(valid_paths)} file(s)" if success else "Failed to copy files"
                if errors:
                    result["errors"] = errors
                logging.info(result["message"])
            except Exception as e:
                result["message"] = f"Failed to copy files: {str(e)}"
                result["errors"] = errors + [str(e)]
                logging.error(result["message"])

            write_result(shared_dir, request_id, result)
            file_path.unlink(missing_ok=True)

        else:
            result["message"] = f"Unknown action: {action}"
            logging.error(result["message"])
            write_result(shared_dir, request_id, result)
            file_path.unlink(missing_ok=True)

    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in {file_path}")
        result = {"sender": "unknown", "request_id": "unknown", "success": False, "message": "Invalid JSON", "errors": []}
        write_result(shared_dir, "unknown", result)
        file_path.unlink(missing_ok=True)
    except Exception as e:
        logging.error(f"Error processing {file_path}: {str(e)}")
        result = {"sender": "unknown", "request_id": "unknown", "success": False, "message": f"Error: {str(e)}", "errors": []}
        write_result(shared_dir, "unknown", result)
        file_path.unlink(missing_ok=True)

def write_result(shared_dir: Path, request_id: str, result: dict):
    """
    Write result to fileclip_results_<uuid>.json.
    Args:
        shared_dir: Directory for the result file.
        request_id: UUID for the result file.
        result: Result dictionary to write.
    """
    result_file = shared_dir / f"fileclip_results_{request_id}.json"
    try:
        with open(result_file, "w") as f:
            json.dump(result, f)
        logging.info(f"Wrote result to {result_file}")
    except OSError as e:
        logging.error(f"Failed to write result to {result_file}: {str(e)}")

def main():
    """
    CLI entry point for fileclip-watcher.
    Monitor shared directory for fileclip_<uuid>.json files and process them.
    """
    try:
        parser = argparse.ArgumentParser(description="Fileclip watcher for copying files to host clipboard.")
        parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                            help="Logging level")
        args = parser.parse_args()
        logging.debug("Parsed arguments successfully")

        shared_dir = Path(os.getenv("FILECLIP_HOST_WORKSPACE", "C:\\Temp\\fileclip")) / ".fileclip"
        log_file = shared_dir / "fileclip_watcher.log"
        logging.debug(f"Setting up logging with file: {log_file}")

        setup_logging(log_file, args.log_level)
        logging.info(f"Starting fileclip-watcher, monitoring {shared_dir}")

        event_handler = FileclipHandler(shared_dir)
        logging.debug("Created FileclipHandler")
        observer = Observer()
        logging.debug("Instantiated Observer")
        observer.schedule(event_handler, str(shared_dir), recursive=False)
        observer.start()
        logging.debug("Started observer")

        try:
            while True:
                time.sleep(1)  # Keep observer running
        except KeyboardInterrupt:
            logging.info("Received shutdown signal, stopping observer")
            observer.stop()
        observer.join()
        logging.info("Fileclip-watcher stopped")
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()