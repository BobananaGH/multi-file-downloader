import sys
import socket
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QLabel, QLineEdit,
    QProgressBar, QScrollArea, QFrame, QStatusBar,
    QMainWindow, QListWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QIcon, QFont

HOST = "127.0.0.1"
PORT = 5000


class DownloadItemWidget(QFrame):
    """Widget representing a single file download progress row."""

    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        self.setObjectName("downloadItem")
        self.filename = filename

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Top row: filename + status
        top_row = QHBoxLayout()
        self.name_label = QLabel(filename)
        self.name_label.setObjectName("downloadFilename")

        self.status_label = QLabel("Queued")
        self.status_label.setObjectName("downloadStatus")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        top_row.addWidget(self.name_label)
        top_row.addStretch()
        top_row.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("downloadProgress")
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)

        # Bottom row: size info
        self.info_label = QLabel("Waiting to start...")
        self.info_label.setObjectName("downloadInfo")

        layout.addLayout(top_row)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.info_label)

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)
        if value >= 100:
            self.status_label.setText("✓ Done")
            self.status_label.setProperty("state", "done")
            self.info_label.setText("Download complete")
        elif value > 0:
            self.status_label.setText(f"{value}%")
            self.status_label.setProperty("state", "active")
            self.info_label.setText(f"Downloading... {value}%")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)


class FetchFilesThread(QThread):
    """Worker thread to fetch file list from server without blocking UI."""
    files_received = Signal(list)
    error_occurred = Signal(str)

    def run(self):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(5)
            client.connect((HOST, PORT))
            data = client.recv(4096).decode()
            client.close()
            if data == "NO_FILES":
                self.files_received.emit([])
            else:
                self.files_received.emit(data.split("|"))
        except Exception as e:
            self.error_occurred.emit(str(e))


class FileClientGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FLUX — Multi File Downloader")
        self.setMinimumSize(620, 700)
        self.resize(680, 760)

        self._all_files: list[str] = []
        self._download_widgets: dict[str, DownloadItemWidget] = {}

        self._build_ui()
        self._load_styles()
        self.load_files()

    # ------------------------------------------------------------------ #
    #  UI Construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────
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

        # ── Divider ─────────────────────────────────────────────────────
        root.addWidget(self._make_divider())

        # ── Body ────────────────────────────────────────────────────────
        body = QWidget()
        body.setObjectName("body")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 0)
        body_layout.setSpacing(14)

        # Search bar
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

        # File list section label
        list_header = QHBoxLayout()
        files_label = QLabel("SERVER FILES")
        files_label.setObjectName("sectionLabel")
        self.count_label = QLabel("0 files")
        self.count_label.setObjectName("countLabel")
        list_header.addWidget(files_label)
        list_header.addStretch()
        list_header.addWidget(self.count_label)
        body_layout.addLayout(list_header)

        # File list
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("fileList")
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.setFixedHeight(220)
        body_layout.addWidget(self.list_widget)

        # Download button
        self.download_btn = QPushButton("⬇  Download Selected")
        self.download_btn.setObjectName("downloadBtn")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.clicked.connect(self._on_download_selected)
        body_layout.addWidget(self.download_btn)

        root.addWidget(body)

        # ── Divider ─────────────────────────────────────────────────────
        root.addSpacing(10)
        root.addWidget(self._make_divider())

        # ── Downloads Panel ─────────────────────────────────────────────
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

        # Scrollable download list
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

        # ── Status Bar ──────────────────────────────────────────────────
        self.status_bar = self.statusBar()
        self.status_bar.setObjectName("mainStatusBar")
        self.status_bar.showMessage("Ready")

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("divider")
        return line

    # ------------------------------------------------------------------ #
    #  Styles                                                              #
    # ------------------------------------------------------------------ #

    def _load_styles(self):
        try:
            with open("clientGui.qss", "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            pass  # Graceful fallback if .qss missing

    # ------------------------------------------------------------------ #
    #  File List Logic                                                     #
    # ------------------------------------------------------------------ #

    def load_files(self):
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("↻  Loading...")
        self.status_bar.showMessage("Connecting to server...")

        self._thread = FetchFilesThread()
        self._thread.files_received.connect(self._on_files_received)
        self._thread.error_occurred.connect(self._on_fetch_error)
        self._thread.finished.connect(lambda: self.refresh_btn.setEnabled(True))
        self._thread.finished.connect(lambda: self.refresh_btn.setText("↻  Refresh"))
        self._thread.start()

    def _on_files_received(self, files: list[str]):
        self._all_files = files
        self._render_file_list(files)
        count = len(files)
        self.status_bar.showMessage(
            f"Connected — {count} file{'s' if count != 1 else ''} available"
        )

    def _on_fetch_error(self, error: str):
        self._all_files = []
        self.list_widget.clear()
        err_item = QListWidgetItem(f"⚠  Connection error: {error}")
        err_item.setFlags(err_item.flags() & ~Qt.ItemIsSelectable)
        self.list_widget.addItem(err_item)
        self.count_label.setText("—")
        self.status_bar.showMessage(f"Error: {error}")

    def _render_file_list(self, files: list[str]):
        self.list_widget.clear()
        if not files:
            empty = QListWidgetItem("No files available on server")
            empty.setFlags(empty.flags() & ~Qt.ItemIsSelectable)
            self.list_widget.addItem(empty)
            self.count_label.setText("0 files")
        else:
            for f in files:
                self.list_widget.addItem(f)
            self.count_label.setText(f"{len(files)} file{'s' if len(files) != 1 else ''}")

    def _filter_files(self, query: str):
        q = query.strip().lower()
        filtered = [f for f in self._all_files if q in f.lower()] if q else self._all_files
        self._render_file_list(filtered)

    def _sort_files(self, mode: str = "name"):
        files = self._all_files.copy()
        if mode == "name":
            files.sort(key=lambda x: x.lower())
        elif mode == "name_desc":
            files.sort(key=lambda x: x.lower(), reverse=True)
        self._render_file_list(files)

    # ------------------------------------------------------------------ #
    #  Download Logic                                                      #
    # ------------------------------------------------------------------ #

    def _on_download_selected(self):
        selected = [item.text() for item in self.list_widget.selectedItems()]
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select at least one file to download.")
            return

        added = 0
        for filename in selected:
            if filename not in self._download_widgets:
                widget = DownloadItemWidget(filename)
                # Insert before the stretch at the end
                idx = self.downloads_layout.count() - 1
                self.downloads_layout.insertWidget(idx, widget)
                self._download_widgets[filename] = widget
                added += 1

        if added:
            self.status_bar.showMessage(f"Queued {added} file{'s' if added != 1 else ''} for download")
        else:
            self.status_bar.showMessage("Selected files are already in the download queue")

    def _clear_downloads(self):
        for widget in self._download_widgets.values():
            self.downloads_layout.removeWidget(widget)
            widget.deleteLater()
        self._download_widgets.clear()
        self.status_bar.showMessage("Download queue cleared")


# ─────────────────────────────────────────────────────────────────────── #

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = FileClientGUI()
    window.show()
    sys.exit(app.exec())
