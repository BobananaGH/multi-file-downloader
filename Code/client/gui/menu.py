# Code/client/gui/menu.py

from PySide6.QtWidgets import QMenu, QApplication, QAbstractItemView
from PySide6.QtGui import QAction

def create_file_context_menu(parent, filename, on_download, on_open_folder):
    menu = QMenu(parent)

    download_action = QAction("⬇  Download", parent)
    download_action.triggered.connect(lambda: on_download(filename))
    menu.addAction(download_action)

    copy_action = QAction("📋  Copy filename", parent)
    copy_action.triggered.connect(
        lambda: QApplication.clipboard().setText(filename)
    )
    menu.addAction(copy_action)

    open_action = QAction("📂  Open downloads folder", parent)
    open_action.triggered.connect(on_open_folder)
    menu.addAction(open_action)

    return menu


def show_file_context_menu(view: QAbstractItemView, pos, filename, on_download, on_open_folder):
    menu = create_file_context_menu(
        view, filename, on_download, on_open_folder
    )

    global_pos = view.viewport().mapToGlobal(pos)
    menu.exec(global_pos)