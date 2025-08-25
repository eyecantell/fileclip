[![CI](https://github.com/eyecantell/fileclip/actions/workflows/ci.yml/badge.svg)](https://github.com/eyecantell/fileclip/actions/runs/16384663620)
[![PyPI version](https://badge.fury.io/py/fileclip.svg)](https://badge.fury.io/py/fileclip)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Downloads](https://pepy.tech/badge/fileclip)](https://pepy.tech/project/fileclip)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# fileclip

A cross-platform Python library and CLI to copy files to the system clipboard as file references, enabling pasting into web UIs or applications (e.g., Grok's UI for file uploads).

## Features
- Copy multiple files to the clipboard on Windows, macOS, and Linux.
- Simple Python API: `fileclip.copy_files(["file1.txt", "file2.pdf"])`.
- Command-line interface (CLI) for copying files or all files in a directory.
- Supports text and non-text files (e.g., PDFs, images) for pasting as attachments.
- Robust error handling and file validation.

## Installation
Install via pip:
```bash
pip install fileclip
```

**Requirements**:
- Python 3.9+
- **Windows**: PowerShell (`powershell.exe`, included by default).
- **macOS**: No additional dependencies (`osascript` is built-in).
- **Linux**: Requires `xclip` (install with `sudo apt install xclip` or equivalent).

## Usage

### Python API
```python
from fileclip.file_clip import copy_files

# Copy files to clipboard
files = ["path/to/file1.txt", "path/to/file2.pdf"]
copy_files(files)

# Paste into a web UI (e.g., Grok at grok.com) with Ctrl+V (Cmd+V on macOS)
```

### Command-Line Interface (CLI)
Copy files directly:
```bash
# Copy specific files
fileclip file1.txt file2.pdf

# Copy all files in a directory
fileclip --dir path/to/directory
```

**Example Output**:
```
Files copied to clipboard (Windows).
Paste into your application (e.g., Grok's UI) with Ctrl+V (or Cmd+V on macOS).
```

## Notes
- **Linux**: Ensure `xclip` is installed. Wayland support may require `wl-clipboard` (planned feature).
- **Limitations**: Not supported in headless environments or non-standard Linux desktop environments.
- **Use Case**: Ideal for copying files for web UI uploads (e.g., code, PDFs into Grok’s interface).

## Contributing
Contributions are welcome! Submit issues or pull requests on [GitHub](https://github.com/eyecantell/fileclip).

## License
MIT License

## Author
eyecantell (paul@pneuma.solutions)