"""ROLE 1 - Time and ordering.

STARTER: a working Lamport clock so the foundation can stamp messages.
Owner: extend with vector clocks and/or Cristian/Berkeley sync (see Node.now()
and the GetTime RPC), and measure ordering under skew + overhead.

Interface other roles rely on:
    clock.tick()        -> int   (call before every send / local event)
    clock.update(ts)    -> int   (call on receive; done automatically in rpc.py)
    clock.time          -> int
"""
import threading


class LamportClock:
    def __init__(self):
        self._t = 0
        self._lock = threading.Lock()

    def tick(self):
        with self._lock:
            self._t += 1
            return self._t

    def update(self, received):
        with self._lock:
            self._t = max(self._t, received) + 1
            return self._t

    @property
    def time(self):
        return self._t
