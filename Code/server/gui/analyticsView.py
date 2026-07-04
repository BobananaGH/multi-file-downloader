
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt


class AnalyticsView(QWidget):
    def __init__(self, format_time, format_size):
        super().__init__()
        self.format_time = format_time
        self.format_size = format_size
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        left_title = QLabel("DOWNLOAD TRANSACTION LOG")
        left_title.setObjectName("sectionLabel")
        left_layout.addWidget(left_title)

        self.history_table = QTableWidget()
        self.history_table.setObjectName("statsTable")
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Time", "Client IP", "Filename", "Total Size", "Sent Bytes", "Status"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setSortingEnabled(True)
        left_layout.addWidget(self.history_table)

        layout.addLayout(left_layout, 2)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)
        right_title = QLabel("POPULAR FILES (TOP DOWNLOADS)")
        right_title.setObjectName("sectionLabel")
        right_layout.addWidget(right_title)

        self.popular_table = QTableWidget()
        self.popular_table.setObjectName("statsTable")
        self.popular_table.setColumnCount(2)
        self.popular_table.setHorizontalHeaderLabels(["Filename", "Downloads Count"])
        self.popular_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.popular_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.popular_table.setSortingEnabled(True)
        right_layout.addWidget(self.popular_table)

        layout.addLayout(right_layout, 1)

    def update_history(self, history):
        self.history_table.setSortingEnabled(False)
        self.history_table.setRowCount(0)

        for event in history:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)

            item_time = QTableWidgetItem(self.format_time(event["timestamp"]))
            item_time.setData(Qt.UserRole, event["timestamp"])

            item_ip = QTableWidgetItem(f"{event['ip']}:{event['port']}")
            item_file = QTableWidgetItem(event["filename"])

            item_size = QTableWidgetItem(self.format_size(event["total_size"]))
            item_size.setData(Qt.UserRole, event["total_size"])

            item_sent = QTableWidgetItem(self.format_size(event["bytes_sent"]))
            item_sent.setData(Qt.UserRole, event["bytes_sent"])

            item_status = QTableWidgetItem(event["status"])
            item_status.setForeground(Qt.green if event["status"] == "Success" else Qt.red)

            for item in (item_time, item_ip, item_file, item_size, item_sent, item_status):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            self.history_table.setItem(row, 0, item_time)
            self.history_table.setItem(row, 1, item_ip)
            self.history_table.setItem(row, 2, item_file)
            self.history_table.setItem(row, 3, item_size)
            self.history_table.setItem(row, 4, item_sent)
            self.history_table.setItem(row, 5, item_status)

        self.history_table.setSortingEnabled(True)

    def update_popular(self, counts):
        self.popular_table.setSortingEnabled(False)
        self.popular_table.setRowCount(0)

        for filename, count in counts.items():
            row = self.popular_table.rowCount()
            self.popular_table.insertRow(row)

            item_file = QTableWidgetItem(filename)
            item_count = QTableWidgetItem(str(count))
            item_count.setData(Qt.DisplayRole, count)

            for item in (item_file, item_count):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            self.popular_table.setItem(row, 0, item_file)
            self.popular_table.setItem(row, 1, item_count)

        self.popular_table.setSortingEnabled(True)
