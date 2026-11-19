FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    CLUSTER_MODE=docker

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 50051

# The node reads NODE_ID, GRPC_PORT and DATA_DIR from compose.yaml.
# (The old health-only server is still available: python -m tools.dev_grpc_node)
CMD ["python", "-m", "nodes.node"]
