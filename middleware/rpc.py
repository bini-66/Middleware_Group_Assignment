"""Shared RPC plumbing used by every mechanism.

* FaultState      - the knobs for fault injection (drop / delay / partition / skew)
* Peers           - how a node calls other nodes (adds sender + Lamport metadata)
* NodeInterceptor - applies faults and merges the Lamport clock on every
                    incoming node-to-node RPC, in ONE place, so no role
                    has to re-implement it.
"""
import random
import threading
import time

import grpc

from middleware import config
from middleware import node_pb2_grpc as pb_grpc

# Admin and client RPCs are never subject to injected faults
EXEMPT_METHODS = {"SetFault", "GetStatus", "SendMessage", "ReadMessages"}


class FaultState:
    def __init__(self):
        self._lock = threading.Lock()
        self.drop_rate = 0.0
        self.delay_ms = 0
        self.blocked = set()
        self.clock_offset = 0.0

    def set(self, drop_rate, delay_ms, blocked, clock_offset):
        with self._lock:
            self.drop_rate = float(drop_rate)
            self.delay_ms = int(delay_ms)
            self.blocked = set(blocked)
            self.clock_offset = float(clock_offset)

    def is_blocked(self, peer_id):
        return peer_id in self.blocked


class Peers:
    """Outgoing calls to other nodes. Returns the reply, or None on ANY failure
    (timeout, node down, partition, injected drop)."""

    def __init__(self, node):
        self.node = node
        self._stubs = {}
        self._lock = threading.Lock()

    def _stub(self, peer_id):
        with self._lock:
            if peer_id not in self._stubs:
                # Short reconnect backoff: gRPC's default grows to minutes, which
                # would make a restarted node look dead long after it is back.
                channel = grpc.insecure_channel(config.NODES[peer_id], options=[
                    ("grpc.initial_reconnect_backoff_ms", 100),
                    ("grpc.min_reconnect_backoff_ms", 100),
                    ("grpc.max_reconnect_backoff_ms", 500)])
                self._stubs[peer_id] = pb_grpc.NodeStub(channel)
            return self._stubs[peer_id]

    def call(self, peer_id, method, request, timeout=config.RPC_TIMEOUT):
        node = self.node
        if node.faults.is_blocked(peer_id):          # simulated partition
            return None
        metadata = (("x-sender", node.id), ("x-lamport", str(node.clock.tick())))
        try:
            return getattr(self._stub(peer_id), method)(
                request, timeout=timeout, metadata=metadata)
        except grpc.RpcError as err:
            node.log.debug("RPC %s -> %s failed: %s", method, peer_id, err.code())
            return None


class NodeInterceptor(grpc.ServerInterceptor):
    def __init__(self, node):
        self.node = node

    def intercept_service(self, continuation, details):
        handler = continuation(details)
        if handler is None or handler.unary_unary is None:
            return handler
        method = details.method.rsplit("/", 1)[-1]
        inner = handler.unary_unary
        node = self.node

        def wrapper(request, context):
            # Only node-to-node calls carry x-sender. Client, admin and the
            # standard gRPC health-check calls are never faulted.
            if method not in EXEMPT_METHODS:
                md = dict(context.invocation_metadata())
                sender = md.get("x-sender")
                if sender:
                    faults = node.faults
                    if faults.is_blocked(sender):
                        context.abort(grpc.StatusCode.UNAVAILABLE, "partitioned")
                    if faults.drop_rate and random.random() < faults.drop_rate:
                        context.abort(grpc.StatusCode.UNAVAILABLE, "dropped (injected)")
                    if faults.delay_ms:
                        time.sleep(faults.delay_ms / 1000.0)
                    node.clock.update(int(md.get("x-lamport", "0")))   # Lamport receive rule
            return inner(request, context)

        return grpc.unary_unary_rpc_method_handler(
            wrapper,
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer)
