"""Cluster-wide settings shared by nodes, clients and tools.

Two modes (env CLUSTER_MODE, set to "docker" inside the Docker image):
  local  (default) - every node on 127.0.0.1, ports 50051, 50052, ...
  docker           - node1:50051, node2:50051, ... (compose service names)
compose.yaml publishes node N on host port 5005N, so clients and tools run
on the host always use the "local" addresses.

Environment variables read here / by the node:
  NODE_ID       which node this process is        (docker: set in compose.yaml)
  GRPC_PORT     port to listen on                 (docker: 50051)
  DATA_DIR      where this node may persist state (docker: /data volume)
  CLUSTER_SIZE  number of nodes in the cluster    (default 3)
"""
import os

CLUSTER_SIZE = int(os.getenv("CLUSTER_SIZE", "3"))
MODE = os.getenv("CLUSTER_MODE", "local")
BASE_PORT = 50050


def _addr(i: int) -> str:
    if MODE == "docker":
        return f"node{i}:50051"
    return f"127.0.0.1:{BASE_PORT + i}"


# node id -> "host:port" as seen by the nodes themselves
NODES = {f"node{i}": _addr(i) for i in range(1, CLUSTER_SIZE + 1)}

# addresses for things running OUTSIDE docker (client, tools/fault.py)
HOST_NODES = {f"node{i}": f"127.0.0.1:{BASE_PORT + i}" for i in range(1, CLUSTER_SIZE + 1)}

MAJORITY = CLUSTER_SIZE // 2 + 1

# ---- timing (seconds) - tune these and report them in your evaluation ----
RPC_TIMEOUT = 1.0          # node-to-node call timeout
HEARTBEAT_INTERVAL = 0.5   # how often each node pings each peer
FAILURE_TIMEOUT = 2.0      # no heartbeat reply for this long => peer is DOWN

LOG_DIR = os.getenv("LOG_DIR", "logs")


def listen_port(node_id: str) -> int:
    if os.getenv("GRPC_PORT"):
        return int(os.environ["GRPC_PORT"])
    return int(NODES[node_id].rsplit(":", 1)[1])


def data_dir(node_id: str) -> str:
    """Per-node directory for persistent state (Role 3/4: write your state here).
    Docker: the node's own /data volume.  Local: data/<node_id>/ ."""
    return os.getenv("DATA_DIR") or os.path.join("data", node_id)
