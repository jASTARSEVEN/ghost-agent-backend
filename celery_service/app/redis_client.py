import redis
from redis import Redis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create a single shared Redis instance
redis_client: Redis = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True
)

def get_redis():
    return redis_client
