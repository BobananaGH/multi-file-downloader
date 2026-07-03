# Code/shared/auth.py
from __future__ import annotations

import os
import json
import hashlib
import secrets
import threading

# =========================
# Protocol additions (client <-> server)
# =========================
REGISTER = "REGISTER"                     # Client -> Server: REGISTER|username|password
LOGIN = "LOGIN"                           # Client -> Server: LOGIN|username|password
AUTH_OK = "AUTH_OK"                       # Server -> Client: AUTH_OK|message
AUTH_FAIL = "AUTH_FAIL"                   # Server -> Client: AUTH_FAIL|reason

MIN_USERNAME_LEN = 3
MIN_PASSWORD_LEN = 4
PBKDF2_ITERATIONS = 200_000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "..", "server", "users.json")


# =========================================================
# 1. Password hashing
# =========================================================
def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return dk.hex()


# =========================================================
# 2. Server-side user storage (JSON file, thread-safe)
# =========================================================
class UserStore:
    """Thread-safe JSON-backed user store. Passwords are never stored in
    plaintext — only a PBKDF2-SHA256 hash + random salt per user."""

    def __init__(self, path: str = USERS_FILE):
        self.path = path
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write({})

    def _read(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.path)  # atomic on POSIX/Windows

    def register(self, username: str, password: str):
        username = (username or "").strip()
        password = password or ""

        if len(username) < MIN_USERNAME_LEN:
            return False, f"Username must be at least {MIN_USERNAME_LEN} characters"
        if len(password) < MIN_PASSWORD_LEN:
            return False, f"Password must be at least {MIN_PASSWORD_LEN} characters"

        with self.lock:
            users = self._read()
            key = username.lower()
            if key in users:
                return False, "Username already exists"

            salt = secrets.token_bytes(16)
            users[key] = {
                "username": username,
                "salt": salt.hex(),
                "hash": _hash_password(password, salt),
            }
            self._write(users)

        return True, "Account created successfully"

    def verify(self, username: str, password: str):
        username = (username or "").strip()
        password = password or ""

        with self.lock:
            users = self._read()
            record = users.get(username.lower())

        if not record:
            return False, "Invalid username or password"

        salt = bytes.fromhex(record["salt"])
        actual = _hash_password(password, salt)

        if not secrets.compare_digest(actual, record["hash"]):
            return False, "Invalid username or password"

        return True, "Login successful"


# =========================================================
# 3. Server-side session tracking (by IP)
# =========================================================
class SessionTracker:
    """Tracks which client IPs have successfully authenticated."""

    def __init__(self):
        self._lock = threading.Lock()
        self._authenticated_ips: set[str] = set()

    def mark_authenticated(self, ip: str) -> None:
        with self._lock:
            self._authenticated_ips.add(ip)

    def is_authenticated(self, ip: str) -> bool:
        with self._lock:
            return ip in self._authenticated_ips

    def clear(self, ip: str) -> None:
        with self._lock:
            self._authenticated_ips.discard(ip)


# =========================================================
# 4. Server-side request handling
# =========================================================
def handle_auth_command(user_store: UserStore, command: str, parts: list[str]):
    """
    parts = the '|'-split request line, e.g. ["LOGIN", "alice", "hunter2"]

    Returns (response_line, authenticated, username)
    """
    if len(parts) < 3:
        return f"{AUTH_FAIL}|Missing username or password", False, None

    username, password = parts[1], parts[2]

    if command == REGISTER:
        ok, msg = user_store.register(username, password)
        if not ok:
            return f"{AUTH_FAIL}|{msg}", False, None
        return f"{AUTH_OK}|{msg}", True, username

    if command == LOGIN:
        ok, msg = user_store.verify(username, password)
        if not ok:
            return f"{AUTH_FAIL}|{msg}", False, None
        return f"{AUTH_OK}|{msg}", True, username

    return f"{AUTH_FAIL}|Unknown auth command", False, None


