# Server Backend Integration Guide (for Server GUI Developer)

Hi there! This guide explains how to connect the backend `ServerEngine` to your **Server GUI** built in PySide6.

All networking logic and status tracking have been fully implemented and run safely in background threads, so **the GUI will never freeze** during file downloads or socket operations.

---

## 🚀 1. How to Import and Instantiate the Server

To import the `ServerEngine` from your GUI script:

```python
from Code.server.server import ServerEngine

# Create the engine instance (binds by default to 0.0.0.0:5000)
server_engine = ServerEngine(host="0.0.0.0", port=5000)
```

---

## 🔌 2. How to Start and Stop the Server

Hook these methods directly to your "Start" and "Stop" buttons on the control panel:

```python
# Start the server (runs non-blocking in background threads)
success = server_engine.start()
if success:
    print("Server started successfully!")
else:
    print("Failed to start server (port might be in use).")

# Stop the server (closes all client sockets and shuts down cleanly)
server_engine.stop()
```

---

## 📈 3. How to Bind Real-Time Statistics (Status, Uptime, Active Connections)

The `ServerEngine` calculates uptime, upload speed, and client connection states automatically. You can register a callback function that will be notified **every 1 second** (or when a client state changes):

```python
def my_gui_status_callback(stats):
    # This dictionary contains all the live metrics!
    is_running = stats["is_running"]
    active_count = stats["active_connections_count"]
    upload_speed = stats["upload_speed_kbps"]  # float in KB/s
    total_sent = stats["total_bytes_sent"]
    uptime = stats["uptime"]  # float in seconds
    
    # Active clients list
    clients = stats["active_clients"]
    for c in clients:
        ip = c["ip"]
        port = c["port"]
        client_uptime = c["uptime"]
        current_action = c["current_action"]  # e.g., "Idle", "Listing Files", "Downloading <filename>"

# Register your GUI callback
server_engine.register_status_callback(my_gui_status_callback)
```

> ⚠️ **Important (PySide6 Thread Safety):**
> Because status callbacks are executed from background threads, you should avoid modifying PySide6 GUI elements directly inside the callback. Instead, use a custom `QObject` with a `Signal` to forward the stats to the GUI thread:
>
> ```python
> from PySide6.QtCore import QObject, Signal
>
> class ServerStatsSignal(QObject):
>     updated = Signal(dict)
>
> stats_notifier = ServerStatsSignal()
> stats_notifier.updated.connect(ui_update_method)  # Connected to your safe GUI update slot
>
> # Pass updates to the notifier inside the callback
> server_engine.register_status_callback(lambda stats: stats_notifier.updated.emit(stats))
> ```

---

## 📝 4. How to Capture Live Server Logs

Whenever the server performs an action, it logs it using `shared.utils.log`. You can easily capture this log stream and display it in a live console/terminal widget in your GUI:

```python
from Code.shared.utils import add_log_handler, remove_log_handler

# Define your log display handler
def my_gui_log_handler(category, message):
    formatted_log = f"[{category:<7}] {message}"
    # Append formatted_log to your QTextEdit / QPlainTextEdit console here!
    
# Register the handler
add_log_handler(my_gui_log_handler)
```

> ⚠️ **Important (PySide6 Thread Safety):**
> Just like status updates, you should forward log entries to the main thread using PySide6 signals:
>
> ```python
> class ServerLogSignal(QObject):
>     new_log = Signal(str, str) # category, message
>
> log_notifier = ServerLogSignal()
> log_notifier.new_log.connect(lambda cat, msg: ui_log_widget.append(f"[{cat}] {msg}"))
>
> add_log_handler(lambda cat, msg: log_notifier.new_log.emit(cat, msg))
> ```

---

## 🎨 5. Complete Integration Example

Here is a template you can give directly to the **Server GUI Developer** showing how they can connect their interface to your backend engine:

```python
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import QObject, Signal, Slot
from Code.server.server import ServerEngine
from Code.shared.utils import add_log_handler

class ServerSignals(QObject):
    stats_updated = Signal(dict)
    log_received = Signal(str, str)

class ServerGUIDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Server Monitor Panel")
        self.resize(500, 400)
        
        # Instantiate the Thread-Safe Backend Engine
        self.engine = ServerEngine(host="127.0.0.1", port=5000)
        
        # Thread-safe Signals
        self.signals = ServerSignals()
        self.signals.stats_updated.connect(self.update_stats_ui)
        self.signals.log_received.connect(self.append_log_ui)
        
        # Hook backend updates to the Thread-Safe Signals
        self.engine.register_status_callback(self.signals.stats_updated.emit)
        add_log_handler(self.signals.log_received.emit)
        
        # Setup UI
        self.label = QLabel("Server: Stopped | Active Connections: 0")
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.btn_start = QPushButton("Start Server")
        self.btn_stop = QPushButton("Stop Server")
        
        self.btn_start.clicked.connect(self.engine.start)
        self.btn_stop.clicked.connect(self.engine.stop)
        
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_stop)
        layout.addWidget(self.console)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    @Slot(dict)
    def update_stats_ui(self, stats):
        status = "RUNNING" if stats["is_running"] else "STOPPED"
        self.label.setText(
            f"Server: {status} | Port: {stats['port']} | "
            f"Active Conn: {stats['active_connections_count']} | "
            f"Speed: {stats['upload_speed_kbps']:.1f} KB/s"
        )

    @Slot(str, str)
    def append_log_ui(self, category, message):
        self.console.append(f"[{category}] {message}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ServerGUIDemo()
    window.show()
    sys.exit(app.exec())
```
