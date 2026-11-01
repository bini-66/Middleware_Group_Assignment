
import socket
import sys

# Get the node ID and port from the command line
node_id = sys.argv[1]
port = int(sys.argv[2])

# Create a TCP server
server = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

# Allow the port to be reused
server.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)

# Listen on localhost using the given port
server.bind(("127.0.0.1", port))
server.listen()

print(f"Node {node_id} is running on port {port}")

# Keep the node running
while True:

    # Wait for a client connection
    connection, address = server.accept()

    # Receive a message
    message = connection.recv(1024).decode()

    print(f"Node {node_id} received: {message}")

    # Send a response
    response = f"Hello from Node {node_id}"

    connection.sendall(response.encode())

    # Close this client connection
    connection.close()
