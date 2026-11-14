
import socket
import json
import struct


# Maximum message size: 1 MB
MAX_MESSAGE_SIZE = 1024 * 1024

# Connection timeout in seconds
TIMEOUT = 5


def send(peer, message):
    """
    Send a JSON message to another node.

    peer format: (host, port)
    message format: Python dictionary
    """

    try:
        # Convert dictionary into JSON bytes
        data = json.dumps(message).encode("utf-8")

        if len(data) > MAX_MESSAGE_SIZE:
            raise ValueError("Message is too large")

        # Add message length as a 4-byte header
        header = struct.pack("!I", len(data))

        # Establish TCP connection
        with socket.create_connection(peer, timeout=TIMEOUT) as client:

            # Send header and message
            client.sendall(header + data)

        return True

    except (OSError, ValueError, TypeError) as error:
        print(f"Failed to send message to {peer}: {error}")
        return False


def receive_message(connection):
    """
    Receive one complete JSON message from a TCP connection.
    """

    def receive_exactly(number_of_bytes):

        data = b""

        while len(data) < number_of_bytes:
            chunk = connection.recv(number_of_bytes - len(data))

            if not chunk:
                raise ConnectionError("Connection closed unexpectedly")

            data += chunk

        return data

    # Read the 4-byte message length
    header = receive_exactly(4)

    message_length = struct.unpack("!I", header)[0]

    if message_length > MAX_MESSAGE_SIZE:
        raise ValueError("Received message is too large")

    # Read the complete message
    data = receive_exactly(message_length)

    # Convert JSON bytes back into a dictionary
    return json.loads(data.decode("utf-8"))
