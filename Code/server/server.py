import socket
import os
import threading
import time
from shared import protocol as p
from shared.utils import log

HOST = "0.0.0.0"
PORT = 5000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_DIR = os.path.join(BASE_DIR, "file_storage")

os.makedirs(FILE_DIR, exist_ok=True)

class ServerEngine:
    def __init__(self, host=HOST, port=PORT, storage_dir=FILE_DIR):
        self.host = host
        self.port = port
        self.storage_dir = storage_dir
        
        self.is_running = False
        self.listener_thread = None
        self.server_socket = None
        
        # Thread safety lock
        self.lock = threading.Lock()
        
        # Active connections tracker
        # Format: { addr_tuple: { "socket": conn, "thread": t, "connect_time": float, "current_action": str } }
        self.active_clients = {}
        
        # Metrics and statistics
        self.start_time = 0.0
        self.total_bytes_sent = 0
        self.current_upload_speed = 0.0  # Bytes/sec
        
        # Speed measurement variables
        self.speed_bytes_sent_in_last_interval = 0
        self.speed_thread = None
        
        # Callbacks for GUI notifications
        self.status_callbacks = []

    def register_status_callback(self, callback):
        """Register a callback function to receive server status/metrics updates."""
        with self.lock:
            if callback not in self.status_callbacks:
                self.status_callbacks.append(callback)
        # Immediately invoke to sync state
        try:
            callback(self.get_stats())
        except Exception as e:
            log("ERROR", f"Error in status callback: {e}")

    def unregister_status_callback(self, callback):
        """Unregister a status callback."""
        with self.lock:
            if callback in self.status_callbacks:
                self.status_callbacks.remove(callback)

    def _notify_status_change(self):
        """Invoke all registered status callbacks with updated metrics."""
        stats = self.get_stats()
        with self.lock:
            callbacks = list(self.status_callbacks)
        for callback in callbacks:
            try:
                callback(stats)
            except Exception as e:
                log("ERROR", f"Error in status callback: {e}")

    def get_stats(self):
        """Retrieve thread-safe server statistics and active client list."""
        with self.lock:
            uptime = 0.0
            if self.is_running and self.start_time > 0:
                uptime = time.time() - self.start_time
                
            clients_info = []
            for addr, info in self.active_clients.items():
                clients_info.append({
                    "ip": addr[0],
                    "port": addr[1],
                    "connect_time": info["connect_time"],
                    "uptime": time.time() - info["connect_time"],
                    "current_action": info["current_action"]
                })
                
            return {
                "is_running": self.is_running,
                "host": self.host,
                "port": self.port,
                "storage_dir": self.storage_dir,
                "uptime": uptime,
                "active_connections_count": len(self.active_clients),
                "active_clients": clients_info,
                "total_bytes_sent": self.total_bytes_sent,
                "upload_speed_kbps": self.current_upload_speed / 1024.0
            }

    def get_file_list(self):
        """Retrieve the list of files stored in server file storage."""
        try:
            return os.listdir(self.storage_dir)
        except Exception as e:
            log("ERROR", f"Failed to list directory {self.storage_dir}: {e}")
            return []

    def start(self):
        """Start the server non-blocking listener in a background thread."""
        with self.lock:
            if self.is_running:
                log("SERVER", "Server is already running.")
                return False
                
            self.is_running = True
            self.start_time = time.time()
            self.total_bytes_sent = 0
            self.current_upload_speed = 0.0
            self.speed_bytes_sent_in_last_interval = 0
            self.active_clients = {}

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.server_socket.settimeout(1.0)  # Use 1.0s timeout to allow check on self.is_running
        except Exception as e:
            log("SERVER", f"Failed to start server: {e}")
            with self.lock:
                self.is_running = False
            return False

        # Start the socket accept thread
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listener_thread.start()

        # Start the bandwidth/speed tracker thread
        self.speed_thread = threading.Thread(target=self._speed_monitor_loop, daemon=True)
        self.speed_thread.start()

        log("SERVER", f"Listening on {self.host}:{self.port}")
        self._notify_status_change()
        return True

    def stop(self):
        """Gracefully stop the server, closing listener and all active client connections."""
        log("SERVER", "Stopping server...")
        with self.lock:
            if not self.is_running:
                return
            self.is_running = False

        # Close listening socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                log("ERROR", f"Error closing server socket: {e}")

        # Close all active client connections
        with self.lock:
            clients = list(self.active_clients.items())

        for addr, info in clients:
            try:
                info["socket"].close()
            except Exception as e:
                log("ERROR", f"Error closing connection for {addr}: {e}")

        # Join the listener thread
        if self.listener_thread:
            self.listener_thread.join(timeout=2.0)

        # Join speed thread
        if self.speed_thread:
            self.speed_thread.join(timeout=2.0)

        log("SERVER", "[SERVER STOPPED]")
        self._notify_status_change()

    def _speed_monitor_loop(self):
        """Calculate upload speed in background every second."""
        while True:
            with self.lock:
                if not self.is_running:
                    break
                self.current_upload_speed = self.speed_bytes_sent_in_last_interval
                self.speed_bytes_sent_in_last_interval = 0

            self._notify_status_change()
            time.sleep(1.0)

    def _listen_loop(self):
        """Accept incoming client socket connections."""
        while True:
            with self.lock:
                if not self.is_running:
                    break

            try:
                conn, addr = self.server_socket.accept()
            except socket.timeout:
                continue
            except Exception as e:
                with self.lock:
                    if not self.is_running:
                        break  # Expected close
                log("ERROR", f"Error accepting connection: {e}")
                continue

            # Create a thread for this client connection
            client_thread = threading.Thread(
                target=self._handle_client_thread,
                args=(conn, addr),
                daemon=True
            )
            
            self._add_client(addr, conn, client_thread)
            client_thread.start()

    def _add_client(self, addr, sock, thread):
        with self.lock:
            self.active_clients[addr] = {
                "socket": sock,
                "thread": thread,
                "connect_time": time.time(),
                "current_action": "Connected"
            }
        log("CLIENT", f"Connected: {addr}")
        self._notify_status_change()

    def _remove_client(self, addr):
        with self.lock:
            if addr in self.active_clients:
                del self.active_clients[addr]
        log("CLIENT", f"Disconnected: {addr}")
        self._notify_status_change()

    def _update_client_action(self, addr, action):
        with self.lock:
            if addr in self.active_clients:
                self.active_clients[addr]["current_action"] = action
        self._notify_status_change()

    def _add_bytes_sent(self, size):
        with self.lock:
            self.total_bytes_sent += size
            self.speed_bytes_sent_in_last_interval += size

    def _handle_client_thread(self, conn, addr):
        """Manage individual client protocol requests."""
        try:
            connection = p.Connection(conn)
            while True:
                with self.lock:
                    if not self.is_running:
                        break

                request = connection.recv_line()
                if request is None:
                    break

                log("REQUEST", f"{addr} -> {request}")
                parts = request.split("|")
                command = parts[0]

                if command == p.LIST:
                    self._update_client_action(addr, "Listing Files")
                    files = self.get_file_list()
                    p.send_line(conn, p.encode_list(files))
                    log("RESP", f"LIST ({len(files)} files)")
                    self._update_client_action(addr, "Idle")

                elif command == p.GET:
                    if len(parts) < 2:
                        p.send_line(conn, p.encode_error("Missing filename"))
                        log("ERROR", f"Missing filename from {addr}")
                        continue

                    filename = os.path.basename(parts[1])
                    
                    if not filename:
                        p.send_line(conn, p.encode_error("Invalid filename"))
                        log("ERROR", f"Empty filename from {addr}")
                        continue
                    
                    filepath = os.path.join(self.storage_dir, filename)

                    if not os.path.exists(filepath):
                        p.send_line(conn, p.encode_error("File not found"))
                        log("ERROR", f"File not found: {filename}")
                    else:
                        size = os.path.getsize(filepath)
                        self._update_client_action(addr, f"Downloading {filename}")
                        
                        p.send_line(conn, p.encode_file_header(filename, size))

                        with open(filepath, "rb") as f:
                            while True:
                                with self.lock:
                                    if not self.is_running:
                                        break
                                chunk = f.read(p.CHUNK_SIZE)
                                if not chunk:
                                    break
                                conn.sendall(chunk)
                                self._add_bytes_sent(len(chunk))

                        log("RESP", f"SEND {filename} ({size} bytes)")
                        self._update_client_action(addr, "Idle")
                else:
                    log("ERROR", f"Unknown command from {addr}: {request}")
                    p.send_line(conn, p.encode_error("Unknown command"))

        except Exception as e:
            with self.lock:
                running = self.is_running
            if running:
                log("ERROR", f"Error handling client {addr}: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
            self._remove_client(addr)

def main():
    engine = ServerEngine(HOST, PORT)
    if engine.start():
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            engine.stop()

if __name__ == "__main__":
    main()