from __future__ import annotations
import logging
import json
import time
from typing import Optional

from app.core.redis_client import RedisCache


class RedisLogHandler(logging.Handler):
    """Logging handler that writes logs to Redis lists with TTL.

    Keys:
      pi-live:logs (global)
      pi-live:logs:<logger_name>
    """

    def __init__(self, cache: Optional[RedisCache] = None, capacity: int = 500):
        super().__init__()
        self.cache = cache or RedisCache()
        self.capacity = capacity

    def emit(self, record: logging.LogRecord) -> None:
        try:
            data = {
                "ts": int(time.time()),
                "name": record.name,
                "level": record.levelname,
                "msg": self.format(record),
            }
            self.cache.push_log_json("logs", data, capacity=self.capacity)
            self.cache.push_log_json(f"logs:{record.name}", data, capacity=self.capacity)
        except Exception:
            pass


def attach_redis_handler(logger: logging.Logger, capacity: int = 500) -> None:
    handler = RedisLogHandler(capacity=capacity)
    fmt = logging.Formatter(fmt='%(asctime)s %(name)s [%(levelname)s] %(message)s')
    handler.setFormatter(fmt)
    logger.addHandler(handler)
