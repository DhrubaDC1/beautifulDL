import os
import json
import redis
from typing import Optional, Dict

class RedisCache:
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        # Allow overriding via environment variables
        self.host = os.getenv('REDIS_HOST', host)
        self.port = int(os.getenv('REDIS_PORT', port))
        self.db = int(os.getenv('REDIS_DB', db))
        self.redis = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=True)

    def get_key(self, video_id: str, format_id: str) -> str:
        return f"video:{video_id}:{format_id}"

    def get(self, video_id: str, format_id: str) -> Optional[Dict]:
        """Retrieve metadata from Redis."""
        key = self.get_key(video_id, format_id)
        data = self.redis.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None

    def set(self, video_id: str, format_id: str, metadata: Dict, ttl: int = 86400):
        """Store metadata in Redis. Default TTL: 24 hours."""
        key = self.get_key(video_id, format_id)
        self.redis.setex(key, ttl, json.dumps(metadata))

    def delete(self, video_id: str, format_id: str):
        """Delete metadata from Redis."""
        key = self.get_key(video_id, format_id)
        self.redis.delete(key)

    def ping(self):
        """Check connection."""
        return self.redis.ping()
