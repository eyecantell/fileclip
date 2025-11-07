[![CI](https://github.com/eyecantell/fileclip/actions/workflows/ci.yml/badge.svg)](https://github.com/eyecantell/fileclip/actions)
[![PyPI version](https://badge.fury.io/py/fileclip.svg)](https://badge.fury.io/py/fileclip)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Downloads](https://pepy.tech/badge/fileclip)](https://pepy.tech/project/fileclip)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Fileclip

Fileclip is a command-line tool for copying file references to the system clipboard, enabling seamless file copy/paste operations across Windows, macOS, and Linux (including WSL and containers). It supports copying multiple files or directories for pasting into file managers (e.g., Windows File Explorer, Nautilus, Dolphin) or applications supporting file references. A Windows host watcher service enables copying files from containers to the Windows clipboard.

## Todo
- Change PollingObserver to use Observer first, then if it fails fall back to pollingObserver
- Test basic copy/paste on Linux

## Features

- **Cross-Platform**: Supports Windows, macOS, and Linux (including WSL and containers).
- **File and Directory Support**: Copies references to individual files or all files within directories (recursive).
- **Clipboard Integration**: Uses native clipboard commands for file references or URIs.
- **WSL/Container Fallback**: Copies `file://` URIs as text to the Windows clipboard for Windows applications.
- **Container Support**: Communicates with a Windows host `fileclip-watcher` to copy native Windows file paths.

## Installation

Fileclip is built with Python and managed using [PDM](https://pdm-project.org/). Follow these steps:

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/eyecantell/fileclip.git
   cd fileclip
   ```

2. **Install Dependencies**:
   Ensure Python 3.9+ is installed, then run:
   ```bash
   pip install pdm
   pdm install -G test -G dev
   ```

3. **Linux Dependencies**:
   On Linux, install `wl-clipboard` (Wayland) or `xclip` (X11):
   ```bash
   sudo apt update && sudo apt install wl-clipboard xclip
   ```

4. **Container Setup (Optional)**:
   For VS Code containers, ensure your workspace is bind-mounted (e.g., via `devcontainer.json`). The tool uses `$FILECLIP_CONTAINER_WORKSPACE/.fileclip` for communication, which is shared via the workspace mount. No additional mount is required unless you want to avoid placing `.fileclip` in your workspace root.
   
   Alternative (to avoid workspace clutter): Add a separate mount to `devcontainer.json` and adjust env vars:
   ```json
   "mounts": [
       "source=C:/Temp/fileclip,target=/tmp/fileclip,type=bind"
   ]
   ```
   Then set `"FILECLIP_CONTAINER_WORKSPACE": "/tmp/fileclip"` and `"FILECLIP_HOST_WORKSPACE": "C:\\Temp\\fileclip"`. Note: Path translation for files outside this dir won't work—use only for non-workspace files.

## Usage

### Copy Files to Clipboard

Run `fileclip` with file or directory paths:
```bash
pdm run fileclip path/to/file1.txt path/to/dir
```

- **Files**: Copies references to specified files.
- **Directories**: Copies references to all files within the directory and subdirectories (recursive).
- **Output**: Confirms files copied or provides `file://` URIs if clipboard operations fail.

### Examples

- Copy a single file:
  ```bash
  pdm run fileclip src/fileclip/file_clip.py
  ```
  Output (Linux):
  ```
  Attempting Wayland clipboard with wl-copy (WAYLAND_DISPLAY=..., XDG_RUNTIME_DIR=/run/user/1000)
  Executing Wayland command: wl-copy --type text/uri-list with input:
  file:///mounted/dev/fileclip/src/fileclip/file_clip.py
  Files copied to clipboard (Wayland).
  ```

- Copy files from a directory (includes subdirectories):
  ```bash
  pdm run fileclip test_dir
  ```
  Output (Windows):
  ```
  Executing Windows command: powershell.exe -Command "Set-Clipboard -Path 'C:\path\to\test_dir\file1.txt','C:\path\to\test_dir\file2.txt'"
  Files copied to clipboard (Windows).
  ```

- Paste into a file manager or application to copy the files.

### Run the Host Watcher (Windows)

Run `fileclip-watcher` on a Windows host to monitor for container file copy requests:
```powershell
pdm run fileclip-watcher --log-level=DEBUG
```

Monitors `$FILECLIP_HOST_WORKSPACE/.fileclip` (default: `C:\Temp\fileclip`). Set the environment variable if needed:
```powershell
set FILECLIP_HOST_WORKSPACE=C:\path\to\workspace
pdm run fileclip-watcher --log-level=DEBUG
```

## Platform-Specific Behavior

### Windows
- Uses PowerShell’s `Set-Clipboard -Path`.
- Example:
  ```powershell
  pdm run fileclip test.txt
  ```
  Paste in File Explorer to copy `test.txt`.

### macOS
- Uses `osascript` for Finder clipboard.
- Example:
  ```bash
  pdm run fileclip test.txt
  ```
  Paste in Finder to copy `test.txt`.

### Linux
- Uses `wl-copy` (Wayland) or `xclip` (X11) for `text/uri-list` URIs.
- Example:
  ```bash
  pdm run fileclip test.txt
  ```
  Paste in Nautilus to copy `test.txt`.
- **Note**: Requires `wl-clipboard` or `xclip` and a Wayland (`WAYLAND_DISPLAY`) or X11 (`DISPLAY`) session.

### WSL and VS Code Containers
- Uses `wl-copy` or `xclip` in Linux environments.
- Falls back to `file://` URIs via `clip.exe` (WSL) or host watcher for Windows applications.
- Example:
  ```bash
  pdm run fileclip test.txt
  ```
  If `wl-copy`/`xclip` fail:
  ```
  No functional display server detected.
  Files copied to clipboard as text URIs (WSL/container fallback to Windows).
  ```
  Paste into Windows File Explorer’s address bar.

## Container Support

For VS Code containers, `fileclip` uses `fileclip-watcher` on the Windows host to copy native Windows file paths.

### Setup
1. **Host Watcher**:
   - Install `fileclip` via PDM on the Windows host.
   - Run:
     ```powershell
     pdm run fileclip-watcher --log-level=DEBUG
     ```
   - Optionally, use Task Scheduler for startup:
     ```powershell
     pdm run fileclip-watcher --log-level=INFO
     ```

2. **Container Configuration**:
   - Ensure your workspace is bind-mounted in `devcontainer.json` (e.g., from host `C:\Users\user\dev` to container `/mounted/dev`).
   - Set environment variables:
     ```json
     "containerEnv": {
         "FILECLIP_HOST_WORKSPACE": "C:\\Users\\user\\dev",
         "FILECLIP_CONTAINER_WORKSPACE": "/mounted/dev",
         "FILECLIP_USE_WATCHER": "true"
     }
     ```
   - The shared directory will be `$FILECLIP_CONTAINER_WORKSPACE/.fileclip` (created automatically).

3. **Usage in Container**:
   - Run:
     ```bash
     pdm run fileclip /mounted/dev/test.txt
     ```
   - Translates paths to host paths, writes to `$FILECLIP_CONTAINER_WORKSPACE/.fileclip/fileclip_request_<uuid>.json`, and the watcher copies to the Windows clipboard.
   - If the watcher isn’t running:
     ```
     Host service not detected. Copied file:// URIs to clipboard as text.
     ```

### Notes
- Ensure your workspace mount shares the directory between host and container.
- Path translation requires correct `FILECLIP_HOST_WORKSPACE` and `FILECLIP_CONTAINER_WORKSPACE`.
- The `.fileclip` directory contains logs (`fileclip_watcher.log`) and temporary JSON files.

## Troubleshooting

- **Linux Clipboard**:
  - Install dependencies:
    ```bash
    sudo apt install wl-clipboard xclip
    ```
  - Check environment:
    ```bash
    env | grep -E 'WAYLAND_DISPLAY|DISPLAY|XDG_RUNTIME_DIR'
    ```
    Set if unset:
    ```bash
    export XDG_RUNTIME_DIR=/run/user/$(id -u)
    ```
  - Test clipboard:
    ```bash
    echo -e "file:///path/to/test.txt" | wl-copy --type text/uri-list
    wl-paste --type text/uri-list
    ```

- **WSL/Container Clipboard**:
  - Test with `clip.exe`:
    ```bash
    echo "file:///path/to/test.txt" | clip.exe
    ```

- **Container Watcher**:
  - Verify `fileclip-watcher` is running.
  - Check shared directory:
    ```bash
    ls -l $FILECLIP_CONTAINER_WORKSPACE/.fileclip
    ```
  - Inspect `$FILECLIP_CONTAINER_WORKSPACE/.fileclip/fileclip_request_*.json`.

- **Timeouts**:
  - Increase timeout in `file_clip.py` (e.g., `timeout=10`).

## Limitations

- Performance may degrade with very large directories (due to recursive scanning).
- WSL/containers may fall back to text URIs.

## Development

- **Run Tests**:
  ```bash
  pdm run pytest -v --cov=src/fileclip --cov-report=term
  ```

- **Project Structure**:
  ```
  fileclip/
  ├── src/
  │   └── fileclip/
  │       ├── __init__.py
  │       ├── file_clip.py
  │       ├── fileclip_watcher.py
  │       ├── main.py
  ├── tests/
  │   ├── test_file_clip.py
  │   ├── test_fileclip_watcher.py
  ├── pyproject.toml
  ├── README.md
  └── .devcontainer/
      ├── Dockerfile
      ├── devcontainer.json
  ```

- **Dependencies**:
  - Runtime: `pyperclip`, `watchdog`
  - Dev: `pytest`, `pytest-cov`, `pytest-mock`, `ruff`, `build`, `twine`

- **Tasks**:
  - Format: `pdm run ruff format .`
  - Lint: `pdm run ruff check .`
  - Build: `pdm run pdm build`
  - Publish: `pdm run pdm publish`

## Future Enhancements

- Add `--include`/`--exclude` flags.
- Enhance CI with container testing.
- Explore HTTP-based host communication.

## License

MIT License. See [LICENSE](LICENSE) for details.