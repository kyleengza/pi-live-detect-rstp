from __future__ import annotations
import sys
import time
from app.core.config import CONFIG
from app.core.redis_client import RedisCache
from app.ingest.rtsp_ingestor import RTSPIngestor
from app.utils.logging_setup import setup_logging


log = setup_logging("svc.ingest")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m app.entrypoints.rtsp_ingestor_service <stream_name>")
        sys.exit(1)
    name = sys.argv[1]
    stream = next((s for s in CONFIG.rtsp_streams if s.name == name), None)
    if not stream:
        log.error("Stream %s not found in config", name)
        sys.exit(1)
    cache = RedisCache()
    ing = RTSPIngestor(stream, cache)
    ing.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
