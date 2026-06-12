# Code/client/gui/widgets.py

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTreeWidgetItem
)
from PySide6.QtCore import Qt, Signal
from shared.icons import get_file_icon

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