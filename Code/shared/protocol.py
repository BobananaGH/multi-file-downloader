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


def encode_list(files):
    """
    Server sends file list to client
    """
    if not files:
        return EMPTY
    return f"LIST|{'|'.join(files)}"


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