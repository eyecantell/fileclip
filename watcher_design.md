# Fileclip Watcher Design

## Overview
The `fileclip-watcher.py` script enables seamless clipboard copying of files from a VSCode Ubuntu container to the Windows host clipboard. It monitors a shared directory for a `fileclip_request_<uuid>.json` file created by the `fileclip` module, processes the file paths, copies them to the host clipboard using `fileclip.file_clip.copy_files`, and provides feedback via `fileclip_results_<uuid>.json`. The design prioritizes reliability, simplicity, and integration with the existing `fileclip` module, using file-based IPC and the `watchdog` library for efficient event detection.

## Goals
- **Reliability**: Instantly detect and process file copy requests from the container, ensuring files reach the host clipboard.
- **Simplicity**: Keep the watcher lightweight, with business logic (path translation, validation) in `fileclip`.
- **User Experience**: Use a hidden `.fileclip` directory to avoid workspace clutter; provide clear warnings if setup is incomplete.
- **Configurability**: Support flexible usage via environment variables and CLI flags.
- **Future-Proofing**: Handle rare concurrent requests using UUID-based file naming and hostname-specific sender IDs.

## Workflow
1. **Watcher on Windows Host**:
   - Run `fileclip-watcher.py` as a background process (e.g., via Task Scheduler).
   - Monitor `<FILECLIP_HOST_WORKSPACE>/.fileclip` for `fileclip_request_<uuid>.json` using `watchdog`.
   - Read JSON (e.g., `{"action": "copy_files", "sender": "container_mycontainer_1234", "request_id": "uuid123", "paths": ["C:/Users/user/dev/file1.txt"]}`).
   - Validate paths exist, call `fileclip.file_clip.copy_files`.
   - Delete `fileclip_request_<uuid>.json`, write `fileclip_results_<uuid>.json` (e.g., `{"sender": "container_mycontainer_1234", "request_id": "uuid123", "success": true, "message": "Copied 1 file"}`).
   - Log actions to `.fileclip/fileclip_watcher.log` with timestamp, log level (e.g., INFO, ERROR), and message.

2. **Fileclip in Container**:
   - Detect container via `os.getenv('DEV_CONTAINER')`, `/.dockerenv`, or `/vscode`.
   - Require `FILECLIP_CONTAINER_WORKSPACE` (e.g., `/mounted/dev`) and `FILECLIP_HOST_WORKSPACE` (e.g., `C:\Users\user\dev`) for path translation.
   - Translate paths (e.g., `/mounted/dev/file1.txt` → `C:\Users\user\dev\file1.txt`) and validate they are within `FILECLIP_CONTAINER_WORKSPACE`.
   - If `FILECLIP_USE_WATCHER=true` or `--use-watcher`:
     - Test watcher: Write `fileclip_request_<uuid>.json` with `{"action": "ping", "sender": "container_<hostname>_<pid>", "request_id": "uuid123"}`, wait 5s for removal. If not removed, warn: "Watcher not running; files may not copy to host. See README."
     - Write `fileclip_request_<uuid>.json` with translated paths, `sender` (`container_<hostname>_<pid>` using `os.getenv('HOSTNAME')` and `os.getpid()`), and `request_id`.
     - Use `watchdog` to wait 10s for `fileclip_results_<uuid>.json`, log status, delete it.
   - Fallback to `copy_files` if watcher disabled or fails. On Linux containers, fallback requires `WAYLAND_DISPLAY` or `DISPLAY` for clipboard operations.

3. **Shared Directory**:
   - Located at `<FILECLIP_CONTAINER_WORKSPACE>/.fileclip` (e.g., `/mounted/dev/.fileclip` → `C:\Users\user\dev\.fileclip`).
   - Auto-created by `fileclip` and `watcher` if missing.
   - Files:
     - `fileclip_request_<uuid>.json`: Container writes, watcher reads/deletes.
     - `fileclip_results_<uuid>.json`: Watcher writes, container reads/deletes.
     - `fileclip_watcher.log`: Watcher logs (INFO: events, ERROR: failures).

## Key Components
- **Watcher (`fileclip-watcher.py`)**:
  - Use `watchdog.observers.polling.PollingObserver` with `PatternMatchingEventHandler(patterns=["fileclip_request_*.json"])`.
  - Process `on_created` events, validate paths, call `copy_files`, write results.
  - CLI: `fileclip-watcher --shared-dir=<path> --log-level=DEBUG`. (Note: `--shared-dir` not implemented; uses env var.)
  - Handle `Ctrl+C` for clean shutdown, stopping the `watchdog` observer gracefully.

- **Fileclip (`file_clip.py`, `main.py`)**:
  - Detect container, translate/validate paths, handle IPC.
  - CLI flags: `--use-watcher`, `--no-watcher`, `--watcher-timeout`.
  - Use `watchdog` to monitor `fileclip_results_<uuid>.json`.
  - Fallback to direct `copy_files` if needed, handling platform-specific clipboard requirements (e.g., `wl-copy`/`xclip` on Linux).
  - Directory scanning is recursive (uses `rglob`).

- **File Formats**:
  - `fileclip_request_<uuid>.json`: `{"action": "copy_files"|"ping", "sender": "container_<hostname>_<pid>", "request_id": "uuid123", "paths": ["C:/path/file1.txt"]}`
  - `fileclip_results_<uuid>.json`: `{"sender": "container_<hostname>_<pid>", "request_id": "uuid123", "success": bool, "message": str, "errors": [str]}`

## Configuration
- **Environment Variables**:
  - `FILECLIP_CONTAINER_WORKSPACE`: Required container path (e.g., `/mounted/dev`).
  - `FILECLIP_HOST_WORKSPACE`: Required host path (e.g., `C:\Users\user\dev`).
  - `FILECLIP_USE_WATCHER`: `true`/`false` (default: auto-detect container).
  - `FILECLIP_WATCHER_TIMEOUT`: Ping/results timeout in seconds (default: 5s for ping, 10s for results).