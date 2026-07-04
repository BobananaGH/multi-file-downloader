# Code/shared/icons.py
import os

FILE_ICONS = {
    # Documents
    ".pdf":  "📄",
    ".doc":  "📝",
    ".docx": "📝",
    ".odt":  "📝",
    ".rtf":  "📝",
    ".txt":  "📝",
    ".md":   "📝",

    # Spreadsheets
    ".xls":  "📊",
    ".xlsx": "📊",
    ".csv":  "📊",
    ".ods":  "📊",

    # Presentations
    ".ppt":  "📽",
    ".pptx": "📽",
    ".odp":  "📽",

    # Images
    ".png":  "🖼",
    ".jpg":  "🖼",
    ".jpeg": "🖼",
    ".gif":  "🖼",
    ".bmp":  "🖼",
    ".webp": "🖼",
    ".svg":  "🖼",
    ".ico":  "🖼",

    # Audio
    ".mp3":  "🎵",
    ".wav":  "🎵",
    ".flac": "🎵",
    ".aac":  "🎵",
    ".ogg":  "🎵",
    ".m4a":  "🎵",

    # Video
    ".mp4":  "🎬",
    ".mkv":  "🎬",
    ".avi":  "🎬",
    ".mov":  "🎬",
    ".wmv":  "🎬",
    ".flv":  "🎬",
    ".webm": "🎬",

    # Archives / compressed
    ".zip":  "📦",
    ".rar":  "📦",
    ".tar":  "📦",
    ".gz":   "📦",
    ".7z":   "📦",
    ".bz2":  "📦",

    # Code / dev
    ".py":   "🐍",
    ".js":   "📜",
    ".ts":   "📜",
    ".html": "🌐",
    ".css":  "🎨",
    ".json": "📋",
    ".xml":  "📋",
    ".yml":  "⚙",
    ".yaml": "⚙",
    ".c":    "💻",
    ".cpp":  "💻",
    ".h":    "💻",
    ".java": "☕",

    # Executables / system
    ".exe":  "⚙",
    ".msi":  "⚙",
    ".sh":   "⚙",
    ".bat":  "⚙",

    # Disk / images
    ".iso":  "💿",
    ".img":  "💿",
}

DEFAULT_FILE_ICON = "📁"

def get_file_icon(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return FILE_ICONS.get(ext, DEFAULT_FILE_ICON)