# =========================================================
# 5. Client-side: PySide6 Login / Register dialog
# =========================================================
try:
    import socket
    import ssl

    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QFormLayout,
        QTabWidget,
        QWidget,
        QLineEdit,
        QPushButton,
        QLabel,
    )

    from . import protocol as p

    def _open_connection(host: str, port: int, timeout: float = 10.0):
        """Open a fresh SSL connection and return a shared.protocol.Connection."""
        cert_path = os.path.join(BASE_DIR, "..", "certs", "server.crt")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cert_path)

        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.settimeout(timeout)
        raw.connect((host, port))

        sock = context.wrap_socket(raw, server_hostname=host)
        sock.settimeout(timeout)

        return p.Connection(sock), sock

    class _AuthThread(QThread):
        """Runs REGISTER/LOGIN on a background thread so the dialog never freezes."""

        result_ready = Signal(bool, str)

        def __init__(self, host, port, command, username, password, parent=None):
            super().__init__(parent)
            self.host = host
            self.port = port
            self.command = command
            self.username = username
            self.password = password

        def run(self):
            conn = None
            sock = None
            try:
                conn, sock = _open_connection(self.host, self.port)
                conn.send_line(f"{self.command}|{self.username}|{self.password}")
                response = conn.recv_line()

                if not response:
                    self.result_ready.emit(False, "No response from server")
                    return

                parts = response.split("|", 1)
                status = parts[0]
                message = parts[1] if len(parts) > 1 else ""
                self.result_ready.emit(status == AUTH_OK, message)

            except Exception as e:
                self.result_ready.emit(False, f"Connection error: {e}")
            finally:
                try:
                    if sock:
                        sock.close()
                except Exception:
                    pass

    class LoginDialog(QDialog):
        """
        Modal dialog with Login / Register tabs. Show this before opening
        the main FileClientGUI window.

            dialog = LoginDialog(host="127.0.0.1", port=5000)
            if dialog.exec() != QDialog.Accepted:
                sys.exit(0)
        """

        def __init__(self, host="127.0.0.1", port=5000, parent=None):
            super().__init__(parent)
            self.host = host
            self.port = port
            self._thread: _AuthThread | None = None

            self.setWindowTitle("FLUX — Sign in")
            self.setMinimumWidth(360)
            self.setModal(True)

            self._build_ui()

        def _build_ui(self):
            root = QVBoxLayout(self)

            self.status_label = QLabel("")
            self.status_label.setWordWrap(True)
            self.status_label.setStyleSheet("color: #d64545;")
            self.status_label.hide()

            self.tabs = QTabWidget()
            self.tabs.addTab(self._build_login_tab(), "Login")
            self.tabs.addTab(self._build_register_tab(), "Register")
            self.tabs.currentChanged.connect(lambda _: self._clear_status())

            root.addWidget(self.tabs)
            root.addWidget(self.status_label)

        def _build_login_tab(self) -> QWidget:
            tab = QWidget()
            layout = QFormLayout(tab)

            self.login_user = QLineEdit()
            self.login_pass = QLineEdit()
            self.login_pass.setEchoMode(QLineEdit.Password)
            self.login_pass.returnPressed.connect(self._on_login)

            layout.addRow("Username", self.login_user)
            layout.addRow("Password", self.login_pass)

            self.login_btn = QPushButton("Login")
            self.login_btn.setCursor(Qt.PointingHandCursor)
            self.login_btn.clicked.connect(self._on_login)
            layout.addRow(self.login_btn)

            return tab

        def _build_register_tab(self) -> QWidget:
            tab = QWidget()
            layout = QFormLayout(tab)

            self.reg_user = QLineEdit()
            self.reg_pass = QLineEdit()
            self.reg_pass.setEchoMode(QLineEdit.Password)
            self.reg_pass_confirm = QLineEdit()
            self.reg_pass_confirm.setEchoMode(QLineEdit.Password)
            self.reg_pass_confirm.returnPressed.connect(self._on_register)

            layout.addRow("Username", self.reg_user)
            layout.addRow("Password", self.reg_pass)
            layout.addRow("Confirm password", self.reg_pass_confirm)

            self.register_btn = QPushButton("Create account")
            self.register_btn.setCursor(Qt.PointingHandCursor)
            self.register_btn.clicked.connect(self._on_register)
            layout.addRow(self.register_btn)

            return tab

        def _clear_status(self):
            self.status_label.hide()
            self.status_label.setText("")

        def _show_status(self, text: str, ok: bool):
            self.status_label.setStyleSheet(
                "color: #2e9e5b;" if ok else "color: #d64545;"
            )
            self.status_label.setText(text)
            self.status_label.show()

        def _set_busy(self, busy: bool):
            self.login_btn.setEnabled(not busy)
            self.register_btn.setEnabled(not busy)

        def _on_login(self):
            username = self.login_user.text().strip()
            password = self.login_pass.text()

            if not username or not password:
                self._show_status("Please fill in both fields", False)
                return

            self._run_auth(LOGIN, username, password)

        def _on_register(self):
            username = self.reg_user.text().strip()
            password = self.reg_pass.text()
            confirm = self.reg_pass_confirm.text()

            if not username or not password:
                self._show_status("Please fill in both fields", False)
                return
            if password != confirm:
                self._show_status("Passwords do not match", False)
                return

            self._run_auth(REGISTER, username, password)

        def _run_auth(self, command: str, username: str, password: str):
            self._clear_status()
            self._set_busy(True)

            self._thread = _AuthThread(self.host, self.port, command, username, password)
            self._thread.result_ready.connect(self._on_auth_result)
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread.start()

        def _on_auth_result(self, ok: bool, message: str):
            self._set_busy(False)
            self._show_status(message, ok)
            if ok:
                self.accept()

except ImportError:
    # PySide6 not installed in this environment (e.g. a headless server
    # deployment). UserStore / SessionTracker / handle_auth_command above
    # still work fine without it — only LoginDialog is unavailable.
    LoginDialog = None