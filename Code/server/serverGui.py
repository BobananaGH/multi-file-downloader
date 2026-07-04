# Code/server/ServerGui.py
import sys
import os
import time
import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget,
    QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QObject, Signal, Slot

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.server import ServerEngine
from shared.utils import add_log_handler, remove_log_handler
from server.gui.dashboardView import DashboardView
from server.gui.clientsView import ClientsView
from server.gui.analyticsView import AnalyticsView


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
        self.analytics_view = AnalyticsView(
    self.format_time,
    self.dashboard.format_size
)

        self.tabs.addTab(
    self.analytics_view,
    "📈  Downloads & Traffic Analytics"
)

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
        self.analytics_view.update_history(
            stats["download_history"]
        )
        self.analytics_view.update_popular(
            stats["download_counts"]
        )
    

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