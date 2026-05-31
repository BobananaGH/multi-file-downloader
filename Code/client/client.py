import os
import socket
from shared import protocol as p

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class Client:
    def __init__(self, host="127.0.0.1", port=5000):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))

        self.conn = p.Connection(self.socket)
        
    def list_files(self):
        self.conn.send_line(p.LIST)

        data = self.conn.recv_line()
        if not data:
            print("Server disconnected")
            return

        parts = data.split("|")

        if parts[0] == p.EMPTY:
            print("No files on server")
            return

        print("\nFiles from server:")
        for f in parts[1:]:
            print("-", f)

    def download_file(self, filename):
        filename = os.path.basename(filename)
        self.conn.send_line(f"{p.GET}|{filename}")
        
        header = self.conn.recv_line()
        
        if not header or "|" not in header:
            print("Malformed header")
            return
        
        parts = header.split("|")
        
        if parts[0] == p.ERROR:
            print("Error:", parts[1])
            return

        if parts[0] != p.FILE:
            print("Unexpected response:", parts[0])
            return

        if len(parts) < 3:
            print("Invalid server response")
            return

        try:
            size = int(parts[2])
        except ValueError:
            print("Invalid size from server")
            return
        
        if size < 0:
            print("Invalid size")
            return        
        
        base,ext = os.path.splitext(filename)
        safe_name = f"{base}_downloaded{ext}"
        
        print(f"Starting download: {safe_name} ({size} bytes)...")
        
        save_path = os.path.join(DOWNLOAD_DIR, safe_name)
        
        with open(save_path, "wb") as f:
            received = 0
            
            while received < size:
                chunk = self.conn.recv_bytes(min(p.CHUNK_SIZE, size - received))
                if not chunk:
                    print("Connection lost during download")
                    break

                f.write(chunk)
                received += len(chunk)
            
        if received == size:
            print(f"Downloaded {safe_name} successfully")
            
        else:
            print(f"Download incomplete ({received}/{size} bytes)")
        
    def close(self):
        try:
            self.conn.close()
        finally:
            self.socket.close()
