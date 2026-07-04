# client/__main__.py

import sys
from PySide6.QtWidgets import QApplication, QDialog
from .clientGui import FileClientGUI
from shared.auth import LoginDialog

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    login = LoginDialog(host="127.0.0.1", port=5000)
    if login.exec() != QDialog.Accepted:
        sys.exit(0)

    username, password = login.credentials
    window = FileClientGUI(username=username, password=password)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()