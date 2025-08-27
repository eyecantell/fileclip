[![CI](https://github.com/eyecantell/fileclip/actions/workflows/ci.yml/badge.svg)](https://github.com/eyecantell/fileclip/actions/runs/16384663620)
[![PyPI version](https://badge.fury.io/py/fileclip.svg)](https://badge.fury.io/py/fileclip)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Downloads](https://pepy.tech/badge/fileclip)](https://pepy.tech/project/fileclip)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[![CI](https://github.com/eyecantell/fileclip/actions/workflows/ci.yml/badge.svg)](https://github.com/eyecantell/fileclip/actions/runs/16384663620)
[![PyPI version](https://badge.fury.io/py/fileclip.svg)](https://badge.fury.io/py/fileclip)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Downloads](https://pepy.tech/badge/fileclip)](https://pepy.tech/project/fileclip)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Fileclip

Fileclip is a command-line tool for copying file references to the system clipboard, enabling seamless file copy/paste operations across supported platforms. It supports copying multiple files or directories, making it easy to paste files into file managers (e.g., Windows File Explorer, Nautilus, Dolphin) or other applications that support file references.

## Features

- **Cross-Platform**: Works on Windows, macOS, and Linux (including WSL and containers).
- **File and Directory Support**: Copies references to individual files or all files within directories (non-recursive by default).
- **Clipboard Integration**: Uses native clipboard commands to copy file references or URIs, depending on the platform.
- **Fallback for WSL/Containers**: In WSL or VS Code containers, falls back to copying `file://` URIs as text to the Windows clipboard for use in Windows applications.
- **Container Support**: In VS Code containers, communicates with a Windows host service to copy native Windows file paths to the clipboard.

## Installation

Fileclip is built with Python and managed using [PDM](https://pdm-project.org/). Follow these steps to install:

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/fileclip.git
   cd fileclip
   ```

2. **Install Dependencies**:
   Ensure Python 3.8+ is installed, then run:
   ```bash
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
   On the Windows host, run the `fileclip-host.py` service (see [Container Support](#container-support)).

## Usage

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
- When pasting to Windows applications (e.g., File Explorer, browsers like grok.com), the clipboard content is transferred as text URIs (e.g., `file:///path/to/file`) due to limitations in WSL/container clipboard sharing, which only reliably supports text.
- Falls back to `clip.exe` (in WSL) to copy URIs to the Windows clipboard as text, or prints URIs for manual copying.
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

For VS Code containers, `fileclip` can communicate with a Windows host service to copy native Windows file paths to the clipboard, enabling seamless pasting into Windows File Explorer or other applications. This uses a file-based communication mechanism.

### Setup
1. **Host Service**:
   - On the Windows host, save the following as `fileclip-host.py`:
     ```python
     import json
     import time
     import subprocess
     from pathlib import Path

     POLL_FILE = Path(r'C:\Temp\fileclip\clipboard.json')
     while True:
         if POLL_FILE.exists():
             with open(POLL_FILE, 'r') as f:
                 data = json.load(f)
             paths = data.get('paths', [])
             if paths:
                 cmd = f"powershell.exe -Command \"Set-Clipboard -Path '{','.join(paths)}'\""
                 subprocess.run(cmd, shell=True, check=True)
                 print(f"Copied {len(paths)} files to clipboard.")
             POLL_FILE.unlink()  # Acknowledge
         time.sleep(1)  # Poll interval
     ```
   - Run it manually in a PowerShell terminal:
     ```powershell
     python fileclip-host.py
     ```
   - Optionally, use Windows Task Scheduler to start it on login.

2. **Container Configuration**:
   - Ensure the container has a shared directory by adding to `devcontainer.json`:
     ```json
     "mounts": [
         "source=C:/Temp/fileclip,target=/tmp/fileclip,type=bind"
     ]
     ```
   - Set environment variables for path translation (optional, in `devcontainer.json` or shell):
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
   - `fileclip` translates container paths (e.g., `/workspaces/project/test.txt`) to host paths (e.g., `C:\path\to\workspace\test.txt`), writes them to `/tmp/fileclip/clipboard.json`, and the host service copies them to the Windows clipboard.
   - If the host service isn’t running, `fileclip` falls back to copying `file://` URIs as text and prints:
     ```
     Host service not detected. Copied file:// URIs to clipboard as text.
     ```
     Paste these URIs into Windows File Explorer’s address bar.

### Notes
- The host service must be started manually on Windows. Containers cannot directly start host processes due to isolation.
- Ensure the mounted directory (e.g., `C:\Temp\fileclip`) exists on the host before starting the container.
- Path translation requires correct `FILECLIP_HOST_WORKSPACE` and `FILECLIP_CONTAINER_WORKSPACE` settings. If unset, `fileclip` will attempt to infer paths or fall back to URIs.

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
    Paste into a file manager to confirm.

- **WSL/Container Clipboard**:
  - If pasting into Windows yields text URIs instead of file references, use the URI in File Explorer’s address bar or a browser.
  - Test with `clip.exe`:
    ```bash
    echo "file:///path/to/test.txt" | clip.exe
    ```
    Paste in Windows to confirm.

- **Container Host Service Issues**:
  - Ensure `fileclip-host.py` is running on the Windows host.
  - Verify the shared directory exists and is writable:
    ```bash
    ls -l /tmp/fileclip
    ```
  - Check path translation:
    ```bash
    env | grep FILECLIP
    ```
  - If paths fail to copy, inspect `/tmp/fileclip/clipboard.json` for errors.

- **Timeouts**:
  - If `wl-copy` or `xclip` time out, check the debug output in `fileclip` and run the logged command manually.
  - Increase timeout in `file_clip.py` (e.g., `timeout=10`).

## Development

- **Run Tests**:
  ```bash
  pdm run pytest -v --cov=src/fileclip --cov-report=term
  ```
  Expected: 18 tests pass (16 on Linux, 5 skipped on Windows).

- **Project Structure**:
  ```
  fileclip/
  ├── src/
  │   └── fileclip/
  │       ├── __init__.py
  │       ├── file_clip.py
  │       └── main.py
  ├── tests/
  │   └── test_file_clip.py
  ├── pyproject.toml
  ├── README.md
  ├── fileclip-host.py
  └── .devcontainer/
      ├── Dockerfile
      └── devcontainer.json
  ```

- **Dependencies**:
  - Python: `pathlib`, `subprocess`, `sys`, `json`
  - Dev: `pytest`, `pytest-cov`

## Future Enhancements

- Add `--include`/`--exclude` flags for file filtering.
- Support recursive directory copying.
- Integrate with `applydir` for advanced file operations.
- Add CI workflow for multi-platform testing, including container scenarios.
- Explore HTTP-based host communication for faster response.

## License

MIT License. See [LICENSE](LICENSE) for details.