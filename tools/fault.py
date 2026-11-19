"""Fault-injection CLI.  Run from the repo root.

  python -m tools.fault status
  python -m tools.fault drop  node2 0.3          drop 30% of node2's incoming node RPCs
  python -m tools.fault delay node2 500          add 500 ms to node2's incoming node RPCs
  python -m tools.fault skew  node3 5            node3's clock runs 5 s fast (-5 = slow)
  python -m tools.fault block node1 node4 node5  node1 can't talk to node4, node5
  python -m tools.fault partition node1,node2,node3 node4,node5
  python -m tools.fault heal [node]              remove all faults (one node or all)

Crashing/restarting a node: `python -m tools.cluster kill|start nodeX` (local)
or `docker compose kill|start nodeX` (Docker).
"""
import sys

import grpc

from middleware import config
from middleware import node_pb2 as pb
from middleware import node_pb2_grpc as pb_grpc

ADDR = config.HOST_NODES


def stub(node):
    return pb_grpc.NodeStub(grpc.insecure_channel(ADDR[node]))


def status(node):
    try:
        return stub(node).GetStatus(pb.Empty(), timeout=1.0)
    except grpc.RpcError:
        return None


def apply(node, **changes):
    s = status(node)
    if s is None:
        print(f"{node}: unreachable"); return
    cfg = dict(drop_rate=s.drop_rate, delay_ms=s.delay_ms,
               blocked=list(s.blocked), clock_offset=s.clock_offset)
    cfg.update(changes)
    stub(node).SetFault(pb.FaultConfig(**cfg), timeout=1.0)
    print(f"{node}: {cfg}")


def show_status():
    print(f"{'node':<7}{'role':<10}{'term':<6}{'leader':<8}{'log':<6}{'lamport':<9}{'alive peers':<28}faults")
    for node in ADDR:
        s = status(node)
        if s is None:
            print(f"{node:<7}DOWN"); continue
        faults = []
        if s.drop_rate: faults.append(f"drop={s.drop_rate}")
        if s.delay_ms: faults.append(f"delay={s.delay_ms}ms")
        if s.blocked: faults.append(f"blocked={','.join(s.blocked)}")
        if s.clock_offset: faults.append(f"skew={s.clock_offset:+}s")
        print(f"{node:<7}{s.role:<10}{s.term:<6}{s.leader_id:<8}{s.log_length:<6}{s.lamport:<9}"
              f"{','.join(s.alive_peers):<28}{' '.join(faults) or '-'}")


def main(argv):
    if not argv: sys.exit(__doc__)
    cmd, a = argv[0], argv[1:]
    if cmd == "status": show_status()
    elif cmd == "drop": apply(a[0], drop_rate=float(a[1]))
    elif cmd == "delay": apply(a[0], delay_ms=int(a[1]))
    elif cmd == "skew": apply(a[0], clock_offset=float(a[1]))
    elif cmd == "block": apply(a[0], blocked=a[1:])
    elif cmd == "partition":
        groups = [g.split(",") for g in a]
        everyone = set(ADDR)
        for g in groups:
            for node in g:
                apply(node, blocked=sorted(everyone - set(g)))
    elif cmd == "heal":
        for node in (a or ADDR):
            apply(node, drop_rate=0.0, delay_ms=0, blocked=[], clock_offset=0.0)
    else: sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
