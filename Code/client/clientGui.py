import sys
import os
import time
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit,
    QProgressBar, QScrollArea, QFrame,
    QMainWindow, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QMenu
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction
from client.client import Client
from shared.icons import get_file_icon

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
    progress = Signal(str, int, float, float)  # filename, percent, speed_kbps, eta_secs
    finished_file = Signal(str, bool, str)

    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        self._cancelled = False
        
    def cancel(self):
        self._cancelled = True

    def run(self):
        c = None
        try:
            c = Client()
            if self._cancelled:
                self.finished_file.emit(self.filename, False, "Cancelled")
                return

            start_time = time.time()
            last_bytes = [0]
            last_time = [start_time]

            def on_progress(received, total):
                if self._cancelled:
                    return
                now = time.time()
                elapsed = max(now - start_time, 0.1)
                interval = now - last_time[0]

                if interval > 0.2:
                    speed_bytes_s = max((received - last_bytes[0]) / interval, 0)
                    last_bytes[0] = received
                    last_time[0] = now
                else:
                    speed_bytes_s = (received / elapsed) if elapsed > 0 else 0

                speed_kb_s = speed_bytes_s / 1024
                remaining = total - received
                eta = (remaining / speed_bytes_s) if speed_bytes_s >= 1 else 0
                percent = 0 if total == 0 else int((received / total) * 100)
                self.progress.emit(self.filename, percent, speed_kb_s, eta)

            try:
                success, save_path = c.download_file(self.filename, on_progress=on_progress, is_cancelled=lambda: self._cancelled)
                if self._cancelled:
                    self.finished_file.emit(self.filename, False, "Cancelled")
                else:
                    self.finished_file.emit(self.filename, success, save_path or "")
            except Exception as e:
                if self._cancelled or "Cancelled" in str(e):
                    self.finished_file.emit(self.filename, False, "Cancelled")
                else:
                    self.finished_file.emit(self.filename, False, str(e))

        finally:
            if c:
                c.close()


class DownloadItemWidget(QFrame):
    cancel_requested = Signal(str)

    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        self.setObjectName("downloadItem")
        self.filename = filename

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Top row: filename + cancel + status
        top_row = QHBoxLayout()
        self.name_label = QLabel(f"{get_file_icon(filename)}  {filename}")
        self.name_label.setObjectName("downloadFilename")

        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setFixedSize(20, 20)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(lambda: self.cancel_requested.emit(self.filename))

        self.status_label = QLabel("Queued")
        self.status_label.setObjectName("downloadStatus")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        top_row.addWidget(self.name_label)
        top_row.addStretch()
        top_row.addWidget(self.cancel_btn)
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

    def set_progress(self, value: int, speed_kbps: float = 0, eta: float = 0):
        self.progress_bar.setValue(value)
        if value >= 100:
            self.status_label.setText("✓ Done")
            self.status_label.setProperty("state", "done")
            self.info_label.setText("Download complete")
            self.cancel_btn.setVisible(False)
        elif value > 0:
            self.status_label.setText(f"{value}%")
            self.status_label.setProperty("state", "active")
            speed_str = f"{speed_kbps:.1f} KB/s" if speed_kbps < 1024 else f"{speed_kbps/1024:.1f} MB/s"
            eta_str = f"{int(eta)}s left" if eta > 0 else ""
            self.info_label.setText(f"Downloading... {value}%  •  {speed_str}  •  {eta_str}")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def set_error(self, reason: str = "Download failed"):
        self.progress_bar.setValue(0)
        self.status_label.setText("✗ Failed")
        self.status_label.setProperty("state", "error")
        self.info_label.setText(reason)
        self.cancel_btn.setVisible(False)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def set_cancelled(self):
        self.status_label.setText("— Cancelled")
        self.status_label.setProperty("state", "error")
        self.info_label.setText("Cancelled by user")
        self.cancel_btn.setVisible(False)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

class SortableTreeItem(QTreeWidgetItem):
    def __lt__(self, other):
        col = self.treeWidget().sortColumn()
        if col == 1:
            return int(self.data(1, Qt.UserRole) or 0) < int(other.data(1, Qt.UserRole) or 0)
        return self.text(col).lower() < other.text(col).lower()
    
