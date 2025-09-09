import cv2
import time
import threading
from typing import Optional, Tuple

from app.utils.logging_setup import setup_logging
from app.core.config import RTSPConfig
from app.core.redis_client import RedisCache


class RTSPIngestor(threading.Thread):
    """Reads frames from an RTSP source and publishes them to Redis."""

    def __init__(self, cfg: RTSPConfig, cache: RedisCache) -> None:
        super().__init__(daemon=True)
        self.cfg = cfg
        self.cache = cache
        self.log = setup_logging(f"ingest.{cfg.name}")
        self.stop_event = threading.Event()
        self.cap: Optional[cv2.VideoCapture] = None

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.cfg.url)
        if not (self.cap and self.cap.isOpened()):
            self.log.error("Failed to open RTSP: %s", self.cfg.url)
            return False
        # Try to configure FPS and size if supported
        self.cap.set(cv2.CAP_PROP_FPS, self.cfg.fps)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.height)
        return True

    def run(self) -> None:
        if not self.open():
            self.cache.publish_probe(self.cfg.name, "error", {"reason": "open_failed"})
            return
        self.cache.publish_probe(self.cfg.name, "ok", {"event": "start"})
        frame_interval = 1.0 / max(self.cfg.fps, 1)
        last = 0.0
        while not self.stop_event.is_set():
            if not self.cap:
                break
            ok, frame = self.cap.read()
            if not ok:
                self.log.warning("Read failed, retrying...")
                time.sleep(0.25)
                continue
            now = time.time()
            if now - last < frame_interval:
                # throttle to desired fps
                time.sleep(max(0.0, frame_interval - (now - last)))
            last = time.time()

            # Encode frame as JPEG for caching and dashboard
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ok:
                self.cache.push_frame(self.cfg.name, buf.tobytes())
                self.cache.push_frame(f"frame:{self.cfg.name}", buf.tobytes())
                self.cache.set_json(f"last_frame_meta:{self.cfg.name}", {
                    "ts": int(last),
                    "w": frame.shape[1],
                    "h": frame.shape[0],
                })
        self.cache.publish_probe(self.cfg.name, "stopped", {"event": "stop"})

    def stop(self) -> None:
        self.stop_event.set()
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
