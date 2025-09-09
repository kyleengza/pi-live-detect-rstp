import logging
import logging.handlers
import os
from typing import Optional

try:
    from app.utils.redis_logging import attach_redis_handler
except Exception:
    attach_redis_handler = None  # Optional dependency at runtime


def setup_logging(name: str = "pi-live", level: int = logging.INFO) -> logging.Logger:
    """Configure logging to syslog, console, and Redis (if available)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(fmt='%(asctime)s %(name)s [%(levelname)s] %(message)s'))

    # Syslog handler (journald forwards from /dev/log)
    syslog_address = '/dev/log' if os.path.exists('/dev/log') else ('localhost', 514)
    sh = logging.handlers.SysLogHandler(address=syslog_address)
    sh.setLevel(level)
    sh.setFormatter(logging.Formatter(fmt='%(name)s[%(process)d]: %(levelname)s %(message)s'))

    logger.addHandler(ch)
    logger.addHandler(sh)

    if attach_redis_handler is not None:
        try:
            attach_redis_handler(logger)
        except Exception:
            pass

    logger.propagate = False
    return logger
