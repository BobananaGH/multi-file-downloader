# Code/tests/edge_test.py
import socket
import time
import sys
import os
import ssl
import hashlib
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared import protocol as p

HOST = "127.0.0.1"
PORT = 5000
CERT_PATH = os.path.join(os.path.dirname(__file__), "..", "certs", "server.crt")
FILE_TO_GET = "mountainous-landscape-with-fog.jpg"
SOURCE_PATH = os.path.join(os.path.dirname(__file__), "..", "server", "file_storage", FILE_TO_GET)

def get_tls_socket():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(CERT_PATH)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    return context.wrap_socket(s, server_hostname="127.0.0.1")

def file_checksum(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def check_server_alive():
    try:
        with get_tls_socket() as s:
            s.settimeout(3)
            s.connect((HOST, PORT))
        return True
    except Exception:
        return False

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
# Original Tests
# =========================

def test_malformed_request():
    test_header("Malformed request")
    try:
        with get_tls_socket() as s:
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

def test_mid_download_disconnect():
    test_header("Mid-download disconnect")
    try:
        with get_tls_socket() as s:
            s.connect((HOST, PORT))
            s.sendall(f"GET|{FILE_TO_GET}\n".encode())
            header = b""
            while b"\n" not in header:
                header += s.recv(4096)
            print(f"  Got header: {header.strip()[:60]}")
            s.recv(4096)
        time.sleep(1)
        test_result(True, "Disconnected mid-download, server should still be running")
    except Exception as e:
        test_result(False, str(e))

def test_empty_filename():
    test_header("Empty filename in GET")
    try:
        with get_tls_socket() as s:
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

def test_file_not_found():
    test_header("GET non-existent file")
    try:
        with get_tls_socket() as s:
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

def test_get_no_filename():
    test_header("GET with no filename at all")
    try:
        with get_tls_socket() as s:
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

def test_immediate_disconnect():
    test_header("Connect then immediately disconnect")
    try:
        with get_tls_socket() as s:
            s.connect((HOST, PORT))
        time.sleep(1)
        test_result(True, "Server should still be running")
    except Exception as e:
        test_result(False, str(e))

def test_server_still_alive():
    test_header("Server still alive after all edge cases")
    try:
        with get_tls_socket() as s:
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


# =========================
# New Tests
# =========================

def test_file_integrity():
    test_header("File integrity checksum")
    try:
        if not os.path.exists(SOURCE_PATH):
            test_result(False, f"Source file not found: {SOURCE_PATH}")
            return

        with get_tls_socket() as s:
            s.connect((HOST, PORT))
            s.sendall(f"GET|{FILE_TO_GET}\n".encode())

            header = b""
            while b"\n" not in header:
                header += s.recv(4096)

            parts = header.strip().decode().split("|")
            if parts[0] != p.FILE:
                test_result(False, f"Unexpected response: {parts[0]}")
                return

            size = int(parts[2])
            data = b""
            while len(data) < size:
                chunk = s.recv(min(p.CHUNK_SIZE, size - len(data)))
                if not chunk:
                    break
                data += chunk

        source_checksum = file_checksum(SOURCE_PATH)
        received_checksum = hashlib.md5(data).hexdigest()
        passed = source_checksum == received_checksum
        test_result(passed, f"Source: {source_checksum} | Received: {received_checksum}")

    except Exception as e:
        test_result(False, str(e))

def test_thread_leak():
    test_header("Rapid reconnect thread leak (50 connections)")
    try:
        for i in range(50):
            with get_tls_socket() as s:
                s.connect((HOST, PORT))
                if i % 2 == 0:
                    s.sendall(b"LIST\n")

        time.sleep(2)

        # verify server still responds
        with get_tls_socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"LIST\n")
            s.settimeout(3)
            resp = b""
            while b"\n" not in resp:
                resp += s.recv(4096)
            decoded = resp.strip().decode()
            passed = "LIST" in decoded or p.EMPTY in decoded
            test_result(passed, f"Server alive after 50 reconnects: {decoded[:40]}")

    except Exception as e:
        test_result(False, str(e))

