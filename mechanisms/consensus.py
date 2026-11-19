"""ROLE 2 - Consensus / leader election.

PLACEHOLDER: leader is statically 'node1' so the rest of the system can be
built and tested. THIS IS NOT SAFE under failures - replace it with real
(Raft-style) election and log agreement.

Interface other roles rely on (keep these names):
    consensus.is_leader()   -> bool
    consensus.leader_id     -> str | None     (None while no leader is known)
    consensus.term          -> int
    consensus.role          -> "leader" | "follower" | "candidate"
    consensus.start() / .stop()
    consensus.handle_request_vote(req, sender)    -> VoteReply
    consensus.handle_append_entries(req, sender)  -> AppendReply
Use node.detector.is_alive(peer) / on_down callbacks for failure info, and
node.peers.call(peer, "RequestVote", ...) to talk to other nodes.
Replication asks you "am I leader?" before accepting client writes.
"""
from middleware import config
from middleware import node_pb2 as pb


class Consensus:
    def __init__(self, node):
        self.node = node
        self.term = 1
        self.leader_id = min(config.NODES)      # PLACEHOLDER: static leader

    def start(self):
        self.node.log.info("consensus: PLACEHOLDER static leader = %s", self.leader_id)

    def stop(self):
        pass

    def is_leader(self):
        return self.node.id == self.leader_id

    @property
    def role(self):
        return "leader" if self.is_leader() else "follower"

    def handle_request_vote(self, req, sender):
        return pb.VoteReply(term=self.term, vote_granted=False)      # TODO Role 2

    def handle_append_entries(self, req, sender):
        return pb.AppendReply(term=self.term, success=False, match_index=0)  # TODO Role 2
