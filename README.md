[![CI](https://github.com/eyecantell/fileclip/actions/workflows/ci.yml/badge.svg)](https://github.com/eyecantell/fileclip/actions)
[![PyPI version](https://badge.fury.io/py/fileclip.svg)](https://badge.fury.io/py/fileclip)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Downloads](https://pepy.tech/badge/fileclip)](https://pepy.tech/project/fileclip)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Fileclip

Fileclip is a command-line tool for copying file references to the system clipboard, enabling seamless file copy/paste operations across supported platforms. It supports copying multiple files or directories, making it easy to paste files into file managers (e.g., Windows File Explorer, Nautilus, Dolphin) or other applications that support file references. A Windows host watcher service facilitates copying files from containers to the Windows clipboard.

## Features

- **Cross-Platform**: Works on Windows, macOS, and Linux (including WSL and containers).
- **File and Directory Support**: Copies references to individual files or all files within directories (non-recursive by default).
- **Clipboard Integration**: Uses native clipboard commands to copy file references or URIs, depending on the platform.
- **Fallback for WSL/Containers**: In WSL or VS Code containers, falls back to copying `file://` URIs as text to the Windows clipboard for use in Windows applications.
- **Container Support**: In VS Code containers, communicates with a Windows host watcher (`fileclip-watcher`) to copy native Windows file paths to the clipboard.

## Installation

Fileclip is built with Python and managed using [PDM](https://pdm-project.org/). Follow these steps to install:

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
   On Linux, install `wl-clipboard` (for Wayland) or `xclip` (for X11):
   ```bash
   sudo apt update && sudo apt install wl-clipboard xclip
   ```

4. **Container Setup (Optional)**:
   For VS Code container usage, add a mount to `devcontainer.json` to share a directory between the container and Windows host:
   ```json
   "mounts": [
       "source=C:/Temp/fileclip,target=/tmp/fileclip,type=bind"
   ]
   ```
   On the Windows host, run the `fileclip-watcher` service (see [Container Support](#container-support)).

## Usage

### Copy Files to Clipboard

Run `fileclip` with one or more file or directory paths:

```bash
pdm run fileclip path/to/file1.txt path/to/dir
```

- **Files**: Copies references to the specified files.
- **Directories**: Copies references to all files directly within the directory (non-recursive).
- **Output**: Confirms files copied to the clipboard or provides `file://` URIs for manual copying if clipboard operations fail.

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

- Copy files from a directory:
  ```bash
  pdm run fileclip test_dir
  ```
  Output (Windows):
  ```
  Executing Windows command: powershell.exe -Command "Set-Clipboard -Path 'C:\path\to\test_dir\file1.txt','C:\path\to\test_dir\file2.txt'"
  Files copied to clipboard (Windows).
  ```

- Paste the clipboard content into a file manager (e.g., Nautilus, Windows File Explorer) or application to copy the files.

### Run the Host Watcher (Windows)

Run the `fileclip-watcher` CLI on a Windows host to monitor the shared directory for file copy requests from containers:

```bash
pdm run fileclip-watcher --log-level=DEBUG
```

The watcher monitors `FILECLIP_HOST_WORKSPACE/.fileclip` (default: `C:\Temp\fileclip\.fileclip`) for `fileclip_*.json` files and copies specified files to the Windows clipboard. Set the environment variable if needed:

```bash
set FILECLIP_HOST_WORKSPACE=C:\path\to\workspace
pdm run fileclip-watcher --log-level=DEBUG
```

## Platform-Specific Behavior

### Windows
- Uses PowerShell’s `Set-Clipboard -Path` to copy file references.
- Pasting into Windows File Explorer or applications like VS Code works natively, copying the actual files.
- Example:
  ```powershell
  pdm run fileclip test.txt
  ```
  Paste in File Explorer to copy `test.txt`.

### macOS
- Uses `osascript` to copy file references to the Finder clipboard.
- Pasting into Finder or compatible applications copies the files.
- Example:
  ```bash
  pdm run fileclip test.txt
  ```
  Paste in Finder to copy `test.txt`.

### Linux
- Uses `wl-copy` (Wayland) or `xclip` (X11) to copy file references as `text/uri-list` URIs.
- Pasting into Linux file managers (e.g., Nautilus, Dolphin) copies the referenced files.
- Example:
  ```bash
  pdm run fileclip test.txt
  ```
  Paste in Nautilus to copy `test.txt`.
- **Note**: Requires `wl-clipboard` or `xclip` and a functional Wayland (`WAYLAND_DISPLAY`) or X11 (`DISPLAY`) session.

### WSL and VS Code Containers
- Copies file references using `wl-copy` or `xclip` within the Linux environment.
- When pasting to Windows applications, falls back to copying `file://` URIs as text to the Windows clipboard via `clip.exe` (WSL) or the host watcher.
- Example:
  ```bash
  pdm run fileclip test.txt
  ```
  If `wl-copy`/`xclip` fail, output:
  ```
  No functional display server detected.
  Files copied to clipboard as text URIs (WSL/container fallback to Windows).
  ```
  Paste into Windows File Explorer’s address bar or a browser to access the file.

## Container Support

For VS Code containers, `fileclip` communicates with the `fileclip-watcher` service on the Windows host to copy native Windows file paths to the clipboard, enabling seamless pasting into Windows File Explorer or other applications.

### Setup
1. **Host Watcher**:
   - On the Windows host, ensure `fileclip` is installed via PDM.
   - Run the watcher:
     ```powershell
     pdm run fileclip-watcher --log-level=DEBUG
     ```
   - Optionally, use Windows Task Scheduler to start it on login:
     ```powershell
     pdm run fileclip-watcher --log-level=INFO
     ```

2. **Container Configuration**:
   - Add a mount to `devcontainer.json` to share a directory:
     ```json
     "mounts": [
         "source=C:/Temp/fileclip,target=/tmp/fileclip,type=bind"
     ]
     ```
   - Set environment variables for path translation (optional):
     ```json
     "containerEnv": {
         "FILECLIP_HOST_WORKSPACE": "C:\\path\\to\\workspace",
         "FILECLIP_CONTAINER_WORKSPACE": "/workspaces/project"
     }
     ```

3. **Usage in Container**:
   - Run `fileclip` as usual:
     ```bash
     pdm run fileclip /workspaces/project/test.txt
     ```
   - `fileclip` translates container paths to host paths, writes them to `/tmp/fileclip/fileclip_<uuid>.json`, and the host `fileclip-watcher` copies them to the Windows clipboard.
   - If the watcher isn’t running, `fileclip` falls back to copying `file://` URIs as text:
     ```
     Host service not detected. Copied file:// URIs to clipboard as text.
     ```
     Paste these URIs into Windows File Explorer’s address bar.

### Notes
- The watcher must be running on the Windows host. Containers cannot directly start host processes.
- Ensure the shared directory (e.g., `C:\Temp\fileclip`) exists on the host.
- Path translation requires correct `FILECLIP_HOST_WORKSPACE` and `FILECLIP_CONTAINER_WORKSPACE` settings.

## Troubleshooting

- **Linux Clipboard Issues**:
  - Ensure `wl-clipboard` or `xclip` is installed:
    ```bash
    sudo apt install wl-clipboard xclip
    ```
  - Verify environment variables:
    ```bash
    env | grep -E 'WAYLAND_DISPLAY|DISPLAY|XDG_RUNTIME_DIR'
    ```
    Set `XDG_RUNTIME_DIR` if unset:
    ```bash
    export XDG_RUNTIME_DIR=/run/user/$(id -u)
    ```
  - Test clipboard manually:
    ```bash
    echo -e "file:///path/to/test.txt" | wl-copy --type text/uri-list
    wl-paste --type text/uri-list
    ```

- **WSL/Container Clipboard**:
  - If pasting into Windows yields text URIs, use the URI in File Explorer’s address bar.
  - Test with `clip.exe`:
    ```bash
    echo "file:///path/to/test.txt" | clip.exe
    ```

- **Container Watcher Issues**:
  - Ensure `fileclip-watcher` is running on the Windows host.
  - Verify the shared directory:
    ```bash
    ls -l /tmp/fileclip
    ```
  - Check path translation:
    ```bash
    env | grep FILECLIP
    ```
  - Inspect `/tmp/fileclip/fileclip_*.json` for errors.

- **Timeouts**:
  - If `wl-copy` or `xclip` time out, increase the timeout in `file_clip.py` (e.g., `timeout=10`).

## Limitations

- The upper limit for file copying has not been tested extensively. Expect performance degradation with very large directories.
- In container/WSL environments, native file references may fall back to text URIs.

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
  │       └── main.py
  ├── tests/
  │   ├── test_file_clip.py
  │   └── test_fileclip_watcher.py
  ├── pyproject.toml
  ├── README.md
  └── .devcontainer/
      ├── Dockerfile
      └── devcontainer.json
  ```

- **Dependencies**:
  - Python: `pathlib`, `subprocess`, `sys`, `json`
  - External: `pyperclip`, `watchdog`
  - Dev: `pytest`, `pytest-cov`, `pytest-mock`, `ruff`, `build`, `twine`

- **Development Tasks**:
  - Format code: `pdm run ruff format .`
  - Lint code: `pdm run ruff check .`
  - Build package: `pdm build`
  - Publish package: `pdm publish`

## Future Enhancements

- Add `--include`/`--exclude` flags for file filtering.
- Support recursive directory copying.
- Integrate with `applydir` for advanced file operations.
- Enhance CI with container testing.
- Explore HTTP-based host communication.

## License

MIT License. See [LICENSE](LICENSE) for details.