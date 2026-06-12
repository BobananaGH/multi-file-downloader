import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QScrollArea, QFrame,QMainWindow, QMessageBox, QTreeWidget, QTreeWidgetItem,QHeaderView, QMenu
)
from PySide6.QtCore import Qt, QThread
from functools import partial

from shared.icons import get_file_icon
from gui.workers import FetchFilesThread, DownloadThread
from gui.widgets import DownloadItemWidget, SortableTreeItem
from gui.helpers import format_size
from gui.menu import show_file_context_menu
    

class FileClientGUI(QMainWindow):
    def __init__(self, auto_load=True):
        super().__init__()
        self.setWindowTitle("FLUX — Multi File Downloader")
        self.setMinimumSize(620, 700)
        self.resize(680, 760)

        self._all_files: list[tuple[str, int]] = []
        self._filtered_files: list[tuple[str, int]] = []
        self._download_widgets: dict[str, DownloadItemWidget] = {}
        self._threads: set[QThread] = set()
        self._downloads: dict[str, dict]

        self._build_ui()
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

        # Body
        body = QWidget()
        body.setObjectName("body")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 0)
        body_layout.setSpacing(14)

        search_row = QHBoxLayout()
        search_icon = QLabel("🔍")
        search_icon.setObjectName("searchIcon")
        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("searchBar")
        self.search_bar.setPlaceholderText("Search files...")
        self.search_bar.textChanged.connect(self._filter_files)
        search_row.addWidget(search_icon)
        search_row.addWidget(self.search_bar)
        body_layout.addLayout(search_row)

        list_header = QHBoxLayout()
        files_label = QLabel("SERVER FILES")
        files_label.setObjectName("sectionLabel")
        self.count_label = QLabel("0 files")
        self.count_label.setObjectName("countLabel")
        list_header.addWidget(files_label)
        list_header.addStretch()
        list_header.addWidget(self.count_label)
        body_layout.addLayout(list_header)

        self.list_widget = QTreeWidget()
        self.list_widget.setObjectName("fileList")
        self.list_widget.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.list_widget.setFixedHeight(220)
        self.list_widget.setHeaderLabels(["Filename", "Size"])
        self.list_widget.setSortingEnabled(True)
        self.list_widget.setRootIsDecorated(False)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_file_context_menu)

        hdr = self.list_widget.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.resizeSection(1, 75)

        body_layout.addWidget(self.list_widget)

        self.download_btn = QPushButton("⬇  Download Selected")
        self.download_btn.setObjectName("downloadBtn")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.clicked.connect(self._start_download)
        body_layout.addWidget(self.download_btn)
        root.addWidget(body)

        root.addSpacing(10)
        root.addWidget(self._make_divider())

        # Downloads panel
        downloads_panel = QWidget()
        downloads_panel.setObjectName("downloadsPanel")
        panel_layout = QVBoxLayout(downloads_panel)
        panel_layout.setContentsMargins(24, 16, 24, 16)
        panel_layout.setSpacing(10)

        dl_header = QHBoxLayout()
        dl_title = QLabel("DOWNLOADS")
        dl_title.setObjectName("sectionLabel")
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("clearBtn")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_downloads)
        dl_header.addWidget(dl_title)
        dl_header.addStretch()
        dl_header.addWidget(self.clear_btn)
        panel_layout.addLayout(dl_header)

        scroll = QScrollArea()
        scroll.setObjectName("downloadScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(200)

        self.downloads_container = QWidget()
        self.downloads_container.setObjectName("downloadsContainer")
        self.downloads_layout = QVBoxLayout(self.downloads_container)
        self.downloads_layout.setContentsMargins(0, 0, 0, 0)
        self.downloads_layout.setSpacing(6)
        self.downloads_layout.addStretch()

        scroll.setWidget(self.downloads_container)
        panel_layout.addWidget(scroll)
        root.addWidget(downloads_panel)
        root.addStretch()

        self.status_bar = self.statusBar()
        self.status_bar.setObjectName("mainStatusBar")
        self.status_bar.showMessage("Ready")

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("divider")
        return line

    def _load_styles(self):
        try:
            qss_path = os.path.join(os.path.dirname(__file__), "clientGui.qss")
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            pass

    def _start_download(self, filename: str):
        if filename in self._download_widgets:
            self.status_bar.showMessage(
                f"{filename} is already in the download queue"
            )
            return

        widget = DownloadItemWidget(filename)
        widget.cancel_requested.connect(self._on_cancel_requested)

        idx = self.downloads_layout.count() - 1
        self.downloads_layout.insertWidget(idx, widget)
        self._download_widgets[filename] = widget

        thread = DownloadThread(filename)
        thread.progress.connect(self._on_download_progress)
        thread.finished_file.connect(self._on_file_finished)

        self._register_thread(thread)

        thread.start()

        self.status_bar.showMessage(f"Downloading {filename}...")

    def load_files(self):
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("↻  Loading...")
        self.status_bar.showMessage("Connecting to server...")

        thread = FetchFilesThread()

        thread.files_received.connect(self._on_files_received)
        thread.error_occurred.connect(self._on_fetch_error)

        thread.finished.connect(partial(self._cleanup_thread, thread))
        thread.finished.connect(thread.deleteLater)

        self._register_thread(thread)
        thread.start()

    def _on_files_received(self, files: list[tuple[str, int]]):
        self._all_files = files
        self._filtered_files = list(files)
        self._render_file_list(files)
        count = len(files)
        self.status_bar.showMessage(
            f"Connected — {count} file{'s' if count != 1 else ''} available"
        )

    def _on_fetch_error(self, error: str):
        self._all_files = []
        self.list_widget.clear()
        item = QTreeWidgetItem([f"⚠  Connection error: {error}", ""])
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self.list_widget.addTopLevelItem(item)
        self.count_label.setText("—")
        self.status_bar.showMessage(f"Error: {error}")

    def _render_file_list(self, files: list[tuple[str, int]]):
        self.list_widget.clear()
        if not files:
            item = QTreeWidgetItem(["No files available on server", ""])
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.list_widget.addTopLevelItem(item)
            self.count_label.setText("0 files")
        else:
            for name, size in files:
                icon = get_file_icon(name)
                item = SortableTreeItem([f"{icon}  {name}", format_size(size)])
                item.setData(0, Qt.UserRole, name)
                item.setData(1, Qt.UserRole, size)
                self.list_widget.addTopLevelItem(item)
            self.count_label.setText(f"{len(files)} file{'s' if len(files) != 1 else ''}")

    def _filter_files(self, query: str):
        q = query.strip().lower()
        self._filtered_files = [(n, s) for n, s in self._all_files if q in n.lower()] if q else list(self._all_files)
        self._render_file_list(self._filtered_files)

    def _on_cancel_requested(self, filename: str):
        for thread in self._download_threads:
            if thread.filename == filename:
                thread.cancel()
                break

    def _on_download_progress(self, filename: str, percent: int, speed: float, eta: float):
        widget = self._download_widgets.get(filename)
        if widget:
            widget.set_progress(percent, speed, eta)

    def _on_file_finished(self, filename: str, success: bool, save_path: str):
        if filename in self._download_widgets:
            if success:
                self._download_widgets[filename].set_progress(100)
            elif save_path == "Cancelled":
                self._download_widgets[filename].set_cancelled()
                self._download_widgets.pop(filename, None)
            else:
                self._download_widgets[filename].set_error(save_path or "Download failed")
                self._download_widgets.pop(filename, None)
        
        self.status_bar.showMessage(
            f"{'✓' if success else '✗'} {filename} — {'saved to ' + save_path if success else save_path or 'failed'}"
        )

    def _clear_downloads(self):
        for thread in self._download_threads:
            thread.cancel()

        for widget in self._download_widgets.values():
            self.downloads_layout.removeWidget(widget)
            widget.deleteLater()

        self._download_widgets.clear()
        self.status_bar.showMessage("Download queue cleared")
    
    def closeEvent(self, event):
        for thread in self._download_threads:
            thread.cancel()
            thread.wait(2000)
        if hasattr(self, '_fetch_thread') and self._fetch_thread.isRunning():
            self._fetch_thread.wait(2000)
        event.accept()
    
    def _register_thread(self, thread):
        self._threads.add(thread)
        thread.finished.connect(lambda: self._cleanup_thread(thread))
    
    def _cleanup_thread(self, thread):
        if thread in self._download_threads:
            self._threads.discard(thread)
        try:
            thread.deleteLater()
        except RuntimeError:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = FileClientGUI()
    window.show()
    sys.exit(app.exec())
