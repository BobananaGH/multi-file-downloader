# Code/server/gui/dashboardView.py

import datetime

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QFrame
)

from PySide6.QtCore import Qt, Signal, Slot


class DashboardView(QWidget):

    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)

        # LEFT
        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        # Controls
        ctrl_card = QFrame()
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setContentsMargins(16, 16, 16, 16)

        ctrl_title = QLabel("SYSTEM CONTROLS")
        ctrl_title.setObjectName("cardHeader")
        ctrl_layout.addWidget(ctrl_title)

        self.start_btn = QPushButton("▶ Start Server")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.clicked.connect(self.start_requested.emit)

        self.stop_btn = QPushButton("■ Stop Server")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_requested.emit)

        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.stop_btn)

        left_col.addWidget(ctrl_card)

        # Metrics
        metrics_card = QFrame()
        metrics_card.setObjectName("metricCard")
        metrics_layout = QVBoxLayout(metrics_card)
        metrics_layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("CORE METRICS")
        title.setObjectName("cardHeader")
        metrics_layout.addWidget(title)

        self.metric_uptime = self._create_metric("Uptime", "0s")
        self.metric_clients = self._create_metric("Clients", "0")
        self.metric_speed = self._create_metric("Speed", "0 KB/s")
        self.metric_bytes = self._create_metric("Bytes", "0 B")

        metrics_layout.addWidget(self.metric_uptime)
        metrics_layout.addWidget(self.metric_clients)
        metrics_layout.addWidget(self.metric_speed)
        metrics_layout.addWidget(self.metric_bytes)

        left_col.addWidget(metrics_card)
        left_col.addStretch()

        layout.addLayout(left_col, 1)

        # RIGHT (LOG)
        right_col = QVBoxLayout()

        header = QHBoxLayout()
        header.addWidget(QLabel("LIVE LOG"))
        header.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("clearBtn")
        clear_btn.clicked.connect(self.clear_logs)
        header.addWidget(clear_btn)

        right_col.addLayout(header)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setObjectName("consoleLog")
        right_col.addWidget(self.log_area)

        layout.addLayout(right_col, 2)

    # ---------------- Metric helper ----------------
    def _create_metric(self, name, value):
        widget = QWidget()
        layout = QHBoxLayout(widget)

        label_name = QLabel(name)
        label_value = QLabel(value)

        label_name.setObjectName("metricLabel")
        label_value.setObjectName("metricValue")

        layout.addWidget(label_name)
        layout.addWidget(label_value)

        widget.value_label = label_value

        return widget

    # ---------------- LOG ----------------
    @Slot(str, str)
    def append_log(self, category, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        self.log_area.append(
            f"[{timestamp}] [{category}] {message}"
        )

        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_logs(self):
        self.log_area.clear()

    # ---------------- METRICS ----------------
    def update_metrics(self, stats):
        self.metric_uptime.value_label.setText(self.format_uptime(stats["uptime"]))
        self.metric_clients.value_label.setText(str(stats["active_connections_count"]))
        self.metric_speed.value_label.setText(f"{stats['upload_speed_kbps']:.1f} KB/s")
        self.metric_bytes.value_label.setText(self.format_size(stats["total_bytes_sent"]))

    def set_server_running(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    # ---------------- FORMAT ----------------
    def format_uptime(self, secs):
        if secs <= 0:
            return "0s"
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)

        if h:
            return f"{h}h {m}m {s}s"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"

    def format_size(self, b):
        if b < 1024:
            return f"{b} B"
        if b < 1024**2:
            return f"{b/1024:.1f} KB"
        if b < 1024**3:
            return f"{b/1024**2:.1f} MB"
        return f"{b/1024**3:.1f} GB"
