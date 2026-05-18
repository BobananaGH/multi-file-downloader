import socket
import os

HOST = "0.0.0.0"
PORT = 5000
FILE_DIR = "file_storage"

def get_file_list():
    return os.listdir(FILE_DIR)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)       #AF_INET = IPv4, SOCK_STREAM = TCP
server.bind((HOST, PORT))
server.listen(5)

print(f"[SERVER STARTED] Listening on port {PORT}...")

while True:
    conn, addr = server.accept()                                 #server.accept() returns connection object and address of the client
    print(f"[CONNECTED] {addr}")

    try:
        files = get_file_list()

        if not files:
            message = "NO_FILES"
        else:
            message = "|".join(files)

        conn.send(message.encode())

    except Exception as e:
        print("[ERROR]", e)

    finally:
        conn.close()
        print("[DISCONNECTED]")