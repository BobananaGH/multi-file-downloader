# Code/client/gui/workers.py

import time
from PySide6.QtCore import QThread, Signal
from client.client import Client

class FetchFilesThread(QThread):
    files_received = Signal(list)
    error_occurred = Signal(str)

    def run(self):
        try:
            c = Client()
            files = c.list_files()
            c.close()
            self.files_received.emit(files)
        except Exception as e:
            self.error_occurred.emit(str(e))
            
            
class DownloadThread(QThread):
    progress = Signal(str, int, float, float)  
    finished_file = Signal(str, bool, str)

    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        self._cancelled = False
        
    def cancel(self):
        self._cancelled = True

    def run(self):
        c = None
        try:
            c = Client()
            if self._cancelled:
                self.finished_file.emit(self.filename, False, "Cancelled")
                return

            start_time = time.time()
            last_bytes = [0]
            last_time = [start_time]

            def on_progress(received, total):
                if self._cancelled:
                    return
                now = time.time()
                elapsed = max(now - start_time, 0.1)
                interval = now - last_time[0]

                if interval > 0.2:
                    speed_bytes_s = max((received - last_bytes[0]) / interval, 0)
                    last_bytes[0] = received
                    last_time[0] = now
                else:
                    speed_bytes_s = (received / elapsed) if elapsed > 0 else 0

                speed_kb_s = speed_bytes_s / 1024
                remaining = total - received
                eta = (remaining / speed_bytes_s) if speed_bytes_s >= 1 else 0
                percent = 0 if total == 0 else int((received / total) * 100)
                self.progress.emit(self.filename, percent, speed_kb_s, eta)

            try:
                success, save_path = c.download_file(self.filename, on_progress=on_progress, is_cancelled=lambda: self._cancelled)
                if self._cancelled:
                    self.finished_file.emit(self.filename, False, "Cancelled")
                else:
                    self.finished_file.emit(self.filename, success, save_path or "")
            except Exception as e:
                if self._cancelled or "Cancelled" in str(e):
                    self.finished_file.emit(self.filename, False, "Cancelled")
                else:
                    self.finished_file.emit(self.filename, False, str(e))

        finally:
            if c:
                c.close()