import sys
from PySide6.QtWidgets import QApplication
from .clientGui import FileClientGUI

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = FileClientGUI()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
