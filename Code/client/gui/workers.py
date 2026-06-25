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


class ChunkDownloadThread(QThread):
    """
    Downloads a single byte range [start, end] of a file and writes it
    into file_handle at the correct offset. One file download may use
    several of these running concurrently.
    """
    progress = Signal(int, float)        # bytes_received_this_chunk, speed_bytes_s
    finished_chunk = Signal(bool, str)    # success, error_message
    
    def __init__(self, filename: str, save_path: str, start: int, end: int):
        super().__init__()
        self.filename = filename
        self.save_path = save_path
        self.range_start = start
        self.range_end = end

    def cancel(self):
        self.requestInterruption()

    def run(self):
        c = None
        f = None
        try:
            c = Client()

            if self.isInterruptionRequested():
                self.finished_chunk.emit(False, "Cancelled")
                return

            try:
                f = open(self.save_path, "r+b")
            except OSError:
                self.finished_chunk.emit(False, "Cannot open file")
                return
            f.seek(self.range_start)

            start_time = time.time()
            last_bytes = [0]
            last_time = [start_time]

            def on_progress(received, total):
                if self.isInterruptionRequested():
                    return
                now = time.time()
                interval = now - last_time[0]
                if interval < 0.2:
                    return
                speed_bytes_s = (received - last_bytes[0]) / max(interval, 0.001)
                last_bytes[0] = received
                last_time[0] = now
                self.progress.emit(received, max(speed_bytes_s, 0))

            success, msg = c.download_range(
                self.filename,
                self.range_start,
                self.range_end,
                f,
                on_progress=on_progress,
                is_cancelled=lambda: self.isInterruptionRequested()
            )

            if success:
                self.finished_chunk.emit(True, "")
            else:
                self.finished_chunk.emit(False, msg or "Download failed")

        except Exception as e:
            if self.isInterruptionRequested():
                self.finished_chunk.emit(False, "Cancelled")
            else:
                print(f"[CHUNK {self.range_start}-{self.range_end}] ERROR: {e}")
                self.finished_chunk.emit(False, str(e))
            
        finally:
            if f:
                f.close()
            if c:
                c.close()