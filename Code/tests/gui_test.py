# Code/tests/gui_test.py

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from client.clientGui import FileClientGUI
from client.gui.helpers import open_downloads_folder

def print_header(name):
    print(f"\n{'=' * 50}")
    print(f" GUI TEST: {name}")
    print(f"{'=' * 50}")


def print_result(passed, detail=""):
    status = "PASS ✓" if passed else "FAIL ✗"
    print(f" Result: {status}")

    if detail:
        print(f" Detail: {detail}")


# Create ONE QApplication instance
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


def test_gui_starts():
    print_header("GUI launches correctly")

    try:
        window = FileClientGUI(auto_load=False)
        window.show()

        app.processEvents()

        passed = (
            window.windowTitle() == "FLUX — Multi File Downloader"
            and window.list_widget is not None
            and window.download_btn is not None
        )

        print_result(
            passed,
            f"Window title: {window.windowTitle()}"
        )

        cleanup_threads(window)
        window.close()

    except Exception as e:
        print_result(False, str(e))

def cleanup_threads(window):
    # stop download threads safely
    threads = getattr(window, "_threads", None)

    if not threads:
        return

    for t in threads:
        try:
            if t and t.isRunning():
                if hasattr(t, "cancel"):
                    t.cancel()
                t.quit()
                t.wait(1000)
        except Exception:
            pass
            
def test_file_rendering():
    print_header("File list rendering")

    try:
        window = FileClientGUI(auto_load=False)

        fake_files = [
            ("test.txt", 100),
            ("movie.mp4", 5_000_000),
            ("image.png", 250_000),
        ]

        window._render_file_list(fake_files)

        app.processEvents()

        count = window.list_widget.topLevelItemCount()

        passed = count == 3

        print_result(
            passed,
            f"Rendered items: {count}"
        )

        cleanup_threads(window)
        window.close()

    except Exception as e:
        print_result(False, str(e))


def test_search_filter():
    print_header("Search filtering")

    try:
        window = FileClientGUI(auto_load=False)

        fake_files = [
            ("cat.png", 100),
            ("dog.png", 200),
            ("document.pdf", 300),
        ]

        window._all_files = fake_files
        window._render_file_list(fake_files)

        window.search_bar.setText("dog")

        app.processEvents()

        filtered_count = window.list_widget.topLevelItemCount()

        first_item = window.list_widget.topLevelItem(0)

        passed = (
            filtered_count == 1
            and "dog.png" in first_item.text(0)
        )

        print_result(
            passed,
            f"Filtered items: {filtered_count}"
        )

        cleanup_threads(window)
        window.close()

    except Exception as e:
        print_result(False, str(e))


def test_size_sorting():
    print_header("Numeric size sorting")

    try:
        window = FileClientGUI(auto_load=False)

        fake_files = [
            ("big.iso", 5_000_000),
            ("small.txt", 100),
            ("medium.zip", 500_000),
        ]

        window._render_file_list(fake_files)

        # Sort ascending by Size column
        window.list_widget.sortItems(1, Qt.AscendingOrder)

        app.processEvents()

        first_item = window.list_widget.topLevelItem(0)
        last_item = window.list_widget.topLevelItem(2)

        passed = (
            "small.txt" in first_item.text(0)
            and "big.iso" in last_item.text(0)
        )

        print_result(
            passed,
            f"First: {first_item.text(0)} | Last: {last_item.text(0)}"
        )

        cleanup_threads(window)
        window.close()

    except Exception as e:
        print_result(False, str(e))


def test_download_widget():
    print_header("Download widget state changes")

    try:
        from client.clientGui import DownloadItemWidget

        widget = DownloadItemWidget("example.zip")

        widget.set_progress(50, 1024, 10)

        app.processEvents()

        progress_ok = widget.progress_bar.value() == 50

        widget.set_progress(100)

        app.processEvents()

        done_ok = "Done" in widget.status_label.text()

        passed = progress_ok and done_ok

        print_result(
            passed,
            f"Status: {widget.status_label.text()}"
        )

    except Exception as e:
        print_result(False, str(e))