class FileClientGUI(QMainWindow):
    def __init__(self, auto_load=True):
        super().__init__()
        self.setWindowTitle("FLUX — Multi File Downloader")
        self.setMinimumSize(620, 700)
        self.resize(680, 760)

        self._all_files: list[tuple[str, int]] = []
        self._filtered_files: list[tuple[str, int]] = []
        self._download_widgets: dict[str, DownloadItemWidget] = {}
        self._download_threads: list[DownloadThread] = []

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
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)

        hdr = self.list_widget.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.resizeSection(1, 75)

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

    # ------------------------------------------------------------------ #
    #  Context Menu                                                        #
    # ------------------------------------------------------------------ #

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return

        filename = item.data(0, Qt.UserRole)
        if not filename:
            return

        menu = QMenu(self)

        download_action = QAction("⬇  Download", self)
        download_action.triggered.connect(lambda: self._download_single(filename))
        menu.addAction(download_action)

        copy_action = QAction("📋  Copy filename", self)
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(filename))
        menu.addAction(copy_action)

        open_action = QAction("📂  Open downloads folder", self)
        open_action.triggered.connect(self._open_downloads_folder)
        menu.addAction(open_action)

        menu.exec(self.list_widget.viewport().mapToGlobal(pos))

    def _download_single(self, filename: str):
        if filename not in self._download_widgets:
            widget = DownloadItemWidget(filename)
            widget.cancel_requested.connect(self._on_cancel_requested)
            idx = self.downloads_layout.count() - 1
            self.downloads_layout.insertWidget(idx, widget)
            self._download_widgets[filename] = widget

            thread = DownloadThread(filename)
            thread.progress.connect(self._on_download_progress)
            thread.finished_file.connect(self._on_file_finished)
            thread.finished.connect(lambda t=thread: self._cleanup_thread(t))
            thread.start()
            self._download_threads.append(thread)
            self.status_bar.showMessage(f"Downloading {filename}...")
        else:
            self.status_bar.showMessage(f"{filename} is already in the download queue")

    def _open_downloads_folder(self):
        path = os.path.join(os.path.dirname(__file__), "downloads")
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    # ------------------------------------------------------------------ #
    #  File List                                                           #
    # ------------------------------------------------------------------ #

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
                item = SortableTreeItem([f"{icon}  {name}", self._format_size(size)])
                item.setData(0, Qt.UserRole, name)
                # store raw size as int for proper numeric sorting
                item.setData(1, Qt.UserRole, size)
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
        self._filtered_files = [(n, s) for n, s in self._all_files if q in n.lower()] if q else list(self._all_files)
        self._render_file_list(self._filtered_files)

    # ------------------------------------------------------------------ #
    #  Download Logic                                                      #
    # ------------------------------------------------------------------ #

    def _on_download_selected(self):
        selected = [item.data(0, Qt.UserRole) for item in self.list_widget.selectedItems()]
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select at least one file to download.")
            return

        to_download = []
        for filename in selected:
            if filename not in self._download_widgets:
                widget = DownloadItemWidget(filename)
                widget.cancel_requested.connect(self._on_cancel_requested)
                idx = self.downloads_layout.count() - 1
                self.downloads_layout.insertWidget(idx, widget)
                self._download_widgets[filename] = widget
                to_download.append(filename)

        if not to_download:
            self.status_bar.showMessage("Selected files are already in the download queue")
            return

        self.status_bar.showMessage(f"Downloading {len(to_download)} file{'s' if len(to_download) != 1 else ''}...")

        for filename in to_download:
            thread = DownloadThread(filename)
            thread.progress.connect(self._on_download_progress)
            thread.finished_file.connect(self._on_file_finished)
            thread.finished.connect(lambda t=thread: self._cleanup_thread(t))
            thread.start()
            self._download_threads.append(thread)

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
            else:
                self._download_widgets[filename].set_error(save_path or "Download failed")
        
        self.status_bar.showMessage(
            f"{'✓' if success else '✗'} {filename} — {'saved to ' + save_path if success else save_path or 'failed'}"
        )

    def _clear_downloads(self):
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
        
    def _cleanup_thread(self, thread):
        if thread in self._download_threads:
            self._download_threads.remove(thread)
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