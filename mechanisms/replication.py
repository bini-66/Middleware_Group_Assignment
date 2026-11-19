"""ROLE 4 - Replication and consistency.

STARTER: leader-based write replication with a majority-ack rule, duplicate
detection by message_id, and gap catch-up via SyncLog. In-memory only.
Owner: decide and justify the consistency model (what reads can return during
failures/partitions), conflict handling, persistence, commit rule, and
rollback of un-acked entries (currently an entry that misses quorum stays in
the leader's log - a known limitation to fix).

Interface other roles rely on:
    replication.client_write(ChatRequest) -> ChatReply   (leader only)
    replication.read(from_index)          -> list[LogEntry]
    replication.handle_replicate(req, sender) / handle_sync(req, sender)
    replication.last_index                -> int
"""
import threading
from concurrent.futures import ThreadPoolExecutor

from middleware import config
from middleware import node_pb2 as pb


class Replication:
    def __init__(self, node):
        self.node = node
        self._lock = threading.RLock()
        self._log = []            # list[LogEntry]; entry i has index i+1
        self._seen = {}           # message_id -> index (duplicate detection)
        self._pool = ThreadPoolExecutor(max_workers=16)

    @property
    def last_index(self):
        return len(self._log)

    # ------------------------------------------------------------ client write
    def client_write(self, req):
        n = self.node
        if not n.consensus.is_leader():
            return pb.ChatReply(ok=False, error="NOT_LEADER",
                                leader_id=n.consensus.leader_id or "")
        with self._lock:
            idx = self._seen.get(req.message_id)
            if idx is None:                       # new message
                entry = pb.LogEntry(
                    index=len(self._log) + 1, term=n.consensus.term,
                    message_id=req.message_id, sender=req.sender, text=req.text,
                    lamport=n.clock.tick(), wall_time=n.now())
                self._append(entry)
            else:                                 # client retry of same message
                entry = self._log[idx - 1]
        acks = 1 + self._push(entry)
        if acks < config.MAJORITY:
            n.log.warning("write #%d lacks quorum (%d/%d)", entry.index, acks, config.MAJORITY)
            return pb.ChatReply(ok=False, error="NO_QUORUM", leader_id=n.id, index=entry.index)
        n.log.info("write #%d '%s: %s' acks=%d lamport=%d",
                   entry.index, entry.sender, entry.text, acks, entry.lamport)
        return pb.ChatReply(ok=True, leader_id=n.id, index=entry.index, lamport=entry.lamport)

    def _push(self, entry):
        """Send entry to every peer believed alive; return number of acks."""
        targets = [p for p in self.node.peer_ids if self.node.detector.is_alive(p)]
        replies = self._pool.map(
            lambda p: self.node.peers.call(p, "Replicate", pb.ReplicateRequest(entry=entry)),
            targets)
        return sum(1 for r in replies if r is not None and r.ok)

    # ------------------------------------------------------------ follower side
    def handle_replicate(self, req, sender):
        entry = req.entry
        with self._lock:
            if entry.index <= len(self._log):                       # duplicate
                return pb.ReplicateReply(ok=True, last_index=len(self._log))
            if entry.index > len(self._log) + 1:                    # gap -> catch up
                self.node.log.warning("gap: have %d, got %d -> syncing from %s",
                                      len(self._log), entry.index, sender)
                self._catch_up(sender)
            if entry.index == len(self._log) + 1:
                self._append(entry)
                return pb.ReplicateReply(ok=True, last_index=len(self._log))
            return pb.ReplicateReply(ok=False, last_index=len(self._log))

    def _catch_up(self, source):
        if not source:
            return
        reply = self.node.peers.call(
            source, "SyncLog", pb.SyncRequest(from_index=len(self._log) + 1))
        if reply is None:
            return
        for e in reply.entries:
            if e.index == len(self._log) + 1:
                self._append(e)
        self.node.log.info("caught up to index %d", len(self._log))

    def handle_sync(self, req, sender):
        with self._lock:
            return pb.SyncReply(entries=self._log[max(req.from_index - 1, 0):])

    # ------------------------------------------------------------ reads
    def read(self, from_index=1):
        with self._lock:
            return list(self._log[max(from_index - 1, 0):])

    def _append(self, entry):
        self._log.append(entry)
        self._seen[entry.message_id] = entry.index
