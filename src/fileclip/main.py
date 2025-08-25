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
        "files",
        nargs="*",
        help="Paths to files to copy to clipboard."
    )
    parser.add_argument(
        "--dir",
        help="Directory path to copy all files from (recursive).",
        default=None
    )

    args = parser.parse_args()

    # Collect file paths
    file_paths = args.files or []
    
    # If --dir is provided, add all files from the directory
    if args.dir:
        if not os.path.isdir(args.dir):
            print(f"Error: Directory '{args.dir}' does not exist.")
            sys.exit(1)
        for root, _, files in os.walk(args.dir):
            for file in files:
                file_paths.append(os.path.join(root, file))

    if not file_paths:
        print("Error: No files specified. Use file paths or --dir.")
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