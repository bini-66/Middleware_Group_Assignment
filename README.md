# Middleware_Group_Assignment

A distributed group chat system built with Python and gRPC for the SCS2314 Middleware Architecture assignment.

The project combines four mechanisms:

- Time and ordering
- Consensus
- Fault tolerance
- Replication and consistency

## Current Docker Setup

The Docker environment starts three development nodes running a standard gRPC health service.

This setup verifies that containers, Python dependencies, networking, and gRPC communication work correctly.

**Chat functionality, leader election, consensus, and replication are not implemented by the development health server.**

## Prerequisites

Install:

- Git
- Docker Desktop on Windows or macOS, or Docker Engine with the Compose plugin on Linux

On Windows:

1. Complete Docker Desktop’s WSL 2 setup.
2. Use Linux containers.
3. Start Docker Desktop and wait for the engine to run.

Verify your installation:

```sh
docker --version
docker compose version
docker run --rm hello-world
```

The final command should display `Hello from Docker!`.

Python does not need to be installed on your computer for this Docker setup. The containers use Python 3.12.

## Setup Files

Run Docker commands from the repository root, which contains:

| File | Purpose |
| --- | --- |
| `Dockerfile` | Builds the shared Python environment |
| `compose.yaml` | Defines three development nodes |
| `requirements.txt` | Defines Python dependencies |
| `.dockerignore` | Excludes unnecessary files from Docker builds |
| `.gitignore` | Excludes local environments, caches, and runtime data from Git |
| `tools/__init__.py` | Empty Python package file |
| `tools/dev_grpc_node.py` | Runs the development gRPC health server |

## Get the Project

After the Docker setup is merged into `dev`, new contributors can run:

```sh
git clone --branch dev https://github.com/bini-66/Middleware_Group_Assignment.git
cd Middleware_Group_Assignment
```

For an existing checkout, commit or stash unfinished work before switching branches:

```sh
git fetch origin
git switch dev
git pull --ff-only origin dev
```

Before the Docker setup is merged, use its branch instead:

```sh
git fetch origin
git switch setup/docker-grpc
```

## Build and Start

Validate the Compose configuration:

```sh
docker compose config --quiet
```

Build the images and start all three nodes:

```sh
docker compose up --build -d
```

The first build may take several minutes.

Check container status:

```sh
docker compose ps
```

Expected result: `node1`, `node2`, and `node3` are running and eventually show `healthy`.

A temporary `health: starting` status is normal during startup.

## View Logs

View recent logs:

```sh
docker compose logs --tail 30
```

Follow all logs:

```sh
docker compose logs -f
```

View one node’s logs:

```sh
docker compose logs --tail 30 node1
```

Press `Ctrl+C` to stop following logs. This does not stop the detached containers.

## Node Addresses

| Node | From your computer | From another container |
| --- | --- | --- |
| `node1` | `localhost:50051` | `node1:50051` |
| `node2` | `localhost:50052` | `node2:50051` |
| `node3` | `localhost:50053` | `node3:50051` |

Each container listens on internal port `50051`. Different host ports allow all three nodes to run on one computer.

Inside a container, `localhost` refers to that same container. Use service names such as `node2:50051` to contact another node.

These are gRPC endpoints, not browser-accessible web pages.

## Test gRPC Communication

Run the following command as one line:

```sh
docker compose exec node1 python -c "import grpc; from grpc_health.v1 import health_pb2, health_pb2_grpc; channel = grpc.insecure_channel('node2:50051'); response = health_pb2_grpc.HealthStub(channel).Check(health_pb2.HealthCheckRequest(), timeout=3); assert response.status == health_pb2.HealthCheckResponse.SERVING; print('PASS: node1 reached node2 using gRPC')"
```

Expected output:

```text
PASS: node1 reached node2 using gRPC
```

To test node 3:

```sh
docker compose exec node1 python -c "import grpc; from grpc_health.v1 import health_pb2, health_pb2_grpc; channel = grpc.insecure_channel('node3:50051'); response = health_pb2_grpc.HealthStub(channel).Check(health_pb2.HealthCheckRequest(), timeout=3); assert response.status == health_pb2.HealthCheckResponse.SERVING; print('PASS: node1 reached node3 using gRPC')"
```

These checks verify networking and gRPC health responses. They do not verify consensus or chat-message delivery.

## Stop and Restart a Node

Gracefully stop node 2:

