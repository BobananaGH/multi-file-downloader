# client/config.py
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)