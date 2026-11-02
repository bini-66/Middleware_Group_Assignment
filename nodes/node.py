
import socket
import sys

node_id = sys.argv[1]
port = int(sys.argv[2])

HOST = "127.0.0.1"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server.bind((HOST, port))
server.listen()

print(f"Node {node_id} is running on port {port}")
print("Waiting for messages...")

while True:
    connection, address = server.accept()

    with connection:
        message = connection.recv(1024).decode()

        print(f"Node {node_id} received: {message}")

        response = f"Message received by Node {node_id}"

        connection.sendall(response.encode())
