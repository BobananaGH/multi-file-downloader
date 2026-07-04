# client/core/downloadManager.py

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from client.core.downloadCoordinator import DownloadCoordinator


class DownloadManager(QObject):
    progress_changed = Signal(str, int, float, float)
    download_finished = Signal(str, bool, str)
    download_started = Signal(str)

    def __init__(self, parent=None, username: str = "", password: str = ""):
        super().__init__(parent)

        self._coordinators: dict[str, DownloadCoordinator] = {}
        self._username = username
        self._password = password
    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def download(self, filename: str, size: int):
        if filename in self._coordinators:
            self.download_finished.emit(filename, False, "Already downloading")
            return

        if size <= 0:
            self.download_finished.emit(filename, False, "Unknown file size")
            return

        coordinator = DownloadCoordinator(filename, size, username=self._username, password=self._password)
        self._coordinators[filename] = coordinator

        coordinator.progress.connect(
            lambda fn, percent, speed, eta:
                self.progress_changed.emit(fn, percent, speed, eta)
        )
        self.download_started.emit(filename)

        coordinator.finished.connect(
            lambda success, msg, fn=filename:
                self._on_finished(fn, success, msg)
        )

        coordinator.start()
    
    def wait_all(self, timeout_ms: int = 3000):
        for coordinator in list(self._coordinators.values()):
            coordinator.wait_chunks(timeout_ms)
        
    def _on_finished(self, filename: str, success: bool, message: str):
        coordinator = self._coordinators.pop(filename, None)
        if coordinator:
            try:
                coordinator.progress.disconnect()
                coordinator.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            coordinator.deleteLater()
        self.download_finished.emit(filename, success, message)
        
    def cancel(self, filename: str):
        coordinator = self._coordinators.get(filename)
        if coordinator:
            coordinator.cancel()
            
    def clear_all(self):
        for coordinator in list(self._coordinators.values()):
            coordinator.cancel()

