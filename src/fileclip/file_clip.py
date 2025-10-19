import os
import subprocess
import sys
import json
import uuid
import time
import socket
from pathlib import Path
from typing import List, Union
from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver as Observer

def is_container() -> bool:
    """
    Detect if running in a container environment.
    Returns:
        bool: True if in a container, False otherwise.
    """
    return (
        os.getenv("DEV_CONTAINER") is not None
        or Path("/.dockerenv").exists()
        or Path("/vscode").exists()
    )

def translate_path(container_path: Union[str, os.PathLike], container_workspace: str, host_workspace: str) -> str:
    """
    Translate a container path to its host equivalent.
    Args:
        container_path: Path in the container.
        container_workspace: Container workspace root (e.g., /mounted/dev).
        host_workspace: Host workspace root (e.g., C:\\Users\\user\\dev).
    Returns:
        str: Translated host path.
    Raises:
        ValueError: If path is not under container_workspace.
    """
    container_path = str(Path(container_path).resolve())
    container_workspace = str(Path(container_workspace).resolve())
    
    if not container_path.startswith(container_workspace):
        raise ValueError(f"Path {container_path} is not under {container_workspace}")
    
    rel_path = container_path[len(container_workspace):].lstrip('/\\')
    rel_path = rel_path.replace('/', '\\')
    
    host_workspace = host_workspace.replace('/', '\\')
    host_path = host_workspace.rstrip('\\') + '\\' + rel_path
    
    return host_path

def validate_path(path: Union[str, os.PathLike], container_workspace: str) -> bool:
    """
    Validate that a path is under the container workspace.
    Args:
        path: Path to validate.
        container_workspace: Container workspace root.
    Returns:
        bool: True if valid, False otherwise.
    """
    try:
        path = Path(path).resolve()
        container_workspace = Path(container_workspace).resolve()
        return str(path).startswith(str(container_workspace))
    except (OSError, ValueError):
        return False

class ResultsHandler(FileSystemEventHandler):
    """Handler to detect fileclip_results_<uuid>.json creation."""
    def __init__(self, results_path: Path, results: dict):
        self.results_path = results_path
        self.results = results

    def on_created(self, event):
        if not event.is_directory and Path(event.src_path).name == self.results_path.name:
            self.results["found"] = True

def wait_for_results(shared_dir: Path, request_id: str, timeout: float = 10.0) -> dict:
    """
    Wait for fileclip_results_<uuid>.json using watchdog.
    Args:
        shared_dir: Directory containing results file.
        request_id: UUID for the results file.
        timeout: Max wait time in seconds.
    Returns:
        dict: Results from fileclip_results_<uuid>.json or {"success": False, "message": "Timeout"}.
    """
    results_path = shared_dir / f"fileclip_results_{request_id}.json"
    results = {"found": False}
    handler = ResultsHandler(results_path, results)
    observer = Observer()
    observer.schedule(handler, str(shared_dir), recursive=False)
    observer.start()
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        if results["found"] and results_path.exists():
            try:
                with open(results_path, "r") as f:
                    data = json.load(f)
                results_path.unlink(missing_ok=True)  # Delete after reading
                observer.stop()
                observer.join()
                return data
            except (json.JSONDecodeError, OSError):
                pass
        time.sleep(0.1)
    
    observer.stop()
    observer.join()
    return {"success": False, "message": f"Timeout waiting for results after {timeout}s"}

def check_watcher(shared_dir: Path, timeout: float = 5.0) -> bool:
    """
    Test if the watcher is running by writing a ping file.
    Args:
        shared_dir: Directory for fileclip_<uuid>.json.
        timeout: Max wait time in seconds.
    Returns:
        bool: True if watcher responds, False otherwise.
    """
    request_id = str(uuid.uuid4())
    ping_file = shared_dir / f"fileclip_{request_id}.json"
    ping_data = {
        "action": "ping",
        "sender": f"container_{socket.gethostname()}_{os.getpid()}",
        "request_id": request_id
    }
    try:
        shared_dir.mkdir(parents=True, exist_ok=True)
        with open(ping_file, "w") as f:
            json.dump(ping_data, f)
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not ping_file.exists():
                return True
            time.sleep(0.1)
        return False
    except OSError:
        return False
    finally:
        ping_file.unlink(missing_ok=True)

