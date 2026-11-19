"""ROLE 3 - Fault tolerance.

STARTER: heartbeat pinging + a simple timeout-based failure detector.
Owner: improve it (adaptive timeouts, phi-accrual, ...), add failover and
recovery orchestration, and MEASURE detection + failover time.

Interface other roles rely on:
    detector.is_alive(peer)   -> bool
    detector.alive_peers()    -> list[str]
    detector.on_down(cb) / detector.on_up(cb)     cb(peer_id)
    detector.handle_heartbeat(req, sender)        -> HeartbeatReply
"""
import threading
import time

from middleware import config
from middleware import node_pb2 as pb


class FailureDetector:
    def __init__(self, node):
        self.node = node
        now = time.monotonic()
        # Optimistic start: assume everyone is alive until proven otherwise
        self._last_seen = {p: now for p in node.peer_ids}
        self._alive = set(node.peer_ids)
        self._down_cbs, self._up_cbs = [], []
        self._lock = threading.Lock()
        self._running = False

    # ---- public API ----
    def is_alive(self, peer):
        return peer in self._alive

    def alive_peers(self):
        return sorted(self._alive)

    def on_down(self, cb):
        self._down_cbs.append(cb)

    def on_up(self, cb):
        self._up_cbs.append(cb)

    def handle_heartbeat(self, req, sender):
        c = self.node.consensus
        return pb.HeartbeatReply(node_id=self.node.id, role=c.role, term=c.term)

    # ---- lifecycle ----
    def start(self):
        self._running = True
        for peer in self.node.peer_ids:
            threading.Thread(target=self._monitor, args=(peer,), daemon=True).start()

    def stop(self):
        self._running = False

    def _monitor(self, peer):
        while self._running:
            reply = self.node.peers.call(
                peer, "Heartbeat", pb.HeartbeatRequest(sender=self.node.id),
                timeout=config.HEARTBEAT_INTERVAL)
            now = time.monotonic()
            with self._lock:
                if reply is not None:
                    self._last_seen[peer] = now
                    if peer not in self._alive:
                        self._alive.add(peer)
                        self.node.log.warning("detector: %s is UP", peer)
                        self._fire(self._up_cbs, peer)
                elif peer in self._alive and now - self._last_seen[peer] > config.FAILURE_TIMEOUT:
                    self._alive.discard(peer)
                    self.node.log.warning("detector: %s is DOWN (silent for %.1fs)",
                                          peer, now - self._last_seen[peer])
                    self._fire(self._down_cbs, peer)
            time.sleep(config.HEARTBEAT_INTERVAL)

    @staticmethod
    def _fire(callbacks, peer):
        for cb in callbacks:
            try:
                cb(peer)
            except Exception:
                pass
