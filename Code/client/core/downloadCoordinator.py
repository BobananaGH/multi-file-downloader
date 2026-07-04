# client/core/downloadCoordinator.py

from __future__ import annotations

import os
from PySide6.QtCore import QObject, Signal

from client.gui.workers import ChunkDownloadThread
from client.config import DOWNLOAD_DIR

MIN_CHUNK_SIZE = 8 * 1024 * 1024  
MAX_CHUNKS = 6


class DownloadCoordinator(QObject):
    """
    Owns the chunk threads for ONE file download.
    Aggregates their progress and reports it as a single stream.
    """

    progress = Signal(str, int, float, float)   # filename, percent, speed_bytes_s, eta
    finished = Signal(bool, str)            # success, message_or_path

    def __init__(self, filename: str, total_size: int, parent=None, username: str = "", password: str = ""):
        super().__init__(parent)
        self.filename = filename
        self.total_size = total_size
        self._username = username
        self._password = password
        self.save_path = self._build_save_path(filename)

        self._chunks: list[ChunkDownloadThread] = []
        self._chunk_received = []   # bytes received per chunk, indexed
        self._chunk_speed = []      # latest speed per chunk
        self._chunk_done = []       # bool per chunk
        self._failed = False
        self._fail_message = ""
        self._cancelled = False
        self._finalized = False

    # ---------------------------------------------------------
    def start(self):
        if self._cancelled:
            self._finalize()
            return
        n = self._calculate_chunk_count(self.total_size)
        ranges = self._split_ranges(self.total_size, n)

        try:
            fd = os.open(self.save_path, os.O_WRONLY | os.O_CREAT, 0o666)
            os.ftruncate(fd, self.total_size)
            os.close(fd)
        except OSError as e:
            self.finished.emit(False, f"Could not create file: {e}")
            return

        self._chunk_received = [0] * n
        self._chunk_speed = [0.0] * n
        self._chunk_done = [False] * n

        for i, (start, end) in enumerate(ranges):
            chunk = ChunkDownloadThread(
                self.filename, self.save_path, start, end,
                username=self._username,
                password=self._password
            )
            chunk.progress.connect(lambda recv, spd, idx=i: self._on_chunk_progress(idx, recv, spd))
            chunk.finished_chunk.connect(lambda ok, msg, idx=i: self._on_chunk_finished(idx, ok, msg))
            chunk.finished.connect(chunk.deleteLater)
            self._chunks.append(chunk)  

        for chunk in self._chunks:
            chunk.start()
            
    def cancel(self):
        self._cancelled = True
        for chunk in self._chunks:
            try:
                if chunk.isRunning():
                    chunk.cancel()
            except RuntimeError:
                pass  
        if not self._chunks:
            self._finalize()

    # ---------------------------------------------------------
    def wait_chunks(self, timeout_ms=3000):
        for chunk in self._chunks:
            try:
                if chunk.isRunning():
                    chunk.wait(timeout_ms)  
            except RuntimeError:
                pass
            
    def _on_chunk_progress(self, idx, received, speed):
        self._chunk_received[idx] = received
        self._chunk_speed[idx] = speed
        self._emit_aggregate_progress()

    def _on_chunk_finished(self, idx, success, message):
        self._chunk_done[idx] = True

        if not success and not self._failed:
            print(f"[COORD] Chunk {idx} failed: {message}")  
            self._failed = True
            self._fail_message = message
            for j, chunk in enumerate(self._chunks):
                if j != idx and not self._chunk_done[j]:
                    chunk.cancel()

        if all(self._chunk_done):
            self._finalize()

    def _emit_aggregate_progress(self):
        received = sum(self._chunk_received)
        speed = sum(self._chunk_speed)
        percent = int((received / self.total_size) * 100) if self.total_size else 0
        remaining = self.total_size - received
        eta = remaining / speed if speed > 0 else 0
        self.progress.emit(self.filename, percent, speed, eta)

    def _finalize(self):
        if self._finalized:
            return
        self._finalized = True    
        
        if self._cancelled:
            self._cleanup_partial_file()
            self.finished.emit(False, "Cancelled")
        elif self._failed:
            self._cleanup_partial_file()
            self.finished.emit(False, self._fail_message or "Download failed")
        else:
            self.finished.emit(True, self.save_path)

    def _cleanup_partial_file(self):
        try:
            if os.path.exists(self.save_path):
                os.remove(self.save_path)
        except OSError:
            pass

    # ---------------------------------------------------------
    @staticmethod
    def _calculate_chunk_count(size: int) -> int:
        if size < MIN_CHUNK_SIZE:
            return 1
        n = size // MIN_CHUNK_SIZE
        return max(1, min(n, MAX_CHUNKS))

    @staticmethod
    def _split_ranges(total_size: int, n: int) -> list[tuple[int, int]]:
        chunk_size = total_size // n
        ranges = []
        for i in range(n):
            start = i * chunk_size
            end = total_size - 1 if i == n - 1 else (start + chunk_size - 1)
            ranges.append((start, end))
        return ranges

    @staticmethod
    def _build_save_path(filename: str) -> str:
        base, ext = os.path.splitext(filename)
        safe_name = f"{base}_downloaded{ext}"
        save_path = os.path.join(DOWNLOAD_DIR, safe_name)
        counter = 1
        while os.path.exists(save_path):
            safe_name = f"{base}_downloaded_{counter}{ext}"
            save_path = os.path.join(DOWNLOAD_DIR, safe_name)
            counter += 1
        return save_path