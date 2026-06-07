# shared/protocol.py

# =========================
# Client → Server Commands
# =========================
LIST = "LIST"                                                     #Client requests list of files from server  
GET = "GET"


# =========================
# Framing config
# =========================
DELIM = "\n"
CHUNK_SIZE = 4096
BUFFER_SIZE = 1024
MAX_BUFFER_SIZE = 1_000_000
DELIM_BYTES = DELIM.encode()


# =========================
# Server → Client Responses
# =========================
EMPTY = "EMPTY"
ERROR = "ERROR"
FILE = "FILE"


# =========================
# Encoding helpers
# =========================


def encode_list(files_with_sizes):
    """
    files_with_sizes: list of (filename, size) tuples
    Format: LIST|filename1:size1|filename2:size2
    """
    if not files_with_sizes:
        return EMPTY
    entries = [f"{name}:{size}" for name, size in files_with_sizes]
    return f"LIST|{'|'.join(entries)}"


def encode_error(message):
    """
    Server sends error message
    """
    return f"{ERROR}|{message}"


def encode_file_header(filename, size):
    """
    Used later when implementing downloads
    """
    return f"{FILE}|{filename}|{size}"


def send_line(conn, message: str):
    conn.sendall((message + DELIM).encode())
    

class Connection:
    def __init__(self, conn):
        self.conn = conn
        self.buffer = b""

    def send_line(self, message: str):
        self.conn.sendall((message + DELIM).encode())

    def recv_line(self):
        while DELIM_BYTES not in self.buffer:
            chunk = self.conn.recv(BUFFER_SIZE)
            if not chunk:
                return None

            self.buffer += chunk

            if len(self.buffer) > MAX_BUFFER_SIZE:
                raise ValueError("Buffer overflow")

        line, self.buffer = self.buffer.split(DELIM_BYTES, 1)
        return line.decode("utf-8", errors="replace")

    def recv_bytes(self, size: int):
        data = bytearray()

        # consume leftover buffered bytes first
        if self.buffer:
            take = min(len(self.buffer), size)
            data += self.buffer[:take]
            self.buffer = self.buffer[take:]

        while len(data) < size:
            chunk = self.conn.recv(min(CHUNK_SIZE, size - len(data)))

            if not chunk:
                break

            data += chunk

        return bytes(data)

    def close(self):
        self.conn.close()