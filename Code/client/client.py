import os
import socket
import ssl
from shared import protocol as p

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class Client:
    def __init__(self, host="127.0.0.1", port=5000):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(os.path.join(os.path.dirname(__file__), "..", "certs", "server.crt"))
        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket = context.wrap_socket(self.socket, server_hostname="127.0.0.1")
        self.socket.connect((host, port))
        self.conn = p.Connection(self.socket)

    def list_files(self) -> list[tuple[str, int]]:
        self.conn.send_line(p.LIST)
        data = self.conn.recv_line()
        if not data:
            return []
        parts = data.split("|")
        if parts[0] == p.EMPTY:
            return []
        result = []
        for entry in parts[1:]:
            if ":" in entry:
                name, size = entry.rsplit(":", 1)
                result.append((name, int(size)))
            else:
                result.append((entry, 0))
        return result

    def download_file(self, filename, on_progress=None, is_cancelled=None):
        filename = os.path.basename(filename)
        self.conn.send_line(f"{p.GET}|{filename}")

        header = self.conn.recv_line()
        if not header or "|" not in header:
            self.close()
            return False, "No header received"

        parts = header.split("|")
        if parts[0] == p.ERROR:
            return False, parts[1] if len(parts) > 1 else "Server error"
        if parts[0] != p.FILE or len(parts) < 3:
            self.close()
            return False, "Malformed header"

        try:
            size = int(parts[2])
        except ValueError:
            self.close()
            return False, "Invalid size"

        if size < 0:
            self.close()
            return False, "Invalid size"

        base, ext = os.path.splitext(filename)
        safe_name = f"{base}_downloaded{ext}"
        save_path = os.path.join(DOWNLOAD_DIR, safe_name)

        counter = 1
        while os.path.exists(save_path):
            safe_name = f"{base}_downloaded_{counter}{ext}"
            save_path = os.path.join(DOWNLOAD_DIR, safe_name)
            counter += 1
        with open(save_path, "wb") as f:
            received = 0
            while received < size:
                if is_cancelled and is_cancelled():
                    return False, "Cancelled"
                chunk = self.conn.recv_bytes(min(p.CHUNK_SIZE, size - received))
                if not chunk:
                    self.close()
                    return False, "Connection lost"
                f.write(chunk)
                received += len(chunk)
                if on_progress:
                    on_progress(received, size)

        return True, save_path  

    def close(self):
        try:
            self.conn.close()
        finally:
            self.socket.close()