```sh
docker compose stop node2
docker compose ps -a
```

Start it again:

```sh
docker compose start node2
docker compose ps
```

Wait for it to become healthy, then repeat the gRPC communication check.

Simulate an abrupt process crash:

```sh
docker compose kill node2
```

Recover the node:

```sh
docker compose start node2
```

Automatic restarts are disabled so nodes deliberately stopped during fault demonstrations remain down until explicitly started.

Leader replacement and data recovery require the actual consensus implementation.

## Stop the Environment

Stop and remove containers while preserving their named data volumes:

```sh
docker compose down
```

Start again:

```sh
docker compose up -d
```

## Persistent Storage

Each node has a separate named volume mounted at `/data`:

- `node1-data`
- `node2-data`
- `node3-data`

Docker may prefix these names with the Compose project name.

The development health server creates the data directory but does not store chat messages or consensus state.

The application must explicitly write persistent state to the directory specified by `DATA_DIR`.

**Only when intentionally deleting all stored cluster data**, run:

```sh
docker compose down -v
```

Never share one consensus storage directory between nodes.

## Developing with Docker

The Docker image contains a copy of the source code. Local changes are not automatically reflected inside existing containers.

After changing Python code, dependencies, or the Dockerfile, rebuild:

```sh
docker compose up --build -d
```

Open a shell inside node 1:

```sh
docker compose exec node1 sh
```

Leave the shell:

```sh
exit
```

Make lasting code changes in your local repository. Changes made only inside a container can be lost when it is recreated.

## Integrating the Application gRPC Server

The current startup command runs:

```sh
python -m tools.dev_grpc_node
```

When the application gRPC server is ready:

1. Define the agreed `.proto` services and generate their Python modules.
2. Register the application’s gRPC handlers.
3. Bind the server to `0.0.0.0:50051` inside the container.
4. Read the environment variables listed below.
5. Configure peers using Docker Compose service names.
6. Replace the Dockerfile startup command with the application server’s entry point.
7. Retain the standard gRPC health service or update the Compose health check.
8. Generate protobuf modules during the build or include compatible generated modules in the repository.

| Variable | Purpose |
| --- | --- |
| `NODE_ID` | Identifies the node |
| `GRPC_PORT` | Internal listening port |
| `DATA_DIR` | Persistent storage directory |

The agreed consensus integration point is:

```python
result = consensus.propose(message)
```

The development health server does not call this interface or connect to peers automatically.

The existing socket-based client must be updated before it can communicate with the application’s gRPC services.

## Contributing Changes

Create feature branches from an up-to-date `dev` branch. Commit or stash unfinished changes before switching branches.

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

Commit and push:

```sh
git commit -m "Describe your change"
git push -u origin your-feature-branch
```

Open a pull request targeting `dev`. Include a description and the checks actually completed.

For the Docker setup, use `setup/docker-grpc` as the source branch.

After merging the Docker setup, teammates can update and start it:

```sh
git switch dev
git pull --ff-only origin dev
docker compose up --build -d
```

To bring merged changes into an existing consensus branch:

```sh
git switch consensus
git fetch origin
git merge origin/dev
```

Replace `consensus` with your actual branch name if different.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Cannot connect to the Docker daemon | Start Docker Desktop, wait for the engine, and run `docker info`. |
| `docker compose` is unavailable | Check Docker Desktop or install the Compose plugin on Linux. |
| No configuration file found | Run commands from the folder containing `compose.yaml`. |
| Port is already allocated | Stop the application using that host port or change the host-side port mapping. |
| `No module named tools.dev_grpc_node` | Check that both files exist inside `tools`, then rebuild. |
| Missing gRPC package | Check `requirements.txt`, inspect build errors, and rebuild. |
| Container is unhealthy or exits | Run `docker compose logs --tail 100 node1` and inspect the error. |
| gRPC request fails | Check the target is healthy and use its service name and internal port from another container. |
| Code changes do not appear | Run `docker compose up --build -d`. |
| Old chat client cannot connect | The development endpoint uses gRPC; use the health check until the gRPC application client is implemented. |

## Documentation

- [Docker Desktop installation](https://docs.docker.com/desktop/setup/install/windows-install/)
- [Docker Compose networking](https://docs.docker.com/compose/how-tos/networking/)
- [Python gRPC quick start](https://grpc.io/docs/languages/python/quickstart/)