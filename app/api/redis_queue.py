import os
import redis
from rq import Queue


# Pull REDIS_HOST from the environment
# REDIS_HOST = os.getenv("REDIS_HOST", "localhost") # Default to localhost for local dev, but in Kubernetes it should be set to 'redis-master' as per the redis-setup.yaml
REDIS_HOST = os.getenv("REDIS_HOST", "redis-master") # Default to 'redis-master' for Kubernetes, fallback to localhost
redis_conn = redis.Redis(host=REDIS_HOST, port=6379)

transcription_queue = Queue(
    "transcriptions",
    connection=redis_conn
)