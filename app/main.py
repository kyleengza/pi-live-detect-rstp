from __future__ import annotations
import threading
import time
import uvicorn

from app.core.config import CONFIG
from app.core.redis_client import RedisCache
from app.ingest.rtsp_ingestor import RTSPIngestor
from app.infer.hailo_infer import HailoYoloV8
from app.core.pipeline import DetectionPipeline
from app.utils.logging_setup import setup_logging


log = setup_logging("main")


def start_all() -> list[threading.Thread]:
    cache = RedisCache()
    hailo = HailoYoloV8(CONFIG.hailo)

    threads: list[threading.Thread] = []

    # Start ingestors and pipelines per stream
    for s in CONFIG.rtsp_streams:
        ing = RTSPIngestor(s, cache)
        pipe = DetectionPipeline(s, cache, hailo)
        ing.start()
        pipe.start()
        threads.extend([ing, pipe])

    return threads


def run_api() -> None:
    uvicorn.run("app.api.server:app", host=CONFIG.api.host, port=CONFIG.api.port, reload=False, access_log=False)


if __name__ == "__main__":
    threads = start_all()
    try:
        run_api()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        time.sleep(0.5)
