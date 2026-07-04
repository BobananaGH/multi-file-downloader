import sys
import os
import time
import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget,
    QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QObject, Signal, Slot

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.server import ServerEngine
from shared.utils import add_log_handler, remove_log_handler
from gui.dashboardView import DashboardView
from gui.clientsView import ClientsView

class ServerSignals(QObject):
    stats_updated = Signal(dict)
    log_received = Signal(str, str)


class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FLUX — Server Administrator Console")
        self.setMinimumSize(950, 720)
        self.resize(1000, 760)

        # Create engine (bind to port 5000)
        self.engine = ServerEngine(host="0.0.0.0", port=5000)

        # Thread-safe Signals
        self.signals = ServerSignals()
        self.signals.stats_updated.connect(self.on_stats_updated)
        self.signals.log_received.connect(self.on_log_received)

        self._build_ui()
        self._load_styles()
        
        # Register callback/handler with engine
        self.engine.register_status_callback(self.signals.stats_updated.emit)
        add_log_handler(self.signals.log_received.emit)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header section
        header = QWidget()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 20, 24, 20)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title = QLabel("FLUX SERVER CONTROL PANEL")
        title.setObjectName("appTitle")
        subtitle = QLabel("Security, Performance & Traffic Management Console")
        subtitle.setObjectName("appSubtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)

        header_layout.addStretch()

        # Live status bulb
        self.status_bulb = QLabel()
        self.status_bulb.setFixedSize(14, 14)
        self.status_bulb.setObjectName("statusBulbStopped")
        header_layout.addWidget(self.status_bulb)

        self.status_label = QLabel("Server: Stopped")
        self.status_label.setObjectName("statusLabel")
        header_layout.addWidget(self.status_label)

        root.addWidget(header)
        root.addWidget(self._make_divider())

        # Main Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        root.addWidget(self.tabs)

        self._build_tab_dashboard()
        self._build_tab_clients()
        self._build_tab_analytics()

        # Status Bar
        self.status_bar = self.statusBar()
        self.status_bar.setObjectName("mainStatusBar")
        self.status_bar.showMessage("Ready")

    def _build_tab_dashboard(self):
        self.dashboard = DashboardView()
        self.dashboard.start_requested.connect(self.start_server)
        self.dashboard.stop_requested.connect(self.stop_server)

        self.tabs.addTab(self.dashboard, "⚙  Dashboard & Console")

    def _build_tab_clients(self):
        self.clients_view = ClientsView()
        self.clients_view.kick_requested.connect(self.kick_client)

        self.tabs.addTab(self.clients_view, "👥  Active Connections")

    def _build_tab_analytics(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)

        # Left: Download History
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

        # Right: Popular Files / File Counts
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

        self.tabs.addTab(tab, "📈  Downloads & Traffic Analytics")

    def _make_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("divider")
        return line

    def _load_styles(self):
        try:
            qss_path = os.path.join(os.path.dirname(__file__), "serverGui.qss")
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            pass

    # ------------------------------------------------------------------ #
    #  Slots / Thread safe handlers                                      #
    # ------------------------------------------------------------------ #

    @Slot(dict)
    def on_stats_updated(self, stats):
        # Update server status indicators
        is_running = stats["is_running"]
        if is_running:
            self.status_label.setText("Server: Running")
            self.status_bulb.setObjectName("statusBulbRunning")
        else:
            self.status_label.setText("Server: Stopped")
            self.status_bulb.setObjectName("statusBulbStopped")
        self.status_bulb.style().unpolish(self.status_bulb)
        self.status_bulb.style().polish(self.status_bulb)

        self.dashboard.set_server_running(is_running)
        self.dashboard.update_metrics(stats)

        # Update Active Clients Table
        self.clients_view.update_clients(stats["active_clients"])

        # Update Analytics Tables
        self._update_analytics_tables(stats["download_history"], stats["download_counts"])

    @Slot(str, str)
    def on_log_received(self, category, message):
        self.dashboard.append_log(category, message)

    # ------------------------------------------------------------------ #
    #  Actions & UI Updates                                              #
    # ------------------------------------------------------------------ #

    def start_server(self):
        self.dashboard.append_log("INFO", "Starting server...")
        if self.engine.start():
            self.status_bar.showMessage("Server started successfully.")
        else:
            QMessageBox.critical(self, "Port Conflict", "Failed to start server. Port 5000 might already be in use!")
            self.status_bar.showMessage("Error: Server failed to start.")

    def stop_server(self):
        self.dashboard.append_log("INFO", "Shutting down server...")
        self.engine.stop()
        self.status_bar.showMessage("Server stopped.")

    def kick_client(self, ip, port):
        if self.engine.kick_client(ip, port):
            self.status_bar.showMessage(f"Kicked client {ip}:{port}")
        else:
            QMessageBox.critical(self, "Error", f"Failed to kick client {ip}:{port}")

    def _update_analytics_tables(self, history, counts):
        # Update download history table
        self.history_table.setSortingEnabled(False)
        self.history_table.setRowCount(0)
        
        for event in history:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)

            time_str = self.format_time(event["timestamp"])
            item_time = QTableWidgetItem(time_str)
            item_time.setData(Qt.UserRole, event["timestamp"])

            ip_str = f"{event['ip']}:{event['port']}"
            item_ip = QTableWidgetItem(ip_str)

            item_file = QTableWidgetItem(event["filename"])
            
            size_str = self.dashboard.format_size(event["total_size"])
            item_size = QTableWidgetItem(size_str)
            item_size.setData(Qt.UserRole, event["total_size"])

            sent_str = self.dashboard.format_size(event["bytes_sent"])
            item_sent = QTableWidgetItem(sent_str)
            item_sent.setData(Qt.UserRole, event["bytes_sent"])

            item_status = QTableWidgetItem(event["status"])
            if event["status"] == "Success":
                item_status.setForeground(Qt.green)
            else:
                item_status.setForeground(Qt.red)

            for item in (item_time, item_ip, item_file, item_size, item_sent, item_status):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            self.history_table.setItem(row, 0, item_time)
            self.history_table.setItem(row, 1, item_ip)
            self.history_table.setItem(row, 2, item_file)
            self.history_table.setItem(row, 3, item_size)
            self.history_table.setItem(row, 4, item_sent)
            self.history_table.setItem(row, 5, item_status)

        self.history_table.setSortingEnabled(True)

        # Update popular files table
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

    # ------------------------------------------------------------------ #
    #  Format Helpers                                                    #
    # ------------------------------------------------------------------ #

    def format_time(self, timestamp):
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def on_destroyed(self):
        # Make sure callbacks are removed and engine stops
        try:
            remove_log_handler(self.signals.log_received.emit)
            self.engine.unregister_status_callback(self.signals.stats_updated.emit)
            self.engine.stop()
        except Exception:
            pass

    def closeEvent(self, event):
        self.on_destroyed()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ServerGUI()
    window.show()
    sys.exit(app.exec())