import socket
import os
from shared import protocol as p
from shared.utils import log

HOST = "0.0.0.0"
PORT = 5000
BASE_DIR = os.path.dirname(__file__)
FILE_DIR = os.path.join(BASE_DIR, "file_storage")

os.makedirs(FILE_DIR, exist_ok=True)

def get_file_list():
    return os.listdir(FILE_DIR)

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    server.settimeout(1.0)                                        # Set timeout to allow shutdown with Ctrl+C

    log("SERVER", f"Listening on port {PORT}")

    try:
        while True:
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue

            log("CLIENT", f"Connected: {addr}")

            try:
                connection = p.Connection(conn)
                while True:
                    
                    request = connection.recv_line()

                    if request is None:
                        break
                    
                    log("REQUEST", f"{addr} -> {request}")
                    
                    parts = request.split("|")
                    command = parts[0]

                    if command == p.LIST:
                        files = get_file_list()
                        p.send_line(conn, p.encode_list(files))
                        log("RESP", f"LIST ({len(files)} files)")

                    elif command == p.GET:
                        if len(parts) < 2:
                            p.send_line(conn, p.encode_error("Missing filename"))
                            log("ERROR", f"Missing filename from {addr}")
                            continue

                        filename = os.path.basename(parts[1])
                        filepath = os.path.join(FILE_DIR, filename)

                        if not os.path.exists(filepath):
                            p.send_line(conn, p.encode_error("File not found"))
                            log("ERROR", f"File not found: {filename}")
                            
                        else:
                            size = os.path.getsize(filepath)
                            p.send_line(conn, p.encode_file_header(filename, size))

                            with open(filepath, "rb") as f:
                                while True:
                                    chunk = f.read(p.CHUNK_SIZE)
                                    if not chunk:
                                        break
                                    conn.sendall(chunk)
                            log("RESP", f"SEND {filename} ({size} bytes)")

                    else:
                        log("ERROR", f"Unknown command from {addr}: {request}")
                        p.send_line(conn, p.encode_error("Unknown command"))

            except Exception as e:
                log("ERROR", f"An error occurred: {e}")

            finally:
                conn.close()
                log("CLIENT", f"Disconnected: {addr}")

    except KeyboardInterrupt:
        log("SERVER", "[SERVER STOPPED]")

    finally:
        server.close()

if __name__ == "__main__":
    main()