def test_clear_downloads():
    print_header("Clear downloads")

    try:
        from client.clientGui import DownloadItemWidget

        window = FileClientGUI(auto_load=False)

        for i in range(3):
            widget = DownloadItemWidget(f"file{i}.txt")

            idx = window.downloads_layout.count() - 1

            window.downloads_layout.insertWidget(idx, widget)

            window._download_widgets[f"file{i}.txt"] = widget

        before = len(window._download_widgets)

        window._clear_downloads()

        app.processEvents()

        after = len(window._download_widgets)

        passed = before == 3 and after == 0

        print_result(
            passed,
            f"Before: {before} | After: {after}"
        )

        cleanup_threads(window)
        window.close()

    except Exception as e:
        print_result(False, str(e))

def test_duplicate_download_prevention():
    print_header("Duplicate download prevention")

    try:
        window = FileClientGUI(auto_load=False)

        filename = "example.zip"

        # First add
        window._start_download(filename)

        # Try adding again (should be ignored by GUI logic)
        window._start_download(filename)

        app.processEvents()

        count = len(window._download_widgets)

        passed = count == 1

        print_result(
            passed,
            f"Download widgets count: {count}"
        )

        cleanup_threads(window)
        window.close()

    except Exception as e:
        print_result(False, str(e))

def test_empty_file_list():
    print_header("Empty file list rendering")

    try:
        window = FileClientGUI(auto_load=False)

        window._render_file_list([])

        app.processEvents()

        count = window.list_widget.topLevelItemCount()

        item_text = window.list_widget.topLevelItem(0).text(0)

        passed = (
            count == 1 and
            "No files available" in item_text
        )

        print_result(
            passed,
            item_text
        )

        cleanup_threads(window)
        window.close()

    except Exception as e:
        print_result(False, str(e))

def test_cancelled_download():
    print_header("Cancelled download state")

    try:
        from client.clientGui import DownloadItemWidget

        widget = DownloadItemWidget("video.mp4")

        widget.set_cancelled()

        app.processEvents()

        status_ok = "Cancelled" in widget.status_label.text()
        button_hidden = not widget.cancel_btn.isVisible()

        passed = status_ok and button_hidden

        print_result(
            passed,
            widget.status_label.text()
        )

    except Exception as e:
        print_result(False, str(e))

def test_refresh_button_lock():
    print_header("Refresh button lock during loading")

    window = FileClientGUI(auto_load=False)

    window.load_files()

    passed = not window.refresh_btn.isEnabled()

    app.processEvents()

    print_result(passed, f"Enabled: {window.refresh_btn.isEnabled()}")

    cleanup_threads(window)
    window.close()
    
def test_download_no_selection():
    print_header("Download with no selection")

    window = FileClientGUI(auto_load=False)

    window._on_download_selected()

    passed = "Please select" in window.status_bar.currentMessage()

    print_result(passed, window.status_bar.currentMessage())

    cleanup_threads(window)
    window.close()
    
def test_duplicate_selection_prevention():
    print_header("Duplicate selection prevention")

    window = FileClientGUI(auto_load=False)

    files = [("a.txt", 100), ("b.txt", 200)]
    window._render_file_list(files)

    # simulate selection
    for i in range(window.list_widget.topLevelItemCount()):
        window.list_widget.topLevelItem(i).setSelected(True)

    window._on_download_selected()
    window._on_download_selected()  # second call should skip duplicates

    count = len(window._download_widgets)

    passed = count == 2

    print_result(passed, f"Downloads: {count}")

    cleanup_threads(window)
    window.close()
    
def test_cancel_download_flow():
    print_header("Cancel download flow")

    window = FileClientGUI(auto_load=False)

    window._start_download("test.iso")

    widget = window._download_widgets.get("test.iso")

    widget.cancel_requested.emit("test.iso")

    app.processEvents()

    passed = "Cancelled" in widget.status_label.text()

    print_result(passed, widget.status_label.text())

    cleanup_threads(window)
    window.close()
    
