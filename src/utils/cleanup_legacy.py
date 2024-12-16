import os
from pathlib import Path

def cleanup_legacy_data(base_dir="data/src"):
    """
    Deletes legacy data stored in the old directory structure.
    """
    base_path = Path(base_dir)
    if not base_path.exists():
        print(f"No legacy data found at {base_path}.")
        return

    # Iterate through directories and delete their contents
    for server_dir in base_path.iterdir():
        if server_dir.is_dir():
            # Delete all files in the directory
            for file in server_dir.iterdir():
                try:
                    file.unlink()  # Remove file
                    print(f"Deleted: {file}")
                except Exception as e:
                    print(f"Error deleting file {file}: {e}")
            # Remove the directory itself
            try:
                server_dir.rmdir()
                print(f"Deleted directory: {server_dir}")
            except Exception as e:
                print(f"Error deleting directory {server_dir}: {e}")

    # Remove the base directory if it's empty
    try:
        base_path.rmdir()
        print(f"Deleted base directory: {base_path}")
    except Exception as e:
        print(f"Error deleting base directory {base_path}: {e}")

if __name__ == "__main__":
    cleanup_legacy_data()