def write_fileclip_json(shared_dir: Path, paths: List[str], sender: str) -> tuple[str, Path]:
    """
    Write fileclip_<uuid>.json with paths to copy.
    Args:
        shared_dir: Directory for fileclip_<uuid>.json.
        paths: List of host paths to copy.
        sender: Sender identifier (e.g., container_<hostname>_<pid>).
    Returns:
        tuple: (request_id, json_file_path).
    """
    request_id = str(uuid.uuid4())
    json_file = shared_dir / f"fileclip_{request_id}.json"
    data = {
        "action": "copy_files",
        "sender": sender,
        "request_id": request_id,
        "paths": paths
    }
    shared_dir.mkdir(parents=True, exist_ok=True)
    with open(json_file, "w") as f:
        json.dump(data, f)
    return request_id, json_file

def copy_files(file_paths: List[Union[str, os.PathLike]], use_watcher: bool = None, watcher_timeout: float = 10.0) -> bool:
    """
    Copy a list of file paths to the system clipboard as file references.
    Args:
        file_paths: List of file paths (absolute or relative) or PathLike objects.
        use_watcher: True to force watcher, False to disable, None to auto-detect.
        watcher_timeout: Timeout for watcher operations.
    Returns:
        bool: True if successful, False otherwise.
    Raises:
        FileNotFoundError: If any file path is invalid.
        RuntimeError: If the platform or clipboard operation is unsupported.
        ValueError: If watcher is used but paths are invalid or env vars are missing.
    """
    # Validate file paths
    valid_paths = []
    for path in file_paths:
        abs_path = Path(path).resolve()
        if not abs_path.is_file():
            raise FileNotFoundError(f"File not found or not a file: {path}")
        valid_paths.append(str(abs_path))

    if not valid_paths:
        print("No valid files to copy.")
        return False

    # Container and watcher logic
    container_workspace = os.getenv("FILECLIP_CONTAINER_WORKSPACE")
    host_workspace = os.getenv("FILECLIP_HOST_WORKSPACE")
    shared_dir = Path(container_workspace) / ".fileclip" if container_workspace else Path("/tmp/fileclip/.fileclip")
    
    use_watcher_env = os.getenv("FILECLIP_USE_WATCHER", "true" if is_container() else "false").lower() == "true"
    use_watcher = use_watcher_env if use_watcher is None else use_watcher

    if is_container() and use_watcher:
        if not (container_workspace and host_workspace):
            raise ValueError("FILECLIP_CONTAINER_WORKSPACE and FILECLIP_HOST_WORKSPACE must be set for watcher mode")
        
        # Validate and translate paths
        translated_paths = []
        for path in valid_paths:
            if not validate_path(path, container_workspace):
                raise ValueError(f"Path {path} is not under {container_workspace}")
            translated_paths.append(translate_path(path, container_workspace, host_workspace))
        
        # Test watcher
        if not check_watcher(shared_dir):
            print("Warning: Watcher not running; files may not copy to host clipboard. See README for setup.")
            return _copy_files_direct(valid_paths)  # Fallback to direct copy
        
        # Write fileclip_<uuid>.json
        sender = f"container_{socket.gethostname()}_{os.getpid()}"
        request_id, json_file = write_fileclip_json(shared_dir, translated_paths, sender)
        
        # Wait for results
        results = wait_for_results(shared_dir, request_id, watcher_timeout)
        if results.get("success", False):
            print(f"Files copied to clipboard via watcher: {results.get('message', '')}")
            return True
        else:
            print(f"Watcher failed: {results.get('message', 'Unknown error')}")
            for error in results.get("errors", []):
                print(f"Error: {error}")
            return _copy_files_direct(valid_paths)  # Fallback to direct copy

    return _copy_files_direct(valid_paths)

