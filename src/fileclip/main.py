import argparse
import os
import sys
from fileclip.file_clip import copy_files

def main():
    """CLI for fileclip to copy files to the system clipboard."""
    parser = argparse.ArgumentParser(
        description="Copy files to the system clipboard for pasting as file references (e.g., into Grok's UI)."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Paths to files or directories (directories are processed recursively)."
    )

    args = parser.parse_args()

    # Collect file paths
    file_paths = []
    
    # Process each path: files are added directly, directories are walked recursively
    for path in args.paths:
        if not os.path.exists(path):
            print(f"Error: Path '{path}' does not exist.")
            sys.exit(1)
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    file_paths.append(os.path.join(root, file))
        elif os.path.isfile(path):
            file_paths.append(path)
        else:
            print(f"Error: Path '{path}' is neither a file nor a directory.")
            sys.exit(1)

    if not file_paths:
        print("Error: No files specified or found in provided paths.")
        parser.print_help()
        sys.exit(1)

    # Copy files to clipboard
    try:
        success = copy_files(file_paths)
        if success:
            print("Paste into your application (e.g., Grok's UI) with Ctrl+V (or Cmd+V on macOS).")
        else:
            sys.exit(1)
    except Exception as e:
        print(f"Failed to copy files: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()