"""Client-side settings."""
from middleware import config

SERVERS = config.HOST_NODES      # node id -> address, as seen from the host machine
REQUEST_TIMEOUT = 3.0            # seconds per attempt
MAX_ATTEMPTS = 8                 # retries (same message_id => no duplicates)
RETRY_DELAY = 0.3
LOG_DIR = config.LOG_DIR