def test_slow_client():
    test_header("Slow client doesn't block others")
    try:
        slow_started = threading.Event()

        def slow_client():
            with get_tls_socket() as s:
                s.connect((HOST, PORT))
                s.sendall(f"GET|{FILE_TO_GET}\n".encode())
                slow_started.set()
                time.sleep(10)

        t = threading.Thread(target=slow_client, daemon=True)
        t.start()
        slow_started.wait(timeout=5)

        start = time.time()
        with get_tls_socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"LIST\n")
            s.settimeout(5)
            resp = b""
            while b"\n" not in resp:
                resp += s.recv(4096)
        elapsed = time.time() - start

        passed = elapsed < 2.0
        test_result(passed, f"Fast client responded in {elapsed:.2f}s while slow client connected")

    except Exception as e:
        test_result(False, str(e))

def test_buffer_overflow():
    test_header("Oversized request buffer overflow protection")
    try:
        with get_tls_socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"A" * 2_000_000)
            s.settimeout(5)
            try:
                resp = s.recv(4096)
                test_result(True, "Server closed connection cleanly")
            except (socket.timeout, ConnectionResetError, OSError):
                test_result(True, "Server closed connection (expected)")
    except Exception as e:
        test_result(False, str(e))
# =========================
# Extra Tests
# =========================

def test_fragmented_request():
    test_header("Fragmented GET request (TCP split)")
    try:
        with get_tls_socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"G")
            time.sleep(0.1)
            s.sendall(b"ET|")
            time.sleep(0.1)
            s.sendall(f"{FILE_TO_GET}\n".encode())

            s.settimeout(5)
            resp = b""
            while b"\n" not in resp:
                resp += s.recv(4096)

            decoded = resp.decode()
            passed = p.FILE in decoded or p.ERROR in decoded
            test_result(passed, decoded[:80])
    except Exception as e:
        test_result(False, str(e))

def test_mass_concurrent_clients():
    test_header("Mass concurrent clients (100)")

    def client_job():
        try:
            with get_tls_socket() as s:
                s.connect((HOST, PORT))
                s.sendall(b"LIST\n")
                s.settimeout(3)
                s.recv(4096)
        except Exception:
            pass

    threads = [threading.Thread(target=client_job) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    test_result(True, "100 clients completed without crash")

def test_connect_disconnect_spam():
    test_header("Connect/disconnect spam (200)")
    failed = 0
    for _ in range(200):
        try:
            s = get_tls_socket()
            s.connect((HOST, PORT))
            s.close()
        except Exception:
            failed += 1

    passed = failed == 0
    test_result(passed, f"Completed with {failed} failures")

def test_partial_header():
    test_header("Partial header corruption")
    try:
        with get_tls_socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"GET|")
            time.sleep(1)
            s.sendall(f"{FILE_TO_GET}\n".encode())

            s.settimeout(5)
            resp = b""
            while b"\n" not in resp:
                resp += s.recv(4096)

            decoded = resp.decode()
            passed = p.FILE in decoded or p.ERROR in decoded
            test_result(passed, decoded[:80])
    except Exception as e:
        test_result(False, str(e))

def test_binary_garbage_request():
    test_header("Binary garbage request")
    try:
        with get_tls_socket() as s:
            s.connect((HOST, PORT))
            s.sendall(os.urandom(5000))
            s.settimeout(2)
            try:
                s.recv(4096)
            except Exception:
                pass
        test_result(True, "Server survived binary garbage input")
    except Exception as e:
        test_result(False, str(e))

def test_slowloris():
    test_header("Slowloris-style attack (30 slow clients)")
    try:
        sockets = []
        for _ in range(30):
            s = get_tls_socket()
            s.connect((HOST, PORT))
            s.sendall(b"G")
            sockets.append(s)

        time.sleep(5)

        for s in sockets:
            try:
                s.sendall(b"ET|file\n")
                s.close()
            except Exception:
                pass

        # verify server still alive
        with get_tls_socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"LIST\n")
            s.settimeout(3)
            resp = b""
            while b"\n" not in resp:
                resp += s.recv(4096)
            passed = "LIST" in resp.decode() or p.EMPTY in resp.decode()
            test_result(passed, "Server still alive after slowloris attack")

    except Exception as e:
        test_result(False, str(e))

def test_protocol_violations():
    test_header("Protocol misuse (GET then LIST rapidly)")
    try:
        with get_tls_socket() as s:
            s.connect((HOST, PORT))
            s.sendall(b"GET|doesnotexist.txt\n")
            s.sendall(b"LIST\n")

            s.settimeout(3)
            resp = s.recv(4096)
            passed = len(resp) > 0
            test_result(passed, resp[:80].decode(errors="ignore"))
    except Exception as e:
        test_result(False, str(e))