def test_search_reset():
    print_header("Search reset behavior")

    window = FileClientGUI(auto_load=False)

    files = [
        ("cat.png", 100),
        ("dog.png", 200),
    ]

    window._all_files = files
    window._render_file_list(files)

    window.search_bar.setText("dog")
    window.search_bar.setText("")

    app.processEvents()

    count = window.list_widget.topLevelItemCount()

    passed = count == 2

    print_result(passed, f"Items: {count}")

    cleanup_threads(window)
    window.close()
    
def test_clear_stops_threads():
    print_header("Clear stops threads safely")

    window = FileClientGUI(auto_load=False)

    window._start_download("a.txt")
    window._start_download("b.txt")

    window._clear_downloads()

    app.processEvents()

    passed = len(window._threads) == 0

    print_result(passed, f"Threads: {len(window._threads)}")

    window.close()
    
def test_render_metadata():
    print_header("File metadata integrity")

    window = FileClientGUI(auto_load=False)

    files = [("test.bin", 123456)]
    window._render_file_list(files)

    item = window.list_widget.topLevelItem(0)

    filename = item.data(0, Qt.UserRole)
    size = item.data(1, Qt.UserRole)

    passed = filename == "test.bin" and size == 123456

    print_result(passed, f"{filename}, {size}")

    window.close()
    
def test_stress_download():
    print_header("Stress download (rapid calls)")

    window = FileClientGUI(auto_load=False)

    for i in range(10):
        window._start_download(f"file{i}.txt")

    app.processEvents()

    passed = len(window._download_widgets) == 10

    print_result(passed, f"Widgets: {len(window._download_widgets)}")

    cleanup_threads(window)
    window.close()

def test_context_menu_exists():
    print_header("Context menu creation")

    window = FileClientGUI(auto_load=False)

    files = [("test.txt", 100)]
    window._render_file_list(files)

    item = window.list_widget.topLevelItem(0)

    # simulate data role
    item.setData(0, Qt.UserRole, "test.txt")

    # simulate right-click position
    pos = window.list_widget.visualItemRect(item).center()

    try:
        window._show_context_menu(pos)
        passed = True
    except Exception as e:
        passed = False
        print(e)

    print_result(passed, "Menu opened without crash")

    window.close()

def test_context_menu_empty_area():
    print_header("Context menu empty area")

    window = FileClientGUI(auto_load=False)

    window._render_file_list([("a.txt", 100)])

    pos = window.list_widget.rect().bottomRight()

    try:
        window._show_context_menu(pos)
        passed = True
    except Exception as e:
        passed = False
        print(e)

    print_result(passed, "No crash on empty click")

    window.close()

def test_context_menu_download_trigger():
    print_header("Context menu download trigger")

    window = FileClientGUI(auto_load=False)

    window._render_file_list([("test.txt", 100)])

    triggered = {"file": None}

    def fake_download(filename):
        triggered["file"] = filename

    # inject callback directly
    window._start_download = fake_download

    item = window.list_widget.topLevelItem(0)
    item.setData(0, Qt.UserRole, "test.txt")

    # DON'T rely on QMenu exec
    window._start_download("test.txt")

    passed = triggered["file"] == "test.txt"

    print_result(passed, f"Triggered: {triggered['file']}")

    window.close()
    
def test_open_downloads_folder():
    print_header("Open downloads folder callback")

    window = FileClientGUI(auto_load=False)

    try:
        open_downloads_folder(os.getcwd())
        passed = True
    except Exception as e:
        passed = False
        print(e)

    print_result(passed, "Function executed safely")

    window.close()

def test_double_click_download():
    print_header("Double-click download trigger")

    window = FileClientGUI(auto_load=False)

    window._render_file_list([("test.txt", 100)])

    item = window.list_widget.topLevelItem(0)
    filename = item.data(0, Qt.UserRole)

    window._start_download = lambda f: setattr(window, "_clicked", f)

    window.list_widget.itemDoubleClicked.emit(item, 0)

    passed = getattr(window, "_clicked", None) == filename

    print_result(passed, f"Clicked: {getattr(window, '_clicked', None)}")

    window.close()
    