def _copy_files_direct(file_paths: List[str]) -> bool:
    """Direct clipboard copy using subprocess (internal)."""
    if sys.platform == "win32":  # Windows
        paths = ','.join(f'"{p}"' for p in file_paths)
        cmd = f'powershell.exe -Command "Set-Clipboard -Path {paths}"'
        print(f"Executing Windows command: {cmd}")
        try:
            subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=5, check=True, env=os.environ.copy()
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Windows clipboard error: {e.stderr}")
        print("Files copied to clipboard (Windows).")
        return True

    elif sys.platform == "darwin":  # macOS
        files = ', '.join(f'POSIX file "{p}"' for p in file_paths)
        cmd = f'osascript -e \'tell app "Finder" to set the clipboard to {{{files}}}\''
        print(f"Executing macOS command: {cmd}")
        try:
            subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=5, check=True, env=os.environ.copy()
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"macOS clipboard error: {e.stderr}")
        print("Files copied to clipboard (macOS).")
        return True

    elif sys.platform == "linux":  # Linux (try wl-clipboard, then xclip)
        uris = '\n'.join(f'file://{p}' for p in file_paths)
        env = os.environ.copy()
        if not env.get('XDG_RUNTIME_DIR') and hasattr(os, 'getuid'):
            env['XDG_RUNTIME_DIR'] = f"/run/user/{os.getuid()}"

        if os.getenv("WAYLAND_DISPLAY"):
            print(f"Attempting Wayland clipboard with wl-copy (WAYLAND_DISPLAY={os.getenv('WAYLAND_DISPLAY')}, XDG_RUNTIME_DIR={env.get('XDG_RUNTIME_DIR')})")
            cmd = ['wl-copy', '--type', 'text/uri-list']
            print(f"Executing Wayland command: {' '.join(cmd)} with input:\n{uris}")
            try:
                subprocess.run(
                    cmd, input=uris.encode(), capture_output=True, check=True, timeout=5, env=env
                )
                print("Files copied to clipboard (Wayland).")
                return True
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Wayland clipboard error: {e.stderr.decode('utf-8', errors='replace')}")
            except FileNotFoundError:
                print("wl-clipboard not found, falling back to xclip.")
            except subprocess.TimeoutExpired as e:
                print(f"Wayland clipboard operation timed out: cmd={e.cmd}, timeout={e.timeout}, stdout={e.stdout.decode('utf-8', errors='replace') if e.stdout else 'None'}, stderr={e.stderr.decode('utf-8', errors='replace') if e.stderr else 'None'}")
                print("Falling back to xclip.")

        if os.getenv("DISPLAY"):
            print(f"Attempting X11 clipboard with xclip (DISPLAY={os.getenv('DISPLAY')})")
            cmd = ['xclip', '-selection', 'clipboard', '-t', 'text/uri-list']
            print(f"Executing X11 command: {' '.join(cmd)} with input:\n{uris}")
            try:
                subprocess.run(
                    cmd, input=uris.encode(), capture_output=True, check=True, timeout=5, env=env
                )
                print("Files copied to clipboard (X11).")
                return True
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"X11 clipboard error: {e.stderr.decode('utf-8', errors='replace')}")
            except FileNotFoundError:
                raise RuntimeError("xclip not found. Install with 'sudo apt install xclip' or equivalent.")
            except subprocess.TimeoutExpired as e:
                print(f"X11 clipboard operation timed out: cmd={e.cmd}, timeout={e.timeout}, stdout={e.stdout.decode('utf-8', errors='replace') if e.stdout else 'None'}, stderr={e.stderr.decode('utf-8', errors='replace') if e.stderr else 'None'}")

        print("No functional display server detected (WAYLAND_DISPLAY or DISPLAY set but unresponsive).")
        print("File URIs (copy manually):")
        for uri in uris.split('\n'):
            print(uri)
        return False

    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")