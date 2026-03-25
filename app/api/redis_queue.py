import redis
from rq import Queue

redis_conn = redis.Redis(host="redis", port=6379)

transcription_queue = Queue(
    "transcriptions",
    connection=redis_conn
)