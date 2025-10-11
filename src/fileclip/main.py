import argparse
import os
import sys
from pathlib import Path
from typing import List
from fileclip.file_clip import copy_files, is_container

def collect_files(paths: List[str]) -> List[str]:
    """
    Collect all files from the given paths, expanding directories.
    Args:
        paths: List of file or directory paths.
    Returns:
        List of file paths (absolute).
    Raises:
        FileNotFoundError: If a path does not exist.
    """
    files = []
    for path in paths:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Path {path} does not exist")
        if path.is_file():
            files.append(str(path.resolve()))
        elif path.is_dir():
            for item in path.rglob("*"):
                if item.is_file():
                    files.append(str(item.resolve()))
    return files

def main():
    """
    CLI entry point for fileclip.
    Copies files or directory contents to the system clipboard.
    """
    parser = argparse.ArgumentParser(description="Copy files to the system clipboard.")
    parser.add_argument("paths", nargs="*", help="Files or directories to copy to clipboard.")
    parser.add_argument("--use-watcher", action="store_true", help="Force use of watcher in container.")
    parser.add_argument("--no-watcher", action="store_true", help="Disable watcher, use container clipboard.")
    parser.add_argument("--watcher-timeout", type=float, default=10.0, help="Timeout for watcher operations (seconds).")
    
    args = parser.parse_args()

    if not args.paths:
        print("Error: No files specified or found in provided paths.", file=sys.stderr)
        sys.exit(1)

    # Create .fileclip directory
    container_workspace = os.getenv("FILECLIP_CONTAINER_WORKSPACE")
    shared_dir = Path(container_workspace) / ".fileclip" if container_workspace else Path("/tmp/fileclip/.fileclip")
    shared_dir.mkdir(parents=True, exist_ok=True)

    try:
        files = collect_files(args.paths)
        if not files:
            print("Error: No files specified or found in provided paths.", file=sys.stderr)
            sys.exit(1)

        use_watcher = None
        if args.use_watcher:
            use_watcher = True
        elif args.no_watcher:
            use_watcher = False
        elif is_container():
            use_watcher = os.getenv("FILECLIP_USE_WATCHER", "true").lower() == "true"

        success = copy_files(files, use_watcher=use_watcher, watcher_timeout=args.watcher_timeout)
        if success:
            print("Files copied to clipboard. Paste into your application.")
        else:
            print("Failed to copy files to clipboard.", file=sys.stderr)
            sys.exit(1)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Failed to copy files: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()