import socket

HOST = "127.0.0.1"
PORT = 5000

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

client.connect((HOST, PORT))

data = client.recv(4096).decode()

files = data.split("|")

print("Files from server:")
for f in files:
    print("-", f)

client.close()