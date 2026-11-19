"""Smoke test for the foundation: boots a real 3-node cluster as processes.
Run from repo root:   python -m unittest tests.test_foundation -v
"""
import os
import subprocess
import sys
import tempfile
import time
import unittest

os.environ["CLUSTER_SIZE"] = "3"
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="cluster_test_")

from client.chat_client import ChatClient          # noqa: E402  (after env setup)
from tools import fault                            # noqa: E402


class FoundationTest(unittest.TestCase):
    procs = {}

    @classmethod
    def start_node(cls, node):
        cls.procs[node] = subprocess.Popen(
            [sys.executable, "-m", "nodes.node", node],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @classmethod
    def setUpClass(cls):
        for n in ("node1", "node2", "node3"):
            cls.start_node(n)
        time.sleep(1.5)

    @classmethod
    def tearDownClass(cls):
        for p in cls.procs.values():
            p.kill()

    def log_len(self, node):
        s = fault.status(node)
        return None if s is None else s.log_length

    def test_end_to_end(self):
        alice = ChatClient("alice")

        # 1. a client that starts at a follower is redirected to the leader
        alice.hint = "node3"
        self.assertTrue(alice.send("hello").ok)
        for i in range(2):
            self.assertTrue(alice.send(f"msg {i}").ok)
        time.sleep(0.3)
        self.assertEqual([self.log_len(n) for n in ("node1", "node2", "node3")], [3, 3, 3])

        # Lamport timestamps strictly increase along the log
        entries = alice.read("node2")
        stamps = [e.lamport for e in entries]
        self.assertEqual(stamps, sorted(set(stamps)))

        # 2. crash a follower: writes still succeed (2 of 3 = majority)
        self.procs["node3"].kill(); self.procs["node3"].wait()
        time.sleep(2.8)                                  # let the detector notice
        self.assertIn("node3", [n for n in ("node3",) if fault.status(n) is None])
        self.assertTrue(alice.send("while node3 down").ok)
        self.assertTrue(alice.send("still fine").ok)

        # 3. restart it: empty log, then catches up on the next write (gap -> SyncLog)
        self.start_node("node3"); time.sleep(1.8)
        self.assertTrue(alice.send("after restart").ok)
        time.sleep(0.5)
        self.assertEqual(self.log_len("node3"), 6)

        # 4. partition the leader away from both followers: no quorum -> write fails
        fault.main(["partition", "node1", "node2,node3"])
        time.sleep(2.8)
        stuck = ChatClient("bob"); stuck.hint = "node1"
        import client.client_config as cc
        cc.MAX_ATTEMPTS = 2
        self.assertIsNone(stuck.send("should not commit"))

        # 5. heal: writes work again
        fault.main(["heal"])
        time.sleep(1.5)
        cc.MAX_ATTEMPTS = 8
        self.assertTrue(alice.send("after heal").ok)


if __name__ == "__main__":
    unittest.main()
