# Middleware_Group_Assignment

A fault-tolerant, replicated group-chat system built with Python and **gRPC** for the
SCS2314 Middleware Architecture assignment.

Clients talk to a cluster of nodes over gRPC; nodes talk to each other over gRPC too.
The project combines four mechanisms, one per group member:

| Role | Mechanism | File |
| --- | --- | --- |
| 1 | Time and ordering | `mechanisms/logical_clock.py` |
| 2 | Consensus / leader election | `mechanisms/consensus.py` |
| 3 | Fault tolerance | `mechanisms/fault_tolerance.py` |
| 4 | Replication and consistency | `mechanisms/replication.py` |

> Members / index numbers / roles / video link: *(fill in before submission)*

## Project status

**Foundation: done.** Shared gRPC contract, threaded node, config, logging, client,
fault injection, Docker environment, smoke test.

**The four mechanisms are starter versions** - see [What is a placeholder](#what-is-a-placeholder-vs-done).
In particular **consensus is a placeholder: `node1` is always the leader**, so killing
`node1` stops writes until Role 2 implements real election.

## Quick start

### Option A - Docker (3 nodes, recommended for demos)

See [Prerequisites](#prerequisites) first, then from the repository root:

```sh
docker compose up --build -d
docker compose ps                       # wait until node1-3 are "healthy"
```

Chat client and tools run on your computer (not in Docker):

```sh
python -m venv venv
venv\Scripts\activate                   # Windows   (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt

python -m client.chat_client --name alice
python -m tools.fault status
```

### Option B - local processes (no Docker, fastest while developing)

```sh
python -m tools.cluster up              # starts 3 nodes on 127.0.0.1:50051-50053
python -m client.chat_client --name alice
python -m tools.fault status
python -m tools.cluster down
```

Works on Windows, macOS and Linux. **Use either A or B, not both at once** - they use
the same host ports (50051-50053).

### Smoke test

```sh
python -m unittest tests.test_foundation -v
```

Boots a real 3-node cluster and checks redirect, replication, crash, catch-up,
partition and heal. Stop any running cluster first (same ports).

## Chat client

```sh
python -m client.chat_client --name alice                  # interactive: /read [node], /quit
python -m client.chat_client --name bob --auto 20          # send 20 messages automatically
python -m client.chat_client --name bob --read node2       # print the log held by node2
```

Run several at once (different `--name`) to test concurrent clients. Every request,
response and error is printed and saved with a timestamp to `logs/client_<name>.log`.
The client follows leader redirects, retries on failure, and reuses the same
`message_id` on retries so a retry never creates a duplicate message.

## Fault injection (assignment demo faults)

| Demo fault | Local processes | Docker |
| --- | --- | --- |
| Crash a node (hard) | `python -m tools.cluster kill node1` | `docker compose kill node1` |
| Stop gracefully | - | `docker compose stop node1` |
| Restart (watch catch-up) | `python -m tools.cluster start node1` | `docker compose start node1` |
| Partition | `python -m tools.fault partition node1,node2 node3` | same |
| Heal | `python -m tools.fault heal` | same |
| Skew a clock | `python -m tools.fault skew node2 5` | same |
| Delay messages | `python -m tools.fault delay node2 500` | same |
| Drop messages | `python -m tools.fault drop node2 0.3` | same |
| Conflicting concurrent clients | run two `chat_client` processes at once | same |

`python -m tools.fault status` shows every node's role, term, leader, log length,
Lamport time, which peers it believes are alive, and active faults.
Injected faults only affect **node-to-node** traffic; client, admin and Docker
health-check calls are never faulted, so you can always heal.

Logs: `logs/<node>.log` (node state - also shared out of the containers) and
`logs/client_<name>.log`. Docker: `docker compose logs -f node1`.

## Architecture

```
 clients --SendMessage/ReadMessages--> any node (non-leaders redirect to the leader)
                                            |
   +----------------------------------------+-----------------------------+
   | Node shell (nodes/node.py): clock, fault state, peers, gRPC server     |
   |   mechanisms/consensus.py        Role 2  leader, terms, voting         |
   |   mechanisms/fault_tolerance.py  Role 3  heartbeats, detection         |
   |   mechanisms/replication.py      Role 4  log, quorum, catch-up         |
   |   mechanisms/logical_clock.py    Role 1  Lamport / sync                |
   +------------------------------------------------------------------------+
   middleware/rpc.py : applies injected faults + the Lamport merge to EVERY
   incoming node-to-node RPC in one place, and adds sender + timestamp to
   outgoing ones. Roles do not re-implement this.
```

The single shared contract is **`middleware/node.proto`**. If you change it, tell the
group, then run `python -m tools.gen_proto` and commit the generated
`middleware/node_pb2*.py` files (generate with the pinned `requirements.txt` versions).

### Interfaces between roles (keep these names stable)

| Provider | Interface | Used by |
| --- | --- | --- |
| Role 1 | `node.clock.tick()`, `.update(ts)`, `.time`; `node.now()` (skewable wall clock) | everyone (stamping is automatic in `rpc.py`) |
| Role 2 | `consensus.is_leader()`, `.leader_id`, `.term`, `.role`, `handle_request_vote`, `handle_append_entries` | Role 4 (writes only on leader), Role 3 (status) |
| Role 3 | `detector.is_alive(p)`, `.alive_peers()`, `.on_down(cb)`, `.on_up(cb)` | Role 2 (trigger election), Role 4 (skip dead peers) |
| Role 4 | `replication.client_write()`, `.read()`, `.handle_replicate()`, `.handle_sync()`, `.last_index` | clients, Role 2 (log up-to-date check), Role 3 (rejoin) |

### What is a placeholder vs. done

| Area | State | Owner's job |
| --- | --- | --- |
| gRPC contract, config, fault injection, logging, client, Docker | **done** | extend only if needed |
| Lamport clock | working starter | vector clocks / clock sync, ordering under skew, overhead measurements |
| Consensus | **placeholder: static leader `node1`** | real election + log agreement, one leader per term, no lost commits |
| Failure detector | working starter (fixed timeout) | tuning, failover, recovery, measure detection/failover time |
| Replication | working starter (majority ack, dedup, gap catch-up; **in memory only**) | consistency model + justification, persistence in `DATA_DIR`, commit/rollback of un-acked entries, conflict handling |

### Findings so far (use in the report)

* gRPC's default reconnect backoff grows to minutes, so a restarted node looked dead to
  its peers. It is capped at 500 ms in `middleware/rpc.py` (affects Role 3's recovery times).
* A write that misses a majority is reported as `NO_QUORUM` but stays in the leader's
  log (no rollback yet) - Role 4 / Role 2 must fix this with a commit rule.

### Configuration

All in `middleware/config.py`: cluster size, addresses, timeouts (`RPC_TIMEOUT`,
`HEARTBEAT_INTERVAL`, `FAILURE_TIMEOUT`). Environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `NODE_ID` | Which node this process is (`python -m nodes.node node1` also works) | - |
| `GRPC_PORT` | Port to listen on | 5005N locally, `50051` in Docker |
| `DATA_DIR` | Directory where the node may persist state | `data/<node>/` locally, `/data` in Docker |
| `CLUSTER_SIZE` | Number of nodes | `3` |
| `CLUSTER_MODE` | `docker` makes nodes address each other as `nodeN:50051` (set in the Dockerfile) | `local` |

To run **5 nodes** (needed to tolerate 2 failures): set `CLUSTER_SIZE=5`
(`python -m tools.cluster up 5`); for Docker also add `node4`/`node5` services to
`compose.yaml` (ports `50054`/`50055`) and set `CLUSTER_SIZE: "5"` in the Dockerfile
`ENV` or each service's `environment`.

## Prerequisites

Install:

- Git
- Docker Desktop on Windows or macOS, or Docker Engine with the Compose plugin on Linux
- Python 3.12+ (only for the client, tools and local mode - not needed inside Docker)

On Windows:

1. Complete Docker Desktop's WSL 2 setup.
2. Use Linux containers.
3. Start Docker Desktop and wait for the engine to run.

Verify your installation:

```sh
docker --version
docker compose version
docker run --rm hello-world
```

The final command should display `Hello from Docker!`.

## Docker details

| File | Purpose |
| --- | --- |
| `Dockerfile` | Builds the shared Python environment; runs `python -m nodes.node` |
| `compose.yaml` | Defines the three nodes, health checks, named data volumes |
| `requirements.txt` | Pinned Python dependencies (gRPC 1.76.0) |
| `.dockerignore` | Excludes unnecessary files from Docker builds |
| `tools/dev_grpc_node.py` | The original health-only dev server (kept for debugging) |

Validate and start:

```sh
docker compose config --quiet
docker compose up --build -d
docker compose ps          # a temporary "health: starting" status is normal
```

### Node addresses

| Node | From your computer | From another container |
| --- | --- | --- |
| `node1` | `localhost:50051` | `node1:50051` |
| `node2` | `localhost:50052` | `node2:50051` |
| `node3` | `localhost:50053` | `node3:50051` |

Inside a container, `localhost` is that same container - use service names such as
`node2:50051` to reach another node. These are gRPC endpoints, not web pages.

### Logs

```sh
docker compose logs --tail 30
docker compose logs -f node1
```

`Ctrl+C` stops following logs; it does not stop the containers.

### Stop, kill and restart nodes

```sh
docker compose stop node2       # graceful
docker compose kill node2       # abrupt crash
docker compose start node2      # recover
```

Automatic restarts are disabled (`restart: "no"`) so nodes deliberately stopped during
fault demonstrations stay down until you start them.

### Stop the environment

```sh
docker compose down             # keeps the data volumes
docker compose down -v          # ONLY when deliberately deleting all stored cluster data
```

### Persistent storage

Each node has its own named volume mounted at `/data` (`node1-data`, `node2-data`,
`node3-data`; Docker may prefix the names with the project name). The node creates its
directory (`node.data_dir`) but the starter replication keeps the log **in memory** -
persisting state to `DATA_DIR` is part of Role 3/4. Never share one storage directory
between nodes.

### Developing with Docker

The image contains a copy of the source. After changing Python code, dependencies or
the Dockerfile, rebuild: `docker compose up --build -d`.
Open a shell in a node: `docker compose exec node1 sh` (`exit` to leave).
Make lasting changes in your local repository, not inside a container.

## Contributing changes

Create feature branches from an up-to-date `dev` branch. Commit or stash unfinished
changes before switching branches.

```sh
git fetch origin
git switch dev
git pull --ff-only origin dev
git switch -c your-feature-branch
```

Review and stage only the intended files:

```sh
git status
git diff
git add path/to/changed-file
git diff --cached
git diff --cached --check
```

Commit and push, then open a pull request targeting `dev` describing the checks you
actually completed:

```sh
git commit -m "Describe your change"
git push -u origin your-feature-branch
```

Everyone must commit their own role's work regularly - per-member commit history is
checked in the viva. To bring merged changes into an existing branch:

```sh
git switch consensus
git fetch origin
git merge origin/dev
```

(Replace `consensus` with your actual branch name.)

## Troubleshooting

| Problem | Action |
| --- | --- |
| Cannot connect to the Docker daemon | Start Docker Desktop, wait for the engine, run `docker info`. |
| `docker compose` is unavailable | Check Docker Desktop, or install the Compose plugin on Linux. |
| No configuration file found | Run commands from the folder containing `compose.yaml`. |
| Port is already allocated / "cannot bind port" | Another cluster is running. `python -m tools.cluster down` or `docker compose down`. |
| Code changes do not appear in Docker | `docker compose up --build -d`. |
| Container unhealthy or exits | `docker compose logs --tail 100 node1`. |
| Client says nodes unreachable | Check `python -m tools.fault status`; client/tools use `localhost:5005N`. |
| `ModuleNotFoundError: middleware` | Run commands from the repository root with `python -m ...`. |
| Protobuf version error on import | Reinstall pinned versions (`pip install -r requirements.txt`) and run `python -m tools.gen_proto`. |
| Writes fail after killing `node1` | Expected for now: consensus is a static-leader placeholder (Role 2). |

## Documentation

- [Docker Desktop installation](https://docs.docker.com/desktop/setup/install/windows-install/)
- [Docker Compose networking](https://docs.docker.com/compose/how-tos/networking/)
- [Python gRPC quick start](https://grpc.io/docs/languages/python/quickstart/)
