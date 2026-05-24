import socket
import os
from shared import protocol as p

HOST = "0.0.0.0"
PORT = 5000
FILE_DIR = "file_storage"


def get_file_list():
    return os.listdir(FILE_DIR)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(5)

print(f"[SERVER STARTED] Listening on port {PORT}...")


while True:
    conn, addr = server.accept()
    print(f"[CONNECTED] {addr}")

    try:
        connection = p.Connection(conn)
        request = connection.recv_line()
        if request is None:
            continue

        # split command (future-proof)
        parts = request.split("|")
        command = parts[0]

        # =========================
        # LIST COMMAND
        # =========================
        if command == p.LIST:
            files = get_file_list()
            response = p.encode_list(files)
            p.send_line(conn, response)


        # =========================
        # GET COMMAND (DOWNLOAD)
        # =========================
        elif command == p.GET:
            if len(parts) < 2:
                p.send_line(conn, p.encode_error("Missing filename"))
                continue
            
            filename = os.path.basename(parts[1])
            filepath = os.path.join(FILE_DIR, filename)

            if not os.path.exists(filepath):
                p.send_line(conn, p.encode_error("File not found"))
            else:
                # send file size first (important later)
                size = os.path.getsize(filepath)
                p.send_line(conn, p.encode_file_header(filename, size))

                # send file data in chunks (BINARY)
                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(p.CHUNK_SIZE)
                        if not chunk:
                            break
                        conn.sendall(chunk)

        else:
            p.send_line(conn, p.encode_error("Unknown command"))

    except Exception as e:
        print("[ERROR]", e)

    finally:
        conn.close()
        print("[DISCONNECTED]")