import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit,
    QProgressBar, QScrollArea, QFrame,
    QMainWindow, QListWidgetItem, QMessageBox, QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QThread, Signal
from client.client import Client


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
    progress = Signal(str, int)
    finished_file = Signal(str, bool, str)

    def __init__(self, filenames: list[str]):
        super().__init__()
        self.filenames = filenames

    def run(self):
        c = None
        try:
            c = Client()

            for filename in self.filenames:
                try:
                    def on_progress(received, total, fn=filename):
                        percent = 0 if total == 0 else int((received / total) * 100)
                        self.progress.emit(fn, percent)

                    success, save_path = c.download_file(
                        filename,
                        on_progress=on_progress
                    )

                    self.finished_file.emit(filename, success, save_path or "")

                except Exception as file_err:
                    self.finished_file.emit(filename, False, str(file_err))

        except Exception as e:
            # global failure (connection broke etc.)
            error_msg = str(e)
            for filename in self.filenames:
                self.finished_file.emit(filename, False, error_msg)

        finally:
            if c:
                c.close()

class DownloadItemWidget(QFrame):
    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        self.setObjectName("downloadItem")
        self.filename = filename

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        self.name_label = QLabel(filename)
        self.name_label.setObjectName("downloadFilename")

        self.status_label = QLabel("Queued")
        self.status_label.setObjectName("downloadStatus")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        top_row.addWidget(self.name_label)
        top_row.addStretch()
        top_row.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("downloadProgress")
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)

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

    def set_error(self):
        self.status_label.setText("✗ Failed")
        self.status_label.setProperty("state", "error")
        self.info_label.setText("Download failed")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)


class FileClientGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FLUX — Multi File Downloader")
        self.setMinimumSize(620, 700)
        self.resize(680, 760)

        self._all_files: list[str] = []
        self._download_widgets: dict[str, DownloadItemWidget] = {}
        self._download_threads: list[DownloadThread] = []

        self._build_ui()
        self._load_styles()
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

        header = self.list_widget.header()

        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)

        header.resizeSection(1, 75)
        
        self.list_widget.setRootIsDecorated(False)
        body_layout.addWidget(self.list_widget)

        self.download_btn = QPushButton("⬇  Download Selected")
        self.download_btn.setObjectName("downloadBtn")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.clicked.connect(self._on_download_selected)
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

    def load_files(self):
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("↻  Loading...")
        self.status_bar.showMessage("Connecting to server...")

        self._fetch_thread = FetchFilesThread()
        self._fetch_thread.files_received.connect(self._on_files_received)
        self._fetch_thread.error_occurred.connect(self._on_fetch_error)
        self._fetch_thread.finished.connect(lambda: self._cleanup_thread(self._fetch_thread))
        self._fetch_thread.finished.connect(lambda: self.refresh_btn.setEnabled(True))
        self._fetch_thread.finished.connect(lambda: self.refresh_btn.setText("↻  Refresh"))
        self._fetch_thread.start()

    def _on_files_received(self, files: list[tuple[str, int]]):
        self._all_files = files
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
                item = QTreeWidgetItem([name, self._format_size(size)])
                item.setData(0, Qt.UserRole, name)
                self.list_widget.addTopLevelItem(item)
            self.count_label.setText(f"{len(files)} file{'s' if len(files) != 1 else ''}")
                
    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        else:
            return f"{size/1024/1024:.1f} MB" 
        
    def _filter_files(self, query: str):
        q = query.strip().lower()
        filtered = [(n, s) for n, s in self._all_files if q in n.lower()] if q else self._all_files
        self._render_file_list(filtered)

    def _on_download_selected(self):
        selected = [item.data(0, Qt.UserRole) for item in self.list_widget.selectedItems()]
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select at least one file to download.")
            return

        to_download = []
        for filename in selected:
            if filename not in self._download_widgets:
                widget = DownloadItemWidget(filename)
                idx = self.downloads_layout.count() - 1
                self.downloads_layout.insertWidget(idx, widget)
                self._download_widgets[filename] = widget
                to_download.append(filename)

        if not to_download:
            self.status_bar.showMessage("Selected files are already in the download queue")
            return

        self.status_bar.showMessage(f"Downloading {len(to_download)} file{'s' if len(to_download) != 1 else ''}...")

        thread = DownloadThread(to_download)
        thread.progress.connect(self._on_download_progress)
        thread.finished_file.connect(self._on_file_finished)
        thread.finished.connect(lambda t=thread: self._cleanup_thread(t))
        thread.start()
        self._download_threads.append(thread)

    def _on_download_progress(self, filename: str, percent: int):
        if filename in self._download_widgets:
            self._download_widgets[filename].set_progress(percent)

    def _on_file_finished(self, filename: str, success: bool, save_path: str):
        if filename in self._download_widgets:
            if success:
                self._download_widgets[filename].set_progress(100)
            else:
                self._download_widgets[filename].set_error()

        self._download_threads = [t for t in self._download_threads if t.isRunning()]

        self.status_bar.showMessage(
            f"{'✓' if success else '✗'} {filename} — {'saved to ' + save_path if success else 'failed'}"
        )
        

    def _clear_downloads(self):
        for widget in self._download_widgets.values():
            self.downloads_layout.removeWidget(widget)
            widget.deleteLater()
        self._download_widgets.clear()
        self.status_bar.showMessage("Download queue cleared")
        
    def _cleanup_thread(self, thread):
        if thread in self._download_threads:
            self._download_threads.remove(thread)
        thread.deleteLater()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = FileClientGUI()
    window.show()
    sys.exit(app.exec())