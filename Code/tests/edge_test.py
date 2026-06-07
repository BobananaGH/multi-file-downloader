# Code/tests/edge_test.py
import socket
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared import protocol as p

HOST = "127.0.0.1"
PORT = 5000

def test_header(name):
    print(f"\n{'='*40}")
    print(f"  TEST: {name}")
    print(f"{'='*40}")

def test_result(passed, detail=""):
    status = "PASS ✓" if passed else "FAIL ✗"
    print(f"  Result: {status}")
    if detail:
        print(f"  Detail: {detail}")

# =========================
# Test 1: Malformed request
# =========================
def test_malformed_request():
    test_header("Malformed request")
    try:
        with socket.socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"GARBAGE\n")
            s.settimeout(3)
            try:
                resp = s.recv(4096)
                test_result(True, f"Server responded: {resp.strip()}")
            except socket.timeout:
                test_result(True, "Server ignored it and timed out (acceptable)")
    except Exception as e:
        test_result(False, str(e))

# =========================
# Test 2: Mid-download disconnect
# =========================
def test_mid_download_disconnect():
    test_header("Mid-download disconnect")
    try:
        with socket.socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"GET|mountainous-landscape-with-fog.jpg\n")
            header = b""
            while b"\n" not in header:
                header += s.recv(4096)
            print(f"  Got header: {header.strip()[:60]}")
            s.recv(4096)  # receive one chunk then bail
        # socket closed here — server should handle it cleanly
        time.sleep(1)  # give server thread time to clean up
        test_result(True, "Disconnected mid-download, server should still be running")
    except Exception as e:
        test_result(False, str(e))

# =========================
# Test 3: Empty filename
# =========================
def test_empty_filename():
    test_header("Empty filename in GET")
    try:
        with socket.socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"GET|\n")
            s.settimeout(3)
            resp = b""
            while b"\n" not in resp:
                resp += s.recv(4096)
            decoded = resp.strip().decode()
            passed = p.ERROR in decoded
            test_result(passed, f"Server responded: {decoded}")
    except Exception as e:
        test_result(False, str(e))

# =========================
# Test 4: File that doesn't exist
# =========================
def test_file_not_found():
    test_header("GET non-existent file")
    try:
        with socket.socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"GET|doesnotexist.xyz\n")
            s.settimeout(3)
            resp = b""
            while b"\n" not in resp:
                resp += s.recv(4096)
            decoded = resp.strip().decode()
            passed = p.ERROR in decoded
            test_result(passed, f"Server responded: {decoded}")
    except Exception as e:
        test_result(False, str(e))

# =========================
# Test 5: GET with no filename
# =========================
def test_get_no_filename():
    test_header("GET with no filename at all")
    try:
        with socket.socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"GET\n")
            s.settimeout(3)
            resp = b""
            while b"\n" not in resp:
                resp += s.recv(4096)
            decoded = resp.strip().decode()
            passed = p.ERROR in decoded
            test_result(passed, f"Server responded: {decoded}")
    except Exception as e:
        test_result(False, str(e))

# =========================
# Test 6: Immediate disconnect (no data sent)
# =========================
def test_immediate_disconnect():
    test_header("Connect then immediately disconnect")
    try:
        with socket.socket() as s:
            s.connect((HOST, PORT))
            # send nothing, just close
        time.sleep(1)
        test_result(True, "Server should still be running")
    except Exception as e:
        test_result(False, str(e))

# =========================
# Test 7: Server still alive after all of the above
# =========================
def test_server_still_alive():
    test_header("Server still alive after all edge cases")
    try:
        with socket.socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"LIST\n")
            s.settimeout(3)
            resp = b""
            while b"\n" not in resp:
                resp += s.recv(4096)
            decoded = resp.strip().decode()
            passed = "LIST" in decoded or p.EMPTY in decoded
            test_result(passed, f"Server responded to LIST: {decoded[:60]}")
    except Exception as e:
        test_result(False, str(e))


if __name__ == "__main__":
    print("\nEdge Case Test Suite")
    print("Make sure the server is running before proceeding")
    print("(python -m server from the Code/ directory)\n")

    test_malformed_request()
    test_mid_download_disconnect()
    test_empty_filename()
    test_file_not_found()
    test_get_no_filename()
    test_immediate_disconnect()
    test_server_still_alive()

    print(f"\n{'='*40}")
    print("  All edge case tests complete")
    print(f"{'='*40}\n")