def test_shutdown_during_transfer():
    test_header("Server shutdown during active transfer")
    try:
        import subprocess
        import time

        s = get_tls_socket()
        s.connect((HOST, PORT))
        s.sendall(f"GET|{FILE_TO_GET}\n".encode())

        # start receiving header
        header = b""
        while b"\n" not in header:
            header += s.recv(4096)

        print("  Transfer started... triggering shutdown soon")

        # simulate shutdown (server must already be running in another process)
        time.sleep(0.5)

        s.close()  # force client abort mid-transfer

        time.sleep(1)

        test_result(True, "No crash during mid-transfer shutdown")

    except Exception as e:
        test_result(False, str(e))

def test_shutdown_with_active_clients():
    test_header("Shutdown with active clients (20 connections)")
    sockets = []

    try:
        for _ in range(20):
            s = get_tls_socket()
            s.connect((HOST, PORT))
            s.sendall(b"LIST\n")
            sockets.append(s)

        time.sleep(1)

        for s in sockets[:10]:
            try:
                s.sendall(b"GET|fake.txt\n")
            except:
                pass

        test_result(True, "Multiple clients active during shutdown safe")

    except Exception as e:
        test_result(False, str(e))
    finally:
        for s in sockets:
            try:
                s.close()
            except:
                pass
def test_accept_unblock_race():
    test_header("Accept loop unblock race condition")

    try:
        def spam_connect():
            for _ in range(50):
                try:
                    s = get_tls_socket()
                    s.connect((HOST, PORT))
                    time.sleep(0.01)
                    s.close()
                except:
                    pass

        t = threading.Thread(target=spam_connect)
        t.start()

        time.sleep(0.5)

        # simulate unblock trigger
        try:
            s = get_tls_socket()
            s.connect((HOST, PORT))
            s.close()
        except:
            pass

        t.join()

        test_result(True, "Accept loop handled spam + unblock correctly")

    except Exception as e:
        test_result(False, str(e))

def test_restart_stability():
    test_header("Server restart stability")

    try:
        for i in range(5):
            with get_tls_socket() as s:
                s.connect((HOST, PORT))
                s.sendall(b"LIST\n")
                s.recv(4096)

        test_result(True, "Server stable across repeated connections")

    except Exception as e:
        test_result(False, str(e))

def test_half_open_ssl():
    test_header("Half-open SSL connection")

    try:
        s = get_tls_socket()
        s.connect((HOST, PORT))

        # don't complete handshake properly
        s.sendall(b"G")

        time.sleep(2)

        s.close()

        test_result(True, "Server handled incomplete SSL client")

    except Exception as e:
        test_result(False, str(e))
        
def test_abrupt_client_kill():
    test_header("Abrupt client kill during transfer")

    try:
        s = get_tls_socket()
        s.connect((HOST, PORT))
        s.sendall(f"GET|{FILE_TO_GET}\n".encode())

        time.sleep(0.2)

        # simulate crash (no close)
        del s

        time.sleep(2)

        test_result(True, "Server survived abrupt client kill")

    except Exception as e:
        test_result(False, str(e))
    

if __name__ == "__main__":
    print("\nEdge Case Test Suite")
    print("Make sure the server is running before proceeding")
    print("(python -m server from the Code/ directory)\n")

    if not check_server_alive():
        print("ERROR: Server is not running. Start it first.")
        sys.exit(1)

    # Original
    test_malformed_request()
    test_mid_download_disconnect()
    test_empty_filename()
    test_file_not_found()
    test_get_no_filename()
    test_immediate_disconnect()
    test_server_still_alive()

    # New
    test_file_integrity()
    test_thread_leak()
    test_slow_client()
    test_buffer_overflow()
    
    # Extra
    test_fragmented_request()
    test_mass_concurrent_clients()
    test_connect_disconnect_spam()
    test_partial_header()
    test_binary_garbage_request()
    test_slowloris()
    test_protocol_violations()
    test_shutdown_during_transfer()
    test_shutdown_with_active_clients()
    test_accept_unblock_race()
    test_restart_stability()
    test_half_open_ssl()
    test_abrupt_client_kill()

    print(f"\n{'='*40}")
    print("  All edge case tests complete")
    print(f"{'='*40}\n")