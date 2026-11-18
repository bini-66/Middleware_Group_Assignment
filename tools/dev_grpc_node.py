import os
import signal
import threading
from concurrent import futures
from pathlib import Path

import grpc
from grpc_health.v1 import health
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc


def main():
    node_id = os.environ.get("NODE_ID", "node1")
    port = int(os.environ.get("GRPC_PORT", "50051"))
    data_dir = Path(os.environ.get("DATA_DIR", "/data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10)
    )

    health_service = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(
        health_service, server
    )
    health_service.set(
        "", health_pb2.HealthCheckResponse.SERVING
    )

    bound_port = server.add_insecure_port(
        f"0.0.0.0:{port}"
    )
    if bound_port == 0:
        raise RuntimeError(f"Cannot bind gRPC port {port}")

    shutdown = threading.Event()

    def request_shutdown(signum, frame):
        shutdown.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    server.start()
    print(
        f"{node_id}: development gRPC health server "
        f"listening on port {port}",
        flush=True,
    )

    shutdown.wait()

    health_service.set(
        "", health_pb2.HealthCheckResponse.NOT_SERVING
    )
    server.stop(grace=3).wait()


if __name__ == "__main__":
    main()