"""Run the cluster as local processes (no Docker). Works on Windows, Mac, Linux.
Run from the repo root:

  python -m tools.cluster up [N]        start N nodes (default 3)
  python -m tools.cluster down          stop everything
  python -m tools.cluster kill node2    crash a node (hard kill, no clean shutdown)
  python -m tools.cluster start node2   (re)start a node, e.g. after kill
  python -m tools.cluster status        same as: python -m tools.fault status

Node output goes to logs/<node>.out and logs/<node>.log; PIDs to logs/<node>.pid.
Do not run this at the same time as `docker compose up` (same host ports).
"""
import os
import signal
import subprocess
import sys
import time

LOG_DIR = "logs"


def _env(size=None):
    env = dict(os.environ)
    for var in ("NODE_ID", "GRPC_PORT", "DATA_DIR", "CLUSTER_MODE"):
        env.pop(var, None)                 # local mode must not inherit Docker settings
    if size:
        env["CLUSTER_SIZE"] = str(size)
    return env


def start_node(node, size=None):
    os.makedirs(LOG_DIR, exist_ok=True)
    out = open(os.path.join(LOG_DIR, f"{node}.out"), "ab")
    kwargs = {}
    if os.name == "nt":
        # No console window per node, and keep running after this script exits.
        # (CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW)
        kwargs["creationflags"] = 0x00000200 | 0x08000000
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen([sys.executable, "-m", "nodes.node", node],
                            stdout=out, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, env=_env(size), **kwargs)
    with open(os.path.join(LOG_DIR, f"{node}.pid"), "w") as f:
        f.write(str(proc.pid))
    print(f"started {node} (pid {proc.pid})")


def _pid(node):
    try:
        return int(open(os.path.join(LOG_DIR, f"{node}.pid")).read())
    except (OSError, ValueError):
        return None


def stop_node(node, hard):
    pid = _pid(node)
    if pid is None:
        print(f"{node}: no pid file (not started by this tool?)"); return
    if os.name == "nt":
        # A venv's python.exe is a launcher that starts the real interpreter as a
        # child, so kill the whole process TREE (/T) or the node keeps running.
        result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                capture_output=True, text=True)
        ok = result.returncode == 0
    else:
        sig = getattr(signal, "SIGKILL", signal.SIGTERM) if hard else signal.SIGTERM
        try:
            os.kill(pid, sig)
            ok = True
        except OSError:
            ok = False
    if ok:
        print(f"{'killed' if hard else 'stopped'} {node} (pid {pid})")
    else:
        print(f"{node}: process {pid} not running")
    try:
        os.remove(os.path.join(LOG_DIR, f"{node}.pid"))
    except OSError:
        pass


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]
    size = int(args[0]) if cmd == "up" and args else int(os.getenv("CLUSTER_SIZE", "3"))
    if cmd == "up":
        for i in range(1, size + 1):
            start_node(f"node{i}", size)
        time.sleep(2)
        os.environ["CLUSTER_SIZE"] = str(size)
        from tools import fault
        fault.show_status()
    elif cmd == "start" and args:
        start_node(args[0], size)
    elif cmd == "kill" and args:
        stop_node(args[0], hard=True)
    elif cmd == "down":
        for fname in sorted(os.listdir(LOG_DIR)) if os.path.isdir(LOG_DIR) else []:
            if fname.endswith(".pid"):
                stop_node(fname[:-4], hard=False)
        print("cluster stopped")
    elif cmd == "status":
        from tools import fault
        fault.show_status()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])