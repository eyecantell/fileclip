import os
import subprocess
import sys
from typing import List, Union

def copy_files(file_paths: List[Union[str, os.PathLike]]) -> bool:
    """
    Copy a list of file paths to the system clipboard as file references.
    
    Args:
        file_paths: List of file paths (absolute or relative) or PathLike objects.
    
    Returns:
        bool: True if successful, False otherwise.
    
    Raises:
        FileNotFoundError: If any file path is invalid.
        RuntimeError: If the platform or clipboard operation is unsupported.
    """
    # Validate file paths
    valid_paths = []
    for path in file_paths:
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"File not found or not a file: {path}")
        valid_paths.append(abs_path)

    if not valid_paths:
        print("No valid files to copy.")
        return False

    if sys.platform == "win32":  # Windows
        paths = ','.join(f'"{p}"' for p in valid_paths)
        cmd = f'powershell.exe -Command "Set-Clipboard -Path {paths}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Windows clipboard error: {result.stderr}")
        print("Files copied to clipboard (Windows).")
        return True

    elif sys.platform == "darwin":  # macOS
        files = ', '.join(f'POSIX file "{p}"' for p in valid_paths)
        cmd = f'osascript -e \'tell app "Finder" to set the clipboard to {{{files}}}\''
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"macOS clipboard error: {result.stderr}")
        print("Files copied to clipboard (macOS).")
        return True

    elif sys.platform == "linux":  # Linux (requires xclip)
        uris = '\n'.join(f'file://{p}' for p in valid_paths)
        result = subprocess.run(
            ['xclip', '-i', '-selection', 'clipboard', '-t', 'text/uri-list'],
            input=uris.encode(), capture_output=True, check=True
        )
        print("Files copied to clipboard (Linux).")
        return True

    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")