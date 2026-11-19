"""A cluster node.  Run from the repo root:

    python -m nodes.node node1          (or set NODE_ID=node1 - what Docker does)

The node is a thin shell: it owns the shared state (clock, faults, peers) and
routes each RPC to the mechanism that owns it. Roles plug in under mechanisms/.
"""
import logging
import os
import signal
import sys
import threading
import time
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from middleware import config
from middleware import node_pb2 as pb
from middleware import node_pb2_grpc as pb_grpc
from middleware.rpc import FaultState, NodeInterceptor, Peers
from mechanisms.consensus import Consensus
from mechanisms.fault_tolerance import FailureDetector
from mechanisms.logical_clock import LamportClock
from mechanisms.replication import Replication


class Node:
    def __init__(self, node_id):
        self.id = node_id
        self.data_dir = config.data_dir(node_id)     # persist state here (Role 3/4)
        os.makedirs(self.data_dir, exist_ok=True)
        self.peer_ids = [n for n in config.NODES if n != node_id]
        self.log = logging.getLogger(node_id)
        self.faults = FaultState()
        self.clock = LamportClock()
        self.peers = Peers(self)
        self.consensus = Consensus(self)
        self.detector = FailureDetector(self)
        self.replication = Replication(self)

    def now(self):
        """This node's wall clock, INCLUDING any injected skew."""
        return time.time() + self.faults.clock_offset

    def start(self):
        self.detector.start()
        self.consensus.start()

    def stop(self):
        self.consensus.stop()
        self.detector.stop()


def _sender(context):
    return dict(context.invocation_metadata()).get("x-sender", "")


class NodeServicer(pb_grpc.NodeServicer):
    def __init__(self, node):
        self.n = node

    # client-facing
    def SendMessage(self, req, ctx):
        return self.n.replication.client_write(req)

    def ReadMessages(self, req, ctx):
        return pb.ReadReply(entries=self.n.replication.read(req.from_index or 1),
                            served_by=self.n.id)

    # role 2
    def RequestVote(self, req, ctx):
        return self.n.consensus.handle_request_vote(req, _sender(ctx))

    def AppendEntries(self, req, ctx):
        return self.n.consensus.handle_append_entries(req, _sender(ctx))

    # role 3
    def Heartbeat(self, req, ctx):
        return self.n.detector.handle_heartbeat(req, _sender(ctx))

    # role 4
    def Replicate(self, req, ctx):
        return self.n.replication.handle_replicate(req, _sender(ctx))

    def SyncLog(self, req, ctx):
        return self.n.replication.handle_sync(req, _sender(ctx))

    # role 1
    def GetTime(self, req, ctx):
        return pb.TimeReply(wall_time=self.n.now())

    # admin
    def SetFault(self, req, ctx):
        self.n.faults.set(req.drop_rate, req.delay_ms, req.blocked, req.clock_offset)
        self.n.log.warning("FAULTS set: drop=%.2f delay=%dms blocked=%s skew=%+.1fs",
                           req.drop_rate, req.delay_ms, sorted(req.blocked), req.clock_offset)
        return pb.FaultAck(ok=True)

    def GetStatus(self, req, ctx):
        n, f = self.n, self.n.faults
        return pb.NodeStatus(
            node_id=n.id, role=n.consensus.role, term=n.consensus.term,
            leader_id=n.consensus.leader_id or "", log_length=n.replication.last_index,
            lamport=n.clock.time, alive_peers=n.detector.alive_peers(),
            drop_rate=f.drop_rate, delay_ms=f.delay_ms, blocked=sorted(f.blocked),
            clock_offset=f.clock_offset, wall_time=n.now())


def setup_logging(node_id):
    os.makedirs(config.LOG_DIR, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s %(message)s",
                            "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout),
              logging.FileHandler(os.path.join(config.LOG_DIR, f"{node_id}.log"))):
        h.setFormatter(fmt)
        root.addHandler(h)


def main():
    node_id = sys.argv[1] if len(sys.argv) > 1 else os.getenv("NODE_ID", "")
    if node_id not in config.NODES:
        sys.exit(f"usage: python -m nodes.node <{'|'.join(config.NODES)}>  (or set NODE_ID)")
    setup_logging(node_id)

    node = Node(node_id)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=32),
                         interceptors=[NodeInterceptor(node)])
    pb_grpc.add_NodeServicer_to_server(NodeServicer(node), server)

    # Standard gRPC health service - used by the Docker health check in compose.yaml
    health_service = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_service, server)

    port = config.listen_port(node_id)
    if server.add_insecure_port(f"0.0.0.0:{port}") == 0:
        sys.exit(f"cannot bind port {port} (is another node/cluster already using it?)")
    server.start()
    health_service.set("", health_pb2.HealthCheckResponse.SERVING)
    node.start()
    node.log.info("started on port %d | peers=%s | majority=%d | data=%s",
                  port, node.peer_ids, config.MAJORITY, node.data_dir)

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    stop.wait()

    node.log.info("shutting down")
    health_service.set("", health_pb2.HealthCheckResponse.NOT_SERVING)
    node.stop()
    server.stop(grace=2).wait()


if __name__ == "__main__":
    main()
