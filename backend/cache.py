import os
import json
import redis
from typing import Optional, Dict

class RedisCache:
    def __init__(self, host: str = None, port: int = 6379, db: int = 0):
        # Allow overriding via environment variables
        self.host = os.getenv('REDIS_HOST', host)
        self.port = int(os.getenv('REDIS_PORT', port))
        self.db = int(os.getenv('REDIS_DB', db))
        self.redis_url = os.getenv('REDIS_URL', None)
        
        self.redis = None
        
        try:
            if self.redis_url:
                self.redis = redis.from_url(self.redis_url, decode_responses=True)
            elif self.host:
                self.redis = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=True)
            # If no host/url provided, cache remains disabled (None)
        except Exception as e:
            print(f"Redis connection failed: {e}. Caching disabled.")
            self.redis = None

    def get_key(self, video_id: str, format_id: str) -> str:
        return f"video:{video_id}:{format_id}"

    def get(self, video_id: str, format_id: str) -> Optional[Dict]:
        """Retrieve metadata from Redis."""
        if not self.redis:
            return None
            
        try:
            key = self.get_key(video_id, format_id)
            data = self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"Cache get error: {e}")
            return None
        return None

    def set(self, video_id: str, format_id: str, metadata: Dict, ttl: int = 86400):
        """Store metadata in Redis. Default TTL: 24 hours."""
        if not self.redis:
            return

        try:
            key = self.get_key(video_id, format_id)
            self.redis.setex(key, ttl, json.dumps(metadata))
        except Exception as e:
            print(f"Cache set error: {e}")

    def delete(self, video_id: str, format_id: str):
        """Delete metadata from Redis."""
        if not self.redis:
            return

        try:
            key = self.get_key(video_id, format_id)
            self.redis.delete(key)
        except Exception as e:
            print(f"Cache delete error: {e}")

    def ping(self):
        """Check connection."""
        if not self.redis:
            return False
            
        try:
            return self.redis.ping()
        except:
            return False
