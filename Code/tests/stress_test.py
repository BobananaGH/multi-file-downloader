# Code/tests/stress_test.py
import threading
import time
import os
import sys

# Make sure shared and client modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.client import Client

# =========================
# Config
# =========================
HOST = "127.0.0.1"
PORT = 5000
NUM_CLIENTS = 10
FILE_TO_GET = "mountainous-landscape-with-fog.jpg"  # must exist in server/file_storage/

# =========================
# Shared state
# =========================
results = []
results_lock = threading.Lock()
barrier = threading.Barrier(NUM_CLIENTS)  # forces all threads to start simultaneously

def simulate_client(client_id):
    result = {
        "client_id": client_id,
        "status": "UNKNOWN",
        "bytes_received": 0,
        "elapsed": 0.0,
        "error": None
    }

    try:
        client = Client(HOST, PORT)

        # Wait for all threads to be connected before proceeding
        barrier.wait()

        start = time.time()

        # List files
        client.list_files()

        # Download file
        client.download_file(FILE_TO_GET)

        elapsed = time.time() - start

        # Check the downloaded file size
        base, ext = os.path.splitext(FILE_TO_GET)
        saved_name = f"{base}_downloaded{ext}"
        saved_path = os.path.join(os.path.dirname(__file__), "client", "downloads", saved_name)

        bytes_received = os.path.getsize(saved_path) if os.path.exists(saved_path) else 0

        result["status"] = "OK"
        result["bytes_received"] = bytes_received
        result["elapsed"] = elapsed

        print(f"[Client {client_id:02d}] Done — {bytes_received / 1024 / 1024:.1f} MB in {elapsed:.2f}s")

    except threading.BrokenBarrierError:
        result["status"] = "ERROR"
        result["error"] = "Barrier broken"
        print(f"[Client {client_id:02d}] Barrier error")

    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)
        print(f"[Client {client_id:02d}] ERROR: {e}")

    finally:
        try:
            client.close()
        except Exception:
            pass
        with results_lock:
            results.append(result)


def main():
    print(f"{'='*50}")
    print(f"  Stress Test — {NUM_CLIENTS} concurrent clients")
    print(f"  Target: {HOST}:{PORT}")
    print(f"  File:   {FILE_TO_GET}")
    print(f"{'='*50}\n")

    threads = [
        threading.Thread(target=simulate_client, args=(i,), name=f"Client-{i:02d}")
        for i in range(NUM_CLIENTS)
    ]

    overall_start = time.time()

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    overall_elapsed = time.time() - overall_start

    # =========================
    # Summary
    # =========================
    ok      = [r for r in results if r["status"] == "OK"]
    errors  = [r for r in results if r["status"] != "OK"]

    print(f"\n{'='*50}")
    print(f"  Results")
    print(f"{'='*50}")
    print(f"  Successful : {len(ok)}/{NUM_CLIENTS}")
    print(f"  Failed     : {len(errors)}/{NUM_CLIENTS}")
    print(f"  Total time : {overall_elapsed:.2f}s")

    if ok:
        avg_time   = sum(r["elapsed"] for r in ok) / len(ok)
        total_mb   = sum(r["bytes_received"] for r in ok) / 1024 / 1024
        throughput = total_mb / overall_elapsed
        print(f"  Avg time   : {avg_time:.2f}s per client")
        print(f"  Total data : {total_mb:.1f} MB")
        print(f"  Throughput : {throughput:.1f} MB/s")

    if errors:
        print(f"\n  Errors:")
        for r in errors:
            print(f"    Client {r['client_id']:02d}: {r['error']}")

    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()