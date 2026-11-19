"""Chat client. Run several at once (different --name) to test concurrency.

  python -m client.chat_client --name alice                 interactive
  python -m client.chat_client --name bob --auto 20         send 20 messages
  python -m client.chat_client --name bob --read node2      dump node2's log

Every request/response/error is logged with a timestamp to
logs/client_<name>.log  (and printed).
"""
import argparse
import os
import random
import threading
import time
import uuid
from datetime import datetime

import grpc

from client import client_config as cc
from middleware import node_pb2 as pb
from middleware import node_pb2_grpc as pb_grpc


class ChatClient:
    def __init__(self, name):
        self.name = name
        self.hint = None                       # last known leader
        self._stubs = {}
        os.makedirs(cc.LOG_DIR, exist_ok=True)
        self._logfile = open(os.path.join(cc.LOG_DIR, f"client_{name}.log"), "a", buffering=1)
        self._lock = threading.Lock()

    def _stub(self, node_id):
        if node_id not in self._stubs:
            self._stubs[node_id] = pb_grpc.NodeStub(grpc.insecure_channel(cc.SERVERS[node_id]))
        return self._stubs[node_id]

    def _log(self, **fields):
        line = f"{datetime.now().isoformat(timespec='milliseconds')} client={self.name} " + \
               " ".join(f"{k}={v}" for k, v in fields.items())
        with self._lock:
            print(line)
            self._logfile.write(line + "\n")

    def send(self, text):
        """Send one message; retries and redirects. Returns the ChatReply or None."""
        mid = uuid.uuid4().hex[:12]               # same id on every retry => exactly-once
        target = self.hint or random.choice(list(cc.SERVERS))
        for attempt in range(1, cc.MAX_ATTEMPTS + 1):
            t0 = time.time()
            try:
                reply = self._stub(target).SendMessage(
                    pb.ChatRequest(message_id=mid, sender=self.name, text=text),
                    timeout=cc.REQUEST_TIMEOUT)
            except grpc.RpcError as e:
                self._log(op="SEND", msg_id=mid, target=target, attempt=attempt,
                          result="ERROR", detail=e.code().name)
                self.hint = None
                ids = list(cc.SERVERS)
                target = ids[(ids.index(target) + 1) % len(ids)]
                time.sleep(cc.RETRY_DELAY)
                continue
            ms = int((time.time() - t0) * 1000)
            if reply.ok:
                self.hint = reply.leader_id
                self._log(op="SEND", msg_id=mid, target=target, attempt=attempt, result="OK",
                          index=reply.index, lamport=reply.lamport, latency_ms=ms)
                return reply
            self._log(op="SEND", msg_id=mid, target=target, attempt=attempt,
                      result=reply.error, leader_hint=reply.leader_id or "-", latency_ms=ms)
            if reply.error == "NOT_LEADER" and reply.leader_id:
                target = reply.leader_id
            time.sleep(cc.RETRY_DELAY)
        self._log(op="SEND", msg_id=mid, result="GAVE_UP")
        return None

    def read(self, node_id, from_index=1):
        try:
            reply = self._stub(node_id).ReadMessages(
                pb.ReadRequest(from_index=from_index), timeout=cc.REQUEST_TIMEOUT)
        except grpc.RpcError as e:
            self._log(op="READ", target=node_id, result="ERROR", detail=e.code().name)
            return None
        self._log(op="READ", target=node_id, result="OK", count=len(reply.entries),
                  last_index=reply.entries[-1].index if reply.entries else 0)
        return list(reply.entries)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="user")
    ap.add_argument("--auto", type=int, help="send N automatic messages")
    ap.add_argument("--interval", type=float, default=0.2)
    ap.add_argument("--read", metavar="NODE", help="print the log held by NODE")
    args = ap.parse_args()
    c = ChatClient(args.name)

    if args.read:
        for e in c.read(args.read) or []:
            print(f"#{e.index:<3} L={e.lamport:<4} t{e.term} {e.sender}: {e.text}")
    elif args.auto:
        for i in range(1, args.auto + 1):
            c.send(f"auto message {i} from {args.name}")
            time.sleep(args.interval)
    else:
        print("Type a message and press Enter.  /read [node]   /quit")
        while True:
            line = input(f"{args.name}> ").strip()
            if line == "/quit":
                break
            if line.startswith("/read"):
                parts = line.split()
                for e in c.read(parts[1] if len(parts) > 1 else "node1") or []:
                    print(f"#{e.index:<3} L={e.lamport:<4} {e.sender}: {e.text}")
            elif line:
                c.send(line)


if __name__ == "__main__":
    main()
