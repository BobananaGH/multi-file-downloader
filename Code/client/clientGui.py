# Code/client/clientGui.py

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QMainWindow, QMessageBox
)
from PySide6.QtCore import Qt

from client.gui.helpers import open_downloads_folder
from client.core.fileBrowser import FileBrowser
from client.gui.fileView import FileView
from client.gui.downloadView import DownloadView
from client.core.downloadManager import DownloadManager
from client.core.fileStatus import FileStatus
from client.config import DOWNLOAD_DIR

class FileClientGUI(QMainWindow):
    def __init__(self, auto_load=True):
        super().__init__()
        self.setWindowTitle("FLUX — Multi File Downloader")
        self.setMinimumSize(600, 735)
        self.resize(680, 760)

        self.browser = FileBrowser()
        self.download_manager = DownloadManager(self)

        self._build_ui()
        self._wire_signals()
        self._load_styles()

        if auto_load:
            self.load_files()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("FLUX")
        title.setObjectName("appTitle")
        subtitle = QLabel("Multi File Downloader")
        subtitle.setObjectName("appSubtitle")
        subtitle.setAlignment(Qt.AlignVCenter)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addStretch()

        self.refresh_btn = QPushButton("↻  Refresh")
        self.refresh_btn.setObjectName("refreshBtn")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.load_files)
        header_layout.addWidget(self.refresh_btn)
        root.addWidget(header)
        root.addWidget(self._make_divider())

        # File view (search + file list)
        file_section = QWidget()
        file_section.setObjectName("body")
        file_section.setMinimumHeight(360)
        file_layout = QVBoxLayout(file_section)
        file_layout.setContentsMargins(24, 20, 24, 0)
        file_layout.setSpacing(14)

        self.file_view = FileView()
        file_layout.addWidget(self.file_view)

        self.download_btn = QPushButton("⬇  Download Selected")
        self.download_btn.setObjectName("downloadBtn")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.clicked.connect(self._on_download_selected)
        self.download_btn.setFixedHeight(44)
        self.download_btn.setMinimumWidth(200)
        self.download_btn.setEnabled(False)
        file_layout.addWidget(self.download_btn)
        

        root.addWidget(file_section)
        root.addSpacing(10)
        root.addWidget(self._make_divider())

        # Downloads panel
        downloads_section = QWidget()
        downloads_section.setObjectName("downloadsPanel")
        downloads_layout = QVBoxLayout(downloads_section)
        downloads_layout.setContentsMargins(24, 16, 24, 16)
        downloads_layout.setSpacing(10)

        self.download_view = DownloadView()
        downloads_layout.addWidget(self.download_view)

        root.addWidget(downloads_section, stretch=1) 

        self.status_bar = self.statusBar()
        self.status_bar.setObjectName("mainStatusBar")
        self.status_bar.showMessage("Ready") 

    def _wire_signals(self):
        # Browser → FileView
        self.browser.files_changed.connect(self.file_view.set_files)
        self.browser.fetch_error.connect(
            lambda e: self.file_view.show_error(f"Connection error: {e}")
        )
        self.browser.status_message.connect(self.status_bar.showMessage)
        self.browser.loading_changed.connect(self._on_loading_changed)

        # FileView → Browser / DownloadManager
        self.file_view.search_changed.connect(self.browser.set_filter)
        self.file_view.download_requested.connect(self.download_manager.download)
        self.file_view.open_downloads_requested.connect(
            lambda: open_downloads_folder(DOWNLOAD_DIR)
        )

        # DownloadManager → DownloadView
        self.download_manager.download_started.connect(self.download_view.add_download)
        self.download_manager.download_started.connect(self._on_download_started)
        self.download_manager.progress_changed.connect(self.download_view.update_progress)
        self.download_manager.download_finished.connect(self._handle_download_result)

        # DownloadView → DownloadManager
        self.download_view.cancel_requested.connect(self.download_manager.cancel)
        self.download_view.clear_requested.connect(self._on_clear_downloads)
        
        # Update Download button's State
        self.file_view.list_widget.itemSelectionChanged.connect(self._update_download_btn)
        self.download_manager.download_started.connect(lambda _: self._update_download_btn())
        self.download_manager.download_finished.connect(lambda *_: self._update_download_btn())
    
    
    def _on_download_started(self, filename: str):
        self.file_view.set_file_status(filename, FileStatus.DOWNLOADING)

    def _handle_download_result(self, filename, success, msg):
        self.download_view.mark_finished(filename, success, msg)

        if success:
            self.file_view.set_file_status(filename, FileStatus.DOWNLOADED)
        elif msg == "Cancelled":
            self.file_view.set_file_status(filename, FileStatus.CANCELLED)
        else:
            self.file_view.set_file_status(filename, FileStatus.FAILED)
        
    def _update_download_btn(self):
        selected = self.file_view.selected_files()
        if not selected:
            self.download_btn.setEnabled(False)
            self.download_btn.setText("⬇  Download Selected")
            return

        active = set(self.download_manager._coordinators.keys())
        downloadable = [(f, s) for f, s in selected if f not in active]

        if not downloadable:
            self.download_btn.setEnabled(False)
            self.download_btn.setText("⬇  Already Downloading")
        else:
            self.download_btn.setEnabled(True)
            self.download_btn.setText(
                f"⬇  Download ({len(downloadable)} file{'s' if len(downloadable) != 1 else ''})"
            )
    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("divider")
        return line

    def _load_styles(self):
        try:
            qss_path = os.path.join(os.path.dirname(__file__), "clientGui.qss")
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print("QSS load failed:", e)

    def load_files(self):
        self.file_view.search_bar.blockSignals(True)
        self.file_view.search_bar.clear()
        self.file_view.search_bar.blockSignals(False)
        self.browser.set_filter("")
        self.browser.load_files()

    def _on_loading_changed(self, is_loading: bool):
        self.refresh_btn.setEnabled(not is_loading)
        self.refresh_btn.setText("↻  Loading..." if is_loading else "↻  Refresh")

    def _on_download_selected(self):
        selected = self.file_view.selected_files()
        if not selected:
            return
        active = set(self.download_manager._coordinators.keys())
        for filename, size in selected:
            if filename not in active:
                self.download_manager.download(filename, size)

    def _on_clear_downloads(self):
        self.download_manager.clear_all()
        self.download_view.clear_all()

    def closeEvent(self, event):
        self.browser.wait_for_fetch(2000)
        self.download_manager.clear_all()
        self.download_manager.wait_all(timeout_ms=3000)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = FileClientGUI()
    window.show()
    sys.exit(app.exec())
