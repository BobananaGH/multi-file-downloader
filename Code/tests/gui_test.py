# Code/tests/gui_test.py

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from client.clientGui import FileClientGUI


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
    threads = getattr(window, "_download_threads", None)

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
        window._download_single(filename)

        # Try adding again (should be ignored by GUI logic)
        window._download_single(filename)

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
    
    print(f"\n{'=' * 50}")
    print(" GUI tests complete")
    print(f"{'=' * 50}\n")