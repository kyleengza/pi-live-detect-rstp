from __future__ import annotations
import json
import time
from typing import Any, Dict, Optional, List
import redis

from .config import CONFIG


class RedisCache:
    """Simple wrapper around Redis with TTL per entry."""

    def __init__(self, prefix: str = "pi-live") -> None:
        self.prefix = prefix
        self.r = redis.Redis(
            host=CONFIG.redis.host,
            port=CONFIG.redis.port,
            db=CONFIG.redis.db,
            password=CONFIG.redis.password,
            decode_responses=True,
        )

    def _k(self, *parts: str) -> str:
        return ":".join([self.prefix, *parts])

    def _normalize_key(self, key_or_parts: str | List[str]) -> str:
        if isinstance(key_or_parts, list):
            return self._k(*key_or_parts)
        key = key_or_parts
        return key if key.startswith(self.prefix + ":") else self._k(key)

    def set_json(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> None:
        ttl = ttl or CONFIG.redis.ttl_seconds
        self.r.setex(self._normalize_key(key), ttl, json.dumps(value))

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        v = self.r.get(self._normalize_key(key))
        return json.loads(v) if v else None

    def push_frame(self, stream: str, frame_bytes: bytes, ttl: Optional[int] = None) -> None:
        ttl = ttl or CONFIG.redis.ttl_seconds
        key = self._k("frame", stream)
        rb = redis.Redis(
            host=CONFIG.redis.host,
            port=CONFIG.redis.port,
            db=CONFIG.redis.db,
            password=CONFIG.redis.password,
            decode_responses=False,
        )
        rb.setex(key, ttl, frame_bytes)

    def get_frame(self, stream: str) -> Optional[bytes]:
        key = stream if stream.startswith(self.prefix + ":") else self._k("frame", stream)
        rb = redis.Redis(
            host=CONFIG.redis.host,
            port=CONFIG.redis.port,
            db=CONFIG.redis.db,
            password=CONFIG.redis.password,
            decode_responses=False,
        )
        return rb.get(key)

    def publish_probe(self, stream: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        data = {"ts": int(time.time()), "status": status, "details": details or {}}
        self.set_json(f"probe:{stream}", data)

    def list_keys(self, pattern: str = "*") -> list[str]:
        return [k for k in self.r.scan_iter(self._k(pattern))]

    def get_many(self, keys: list[str]) -> Dict[str, Any]:
        pipe = self.r.pipeline()
        for k in keys:
            pipe.get(k if k.startswith(self.prefix + ":") else self._k(k))
        vals = pipe.execute()
        out = {}
        for k, v in zip(keys, vals):
            try:
                out[k] = json.loads(v) if v else None
            except Exception:
                out[k] = v
        return out

    # Log helpers
    def push_log_json(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None, capacity: int = 500) -> None:
        ttl = ttl or CONFIG.redis.ttl_seconds
        k = self._normalize_key(key)
        pipe = self.r.pipeline()
        pipe.lpush(k, json.dumps(value))
        pipe.ltrim(k, 0, capacity - 1)
        pipe.expire(k, ttl)
        pipe.execute()

    def read_logs(self, key: str, n: int = 100) -> list[Dict[str, Any]]:
        k = self._normalize_key(key)
        entries = self.r.lrange(k, 0, max(0, n - 1))
        out: list[Dict[str, Any]] = []
        for e in entries:
            try:
                out.append(json.loads(e))
            except Exception:
                pass
        return out
