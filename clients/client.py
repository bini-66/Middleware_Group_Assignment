
import socket

# Choose which node to contact
host = "127.0.0.1"
port = 5003

# Create a client socket
client = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

# Connect to Node 1
client.connect((host, port))

# Send a message
client.sendall(b"Book ticket T001")

# Receive the response
response = client.recv(1024).decode()

print("Response:", response)

client.close()
