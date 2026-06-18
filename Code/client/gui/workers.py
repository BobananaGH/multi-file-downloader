# Code/client/gui/workers.py

import time
from PySide6.QtCore import QThread, Signal
from ..client import Client

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
        
    def cancel(self):
        self.requestInterruption()

    def run(self):
        c = None
        try:
            c = Client()

            if self.isInterruptionRequested():
                self._finish(False, "Cancelled")
                return

            start_time = time.time()
            last_bytes = [0]
            last_time = [start_time]

            def on_progress(received, total):
                if self.isInterruptionRequested():
                    return

                now = time.time()
                interval = max(now - last_time[0], 0.001)
                elapsed = max(now - start_time, 0.1)

                if interval > 0.2:
                    speed_bytes_s = max((received - last_bytes[0]) / interval, 0)
                else:
                    speed_bytes_s = received / elapsed

                last_bytes[0] = received
                last_time[0] = now

                speed_kbps = speed_bytes_s / 1024
                eta = (total - received) / speed_bytes_s if speed_bytes_s > 0 else 0
                percent = int((received / total) * 100) if total else 0

                self.progress.emit(self.filename, percent, speed_kbps, eta)

            success, save_path = c.download_file(
                self.filename,
                on_progress=on_progress,
                is_cancelled=lambda: self.isInterruptionRequested()
            )

            if self.isInterruptionRequested():
                self._finish(False, "Cancelled")
            else:
                self._finish(success, save_path or "")

        except Exception as e:
            if self.isInterruptionRequested():
                self._finish(False, "Cancelled")
            else:
                self._finish(False, str(e))

        finally:
            if c:
                c.close()
                
    def _finish(self, success: bool, msg: str):
        self.finished_file.emit(self.filename, success, msg)