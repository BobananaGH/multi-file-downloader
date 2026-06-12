# Code/client/gui/helpers.py

import os
import sys
import subprocess

def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size/1024:.1f} KB"
    else:
        return f"{size/1024/1024:.1f} MB"


def open_downloads_folder(base_path: str):
    os.makedirs(base_path, exist_ok=True)

    if sys.platform == "win32":
        os.startfile(base_path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", base_path])
    else:
        subprocess.Popen(["xdg-open", base_path])