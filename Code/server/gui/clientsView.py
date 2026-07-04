import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, Signal


class ClientsView(QWidget):
    """Tab hiển thị danh sách client đang kết nối tới server (tách từ _build_tab_clients / _update_clients_table trong serverGui.py)."""

    kick_requested = Signal(str, str)  # ip, port

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        title = QLabel("ACTIVE CLIENT CONNECTIONS")
        title.setObjectName("sectionLabel")
        header_row.addWidget(title)
        header_row.addStretch()
        layout.addLayout(header_row)

        # Client details table
        self.client_table = QTableWidget()
        self.client_table.setObjectName("statsTable")
        self.client_table.setColumnCount(5)
        self.client_table.setHorizontalHeaderLabels([
            "IP Address", "Port", "Connected Since", "Uptime", "Current Activity"
        ])
        self.client_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.client_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.client_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.client_table.setSelectionMode(QTableWidget.SingleSelection)
        self.client_table.setSortingEnabled(True)
        layout.addWidget(self.client_table)

        # Action row
        action_row = QHBoxLayout()
        self.kick_btn = QPushButton("⚠  Kick Selected Client")
        self.kick_btn.setObjectName("kickBtn")
        self.kick_btn.setCursor(Qt.PointingHandCursor)
        self.kick_btn.setEnabled(False)
        self.kick_btn.clicked.connect(self._on_kick_clicked)
        action_row.addWidget(self.kick_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.client_table.itemSelectionChanged.connect(
            lambda: self.kick_btn.setEnabled(len(self.client_table.selectedItems()) > 0)
        )

    # ---------------- Public API ----------------
    def selected_client(self):
        """Trả về tuple (ip, port) của client đang được chọn trong bảng, hoặc None nếu chưa chọn gì."""
        selected_rows = self.client_table.selectedItems()
        if not selected_rows:
            return None

        row = selected_rows[0].row()
        ip = self.client_table.item(row, 0).text()
        port = self.client_table.item(row, 1).text()
        return ip, port

    def update_clients(self, clients):
        """Cập nhật lại toàn bộ bảng client (gọi mỗi khi ServerGUI nhận stats mới từ engine)."""
        self.client_table.setSortingEnabled(False)
        self.client_table.setRowCount(0)

        for info in clients:
            row = self.client_table.rowCount()
            self.client_table.insertRow(row)

            # Columns: IP, Port, Connected Since, Uptime, Activity
            item_ip = QTableWidgetItem(info["ip"])
            item_port = QTableWidgetItem(str(info["port"]))
            item_port.setData(Qt.DisplayRole, info["port"])

            conn_time = self._format_time(info["connect_time"])
            item_conn = QTableWidgetItem(conn_time)

            uptime_str = self._format_uptime(info["uptime"])
            item_uptime = QTableWidgetItem(uptime_str)
            item_uptime.setData(Qt.UserRole, info["uptime"])

            item_act = QTableWidgetItem(info["current_action"])

            # Read-only
            for item in (item_ip, item_port, item_conn, item_uptime, item_act):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            self.client_table.setItem(row, 0, item_ip)
            self.client_table.setItem(row, 1, item_port)
            self.client_table.setItem(row, 2, item_conn)
            self.client_table.setItem(row, 3, item_uptime)
            self.client_table.setItem(row, 4, item_act)

        self.client_table.setSortingEnabled(True)

    # ---------------- Internal handlers ----------------
    def _on_kick_clicked(self):
        client = self.selected_client()
        if not client:
            return
        ip, port = client

        confirm = QMessageBox.warning(
            self, "Kick Connection",
            f"Are you sure you want to kick client connection {ip}:{port}?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            self.kick_requested.emit(ip, port)

    # ---------------- Format helpers ----------------
    @staticmethod
    def _format_uptime(secs):
        if secs <= 0:
            return "0s"
        hrs = int(secs // 3600)
        mins = int((secs % 3600) // 60)
        seconds = int(secs % 60)
        if hrs > 0:
            return f"{hrs}h {mins}m {seconds}s"
        if mins > 0:
            return f"{mins}m {seconds}s"
        return f"{seconds}s"

    @staticmethod
    def _format_time(timestamp):
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")