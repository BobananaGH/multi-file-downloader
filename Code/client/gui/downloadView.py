# Code/client/gui/downloadView.py

from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy
)

from client.gui.widgets import DownloadItemWidget

class DownloadView(QWidget):
    """
    Pure UI for displaying downloads.

    Responsibilities:
    - Own DownloadItemWidgets
    - Show progress
    - Show completion state
    - Emit cancel requests

    No threads.
    No networking.
    """
    
    cancel_requested = Signal(str)
    clear_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._widgets: dict[str, DownloadItemWidget] = {}

        self._build_ui()

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        
        header = QHBoxLayout()

        title = QLabel("DOWNLOADS")
        title.setObjectName("sectionLabel")

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("clearBtn")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.clear_btn)

        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("downloadScroll")
        self.scroll.setWidgetResizable(True)

        self.scroll.setMinimumHeight(150)
        
        self.container = QWidget()
        
        self.download_layout = QVBoxLayout(self.container)
        self.download_layout.setContentsMargins(0, 0, 0, 0)
        self.download_layout.setAlignment(Qt.AlignTop)
        self.download_layout.setSpacing(6)
        
        self.scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll.setWidget(self.container)
        
        root.addWidget(self.scroll)
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        
    def add_download(self, filename: str):
        if filename in self._widgets:
            return

        widget = DownloadItemWidget(filename)

        widget.cancel_requested.connect(
            self.cancel_requested.emit
        )

        self.download_layout.addWidget(widget)

        self._widgets[filename] = widget
        
    def update_progress(
        self,
        filename: str,
        percent: int,
        speed: float,
        eta: float,
    ):
        widget = self._widgets.get(filename)

        if widget:
            widget.set_progress(
                percent,
                speed,
                eta,
            )
            
    def mark_finished(
        self,
        filename: str,
        success: bool,
        message: str,
    ):
        widget = self._widgets.get(filename)

        if not widget:
            return

        if success:
            widget.set_progress(100)

        elif message == "Cancelled":
            widget.set_cancelled()

        else:
            widget.set_error(message)
            
    def remove_download(self, filename: str):
        widget = self._widgets.pop(filename, None)

        if not widget:
            return

        self.download_layout.removeWidget(widget)

        widget.deleteLater()
        
    def clear_all(self):
        for filename in list(self._widgets.keys()):
            self.remove_download(filename)
        