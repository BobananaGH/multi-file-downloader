# Code/client/core/fileBrowser.py

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from client.gui.workers import FetchFilesThread


class FileBrowser(QObject):
    """
    Handles server file listings.

    Responsibilities:
    - Fetch files
    - Store all files
    - Filter files
    - Emit updated file lists

    No widgets.
    No download logic.
    """

    files_changed = Signal(list)
    status_message = Signal(str)
    loading_changed = Signal(bool)
    fetch_error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        self._all_files: list[tuple[str, int]] = []
        self._filtered_files: list[tuple[str, int]] = []

        self._query = ""
        self._fetch_thread: FetchFilesThread | None = None

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def load_files(self) -> None:
        if self._fetch_thread and self._fetch_thread.isRunning():
            return

        self.loading_changed.emit(True)
        self.status_message.emit("Connecting to server...")

        self._fetch_thread = FetchFilesThread()

        self._fetch_thread.files_received.connect(
            self._on_files_received
        )

        self._fetch_thread.error_occurred.connect(
            self._on_fetch_error
        )
        
        self._fetch_thread.finished.connect(
            self._on_fetch_finished
        )

        self._fetch_thread.finished.connect(
            self._fetch_thread.deleteLater
        )

        self._fetch_thread.start()

    def set_filter(self, query: str) -> None:
        self._query = query.strip().lower()
        self._apply_filter()

    def wait_for_fetch(self, timeout_ms: int = 2000) -> None:
        if self._fetch_thread:
            try:
                self._fetch_thread.wait(timeout_ms)
            except RuntimeError:
                pass

    # ---------------------------------------------------------
    # Internal
    # ---------------------------------------------------------

    def _on_files_received(
        self,
        files: list[tuple[str, int]]
    ) -> None:
        self._all_files = files

        self._apply_filter()

        count = len(files)

        self.status_message.emit(
            f"Connected — {count} file{'s' if count != 1 else ''} available"
        )

    def _on_fetch_error(self, error: str) -> None:
        self._all_files = []
        self._filtered_files = []

        self.files_changed.emit([])

        self.fetch_error.emit(error)

        self.status_message.emit(
            f"Error: {error}"
        )

    def _on_fetch_finished(self):
        self.loading_changed.emit(False)
        self._fetch_thread = None
    
    def _apply_filter(self) -> None:
        if self._query:
            self._filtered_files = [
                (name, size)
                for name, size in self._all_files
                if self._query in name.lower()
            ]
        else:
            self._filtered_files = list(self._all_files)

        self.files_changed.emit(
            self._filtered_files
        )