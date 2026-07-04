# Code/server/server.py

import socket
import os
import threading
import time
import ssl
from shared import protocol as p
from shared.utils import LogLevel, log
from shared import auth

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
        self.active_clients = {}
        
        # Authentication
        self.user_store = auth.UserStore()
        self.sessions = auth.SessionTracker()
        
        # Metrics and statistics
        self.start_time = 0.0
        self.total_bytes_sent = 0
        self.current_upload_speed = 0.0  # Bytes/sec
        
        # Speed measurement variables
        self.speed_bytes_sent_in_last_interval = 0
        self.speed_thread = None
        
        # Callbacks for GUI notifications
        self.status_callbacks = []
        
        # Download history and counts
        self.download_history = []
        self.download_counts = {}

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
                
    def _unblock_accept(self):
        try:
            dummy = socket.create_connection((self.host, self.port), timeout=0.5)
            dummy.close()
        except:
            pass
    
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
                "upload_speed_kbps": self.current_upload_speed / 1024.0,
                "download_history": list(self.download_history),
                "download_counts": dict(self.download_counts)
            }

    def _record_download(self, addr, filename, total_size, bytes_sent, success):
        status = "Success" if success and bytes_sent == total_size else "Failed/Incomplete"
        event = {
            "timestamp": time.time(),
            "ip": addr[0],
            "port": addr[1],
            "filename": filename,
            "total_size": total_size,
            "bytes_sent": bytes_sent,
            "status": status
        }
        with self.lock:
            self.download_history.append(event)
            if len(self.download_history) > 1000:
                self.download_history.pop(0)
            if status == "Success":
                self.download_counts[filename] = self.download_counts.get(filename, 0) + 1
        self._notify_status_change()

    def kick_client(self, ip, port):
        """Forcefully disconnect a client connection by IP and Port."""
        target_addr = (ip, int(port))
        with self.lock:
            if target_addr in self.active_clients:
                info = self.active_clients[target_addr]
                sock = info["socket"]
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                try:
                    sock.close()
                except:
                    pass
                log("SERVER", f"Kicked client {target_addr}")
                return True
        return False

    def get_file_list(self):
        try:
            files = os.listdir(self.storage_dir)
            result = []
            for f in files:
                path = os.path.join(self.storage_dir, f)
                size = os.path.getsize(path)
                result.append((f, size))
            return result
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
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(
                certfile=os.path.join(BASE_DIR, "..", "certs", "server.crt"),
                keyfile=os.path.join(BASE_DIR, "..", "certs", "server.key")
            )

            raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            raw_sock.bind((self.host, self.port))
            raw_sock.listen(5)
            raw_sock.settimeout(1.0)
            self.server_socket = raw_sock  # raw socket only
            self.ssl_context = context     # store context for per-connection wrapping
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
        log("SERVER", "Stopping server...")

        with self.lock:
            if not self.is_running:
                return
            self.is_running = False

            clients = list(self.active_clients.items())
            threads = [info["thread"] for info in self.active_clients.values()]
            self.active_clients.clear()
            
        self._unblock_accept()
        
        # close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        # close clients
        for addr, info in clients:
            try:
                info["socket"].shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                info["socket"].close()
            except:
                pass

        # join threads
        for t in threads:
            t.join(timeout=2.0)

        if self.listener_thread:
            self.listener_thread.join(timeout=2.0)

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
                sock = self.server_socket
                
            try:
                conn, addr = sock.accept()
                try:
                    conn = self.ssl_context.wrap_socket(conn, server_side=True)
                except ssl.SSLError as e:
                    log("ERROR", f"SSL handshake failed for {addr}: {e}")
                    conn.close()
                    continue
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
                daemon=False
            )
            
            self._add_client(addr, conn, client_thread)
            client_thread.start()

    def _add_client(self, addr, sock, thread):
        client_id = f"C-{addr[0]}:{addr[1]}"
        with self.lock:
            self.active_clients[addr] = {
                "socket": sock,
                "thread": thread,
                "connect_time": time.time(),
                "current_action": "Connected",
                "id": client_id
            }
        log("SESSION", f"{addr} connected")
        self._notify_status_change()

    def _remove_client(self, addr):
        with self.lock:
            self.active_clients.pop(addr, None)
        self.sessions.clear(addr[0])  
        log("SESSION", f"{addr} disconnected")
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
            conn.settimeout(0.3)
            connection = p.Connection(conn)
            while True:
                with self.lock:
                    if not self.is_running:
                        break
                try:    
                    request = connection.recv_line()
                except socket.timeout:
                    continue
                if request is None:
                    break

                log("REQUEST", f"{addr} -> {request}", LogLevel.DEBUG)
                parts = request.split("|")
                command = parts[0]

                if command in (auth.REGISTER, auth.LOGIN):
                    response, ok, username = auth.handle_auth_command(
                        self.user_store, command, parts
                    )
                    if ok:
                        self.sessions.mark_authenticated(addr[0])
                        log("AUTH", f"{addr} success: {username}", LogLevel.INFO)
                    else:
                        log("AUTH", f"{addr} failed login", LogLevel.WARN)
                    p.send_line(conn, response)
                    continue

                if not self.sessions.is_authenticated(addr[0]):
                    p.send_line(conn, p.encode_error("Not authenticated. Please login first."))
                    log("AUTH", "unauthorized access attempt", LogLevel.WARN)
                    continue

                if command == p.LIST:
                    self._update_client_action(addr, "Listing Files")
                    files = self.get_file_list()
                    p.send_line(conn, p.encode_list(files))
                    log("RESP", f"{addr} LIST ({len(files)} files)", LogLevel.DEBUG)
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
                        continue

                    full_size = os.path.getsize(filepath)
                
                    # parse optional byte range
                    
                    if len(parts) not in (2, 4):
                        p.send_line(conn, p.encode_error("Invalid GET request"))
                        continue
                    
                    if len(parts) == 4:
                        try:
                            start = int(parts[2])
                            end = int(parts[3])
                        except ValueError:
                            p.send_line(conn, p.encode_error("Invalid range"))
                            continue
                        if start < 0 or end >= full_size or start > end:
                            p.send_line(conn, p.encode_error("Invalid range"))
                            continue
                        chunk_size = end - start + 1
                    else:
                        start = 0
                        chunk_size = full_size

                    self._update_client_action(addr, f"Downloading {filename}")
                    p.send_line(conn, p.encode_file_header(filename, chunk_size))

                    bytes_sent = 0
                    interrupted_by_client = False
                    try:
                        with open(filepath, "rb") as f:
                            f.seek(start)
                            remaining = chunk_size
                            while remaining > 0:
                                with self.lock:
                                    if not self.is_running:
                                        break
                                to_read = min(p.CHUNK_SIZE, remaining)
                                chunk = f.read(to_read)
                                if not chunk:
                                    break
                                try:
                                    conn.sendall(chunk)
                                except (
                                    socket.timeout,
                                    BrokenPipeError,
                                    ConnectionResetError,
                                    ssl.SSLError,
                                    OSError
                                ):
                                    interrupted_by_client = True
                                    break
                                bytes_sent += len(chunk)
                                remaining -= len(chunk)

                            success = (bytes_sent == chunk_size) or interrupted_by_client

                    except Exception as e:
                        log("ERROR", f"Error sending file {filename} to {addr}: {e}")
                    finally:
                        self._record_download(addr, filename, chunk_size, bytes_sent, success)
                        self._update_client_action(addr, "Idle")

                    if success:
                        log("TRANSFER", f"SEND {filename} [{start}:{start+chunk_size-1}] ({bytes_sent}/{chunk_size} bytes) OK", LogLevel.INFO)
                    else:
                        log("TRANSFER", f"SEND {filename} [{start}:{start+chunk_size-1}] ({bytes_sent}/{chunk_size} bytes) incomplete", LogLevel.WARN)
                else:
                    log("WARN", f"Unknown command from {addr}: {request}")
                    p.send_line(conn, p.encode_error("Unknown command"))

        except Exception as e:
            with self.lock:
                running = self.is_running
            if running:
                log("ERROR", f"Error handling client {addr}: {e}")
        finally:
            try:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except:
                    pass
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