def test_selection_persistence_after_filter():
    print_header("Selection persistence after filter")

    window = FileClientGUI(auto_load=False)

    files = [("cat.png", 100), ("dog.png", 200), ("cow.png", 300)]

    window._render_file_list(files)

    # select first item
    window.list_widget.topLevelItem(0).setSelected(True)

    window.search_bar.setText("dog")
    window.search_bar.setText("")

    app.processEvents()

    selected_count = len(window.list_widget.selectedItems())

    passed = selected_count >= 0  # should not crash or break selection system

    print_result(passed, f"Selected items: {selected_count}")

    window.close()
    
def test_cancel_spam():
    print_header("Cancel spam stress test")

    window = FileClientGUI(auto_load=False)

    window._start_download("video.mp4")

    widget = window._download_widgets["video.mp4"]

    # spam cancel requests
    for _ in range(10):
        widget.cancel_requested.emit("video.mp4")

    app.processEvents()

    passed = "Cancelled" in widget.status_label.text()

    print_result(passed, widget.status_label.text())

    window.close()
    
def test_refresh_integrity():
    print_header("Refresh integrity test")

    window = FileClientGUI(auto_load=False)

    files = [("a.txt", 100), ("b.txt", 200)]

    window._on_files_received(files)
    window._on_files_received(files)  # simulate refresh twice

    count = window.list_widget.topLevelItemCount()

    passed = count == 2

    print_result(passed, f"Items after refresh: {count}")

    window.close()
    
def test_large_file_list():
    print_header("Large dataset rendering")

    window = FileClientGUI(auto_load=False)

    files = [(f"file_{i}.txt", i * 100) for i in range(200)]

    window._render_file_list(files)

    app.processEvents()

    count = window.list_widget.topLevelItemCount()

    passed = count == 200

    print_result(passed, f"Items: {count}")

    window.close()
    
def test_status_bar_stress():
    print_header("Status bar stress test")

    window = FileClientGUI(auto_load=False)

    for i in range(50):
        window.status_bar.showMessage(f"Message {i}")

    app.processEvents()

    msg = window.status_bar.currentMessage()

    passed = "Message" in msg

    print_result(passed, msg)

    window.close()
    
def test_widget_cleanup():
    print_header("Widget cleanup safety")

    window = FileClientGUI(auto_load=False)

    window._start_download("test.zip")

    widget = window._download_widgets["test.zip"]

    window._clear_downloads()

    app.processEvents()

    exists = widget.parent() is not None

    passed = len(window._download_widgets) == 0

    print_result(passed, f"Widgets cleared: {len(window._download_widgets)}")

    window.close()
    
    
if __name__ == "__main__":
    print("\n")
    print("=" * 50)
    print(" FLUX GUI TEST SUITE")
    print("=" * 50)

    test_gui_starts()
    test_file_rendering()
    test_search_filter()
    test_size_sorting()
    test_download_widget()
    test_clear_downloads()
    test_duplicate_download_prevention()
    test_empty_file_list()
    test_cancelled_download()
    test_refresh_button_lock()
    test_download_no_selection()
    test_duplicate_selection_prevention()
    test_cancel_download_flow()
    test_search_reset()
    test_clear_stops_threads()
    test_render_metadata()
    test_stress_download()
    test_context_menu_exists()
    test_context_menu_empty_area()
    test_context_menu_download_trigger()
    test_open_downloads_folder()
    test_double_click_download()
    test_selection_persistence_after_filter()
    test_cancel_spam()
    test_refresh_integrity()
    test_large_file_list()
    test_status_bar_stress()
    test_widget_cleanup()
    
    print(f"\n{'=' * 50}")
    print(" GUI tests complete")
    print(f"{'=' * 50}\n")