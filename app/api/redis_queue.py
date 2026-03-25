import os
import redis
from rq import Queue


# Pull REDIS_HOST from the environment
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
redis_conn = redis.Redis(host=REDIS_HOST, port=6379)

transcription_queue = Queue(
    "transcriptions",
    connection=redis_conn
)