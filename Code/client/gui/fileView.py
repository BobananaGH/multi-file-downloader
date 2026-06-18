# Code/client/gui/fileView.py

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Qt, Signal

from shared.icons import get_file_icon
from client.gui.helpers import format_size
from client.gui.menu import show_file_context_menu
from client.gui.widgets import SortableTreeItem

class FileView(QWidget):
    """
    Pure-UI file list.

    Knows how to display files and emit user intent.
    Does NOT fetch, filter, or download anything.

    Signals
    -------
    download_requested(filename)   User double-clicked or picked Download.
    search_changed(query)          User typed in the search bar.
    """

    download_requested = Signal(str)
    search_changed     = Signal(str)
    open_downloads_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Search row
        search_row = QHBoxLayout()
        search_icon = QLabel("🔍")
        search_icon.setObjectName("searchIcon")
        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("searchBar")
        self.search_bar.setPlaceholderText("Search files...")
        self.search_bar.textChanged.connect(
            lambda text: self.search_changed.emit(text.strip())
        )
        search_row.addWidget(search_icon)
        search_row.addWidget(self.search_bar)
        layout.addLayout(search_row)

        # Section header
        list_header = QHBoxLayout()
        files_label = QLabel("SERVER FILES")
        files_label.setObjectName("sectionLabel")
        self.count_label = QLabel("0 files")
        self.count_label.setObjectName("countLabel")
        list_header.addWidget(files_label)
        list_header.addStretch()
        list_header.addWidget(self.count_label)
        layout.addLayout(list_header)

        # Tree
        self.list_widget = QTreeWidget()
        self.list_widget.setObjectName("fileList")
        self.list_widget.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.list_widget.setMinimumHeight(220)
        self.list_widget.setHeaderLabels(["Filename", "Size"])
        self.list_widget.setSortingEnabled(True)
        self.list_widget.setRootIsDecorated(False)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.itemDoubleClicked.connect(self._on_double_clicked)

        hdr = self.list_widget.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.resizeSection(1, 75)

        layout.addWidget(self.list_widget)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_files(self, files: list[tuple[str, int]]) -> None:
        """Render *files* into the tree. Replaces whatever was there."""
        self.list_widget.clear()

        if not files:
            placeholder = QTreeWidgetItem(["No files available on server", ""])
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsSelectable)
            self.list_widget.addTopLevelItem(placeholder)
            self.count_label.setText("0 files")
            return

        for name, size in files:
            icon = get_file_icon(name)
            item = SortableTreeItem([f"{icon}  {name}", format_size(size)])
            item.setData(0, Qt.UserRole, name)
            item.setData(1, Qt.UserRole, size)
            self.list_widget.addTopLevelItem(item)

        n = len(files)
        self.count_label.setText(f"{n} file{'s' if n != 1 else ''}")

    def show_error(self, message: str) -> None:
        """Replace the file list with a single non-selectable error row."""
        self.list_widget.clear()
        item = QTreeWidgetItem([f"⚠  {message}", ""])
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self.list_widget.addTopLevelItem(item)
        self.count_label.setText("—")

    def selected_filenames(self) -> list[str]:
        return [
            item.data(0, Qt.UserRole)
            for item in self.list_widget.selectedItems()
            if item.data(0, Qt.UserRole)
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_double_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        filename = item.data(0, Qt.UserRole)
        if filename:
            self.download_requested.emit(filename)

    def _show_context_menu(self, pos) -> None:
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        filename = item.data(0, Qt.UserRole)
        if not filename:
            return
        show_file_context_menu(
            self.list_widget,
            pos,
            filename,
            lambda fn: self.download_requested.emit(fn),
            lambda: self.open_downloads_requested.emit(),
        )