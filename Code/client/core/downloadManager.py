# client/core/downloadManager.py

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from client.gui.workers import DownloadThread


class DownloadManager(QObject):
    """
    Phase 1 refactor of your original _start_download logic.

    Still 1-thread-per-file (no multi-chunk yet),
    but now safe and architecture-ready.
    """

    progress_changed = Signal(str, int, float, float)
    download_finished = Signal(str, bool, str)
    download_started = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._threads: dict[str, DownloadThread] = {}

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def download(self, filename: str):
        if filename in self._threads:
            return
                
        thread = DownloadThread(filename)
        self._threads[filename] = thread

        self.download_started.emit(filename)

        thread.progress.connect(
            self.progress_changed
        )

        thread.finished_file.connect(
            self.download_finished
        )

        thread.finished.connect(lambda: self._cleanup(filename))

        thread.start()
        
    def _on_progress(self, filename: str, percent: int, speed: float, eta: float):
        self.progress_changed.emit(filename, percent, speed, eta)
        
    def _on_finished(self, filename: str, success: bool, save_path: str):
        self.download_finished.emit(filename, success, save_path)
        
    def _cleanup(self, filename: str):
        thread = self._threads.pop(filename, None)
        if not thread:
            return

        try:
            thread.progress.disconnect()
        except (TypeError, RuntimeError):
            pass

        try:
            thread.finished_file.disconnect()
        except (TypeError, RuntimeError):
            pass

        thread.deleteLater()
        
    def cancel(self, filename: str):
        thread = self._threads.get(filename)

        if thread and thread.isRunning():
            thread.cancel()
            
    def clear_all(self):
        for filename in list(self._threads.keys()):
            self.cancel(filename)
