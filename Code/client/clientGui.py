import sys
import socket
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout,
    QPushButton, QListWidget, QLabel
)

HOST = "127.0.0.1"
PORT = 5000


class FileClientGUI(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Multi File Downloader")
        self.setGeometry(200, 200, 400, 300)

        self.load_styles()
        
        # UI elements
        self.label = QLabel("Files from server:")
        self.list_widget = QListWidget()
        self.refresh_btn = QPushButton("Refresh Files")

        # layout
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.refresh_btn)
        self.setLayout(layout)

        # button action
        self.refresh_btn.clicked.connect(self.load_files)

        # auto load on start
        self.load_files()

    def load_files(self):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((HOST, PORT))

            data = client.recv(4096).decode()
            client.close()

            if data == "NO_FILES":
                self.list_widget.clear()
                self.list_widget.addItem("No files available")
                return

            files = data.split("|")

            self.list_widget.clear()
            for f in files:
                self.list_widget.addItem(f)

        except Exception as e:
            self.list_widget.clear()
            self.list_widget.addItem(f"Error: {e}")
            
    def load_styles(self):
        with open("clientGui.qss", "r") as f:
            self.setStyleSheet(f.read())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FileClientGUI()
    window.show()
    sys.exit(app.exec())