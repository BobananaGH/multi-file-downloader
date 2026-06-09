import sys
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit,
    QTreeWidget, QFrame
)
from PySide6.QtCore import Qt


class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FLUX Server Dashboard")
        self.setMinimumSize(700, 600)

        self._build_ui()
        self._load_styles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel("FLUX SERVER")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        self.status_label = QLabel("Server Status: Stopped")
        self.status_label.setObjectName("statusLabel")
        root.addWidget(self.status_label)

        self.info_label = QLabel("IP: 127.0.0.1  |  Port: 5000  |  TLS: Enabled")
        root.addWidget(self.info_label)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start Server")
        self.stop_btn = QPushButton("Stop Server")
        self.clear_btn = QPushButton("Clear Logs")

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.clear_btn)
        root.addLayout(btn_row)

        root.addWidget(self._make_divider())

        logs_title = QLabel("SERVER LOGS")
        logs_title.setObjectName("sectionLabel")
        root.addWidget(logs_title)

        self.log_area = QTextEdit()
        self.log_area.setPlaceholderText("Server logs will be displayed here...")
        root.addWidget(self.log_area)

        clients_title = QLabel("CONNECTED CLIENTS")
        clients_title.setObjectName("sectionLabel")
        root.addWidget(clients_title)

        self.client_list = QTreeWidget()
        self.client_list.setHeaderLabels(["Username", "IP Address", "Status"])
        root.addWidget(self.client_list)

        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)
        self.clear_btn.clicked.connect(self.clear_logs)

    def _make_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        return line

    def _load_styles(self):
        try:
            qss_path = os.path.join(os.path.dirname(__file__), "serverGui.qss")
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            pass

    def start_server(self):
        self.status_label.setText("Server Status: Running")
        self.log_area.append("[INFO] Server started")

    def stop_server(self):
        self.status_label.setText("Server Status: Stopped")
        self.log_area.append("[INFO] Server stopped")

    def clear_logs(self):
        self.log_area.clear()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ServerGUI()
    window.show()
    sys.exit(app.exec())