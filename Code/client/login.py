# Code/client/login.py
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QApplication, QDialog

from shared.auth import LoginDialog


def parse_args():
    parser = argparse.ArgumentParser(description="FLUX login / register")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Server port (default: 5000)")
    parser.add_argument(
        "--dialog-only",
        action="store_true",
        help="Just show the login dialog and exit, without opening the file browser window.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    dialog = LoginDialog(host=args.host, port=args.port)
    if dialog.exec() != QDialog.Accepted:
        sys.exit(0)

    if args.dialog_only:
        sys.exit(0)

    from client.clientGui import FileClientGUI

    window = FileClientGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()