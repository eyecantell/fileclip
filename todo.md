# Fileclip Watcher Architecture Changes

## Overview

This document outlines the final architecture for the Fileclip project's watcher system, focusing on the observer selection logic for cross-platform reliability. The design prioritizes native file event detection (e.g., FSEvents on macOS, inotify on Linux) by default, with an automatic fallback to polling if native detection fails. A ping test is always performed to check watcher liveness, providing clear diagnostics. Users can force polling via environment variables or CLI flags for problematic environments.

Key goals:
- **Adaptive**: Auto-detects the best observer type.
- **Diagnostic**: Always pings the watcher and warns if it's not responding.
- **Configurable**: Override with `FILECLIP_FORCE_POLLING=true` or `--force-polling`.
- **Cross-Platform**: Works in containers (e.g., Docker in VS Code) on Windows, macOS, and Linux.

## Workflow

The core flow in `file_clip.py` (container-side) for copying files using the watcher:

1. **Detect Container**: If in container and watcher mode enabled.
2. **Get Observer Type**: Run ping test → decide Native vs. Polling.
3. **Translate & Validate Paths**: Convert container paths to host equivalents.
4. **Write Request JSON**: Create `fileclip_request_<uuid>.json`.
5. **Wait for Results**: Use selected observer to monitor for `fileclip_results_<uuid>.json`.
6. **Handle Response**: Log success/failure; fallback if timeout.

### Decision Flow (Mermaid Diagram)

```mermaid
flowchart TD
    Start[copy_files()] --> Force?{FILECLIP_FORCE_POLLING?}
    Force? -->|Yes| UsePolling[Use PollingObserver]
    Force? -->|No| Ping[Run ping test<br>check_watcher()]

    Ping --> Alive?{Watcher Alive?}
    Alive? -->|Yes| UseNative[Use NativeObserver]
    Alive? -->|No| WarnDead[Warn: Watcher not responding!<br>Is fileclip-watcher running?]
    WarnDead --> UsePolling

    UsePolling --> WarnFallback[If not forced:<br>Warn: Native failed, fallback to polling<br>Recommend set FORCE_POLLING=true]
    UseNative --> Proceed[Proceed with Observer]
    UsePolling --> Proceed
```

On the host-side (`fileclip_watcher.py`):
- Respect `FILECLIP_FORCE_POLLING` for observer choice (no ping needed, as it's the responder).
- Monitor shared dir for requests → process → write results.

## Key Code Snippets

### Observer Selection (`file_clip.py`)

```python
import os
from watchdog.observers import Observer as NativeObserver
from watchdog.observers.polling import PollingObserver

_OBSERVER_TYPE_CACHE = None

def get_observer_type(shared_dir: Path, ping_timeout: float = 5.0) -> type:
    global _OBSERVER_TYPE_CACHE
    if _OBSERVER_TYPE_CACHE is not None:
        return _OBSERVER_TYPE_CACHE

    force_polling = os.getenv("FILECLIP_FORCE_POLLING", "false").lower() == "true"

    # Always run ping for diagnostics
    logger.debug("Running watcher ping test...")
    watcher_alive = check_watcher(shared_dir, timeout=ping_timeout)

    if not watcher_alive:
        logger.warning(
            "Watcher is not responding! Is `fileclip-watcher` running on the host?\n"
            "   Shared dir: %s\n"
            "   Tip: Run `pdm run fileclip-watcher` on Windows host.",
            shared_dir
        )

    # Decide observer
    if force_polling:
        logger.info("FILECLIP_FORCE_POLLING=true → using PollingObserver")
        _OBSERVER_TYPE_CACHE = PollingObserver
    elif watcher_alive:
        logger.debug("Native events confirmed → using NativeObserver")
        _OBSERVER_TYPE_CACHE = NativeObserver
    else:
        logger.warning(
            "Native events failed, falling back to PollingObserver.\n"
            "   Recommend: export FILECLIP_FORCE_POLLING=true"
        )
        _OBSERVER_TYPE_CACHE = PollingObserver

    return _OBSERVER_TYPE_CACHE
```

### Usage in `wait_for_results()`

```python
ObserverClass = get_observer_type(shared_dir, ping_timeout=5.0)
observer = ObserverClass(timeout=0.1)
observer.schedule(handler, str(shared_dir), recursive=False)
observer.start()
# ... wait loop ...
observer.stop()
observer.join()
```

### Watcher Setup (`fileclip_watcher.py`)

```python
force_polling = os.getenv("FILECLIP_FORCE_POLLING", "false").lower() == "true"
ObserverClass = PollingObserver if force_polling else NativeObserver
observer = ObserverClass(timeout=0.1)
logger.info(f"Using {'PollingObserver' if force_polling else 'Native Observer'}")
observer.schedule(FileclipHandler(shared_dir), str(shared_dir), recursive=False)
observer.start()
```

### Enhanced `check_watcher()`

```python
def check_watcher(shared_dir: Path, timeout: float = 15.0) -> bool:
    # ... write ping_file ...
    with open(ping_file, "w") as f:
        json.dump(ping_data, f)
    os.sync()  # Ensure flush for mounts

    start = time.time()
    while time.time() - start < timeout:
        if not ping_file.exists():
            return True
        time.sleep(0.05)

    return False
```

## Configuration

- **Env Vars**:
  - `FILECLIP_FORCE_POLLING=true`: Force polling (still pings for liveness).
  - `FILECLIP_CONTAINER_WORKSPACE`: Container root (e.g., `/mounted/dev`).
  - `FILECLIP_HOST_WORKSPACE`: Host root (e.g., `C:\Users\user\dev`).
  - `FILECLIP_USE_WATCHER=true`: Enable watcher mode.

- **CLI Flags** (in `main.py`):
  - `--force-polling`: Sets env var internally.

## Testing Recommendations

- **Unit Tests**: Mock `check_watcher()` to test all branches (alive/dead, force/no-force).
- **Integration Tests**: Use `test_integration_watcher.py` variants:
  - Native success.
  - Native fail → fallback.
  - Force polling + watcher dead → warning.
- **Platforms**: Test on Windows (Docker), macOS (Docker), Linux (native).
- **Edge Cases**: Concurrent requests, mount delays, no shared dir.

## Troubleshooting

- **Logs**: Check `.fileclip/fileclip_watcher.log` for events.
- **Warnings**: Act on "Watcher not responding" or "fallback to polling".
- **Debug**: Set `--log-level=DEBUG` on watcher.

This architecture ensures reliability across platforms. For questions, refer to the original conversation or code.