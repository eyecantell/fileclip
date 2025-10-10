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
        files = ', '.join(f'POSIX file "{p}"' for p in valid_paths)
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
        # Format URIs with no trailing newline
        uris = '\n'.join(f'file://{p}' for p in valid_paths)
        env = os.environ.copy()
        if not env.get('XDG_RUNTIME_DIR'):
            env['XDG_RUNTIME_DIR'] = f"/run/user/{os.getuid()}"

        if os.getenv("WAYLAND_DISPLAY"):  # Wayland environment
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

        if os.getenv("DISPLAY"):  # X11 environment
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

        # Fallback for non-GUI environments
        print("No functional display server detected (WAYLAND_DISPLAY or DISPLAY set but unresponsive).")
        print("File URIs (copy manually):")
        for uri in uris.split('\n'):
            print(uri)
        return False

    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")